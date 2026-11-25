"""Figuras em português para os cruzamentos exploratórios da Etapa 02."""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter

from .exploracao import DENSIDADE, FASES, MINIMO_IC, POPULACAO, SEM_DADO

AZUL = "#175985"
VERDE = "#187568"
TEXTO = "#203042"
GRADE = "#dce4ea"


def percentual(valor, casas=0):
    return f"{valor:.{casas}%}".replace(".", ",")


def inteiro(valor):
    return f"{valor:,}".replace(",", ".")


def estilizar(figura, eixo, titulo, subtitulo):
    altura = figura.get_figheight()
    figura.suptitle(titulo, x=0.04, y=1 - 0.14 / altura, ha="left",
                   fontsize=16, weight="bold", color=TEXTO)
    figura.text(0.04, 1 - 0.50 / altura, subtitulo, color=TEXTO, fontsize=9)
    eixo.spines[["top", "right", "left"]].set_visible(False)
    eixo.spines["bottom"].set_color(GRADE)
    eixo.tick_params(axis="both", colors=TEXTO, length=0)


def salvar(figura, pasta, nome):
    pasta.mkdir(parents=True, exist_ok=True)
    figura.savefig(pasta / f"{nome}.png", dpi=250, facecolor="white")
    plt.close(figura)


def pontos(pasta, nome, titulo, subtitulo, linhas, rotulo, taxa_global, margem):
    linhas = [linha for linha in linhas if not linha["grupo_pequeno"]]
    if not linhas:
        return
    altura = max(4.1, len(linhas) * 0.39 + 1.5)
    figura, eixo = plt.subplots(figsize=(10.6, altura))
    estilizar(figura, eixo, titulo, subtitulo)
    figura.subplots_adjust(left=margem, right=0.94, top=1 - 0.81 / altura,
                           bottom=max(0.11, 0.55 / altura))
    eixo.set_axisbelow(True)
    eixo.xaxis.grid(color=GRADE)
    eixo.xaxis.set_major_formatter(FuncFormatter(lambda x, _: percentual(x)))
    eixo.axvline(taxa_global, color="#657584", lw=1, ls="--")
    eixo.set_xlabel("Proporção de acidentes graves", color=TEXTO, labelpad=8)
    eixo.set_yticks(range(len(linhas)), [rotulo(linha) for linha in linhas], fontsize=9)
    eixo.invert_yaxis()
    maior = max(linha["ic95_superior"] for linha in linhas)
    eixo.set_xlim(0, min(1, max(maior, taxa_global) * 1.26 + 0.08))
    for posicao, linha in enumerate(linhas):
        proporcao = linha["proporcao_grave"]
        erro = [[proporcao - linha["ic95_inferior"]], [linha["ic95_superior"] - proporcao]]
        eixo.errorbar(proporcao, posicao, xerr=erro, fmt="o", color=AZUL, capsize=3, ms=5)
        eixo.annotate(f"{percentual(proporcao, 1)}  ({inteiro(linha['graves'])}/{inteiro(linha['ocorrencias'])})",
                      (linha["ic95_superior"], posicao), xytext=(7, 0), textcoords="offset points",
                      va="center", fontsize=8, color=TEXTO,
                      bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.6})
    salvar(figura, pasta, nome)


def grafico_uso(pasta, linhas):
    faixas = [faixa for faixa in (*DENSIDADE, SEM_DADO)
              if any(linha["faixa_densidade"] == faixa for linha in linhas)]
    uso = {(linha["faixa_densidade"], linha["uso_solo_prf"]): linha for linha in linhas}
    figura, eixo = plt.subplots(figsize=(10.6, 4.5))
    estilizar(figura, eixo, "Uso do solo no local da ocorrência por densidade municipal",
               "Percentual dentro de cada faixa de densidade de 2022 · Paraná, 2023–2025")
    figura.subplots_adjust(left=0.09, right=0.97, top=0.80, bottom=0.26)
    acumulado = np.zeros(len(faixas))
    for categoria, cor in (("Urbano", AZUL), ("Rural", VERDE), (SEM_DADO, "#657584")):
        valores = [uso.get((faixa, categoria), {}).get("proporcao_na_faixa", 0) for faixa in faixas]
        if not any(valores):
            continue
        eixo.bar(faixas, valores, bottom=acumulado, label=categoria, color=cor, width=0.67)
        for i, valor in enumerate(valores):
            if valor >= 0.09:
                eixo.text(i, acumulado[i] + valor / 2, percentual(valor, 1),
                          ha="center", va="center", color="white", fontsize=9)
        acumulado += valores
    eixo.set_xticks(range(len(faixas)), [
        f"{faixa}\nn = {inteiro(next(l['denominador_na_faixa'] for l in linhas if l['faixa_densidade'] == faixa))}"
        for faixa in faixas
    ])
    eixo.set_ylim(0, 1)
    eixo.yaxis.set_major_formatter(FuncFormatter(lambda x, _: percentual(x)))
    eixo.set_xlabel("Densidade de 2022 (hab./km²)", color=TEXTO, labelpad=10)
    figura.legend(loc="lower center", bbox_to_anchor=(0.53, 0.03), ncols=3, frameon=False)
    salvar(figura, pasta, "uso_solo_densidade")


