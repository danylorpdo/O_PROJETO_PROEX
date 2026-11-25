"""Comparação temporal com as mesmas ocorrências e atributos censitários fixos."""

import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text
from threadpoolctl import threadpool_limits

SEMENTE = 42
ANOS = (2023, 2024, 2025)
CATEGORICAS = ("dia_semana", "fase_dia", "condicao_metereologica", "tipo_pista", "uso_solo", "br", "mes")
NUMERICAS = ("populacao_2022", "area_km2_2022", "densidade_hab_km2_2022", "proporcao_urbana_2022")
CENARIOS = {"prf": "PRF", "prf_ibge": "PRF + IBGE"}
NOMES = {
    "majoritaria": "Referência majoritária", "logistica": "Regressão Logística",
    "arvore": "Árvore de Decisão", "floresta": "Random Forest",
}
ROTULOS = dict(zip(CATEGORICAS + NUMERICAS, (
    "Dia da semana", "Fase do dia", "Clima", "Tipo de pista", "Uso do solo", "Rodovia", "Mês",
    "População (2022)", "Área (2022)", "Densidade (2022)", "Proporção urbana (2022)",
)))
N_REAMOSTRAGENS = 500


def dividir_por_ano(base):
    if set(base.ano) != set(ANOS) or base.id.isna().any() or not base.id.is_unique:
        raise ValueError("Esperados IDs únicos e ocorrências dos anos 2023, 2024 e 2025.")
    particoes = {}
    for ano in ANOS:
        particao = base.loc[base.ano == ano]
        if set(particao.gravidade) != {"grave", "nao_grave"}:
            raise ValueError(f"Ocorrências com classes ausentes ou inválidas em {ano}.")
        particoes[ano] = particao
    return particoes


def estimadores():
    return {
        "majoritaria": DummyClassifier(strategy="most_frequent"),
        "logistica": LogisticRegression(max_iter=500, class_weight="balanced", random_state=SEMENTE),
        "arvore": DecisionTreeClassifier(max_depth=4, min_samples_leaf=30,
                                         class_weight="balanced", random_state=SEMENTE),
        "floresta": RandomForestClassifier(n_estimators=200, max_depth=12, min_samples_leaf=15,
                                           class_weight="balanced", random_state=SEMENTE, n_jobs=1),
    }


def pipeline(modelo, cenario):
    categorias = make_pipeline(SimpleImputer(strategy="constant", fill_value="Não informado"),
                                OneHotEncoder(handle_unknown="ignore"))
    transformacoes = [("categorias", categorias, list(CATEGORICAS))]
    if cenario == "prf_ibge":
        etapas = [SimpleImputer(strategy="median", keep_empty_features=True)]
        if isinstance(modelo, LogisticRegression):
            etapas.append(StandardScaler())
        transformacoes.append(("censo", make_pipeline(*etapas), list(NUMERICAS)))
    return make_pipeline(ColumnTransformer(transformacoes), modelo)


def calcular_metricas(y, previsto, escore):
    precisao, recall, f1, _ = precision_recall_fscore_support(
        y, previsto, average="binary", zero_division=0,
    )
    vn, fp, fn, vp = confusion_matrix(y, previsto, labels=[0, 1]).ravel().tolist()
    return {
        "ocorrencias": len(y), "acuracia": float(accuracy_score(y, previsto)),
        "precisao": float(precisao), "recall": float(recall), "f1": float(f1),
        "roc_auc": float(roc_auc_score(y, escore)), "vn": vn, "fp": fp, "fn": fn, "vp": vp,
    }


def interpretar(pipe, cenario):
    preparo, estimador = (etapa[1] for etapa in pipe.steps)
    encoder = preparo.named_transformers_["categorias"].named_steps["onehotencoder"]
    importancias = estimador.feature_importances_
    grupos = []
    inicio = 0
    for campo, categorias in zip(CATEGORICAS, encoder.categories_, strict=True):
        fim = inicio + len(categorias)
        grupos.append({"campo": ROTULOS[campo], "importancia": float(importancias[inicio:fim].sum())})
        inicio = fim
    if cenario == "prf_ibge":
        grupos.extend({"campo": ROTULOS[campo], "importancia": float(valor)}
                      for campo, valor in zip(NUMERICAS, importancias[inicio:], strict=True))
    resposta = {"importancias": grupos}
    if isinstance(estimador, DecisionTreeClassifier):
        nomes = [nome.split("__", 1)[1] for nome in preparo.get_feature_names_out()]
        resposta["arvore"] = export_text(estimador, feature_names=nomes, max_depth=4)
    return resposta


def f1_binario(y, previsto):
    denominador = np.count_nonzero(y) + np.count_nonzero(previsto)
    return 2 * np.count_nonzero(y & previsto) / denominador if denominador else 0.0


