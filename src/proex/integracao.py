"""Junção municipal por nome e UF, com dimensão única por código IBGE."""

from collections import Counter, defaultdict

from .arquivos import hash_arquivo, ler_csv, salvar_csv, salvar_json
from .geografia import MalhaMunicipal, conferir_coordenadas
from .ibge import CAMPOS_MUNICIPAIS, ler_dimensoes, normalizar_municipio
from .prf import CAMPOS, PREDITORES_PRF

ATRIBUTOS_IBGE = tuple(campo for campo in CAMPOS_MUNICIPAIS if campo != "uf")
CAMPOS_INTEGRADOS = CAMPOS + ATRIBUTOS_IBGE + (
    "municipio_chave", "status_vinculo_ibge", "codigos_candidatos_ibge",
    "populacao_estimada_ano", "status_estimativa",
    "codigos_malha_2022", "verificacao_geografica",
)
PREDITORES = PREDITORES_PRF + (
    "codigo_ibge", "populacao_2022", "area_km2_2022", "densidade_hab_km2_2022",
    "proporcao_urbana_2022",
)
CAMPOS_AUSENCIA_DECLARADA = {
    "br": {0, "0"},
    "condicao_metereologica": {"Ignorado"},
    "sentido_via": {"Não Informado"},
    "classificacao_acidente": {"Ignorado"},
}


def extrair_preditores(ocorrencia):
    """Projeta somente as colunas autorizadas do recorte de contexto."""
    atributos = {campo: ocorrencia[campo] for campo in PREDITORES}
    if atributos["br"] in CAMPOS_AUSENCIA_DECLARADA["br"]:
        atributos["br"] = None
    return atributos


def chave_municipal(uf, municipio):
    return (uf or "").strip().upper(), normalizar_municipio(municipio)


def indexar_municipios(municipios):
    indice = defaultdict(list)
    for codigo, municipio in municipios.items():
        chave = chave_municipal(municipio["uf"], municipio["municipio_ibge"])
        indice[chave].append(codigo)
    return indice


def ler_aliases(caminho, municipios, indice):
    aliases = {}
    for linha in ler_csv(caminho):
        chave = chave_municipal(linha["uf"], linha["municipio_prf"])
        codigo = linha["codigo_ibge"]
        destino = municipios.get(codigo)
        if (chave in aliases or chave in indice or not chave[1] or not destino
                or destino["uf"] != chave[0] or not linha["justificativa"].strip()
                or not linha["fonte"].strip()):
            raise ValueError(f"Equivalência municipal inválida ou duplicada: {chave}.")
        aliases[chave] = codigo
    return aliases


def vincular_municipio(chave, indice, aliases):
    candidatos = indice.get(chave, [])
    if len(candidatos) == 1:
        return candidatos[0], "exato_normalizado", candidatos
    if len(candidatos) > 1:
        return None, "ambiguo", sorted(candidatos)
    if chave in aliases:
        return aliases[chave], "alias_documentado", [aliases[chave]]
    return None, "sem_correspondencia", []


def integrar_ocorrencias(ocorrencias, municipios, estimativas, indice, aliases, malha):
    ids = [linha["id"] for linha in ocorrencias]
    if len(set(ids)) != len(ids):
        raise ValueError("Identificadores PRF duplicados antes da integração.")

    integradas = []
    for linha in ocorrencias:
        chave = chave_municipal(linha["uf"], linha["municipio"])
        codigo, metodo, candidatos = vincular_municipio(chave, indice, aliases)
        municipio = municipios.get(codigo, {})
        ano = int(linha["ano"])
        estimativa = estimativas.get((codigo, ano))
        if codigo is None:
            status_estimativa = "sem_vinculo_ibge"
        elif estimativa is None:
            status_estimativa = "ano_sem_estimativa"
        else:
            status_estimativa = "disponivel"
        geocodigos = malha.localizar(linha["latitude"], linha["longitude"])
        integradas.append({
            **linha, **{campo: municipio.get(campo) for campo in ATRIBUTOS_IBGE},
            "municipio_chave": chave[1], "status_vinculo_ibge": metodo,
            "codigos_candidatos_ibge": "|".join(candidatos),
            "populacao_estimada_ano": estimativa, "status_estimativa": status_estimativa,
            "codigos_malha_2022": "|".join(geocodigos or ()),
            "verificacao_geografica": conferir_coordenadas(codigo, geocodigos),
        })

    antes = [(linha["id"], linha["gravidade"]) for linha in ocorrencias]
    depois = [(linha["id"], linha["gravidade"]) for linha in integradas]
    if antes != depois:
        raise ValueError("A integração alterou as ocorrências ou a gravidade.")
    return integradas


