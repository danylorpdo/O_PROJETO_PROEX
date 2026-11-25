"""Leitura dos ZIPs da PRF e validação da base por ocorrência."""

import csv
import io
import math
import re
import zipfile
from collections import Counter
from datetime import date, time
from decimal import Decimal

from .arquivos import hash_arquivo, ler_json, salvar_csv, salvar_json

ANOS = (2023, 2024, 2025)
DIAS = ("segunda-feira", "terça-feira", "quarta-feira", "quinta-feira",
        "sexta-feira", "sábado", "domingo")
CONTAGENS = ("pessoas", "mortos", "feridos_leves", "feridos_graves", "ilesos",
             "ignorados", "feridos", "veiculos")
DOMINIOS = {
    "dia_semana": set(DIAS),
    "fase_dia": {"Amanhecer", "Anoitecer", "Plena Noite", "Pleno dia"},
    "tipo_pista": {"Dupla", "Múltipla", "Simples"},
    "uso_solo": {"Não", "Sim"},
    "sentido_via": {"Crescente", "Decrescente", "Não Informado"},
    "condicao_metereologica": {
        "Chuva", "Céu Claro", "Garoa/Chuvisco", "Ignorado",
        "Nevoeiro/Neblina", "Nublado", "Sol", "Vento",
    },
    "classificacao_acidente": {
        "Com Vítimas Fatais", "Com Vítimas Feridas", "Sem Vítimas", "Ignorado",
    },
    "tipo_acidente": {
        "Atropelamento de Animal", "Atropelamento de Pedestre", "Capotamento",
        "Colisão com objeto", "Colisão frontal", "Colisão lateral mesmo sentido",
        "Colisão lateral sentido oposto", "Colisão transversal", "Colisão traseira",
        "Derramamento de carga", "Engavetamento", "Eventos atípicos", "Incêndio",
        "Queda de ocupante de veículo", "Saída de leito carroçável",
        "Sinistro pessoal de trânsito", "Tombamento",
    },
}
TRACADOS = {
    "Aclive", "Curva", "Declive", "Desvio Temporário", "Em Obras",
    "Interseção de Vias", "Ponte", "Reta", "Retorno Regulamentado",
    "Rotatória", "Túnel", "Viaduto",
}
TEXTO = ("uf", "municipio", "causa_acidente", "tracado_via", "regional", "delegacia", "uop")
CAMPOS_ORIGINAIS = (
    "id", "data_inversa", "dia_semana", "horario", "uf", "br", "km", "municipio",
    "causa_acidente", "tipo_acidente", "classificacao_acidente", "fase_dia",
    "sentido_via", "condicao_metereologica", "tipo_pista", "tracado_via", "uso_solo",
    *CONTAGENS, "latitude", "longitude", "regional", "delegacia", "uop",
)
CAMPOS = ("ano", "mes", *CAMPOS_ORIGINAIS, "gravidade")
PREDITORES_PRF = (
    "ano", "mes", "dia_semana", "horario", "uf", "br", "km", "latitude", "longitude",
    "fase_dia", "sentido_via", "condicao_metereologica", "tipo_pista", "tracado_via",
    "uso_solo",
)


def ler_prf(caminho):
    """Lê as ocorrências originais, preservando acentos e campos entre aspas."""
    with zipfile.ZipFile(caminho) as zip_prf:
        membros = [nome for nome in zip_prf.namelist() if nome.lower().endswith(".csv")]
        if len(membros) != 1:
            raise ValueError(f"{caminho.name}: esperado exatamente um CSV.")
        with zip_prf.open(membros[0]) as conteudo:
            leitor = csv.DictReader(io.TextIOWrapper(conteudo, encoding="latin-1", newline=""),
                                     delimiter=";", strict=True)
            cabecalho = leitor.fieldnames or ()
            if len(cabecalho) != len(CAMPOS_ORIGINAIS) or set(cabecalho) != set(CAMPOS_ORIGINAIS):
                raise ValueError(f"{caminho.name}: esquema original divergente.")
            for linha in leitor:
                if None in linha or None in linha.values():
                    raise ValueError(f"{caminho.name}, linha {leitor.line_num}: colunas incompletas.")
                yield linha


def inteiro(valor, campo):
    if not re.fullmatch(r"[0-9]+", valor):
        raise ValueError(f"{campo} inválido: {valor!r}")
    return int(valor)


def validar_id(valor):
    if not re.fullmatch(r"[0-9]+(?:[eE]\+[0-9]{1,3})?", valor) or Decimal(valor) <= 0:
        raise ValueError(f"Identificador inválido: {valor!r}")


def decimal(valor, campo, minimo, maximo):
    if valor.casefold() in {"", "null", "(null)"}:
        return None
    numero = float(valor.replace(",", "."))
    if not math.isfinite(numero) or not minimo <= numero <= maximo:
        raise ValueError(f"{campo} fora do domínio: {valor!r}")
    return numero


def definir_gravidade(mortos, feridos_graves):
    if any(type(n) is not int or n < 0 for n in (mortos, feridos_graves)):
        raise ValueError("Contagens do alvo devem ser inteiros não negativos.")
    return "grave" if mortos or feridos_graves else "nao_grave"


