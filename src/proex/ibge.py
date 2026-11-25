"""Coleta verificável e leitura das dimensões municipais do IBGE."""

import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from subprocess import run
from zoneinfo import ZoneInfo
from zipfile import ZipFile

from .arquivos import hash_arquivo, ler_json, salvar_bytes, salvar_json

SIDRA = "https://apisidra.ibge.gov.br/values"
MUNICIPIOS_PR = "n6/in%20n3%2041"
FONTES = {
    "localidades_pr.json": {
        "url": "https://servicodados.ibge.gov.br/api/v1/localidades/estados/41/municipios",
        "referencia": "Cadastro consultado na data de obtenção",
        "formato": "JSON",
        "variaveis": ["id", "nome", "sigla da UF"],
    },
    "sidra_4714_pr_2022.json": {
        "url": f"{SIDRA}/t/4714/{MUNICIPIOS_PR}/v/all/p/2022",
        "referencia": "Censo 2022, primeiros resultados de população e domicílios",
        "formato": "JSON",
        "variaveis": ["93: população residente", "6318: área territorial (km²)",
                      "614: densidade demográfica (hab./km²)"],
    },
    "sidra_9923_pr_2022.json": {
        "url": f"{SIDRA}/t/9923/{MUNICIPIOS_PR}/v/93/p/2022/c1/all",
        "referencia": "Censo 2022, situação do domicílio",
        "formato": "JSON",
        "variaveis": ["93: população residente, total, urbana e rural"],
    },
    "sidra_6579_pr_2024_2025.json": {
        "url": f"{SIDRA}/t/6579/{MUNICIPIOS_PR}/v/9324/p/2024,2025",
        "referencia": "1º de julho de 2024 e 1º de julho de 2025",
        "formato": "JSON",
        "variaveis": ["9324: população residente estimada"],
    },
    "PR_Municipios_2022.zip": {
        "url": "https://geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/"
               "malhas_municipais/municipio_2022/UFs/PR/PR_Municipios_2022.zip",
        "referencia": "Malha Municipal Digital 2022, Paraná, SIRGAS 2000 (EPSG:4674)",
        "formato": "ZIP (Shapefile)",
        "variaveis": ["CD_MUN", "SIGLA_UF", "geometria"],
    },
}
MANIFESTO = "manifesto.json"
N_MUNICIPIOS_PR = 399
CENSO = {"93": ("populacao_2022", int), "6318": ("area_km2_2022", float),
         "614": ("densidade_hab_km2_2022", float)}
DOMICILIOS = {"6795": "total", "1": "urbana", "2": "rural"}
CAMPOS_MUNICIPAIS = (
    "codigo_ibge", "municipio_ibge", "uf", "populacao_2022", "area_km2_2022",
    "densidade_hab_km2_2022", "populacao_urbana_2022", "populacao_rural_2022",
    "proporcao_urbana_2022",
)


def normalizar_municipio(nome):
    texto = unicodedata.normalize("NFKD", (nome or "").upper())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return " ".join(re.findall(r"[A-Z0-9]+", texto))


def registro_fonte(caminho, fonte, metadados):
    return (metadados.get("url") == fonte["url"] and metadados.get("obtido_em")
            and caminho.is_file() and metadados.get("sha256") == hash_arquivo(caminho))


def coletar_ibge(pasta):
    manifesto = pasta / MANIFESTO
    anterior = ler_json(manifesto) if manifesto.exists() else {}
    fontes, novos = {}, {}
    for nome, fonte in FONTES.items():
        caminho = pasta / nome
        metadados = anterior.get(nome, {})
        if registro_fonte(caminho, fonte, metadados):
            fontes[nome] = metadados
            continue
        if caminho.exists() and metadados:
            raise ValueError(f"Conteúdo local de {nome} diverge do manifesto.")
        resposta = run(["curl", "--fail", "--location", "--silent", "--show-error",
                        "--max-time", "45", "--retry", "2", "--retry-max-time", "60", fonte["url"]],
                       capture_output=True)
        if resposta.returncode:
            raise OSError(f"Falha ao obter {nome}: {resposta.stderr.decode(errors='replace').strip()}")
        dados = resposta.stdout
        if fonte["formato"] == "JSON":
            tabela = json.loads(dados)
            if not isinstance(tabela, list) or len(tabela) < N_MUNICIPIOS_PR:
                raise ValueError(f"Resposta incompleta do IBGE em {nome}.")
        else:
            with ZipFile(BytesIO(dados)) as arquivo:
                if arquivo.testzip() or not any(item.endswith(".shp") for item in arquivo.namelist()):
                    raise ValueError(f"Shapefile inválido em {nome}.")
        novos[caminho] = dados
        fontes[nome] = {
            **fonte, "obtido_em": datetime.now(ZoneInfo("America/Sao_Paulo")).isoformat(timespec="seconds"),
            "bytes": len(dados), "sha256": sha256(dados).hexdigest(),
        }
    for caminho, dados in novos.items():
        salvar_bytes(caminho, dados)
    salvar_json(manifesto, fontes)
    return fontes