def cobertura(grupo, recorte, valor):
    total = len(grupo)
    vinculados = [linha for linha in grupo if linha["codigo_ibge"]]
    com_estimativa = sum(linha["populacao_estimada_ano"] is not None for linha in grupo)
    return {
        "recorte": recorte, "valor": valor, "ocorrencias": total,
        "municipios_prf_distintos": len({(linha["uf"], linha["municipio_chave"])
                                         for linha in grupo if linha["municipio_chave"]}),
        "municipios_ibge_distintos": len({linha["codigo_ibge"] for linha in vinculados}),
        "vinculados": len(vinculados), "sem_vinculo": total - len(vinculados),
        "taxa_vinculo": len(vinculados) / total if total else None,
        "com_estimativa_do_ano": com_estimativa,
        "taxa_estimativa_do_ano": com_estimativa / total if total else None,
    }


def auditar_integracao(antes, depois, municipios, indice, pasta, hash_integrada):
    recortes = [cobertura(depois, "total", "2023–2025")]
    for campo in ("ano", "gravidade"):
        grupos = defaultdict(list)
        for linha in depois:
            grupos[linha[campo]].append(linha)
        recortes.extend(cobertura(grupo, campo, chave) for chave, grupo in sorted(grupos.items()))

    por_municipio = defaultdict(list)
    for linha in depois:
        por_municipio[(linha["uf"], linha["municipio"])].append(linha)
    correspondencias = []
    for (uf, nome), registros in sorted(por_municipio.items(), key=lambda item: (item[0][0], item[0][1] or "")):
        primeira = registros[0]
        geografias = Counter(linha["verificacao_geografica"] for linha in registros)
        correspondencias.append({
            "uf": uf, "municipio_prf": nome, "municipio_chave": primeira["municipio_chave"],
            "codigo_ibge": primeira["codigo_ibge"], "municipio_ibge": primeira["municipio_ibge"],
            "status_vinculo_ibge": primeira["status_vinculo_ibge"],
            "codigos_candidatos_ibge": primeira["codigos_candidatos_ibge"],
            "ocorrencias": len(registros), "coord_confere": geografias["confere"],
            "coord_diverge": geografias["diverge"],
            "coord_fora_da_malha": geografias["fora_da_malha_pr_2022"],
        })

    ausencias = []
    for campo in CAMPOS_INTEGRADOS:
        marcador = CAMPOS_AUSENCIA_DECLARADA.get(campo, set())
        nulos = sum(linha[campo] in (None, "") for linha in depois)
        codificados = sum(linha[campo] in marcador for linha in depois)
        ausencias.append({"campo": campo, "vazios_ou_nulos": nulos,
                          "ausencias_codificadas": codificados,
                          "taxa_ausencia": (nulos + codificados) / len(depois)})
    geo_por_ano = Counter((linha["ano"], linha["verificacao_geografica"]) for linha in depois)
    geografias = [{"ano": ano, "verificacao_geografica": status, "ocorrencias": quantidade}
                  for (ano, status), quantidade in sorted(geo_por_ano.items())]
    geo_campos = ("id", "ano", "municipio", "codigo_ibge", "status_vinculo_ibge",
                  "latitude", "longitude", "codigos_malha_2022", "verificacao_geografica")
    revisao = ({campo: linha[campo] for campo in geo_campos} for linha in depois
               if linha["status_vinculo_ibge"] != "exato_normalizado" or linha["verificacao_geografica"] != "confere")

    classes_antes = Counter(linha["gravidade"] for linha in antes)
    classes_depois = Counter(linha["gravidade"] for linha in depois)
    distribuicao = [{"gravidade": classe, "antes": classes_antes[classe], "depois": classes_depois[classe]}
                    for classe in sorted(classes_antes.keys() | classes_depois.keys())]
    salvaguardas = {
        "tipo_juncao": "esquerda", "cardinalidade": "many-to-one",
        "ocorrencias_antes": len(antes), "ocorrencias_depois": len(depois),
        "ids_distintos_antes": len({linha["id"] for linha in antes}),
        "ids_distintos_depois": len({linha["id"] for linha in depois}),
        "ocorrencias_adicionadas": len(depois) - len(antes),
        "municipios_distintos_na_dimensao_ibge": len(municipios),
        "distribuicao_gravidade_preservada": all(linha["antes"] == linha["depois"] for linha in distribuicao),
    }
    salvar_csv(pasta / "validacoes_integracao.csv", ("indicador", "valor"),
               ({"indicador": k, "valor": v} for k, v in salvaguardas.items()))
    for nome, linhas in (
        ("cobertura", recortes), ("correspondencias_municipais", correspondencias),
        ("valores_ausentes", ausencias), ("distribuicao_gravidade", distribuicao),
        ("conferencia_geografica_por_ano", geografias),
    ):
        salvar_csv(pasta / f"{nome}.csv", tuple(linhas[0]), linhas)
    salvar_csv(pasta / "revisao_geografica.csv", geo_campos, revisao)
    salvar_json(pasta / "integracao.json", {
        **salvaguardas, "sha256_base_integrada": hash_integrada, "cobertura": recortes,
        "distribuicao_gravidade": distribuicao,
        "ocorrencias_por_metodo": dict(Counter(linha["status_vinculo_ibge"] for linha in depois)),
        "chaves_ambiguas_no_ibge": [{"uf": uf, "chave": nome, "codigos": codigos}
                                   for (uf, nome), codigos in sorted(indice.items()) if len(codigos) > 1],
        "municipios_encontrados": [linha for linha in correspondencias if linha["codigo_ibge"]],
        "municipios_nao_encontrados": [linha for linha in correspondencias if not linha["codigo_ibge"]],
        "valores_ausentes": ausencias, "conferencia_geografica_por_ano": geografias,
    })


