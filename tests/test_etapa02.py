from collections import Counter
from datetime import date

import pytest

from src.proex.arquivos import BRUTOS_PRF, EXTERNOS, RAIZ, ler_csv, ler_json
from src.proex.exploracao import gerar_resultados
from src.proex.ibge import conferir_fontes, ler_dimensoes, normalizar_municipio
from src.proex.integracao import (
    CAMPOS_INTEGRADOS,
    extrair_preditores,
    indexar_municipios,
    integrar_ocorrencias,
    integrar_prf,
    ler_aliases,
)
from src.proex.prf import (
    CAMPOS,
    CAMPOS_ORIGINAIS,
    CONTAGENS,
    DIAS,
    definir_gravidade,
    ler_prf,
    preparar_linha,
    preparar_prf,
)

CONTAGENS_PRF = {2023: (67766, 7110, 1952), 2024: (73202, 7583, 1966), 2025: (72529, 7630, 1946)}
ALIASES = RAIZ / "dados" / "referencias" / "aliases_municipais.csv"


@pytest.fixture(scope="module")
def bases(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("etapa02")
    preparada = preparar_prf(BRUTOS_PRF, pasta, pasta)
    integrada = integrar_prf(preparada, EXTERNOS, ALIASES, pasta, pasta)
    return preparada, integrada, pasta


@pytest.mark.parametrize("ano", CONTAGENS_PRF)
def test_leitura_originais(ano):
    nacional, parana, graves = CONTAGENS_PRF[ano]
    linhas = list(ler_prf(BRUTOS_PRF / f"datatran{ano}.zip"))
    linhas_pr = [linha for linha in linhas if linha["uf"] == "PR"]
    assert len(linhas) == nacional and len(linhas_pr) == parana
    assert set(linhas[0]) == set(CAMPOS_ORIGINAIS)
    assert sum(int(r["mortos"]) > 0 or int(r["feridos_graves"]) > 0 for r in linhas_pr) == graves


def test_esquema_e_unicidade_prf(bases):
    preparada, _, pasta = bases
    assert len(preparada) == len({linha["id"] for linha in preparada}) == 22323
    assert all(tuple(linha) == CAMPOS and linha["uf"] == "PR" for linha in preparada)
    assert sum(linha["id"] == "6e+05" and linha["ano"] == 2024 for linha in preparada) == 1
    assert all(isinstance(linha["latitude"], float) for linha in preparada)
    assert all(isinstance(linha["km"], float) for linha in preparada)
    assert all(isinstance(linha["mortos"], int) for linha in preparada)
    assert ler_json(pasta / "prf.json")["reconciliado"]
    assert tuple(ler_csv(pasta / "prf_preparada.csv")[0]) == CAMPOS


def test_datas_e_horarios(bases):
    preparada, _, _ = bases
    for linha in preparada:
        dia = date.fromisoformat(linha["data_inversa"])
        assert (linha["ano"], linha["mes"], linha["dia_semana"]) == (dia.year, dia.month, DIAS[dia.weekday()])
        assert len(linha["horario"]) == 8


@pytest.mark.parametrize("campo,valor", [
    ("id", "A"),
    ("data_inversa", "2023-02-30"),
    ("dia_semana", "incompatível"),
    ("horario", "25:00:00"),
    ("horario", "09:00:00+00:00"),
    ("latitude", "91"),
    ("longitude", "NaN"),
    ("tipo_pista", "categoria inesperada"),
])
def test_validacao_campos(campo, valor):
    linha = next(linha for linha in ler_prf(BRUTOS_PRF / "datatran2023.zip") if linha["uf"] == "PR")
    with pytest.raises(ValueError):
        preparar_linha({**linha, campo: valor}, 2023)


@pytest.mark.parametrize("mortos,feridos,alvo", [(0, 0, "nao_grave"), (2, 0, "grave"), (0, 1, "grave"), (2, 3, "grave")])
def test_definicao_alvo(mortos, feridos, alvo):
    assert definir_gravidade(mortos, feridos) == alvo


def test_alvo_e_projecao_sem_vazamento(bases):
    _, integrada, _ = bases
    assert all((r["gravidade"] == "grave") == (r["mortos"] + r["feridos_graves"] > 0) for r in integrada)
    campos = set(extrair_preditores(integrada[0]))
    assert not campos.intersection((*CONTAGENS, "gravidade", "classificacao_acidente", "id"))
    sem_br = [linha for linha in integrada if linha["br"] == 0]
    assert len(sem_br) == 31 and all(extrair_preditores(linha)["br"] is None for linha in sem_br)
    with pytest.raises(ValueError, match="não negativos"):
        definir_gravidade(0, -1)


@pytest.mark.parametrize("nome,esperado", [
    ("  São   José dos Pinhais  ", "SAO JOSE DOS PINHAIS"),
    ("Rancho Alegre D’Oeste", "RANCHO ALEGRE D OESTE"),
    ("Pérola d'Oeste", "PEROLA D OESTE"),
    ("Pérola-d’Oeste", "PEROLA D OESTE"),
    (None, ""),
])
def test_normalizacao_municipal(nome, esperado):
    assert normalizar_municipio(nome) == esperado


def test_fontes_e_dimensoes_unicas():
    manifesto = conferir_fontes(EXTERNOS)
    assert len(manifesto) == 5 and all(len(item["sha256"]) == 64 for item in manifesto.values())
    municipios, estimativas = ler_dimensoes(EXTERNOS)
    assert len(municipios) == 399 and len(estimativas) == 798
    assert municipios["4106902"]["populacao_rural_2022"] == 0
    assert {ano for _, ano in estimativas} == {2024, 2025}
    assert all(linha["proporcao_urbana_2022"] <= 1 for linha in municipios.values())


def test_juncao_integral_sem_multiplicacao(bases):
    preparada, integrada, pasta = bases
    auditoria = ler_json(pasta / "integracao.json")
    assert auditoria["cardinalidade"] == "many-to-one"
    assert auditoria["ocorrencias_adicionadas"] == 0
    assert auditoria["distribuicao_gravidade_preservada"]
    assert len(preparada) == len(integrada) == 22323
    assert [linha["id"] for linha in preparada] == [linha["id"] for linha in integrada]
    assert Counter(linha["gravidade"] for linha in integrada) == {"grave": 5864, "nao_grave": 16459}
    assert all({campo: posterior[campo] for campo in CAMPOS} == anterior
               for anterior, posterior in zip(preparada, integrada, strict=True))
    assert tuple(ler_csv(pasta / "prf_ibge_integrada.csv")[0]) == CAMPOS_INTEGRADOS
    assert auditoria["ocorrencias_por_metodo"] == {"exato_normalizado": 22293, "alias_documentado": 30}
    assert all(r["codigo_ibge"] for r in integrada)
    assert {linha["status_estimativa"] for linha in integrada if linha["ano"] == 2023} == {"ano_sem_estimativa"}
    assert all(linha["populacao_estimada_ano"] for linha in integrada if linha["ano"] != 2023)
    assert len({linha["codigo_ibge"] for linha in ler_csv(pasta / "municipios_pr_ibge.csv")}) == 399


class MalhaSimulada:
    def localizar(self, latitude, longitude):
        return ("4119004",)


def test_sem_vinculo_ambiguo_e_uf():
    municipios = {
        "4100001": {"uf": "PR", "municipio_ibge": "Nome Igual"},
        "4100002": {"uf": "PR", "municipio_ibge": "Nóme Igual"},
    }
    ocorrencias = [
        {"id": "1", "ano": 2023, "uf": "PR", "municipio": "Nome Inexistente", "latitude": -25,
         "longitude": -52, "gravidade": "grave"},
        {"id": "2", "ano": 2023, "uf": "PR", "municipio": "Nome Igual", "latitude": -25,
         "longitude": -52, "gravidade": "nao_grave"},
        {"id": "3", "ano": 2023, "uf": "SC", "municipio": "Nome Igual", "latitude": -25,
         "longitude": -52, "gravidade": "grave"},
    ]
    indice = indexar_municipios(municipios)
    resultado = integrar_ocorrencias(ocorrencias, municipios, {}, indice, {}, MalhaSimulada())
    assert [linha["status_vinculo_ibge"] for linha in resultado] == [
        "sem_correspondencia", "ambiguo", "sem_correspondencia",
    ]
    assert all(linha["codigo_ibge"] is None and linha["populacao_2022"] is None for linha in resultado)
    assert resultado[1]["codigos_candidatos_ibge"] == "4100001|4100002"
    assert [linha["id"] for linha in resultado] == ["1", "2", "3"]
    with pytest.raises(ValueError, match="duplicados"):
        integrar_ocorrencias(ocorrencias + ocorrencias[:1], municipios, {}, indice, {}, MalhaSimulada())


def test_aliases_e_conferencia_geografica(bases):
    _, integrada, _ = bases
    municipios, _ = ler_dimensoes(EXTERNOS)
    aliases = ler_aliases(ALIASES, municipios, indexar_municipios(municipios))
    assert aliases == {("PR", "PEROLA DOESTE"): "4119004", ("PR", "RANCHO ALEGRE DOESTE"): "4121356"}
    linhas = [linha for linha in integrada if linha["status_vinculo_ibge"] == "alias_documentado"]
    assert all(linha["codigo_ibge"] == aliases[linha["uf"], linha["municipio_chave"]] for linha in linhas)
    assert Counter(linha["verificacao_geografica"] for linha in linhas) == {"confere": 23, "diverge": 7}
    assert Counter(linha["verificacao_geografica"] for linha in integrada) == {
        "confere": 20986, "diverge": 1290, "fora_da_malha_pr_2022": 47,
    }


def test_denominadores_exploratorios(bases, tmp_path):
    _, integrada, _ = bases
    tabelas = gerar_resultados(integrada, tmp_path)
    for nome, tabela in tabelas.items():
        assert sum(linha["ocorrencias"] for linha in tabela) == len(integrada)
        if nome != "uso_solo_densidade":
            assert sum(linha["graves"] for linha in tabela) == 5864
            assert all((linha["ic95_inferior"] is None) == (linha["ocorrencias"] < 30) for linha in tabela)