def conferir_fontes(pasta):
    manifesto = ler_json(pasta / MANIFESTO)
    for nome, fonte in FONTES.items():
        if not registro_fonte(pasta / nome, fonte, manifesto.get(nome, {})):
            raise ValueError(f"Fonte IBGE ausente ou divergente do manifesto: {nome}.")
    return manifesto


def inserir_unico(destino, chave, valor, fonte):
    if chave in destino:
        raise ValueError(f"Chave duplicada em {fonte}: {chave}.")
    destino[chave] = valor


def ler_dimensoes(pasta):
    conferir_fontes(pasta)
    municipios = {}
    for reg in ler_json(pasta / "localidades_pr.json"):
        codigo = str(reg["id"])
        uf = reg["microrregiao"]["mesorregiao"]["UF"]["sigla"]
        if uf != "PR" or not re.fullmatch(r"41[0-9]{5}", codigo) or not normalizar_municipio(reg["nome"]):
            raise ValueError(f"Cadastro oficial inválido para o código {codigo}.")
        inserir_unico(municipios, codigo, {"codigo_ibge": codigo, "municipio_ibge": reg["nome"], "uf": uf},
                      "Localidades")
    if len(municipios) != N_MUNICIPIOS_PR:
        raise ValueError(f"Cadastro com {len(municipios)} municípios, esperados {N_MUNICIPIOS_PR}.")

    def linhas_sidra(nome):
        for linha in ler_json(pasta / nome)[1:]:
            codigo = linha["D1C"]
            nome_uf = f"{municipios[codigo]['municipio_ibge']} - PR"
            if linha["NC"] != "6" or normalizar_municipio(linha["D1N"]) != normalizar_municipio(nome_uf):
                raise ValueError(f"Nome ou nível territorial divergente em {nome}: {codigo}.")
            yield codigo, linha

    for codigo, linha in linhas_sidra("sidra_4714_pr_2022.json"):
        if linha["D3C"] != "2022":
            raise ValueError("Período incompatível na tabela 4714.")
        campo, converter = CENSO[linha["D2C"]]
        numero = converter(linha["V"])
        if not 0 < numero < float("inf"):
            raise ValueError(f"Valor censitário inválido: {campo}, {codigo}.")
        inserir_unico(municipios[codigo], campo, numero, "SIDRA 4714")

    domicilios = defaultdict(dict)
    for codigo, linha in linhas_sidra("sidra_9923_pr_2022.json"):
        if linha["D2C"] != "93" or linha["D3C"] != "2022":
            raise ValueError("Variável ou período incompatível na tabela 9923.")
        categoria = DOMICILIOS[linha["D4C"]]
        valor = 0 if linha["V"] == "-" else int(linha["V"])
        inserir_unico(domicilios[codigo], categoria, valor, "SIDRA 9923")

    estimativas = {}
    for codigo, linha in linhas_sidra("sidra_6579_pr_2024_2025.json"):
        ano, valor = int(linha["D3C"]), int(linha["V"])
        if linha["D2C"] != "9324" or ano not in (2024, 2025) or valor <= 0:
            raise ValueError(f"Variável, valor ou ano incompatível na tabela 6579: {codigo}.")
        inserir_unico(estimativas, (codigo, ano), valor, "SIDRA 6579")

    for codigo, municipio in municipios.items():
        total, urbana, rural = (domicilios[codigo][campo] for campo in ("total", "urbana", "rural"))
        if min(urbana, rural) < 0 or urbana + rural != total or total != municipio["populacao_2022"]:
            raise ValueError(f"População censitária divergente para {codigo}.")
        municipio.update(populacao_urbana_2022=urbana, populacao_rural_2022=rural,
                         proporcao_urbana_2022=urbana / total)
        if set(municipio) != set(CAMPOS_MUNICIPAIS) or any((codigo, ano) not in estimativas for ano in (2024, 2025)):
            raise ValueError(f"Dimensão municipal incompleta para {codigo}.")
    return municipios, estimativas