def grafico_tipo(pasta, linhas):
    totais = {}
    for linha in linhas:
        tipo = linha["tipo_acidente"]
        totais[tipo] = totais.get(tipo, 0) + linha["ocorrencias"]
    tipos = sorted(totais, key=totais.get, reverse=True)[:6]
    celulas = {(linha["tipo_acidente"], linha["faixa_densidade"]): linha for linha in linhas}
    dados = np.full((len(tipos), len(DENSIDADE)), np.nan)
    figura, eixo = plt.subplots(figsize=(11.3, 5.35))
    estilizar(figura, eixo, "Gravidade por tipo de acidente e densidade municipal",
               f"Seis tipos mais frequentes · Paraná, 2023–2025 · Traço indica grupo com menos de {MINIMO_IC} ocorrências")
    figura.subplots_adjust(left=0.29, right=0.95, top=0.81, bottom=0.16)
    for i, tipo in enumerate(tipos):
        for j, faixa in enumerate(DENSIDADE):
            linha = celulas.get((tipo, faixa))
            if linha and not linha["grupo_pequeno"]:
                valor = linha["proporcao_grave"]
                dados[i, j] = valor
                eixo.text(j, i, f"{percentual(valor, 1)}\nn = {inteiro(linha['ocorrencias'])}",
                          ha="center", va="center", fontsize=9, color="white" if valor >= 0.32 else TEXTO)
            else:
                eixo.text(j, i, "–", ha="center", va="center", color=TEXTO)
    mapa = eixo.imshow(dados, cmap="Blues", vmin=0, vmax=max(0.5, np.nanmax(dados)), aspect="auto")
    eixo.set_xticks(range(len(DENSIDADE)), DENSIDADE)
    eixo.set_yticks(range(len(tipos)), tipos, fontsize=9)
    eixo.set_xlabel("Densidade de 2022 (hab./km²)", color=TEXTO, labelpad=10)
    escala = figura.colorbar(mapa, ax=eixo, fraction=0.045, pad=0.035,
                             format=FuncFormatter(lambda x, _: percentual(x)))
    escala.set_label("Acidentes graves", color=TEXTO)
    salvar(figura, pasta, "tipo_acidente_contexto_gravidade")


def gerar_graficos(tabelas, pasta: Path):
    densidades = tabelas["densidade_gravidade"]
    taxa_global = sum(g["graves"] for g in densidades) / sum(g["ocorrencias"] for g in densidades)
    subtitulo = "Paraná, 2023–2025 · IC de 95% de Wilson · Linha tracejada representa o total da base"
    for nome, titulo, coluna, ordem in (
        ("densidade_gravidade", "Gravidade por densidade demográfica municipal (hab./km²)",
         "faixa_densidade", (*DENSIDADE, SEM_DADO)),
        ("populacao_gravidade", "Gravidade por faixa populacional do município",
         "faixa_populacao", (*POPULACAO, SEM_DADO)),
    ):
        linhas = sorted(tabelas[nome], key=lambda linha: ordem.index(linha[coluna]))
        pontos(pasta, nome, titulo, subtitulo, linhas, lambda linha: linha[coluna], taxa_global, 0.14)

    nome = "municipio_gravidade"
    pontos(pasta, nome, "Gravidade nos municípios com mais acidentes", subtitulo,
           tabelas[nome][:12], lambda linha: linha["municipio"], taxa_global, 0.25)
    nome = "pista_fase_gravidade"
    linhas = sorted(tabelas[nome], key=lambda linha: (linha["tipo_pista"], FASES.index(linha["fase_dia"])))
    pontos(pasta, nome, "Gravidade por tipo de pista e fase do dia", subtitulo, linhas,
           lambda linha: f"{linha['tipo_pista']} · {linha['fase_dia']}", taxa_global, 0.25)
    nome = "rodovia_municipio_gravidade"
    linhas = [linha for linha in tabelas[nome] if linha["rodovia"] != SEM_DADO][:12]
    pontos(pasta, nome, "Gravidade nos pares rodovia–município com mais acidentes", subtitulo,
           linhas, lambda linha: f"{linha['rodovia']} · {linha['municipio']}", taxa_global, 0.30)
    grafico_uso(pasta, tabelas["uso_solo_densidade"])
    grafico_tipo(pasta, tabelas["tipo_acidente_contexto_gravidade"])