def intervalos_pareados(y, municipios, previsoes, repeticoes=N_REAMOSTRAGENS):
    """Reamostra municípios inteiros e usa as mesmas linhas para os dois cenários."""
    _, grupos = np.unique(municipios, return_inverse=True)
    indices = [np.flatnonzero(grupos == i) for i in range(len(np.unique(grupos)))]
    rng = np.random.default_rng(SEMENTE)
    distribuicoes = {modelo: [] for modelo in previsoes}
    for _ in range(repeticoes):
        amostra = np.concatenate([indices[i] for i in rng.integers(len(indices), size=len(indices))])
        real = y[amostra]
        if np.all(real == real[0]):
            continue
        for modelo, (pred_prf, escore_prf, pred_ibge, escore_ibge) in previsoes.items():
            distribuicoes[modelo].append((
                f1_binario(real, pred_ibge[amostra]) - f1_binario(real, pred_prf[amostra]),
                roc_auc_score(real, escore_ibge[amostra]) - roc_auc_score(real, escore_prf[amostra]),
            ))
    return {modelo: np.quantile(dados, (0.025, 0.975), axis=0).tolist()
            for modelo, dados in distribuicoes.items()}


def avaliar(base):
    base = base.copy()
    base["br"] = base["br"].replace("0", np.nan)
    particoes = dividir_por_ano(base)
    treino = particoes[2023]
    y = {ano: particao.gravidade.eq("grave").to_numpy(dtype=np.int8) for ano, particao in particoes.items()}
    if base["codigo_ibge"].isna().any():
        raise ValueError("A avaliação atual requer código municipal para a reamostragem pareada.")

    resultados, predicoes, interpretacoes = {}, {}, {}
    for cenario in CENARIOS:
        for nome, modelo in estimadores().items():
            if nome == "majoritaria" and cenario != "prf":
                continue
            with threadpool_limits(limits=1):
                pipe = pipeline(modelo, cenario).fit(treino, y[2023])
            for ano in (2024, 2025):
                previsto = pipe.predict(particoes[ano])
                escore = pipe.predict_proba(particoes[ano])[:, 1]
                resultados[ano, nome, cenario] = calcular_metricas(y[ano], previsto, escore)
                if ano == 2025:
                    predicoes[nome, cenario] = previsto, escore
            if nome in {"arvore", "floresta"}:
                interpretacoes[f"{nome}_{cenario}"] = interpretar(pipe, cenario)

    comparacoes = {nome: (*predicoes[nome, "prf"], *predicoes[nome, "prf_ibge"])
                   for nome in NOMES if nome != "majoritaria"}
    teste = particoes[2025]
    intervalos = intervalos_pareados(y[2025], teste["codigo_ibge"].to_numpy(), comparacoes)
    ganhos = []
    for nome, (inferiores, superiores) in intervalos.items():
        antes, depois = (resultados[2025, nome, cenario] for cenario in CENARIOS)
        ganhos.append({
            "modelo": nome, **{f"delta_{campo}": depois[campo] - antes[campo]
                               for campo in ("acuracia", "precisao", "recall", "f1", "roc_auc")},
            "f1_ic95_inferior": inferiores[0], "f1_ic95_superior": superiores[0],
            "roc_auc_ic95_inferior": inferiores[1], "roc_auc_ic95_superior": superiores[1],
        })

    metricas = [{"ano": ano, "modelo": nome, "cenario": cenario, **resultados[ano, nome, cenario]}
                for ano in (2024, 2025) for nome in NOMES
                for cenario in (("prf",) if nome == "majoritaria" else CENARIOS)]
    previsoes_teste = {"id": teste.id.to_numpy(), "real": y[2025]}
    for (nome, cenario), (previsto, escore) in predicoes.items():
        previsoes_teste[f"{nome}_{cenario}_previsto"] = previsto
        previsoes_teste[f"{nome}_{cenario}_escore"] = escore
    resumo = {
        "particoes": {papel: {"ano": ano, "ocorrencias": len(y[ano]), "graves": int(y[ano].sum())}
                      for papel, ano in zip(("treino", "validacao", "teste"), ANOS, strict=True)},
        "atributos_prf": CATEGORICAS, "atributos_ibge_2022": NUMERICAS, "nomes_modelos": NOMES,
        "parametros_modelos": {nome: modelo.get_params() for nome, modelo in estimadores().items()},
        "cenarios": CENARIOS, "semente": SEMENTE, "bootstrap_municipal_repeticoes": N_REAMOSTRAGENS,
        "municipios_teste": int(teste.codigo_ibge.nunique()),
        "rotulos_matrizes": ["Não grave", "Grave"], "metricas": metricas, "ganhos_teste": ganhos,
        "interpretacoes": interpretacoes,
    }
    return resumo, previsoes_teste