def preparar_linha(linha, ano):
    linha = {campo: linha[campo].strip() for campo in CAMPOS_ORIGINAIS}
    if linha["uf"] != "PR":
        raise ValueError("UF fora do recorte da preparação.")
    dia = date.fromisoformat(linha["data_inversa"])
    horario = time.fromisoformat(linha["horario"])
    if (dia.year != ano or DIAS[dia.weekday()] != linha["dia_semana"]
            or dia.isoformat() != linha["data_inversa"]):
        raise ValueError("Data, ano ou dia da semana inconsistentes.")
    if horario.tzinfo is not None or horario.isoformat(timespec="seconds") != linha["horario"]:
        raise ValueError("Horário fora do formato HH:MM:SS.")
    for campo, valores in DOMINIOS.items():
        if linha[campo] not in valores:
            raise ValueError(f"Categoria inválida em {campo}: {linha[campo]!r}")
    if not set(linha["tracado_via"].split(";")).issubset(TRACADOS):
        raise ValueError(f"Categoria de traçado inválida: {linha['tracado_via']!r}")
    for campo in TEXTO:
        if any(not caractere.isprintable() for caractere in linha[campo]):
            raise ValueError(f"Caractere inválido em {campo}.")
        if linha[campo].casefold() in {"", "null", "(null)"}:
            linha[campo] = None
    if not linha["causa_acidente"]:
        raise ValueError("Causa principal ausente.")
    validar_id(linha["id"])
    linha["br"] = inteiro(linha["br"], "br") if linha["br"] else None
    if linha["br"] is not None and linha["br"] > 999:
        raise ValueError("BR fora do domínio.")
    linha["km"] = decimal(linha["km"], "km", 0, math.inf)
    linha["latitude"] = decimal(linha["latitude"], "latitude", -90, 90)
    linha["longitude"] = decimal(linha["longitude"], "longitude", -180, 180)
    for campo in CONTAGENS:
        linha[campo] = inteiro(linha[campo], campo)
    return {
        "ano": ano, "mes": dia.month, **linha,
        "gravidade": definir_gravidade(linha["mortos"], linha["feridos_graves"]),
    }


def preparar_prf(brutos, processados, auditoria):
    anterior = ler_json(brutos / "resultados" / "resumo.json")
    referencia = {linha["ano"]: linha for linha in anterior["auditoria"]}
    registros, resumo, erros = [], [], []
    ids = set()

    for ano in ANOS:
        caminho = brutos / f"datatran{ano}.zip"
        esperado = referencia[ano]
        contagem = Counter()
        for original in ler_prf(caminho):
            contagem["brasil"] += 1
            if original["uf"].strip() != "PR":
                continue
            contagem["parana_bruto"] += 1
            try:
                linha = preparar_linha(original, ano)
                identificador = Decimal(linha["id"])
                if identificador in ids:
                    contagem["duplicados"] += 1
                    raise ValueError("Identificador de ocorrência repetido.")
                ids.add(identificador)
            except ValueError as erro:
                erros.append({"ano": ano, "id": original["id"], "erro": str(erro)})
                continue
            contagem["analisados"] += 1
            contagem["graves"] += linha["gravidade"] == "grave"
            contagem["id_notacao_cientifica"] += "e" in linha["id"].lower()
            contagem["br_zero_original"] += original["br"].strip() == "0"
            contagem["km_zero_original"] += linha["km"] == 0
            contagem["coordenadas_incompletas"] += None in (linha["latitude"], linha["longitude"])
            contagem["classificacao_fatal_divergente"] += (
                (linha["classificacao_acidente"] == "Com Vítimas Fatais") != bool(linha["mortos"])
            )
            registros.append(linha)
        atual = {campo: contagem[campo] for campo in (
            "brasil", "parana_bruto", "analisados", "graves", "duplicados",
            "id_notacao_cientifica", "br_zero_original", "km_zero_original",
            "coordenadas_incompletas", "classificacao_fatal_divergente",
        )}
        atual.update(sha256=hash_arquivo(caminho), nao_graves=contagem["analisados"] - contagem["graves"])
        diferencas = {campo: {"esperado": esperado[campo], "observado": atual[campo]}
                      for campo in ("brasil", "parana_bruto", "analisados", "graves", "sha256")
                      if esperado[campo] != atual[campo]}
        resumo.append({"ano": ano, "arquivo": f"work/{caminho.name}", "url": esperado["url"],
                       **atual, "diferencas": diferencas})

    totais = {"n": len(registros), "graves": sum(linha["gravidade"] == "grave" for linha in registros)}
    totais["nao_graves"] = totais["n"] - totais["graves"]
    esperados = {"n": anterior["n"], "graves": anterior["graves"],
                 "nao_graves": anterior["n"] - anterior["graves"]}
    reconciliado = totais == esperados and not erros and not any(linha["diferencas"] for linha in resumo)
    relatorio = {"anos": resumo, "totais": totais, "esperados": esperados,
                 "reconciliado": reconciliado, "erros_validacao": erros}
    if reconciliado:
        preparada = processados / "prf_preparada.csv"
        salvar_csv(preparada, CAMPOS, registros)
        relatorio["sha256_base_preparada"] = hash_arquivo(preparada)
    salvar_json(auditoria / "prf.json", relatorio)
    salvar_csv(auditoria / "prf.csv", tuple(campo for campo in resumo[0] if campo != "diferencas"),
               ({k: v for k, v in linha.items() if k != "diferencas"} for linha in resumo))
    if not reconciliado:
        raise ValueError("PRF divergente da auditoria anterior ou com linha inválida. Consulte prf.json.")
    return registros