def integrar_prf(ocorrencias, externos, arquivo_aliases, processados, auditoria):
    municipios, estimativas = ler_dimensoes(externos)
    indice = indexar_municipios(municipios)
    aliases = ler_aliases(arquivo_aliases, municipios, indice)
    malha = MalhaMunicipal(externos / "PR_Municipios_2022.zip", municipios)
    integradas = integrar_ocorrencias(ocorrencias, municipios, estimativas, indice, aliases, malha)
    campos_dimensao = CAMPOS_MUNICIPAIS + ("populacao_estimada_2024", "populacao_estimada_2025")
    salvar_csv(processados / "municipios_pr_ibge.csv", campos_dimensao, (
        {**municipio, **{f"populacao_estimada_{ano}": estimativas[(codigo, ano)] for ano in (2024, 2025)}}
        for codigo, municipio in sorted(municipios.items())
    ))
    arquivo_integrado = processados / "prf_ibge_integrada.csv"
    salvar_csv(arquivo_integrado, CAMPOS_INTEGRADOS, integradas)
    auditar_integracao(ocorrencias, integradas, municipios, indice, auditoria, hash_arquivo(arquivo_integrado))
    salvar_json(processados / "politica_preditores.json", {
        "alvo": "gravidade", "definicao": "mortos > 0 ou feridos_graves > 0",
        "preditores_permitidos": PREDITORES,
        "demais_campos_fora_da_projecao": [campo for campo in CAMPOS_INTEGRADOS if campo not in PREDITORES],
    })
    return integradas
