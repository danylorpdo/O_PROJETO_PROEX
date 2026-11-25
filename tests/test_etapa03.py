import numpy as np
import pandas as pd
from streamlit.testing.v1 import AppTest

from scripts.etapa03 import SAIDA, carregar_base, estabilidade_apriori
from src.proex.arquivos import RAIZ, ler_json
from src.proex.classificacao import calcular_metricas, dividir_por_ano
from work.analisar import FIELDS, minerar_regras


def test_resultados_temporais_reproduziveis_a_partir_das_previsoes():
    base, sha256 = carregar_base()
    particoes = dividir_por_ano(base)
    assert {ano: len(dados) for ano, dados in particoes.items()} == {2023: 7110, 2024: 7583, 2025: 7630}
    assert len(set().union(*(set(dados.id) for dados in particoes.values()))) == 22323
    teste = particoes[2025]
    previsoes = pd.read_csv(SAIDA / "previsoes_2025.csv", sep=";", dtype={"id": str})
    assert previsoes.id.tolist() == teste.id.tolist()
    assert np.array_equal(previsoes.real, teste.gravidade.eq("grave"))
    resumo = ler_json(SAIDA / "classificacao.json")
    assert resumo["sha256_base_integrada"] == sha256
    assert len(resumo["metricas"]) == 14
    for item in resumo["metricas"]:
        if item["ano"] == 2025:
            prefixo = f"{item['modelo']}_{item['cenario']}"
            calculadas = calcular_metricas(previsoes.real, previsoes[f"{prefixo}_previsto"],
                                           previsoes[f"{prefixo}_escore"])
            assert calculadas == {chave: item[chave] for chave in calculadas}
        else:
            assert item["ano"] == 2024
            assert item["fn"] + item["vp"] == 1966
            assert item["vn"] + item["fp"] == 5617


def test_apriori_original_e_independencia_da_descoberta():
    trabalho = RAIZ / "work" / "resultados"
    base, _ = carregar_base()
    transacoes = base[[*FIELDS, "gravidade"]].fillna("Não informado").to_dict("records")
    regras_originais, _, graves, _ = minerar_regras(transacoes)
    assert graves == 5864
    assert regras_originais == ler_json(trabalho / "resumo.json")["regras"]
    resumo, regras = estabilidade_apriori(base)
    assert resumo["regras_descobertas"] == 50
    assert resumo["mantem_criterios_2025"] == 37
    alterada = base.assign(gravidade=base.gravidade.mask(base.ano.eq(2025), "nao_grave"))
    _, regras_alteradas = estabilidade_apriori(alterada)
    assert [r["antecedente"] for r in regras] == [r["antecedente"] for r in regras_alteradas]
    assert all(regra["suporte_2025"] == 0 for regra in regras_alteradas)
    assert all(not regra["mantem_criterios_2025"] for regra in regras_alteradas)


def test_dashboard_carrega_e_filtra_sem_retreinar():
    app = AppTest.from_file(str(RAIZ / "outputs" / "dashboard_prf" / "app.py"), default_timeout=30).run()
    assert not app.exception and not app.error
    assert app.metric[0].value == "22.323"
    assert app.metric[3].value == "100,00%"
    assert {"Visão geral", "Classificação", "Interpretação", "Base e método"}.issubset(t.label for t in app.tabs)
    app.multiselect[0].set_value([2025])
    app.multiselect[1].set_value(["Curitiba"])
    app.radio[0].set_value(2024)
    app.selectbox[0].set_value("majoritaria")
    app.run()
    assert not app.exception and not app.error
    assert app.metric[0].value == "702"
    assert app.radio[0].value == 2024
    assert app.selectbox[0].value == "majoritaria"
