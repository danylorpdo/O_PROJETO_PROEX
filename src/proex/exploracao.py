"""Tabelas exploratórias por ocorrência e intervalos binomiais de Wilson."""

from collections import Counter
from math import sqrt

from .arquivos import salvar_csv, salvar_json

MINIMO_IC = 30
SEM_DADO = "Sem informação"
DENSIDADE = ("< 25", "25 a < 50", "50 a < 100", "100 a < 500", "≥ 500")
POPULACAO = ("< 10 mil", "10 a < 25 mil", "25 a < 50 mil", "50 a < 100 mil", "≥ 100 mil")
FASES = ("Amanhecer", "Pleno dia", "Anoitecer", "Plena Noite")
CRUZAMENTOS = {
    "municipio_gravidade": ("municipio",),
    "densidade_gravidade": ("faixa_densidade",),
    "populacao_gravidade": ("faixa_populacao",),
    "pista_fase_gravidade": ("tipo_pista", "fase_dia"),
    "tipo_acidente_contexto_gravidade": ("tipo_acidente", "faixa_densidade"),
    "rodovia_municipio_gravidade": ("rodovia", "municipio"),
}
METRICAS_GRAVIDADE = ("ocorrencias", "graves", "nao_graves", "proporcao_grave",
                      "proporcao_nao_grave", "ic95_inferior", "ic95_superior", "grupo_pequeno")


def faixa(valor, cortes, rotulos):
    if valor in ("", None):
        return SEM_DADO
    numero = float(valor)
    indice = sum(numero >= corte for corte in cortes)
    return rotulos[indice]


def contextualizar(linha):
    municipio = linha["municipio_ibge"]
    br = linha["br"]
    if not municipio:
        municipio = f"{linha['municipio'] or SEM_DADO} (sem vínculo)"
    return {
        **linha,
        "municipio": municipio,
        "faixa_densidade": faixa(linha["densidade_hab_km2_2022"], (25, 50, 100, 500), DENSIDADE),
        "faixa_populacao": faixa(linha["populacao_2022"], (10_000, 25_000, 50_000, 100_000), POPULACAO),
        "rodovia": f"BR-{int(br):03d}" if br not in (None, "", 0, "0") else SEM_DADO,
        "uso_solo_prf": {"Sim": "Urbano", "Não": "Rural"}.get(linha["uso_solo"], SEM_DADO),
    }


def wilson(sucessos, total):
    if total < MINIMO_IC:
        return None, None
    z = 1.959963984540054
    proporcao = sucessos / total
    ajuste = 1 + z**2 / total
    centro = (proporcao + z**2 / (2 * total)) / ajuste
    margem = z * sqrt(proporcao * (1 - proporcao) / total + z**2 / (4 * total**2)) / ajuste
    return max(0.0, centro - margem), min(1.0, centro + margem)


def agregar_gravidade(linhas, campos):
    totais = Counter(tuple(linha[campo] for campo in campos) for linha in linhas)
    graves = Counter(tuple(linha[campo] for campo in campos)
                     for linha in linhas if linha["gravidade"] == "grave")
    resultado = []
    for chave, total in sorted(totais.items(), key=lambda item: (-item[1], item[0])):
        n_graves = graves[chave]
        inferior, superior = wilson(n_graves, total)
        resultado.append({
            **dict(zip(campos, chave)),
            "ocorrencias": total, "graves": n_graves, "nao_graves": total - n_graves,
            "proporcao_grave": n_graves / total, "proporcao_nao_grave": (total - n_graves) / total,
            "ic95_inferior": inferior, "ic95_superior": superior, "grupo_pequeno": total < MINIMO_IC,
        })
    return resultado


def agregar_uso(linhas):
    campos = ("faixa_densidade", "uso_solo_prf")
    totais = Counter(linha["faixa_densidade"] for linha in linhas)
    combinacoes = Counter((linha["faixa_densidade"], linha["uso_solo_prf"]) for linha in linhas)
    resultado = []
    for densidade in [*DENSIDADE, SEM_DADO]:
        total = totais[densidade]
        if not total:
            continue
        for uso in ("Urbano", "Rural", SEM_DADO):
            ocorrencias = combinacoes[densidade, uso]
            if uso == SEM_DADO and not ocorrencias:
                continue
            inferior, superior = wilson(ocorrencias, total)
            resultado.append({
                **dict(zip(campos, (densidade, uso))),
                "ocorrencias": ocorrencias, "denominador_na_faixa": total,
                "proporcao_na_faixa": ocorrencias / total, "ic95_inferior": inferior,
                "ic95_superior": superior, "grupo_pequeno": total < MINIMO_IC,
            })
    return resultado


def gerar_resultados(registros, pasta):
    linhas = [contextualizar(linha) for linha in registros]
    tabelas = {}
    for nome, campos in CRUZAMENTOS.items():
        tabelas[nome] = agregar_gravidade(linhas, campos)
        if sum(grupo["ocorrencias"] for grupo in tabelas[nome]) != len(linhas):
            raise ValueError(f"Denominadores incompletos em {nome}.")
        salvar_csv(pasta / f"{nome}.csv", campos + METRICAS_GRAVIDADE, tabelas[nome])

    uso = agregar_uso(linhas)
    salvar_csv(pasta / "uso_solo_densidade.csv", tuple(uso[0]), uso)
    tabelas["uso_solo_densidade"] = uso

    conferidos = [linha for linha in linhas if linha["verificacao_geografica"] == "confere"]
    sensibilidade = [
        {"amostra": amostra, **linha}
        for amostra, recorte in (("todos_os_registros", linhas), ("coordenadas_conferem", conferidos))
        for linha in agregar_gravidade(recorte, ("faixa_densidade",))
    ]
    salvar_csv(pasta / "sensibilidade_geografica_densidade.csv",
               ("amostra", "faixa_densidade", *METRICAS_GRAVIDADE), sensibilidade)
    salvar_json(pasta / "criterios.json", {
        "unidade": "ocorrência PRF", "densidade_2022_hab_km2": DENSIDADE,
        "populacao_residente_2022": POPULACAO,
        "grupo_pequeno_quando_denominador_menor_que": MINIMO_IC,
        "intervalos": "Wilson de 95%, descritivos, sem ajuste para dependência entre ocorrências.",
        "denominador_gravidade": "Total de ocorrências de cada combinação das categorias.",
        "denominador_uso_solo": "Total de ocorrências na faixa de densidade correspondente.",
        "contexto_municipal_no_cruzamento_por_tipo": "Faixa fixa de densidade demográfica de 2022.",
    })
    return tabelas
