"""Gera classificação temporal e estabilidade de regras para o dashboard."""

import argparse

import pandas as pd
import sklearn

from src.proex.arquivos import PROCESSADOS, RAIZ, RESULTADOS, hash_arquivo, ler_json, salvar_csv, salvar_json
from src.proex.classificacao import CATEGORICAS, NUMERICAS, avaliar
from work.analisar import CONFIANCA_MINIMA, FIELDS, MAX_ITENS, SUPORTE_MINIMO, minerar_regras

SAIDA = RAIZ / "resultados" / "etapa03"


def carregar_base():
    arquivo = PROCESSADOS / "prf_ibge_integrada.csv"
    sha256 = hash_arquivo(arquivo)
    auditoria = ler_json(RESULTADOS / "auditoria" / "integracao.json")
    if sha256 != auditoria.get("sha256_base_integrada"):
        raise ValueError("A base integrada diverge da auditoria da Etapa 02.")
    politica = ler_json(PROCESSADOS / "politica_preditores.json")
    if set(CATEGORICAS + NUMERICAS).difference(politica["preditores_permitidos"]):
        raise ValueError("Há preditores fora da lista da Etapa 02.")
    base = pd.read_csv(arquivo, sep=";", encoding="utf-8-sig",
                       dtype={"id": str, "codigo_ibge": str, "br": str, "mes": str})
    return base, sha256


def medir_regra(antecedente, particao):
    selecionadas = particao
    for item in antecedente.split(" E "):
        coluna, valor = item.split("=", 1)
        selecionadas = selecionadas[selecionadas[coluna].eq(valor)]
    cobertas = len(selecionadas)
    graves = int(selecionadas.gravidade.eq("grave").sum())
    prevalencia = float(particao.gravidade.eq("grave").mean())
    confianca = graves / cobertas if cobertas else None
    return {
        "n_antecedente": cobertas, "n_graves": graves, "suporte": graves / len(particao),
        "confianca": confianca, "lift": confianca / prevalencia if cobertas and prevalencia else None,
    }


def estabilidade_apriori(base):
    colunas = [*FIELDS, "gravidade"]
    descoberta = base.loc[base.ano.isin((2023, 2024)), colunas].fillna("Não informado")
    teste = base.loc[base.ano.eq(2025), colunas].fillna("Não informado")
    regras, _, graves, taxa = minerar_regras(descoberta.to_dict("records"))
    resultados = []
    for posicao, regra in enumerate(regras, start=1):
        verificacao = medir_regra(regra["antecedente"], teste)
        estavel = (verificacao["suporte"] >= SUPORTE_MINIMO
                   and verificacao["confianca"] is not None
                   and verificacao["confianca"] >= CONFIANCA_MINIMA
                   and verificacao["lift"] is not None and verificacao["lift"] > 1)
        resultados.append({
            "posicao_descoberta": posicao, "antecedente": regra["antecedente"],
            "consequente": regra["consequente"],
            **{f"{campo}_2023_2024": regra[campo] for campo in verificacao},
            **{f"{campo}_2025": valor for campo, valor in verificacao.items()},
            "mantem_criterios_2025": estavel,
        })
    resumo = {
        "descoberta": {"anos": [2023, 2024], "ocorrencias": len(descoberta), "graves": graves,
                       "proporcao_grave": taxa},
        "teste": {"ano": 2025, "ocorrencias": len(teste), "graves": int(teste.gravidade.eq("grave").sum()),
                  "proporcao_grave": float(teste.gravidade.eq("grave").mean())},
        "criterios": {"suporte_minimo": SUPORTE_MINIMO, "confianca_minima": CONFIANCA_MINIMA,
                      "lift_maior_que": 1, "max_itens": MAX_ITENS},
        "regras_descobertas": len(resultados),
        "mantem_criterios_2025": sum(regra["mantem_criterios_2025"] for regra in resultados),
        "principais_dez_estaveis": sum(regra["mantem_criterios_2025"] for regra in resultados[:10]),
    }
    return resumo, resultados


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    base, sha256 = carregar_base()
    classificacao, previsoes = avaliar(base)
    classificacao.update(sha256_base_integrada=sha256, versao_scikit_learn=sklearn.__version__)
    regras_resumo, regras = estabilidade_apriori(base)
    metricas, ganhos = classificacao["metricas"], classificacao["ganhos_teste"]

    salvar_csv(SAIDA / "metricas_temporais.csv", tuple(metricas[0]), metricas)
    salvar_csv(SAIDA / "ganhos_ibge_2025.csv", tuple(ganhos[0]), ganhos)
    colunas = tuple(previsoes)
    salvar_csv(SAIDA / "previsoes_2025.csv", colunas,
               (dict(zip(colunas, linha, strict=True)) for linha in zip(*previsoes.values(), strict=True)))
    salvar_csv(SAIDA / "estabilidade_apriori.csv", tuple(regras[0]), regras)
    salvar_json(SAIDA / "apriori.json", regras_resumo)
    salvar_json(SAIDA / "classificacao.json", classificacao)
    print(f"Classificação e estabilidade das regras gravadas em {SAIDA.relative_to(RAIZ)}.")


if __name__ == "__main__":
    main()
