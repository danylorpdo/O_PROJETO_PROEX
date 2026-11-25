"""Comandos independentes para a reprodução da Etapa 02."""

import argparse
import csv
from zipfile import BadZipFile

from src.proex.arquivos import (
    BRUTOS_PRF, EXTERNOS, PROCESSADOS, RAIZ, RESULTADOS, hash_arquivo, ler_csv, ler_json,
)
from src.proex.ibge import coletar_ibge
from src.proex.prf import preparar_linha, preparar_prf

AUDITORIA = RESULTADOS / "auditoria"
ALIASES = RAIZ / "dados" / "referencias" / "aliases_municipais.csv"


def conferir_base(nome, auditoria, chave):
    caminho = PROCESSADOS / nome
    relatorio = ler_json(AUDITORIA / auditoria)
    if not relatorio.get(chave) or hash_arquivo(caminho) != relatorio[chave]:
        raise ValueError(f"Base divergente da auditoria: {nome}. Execute novamente a etapa que a gera.")
    return ler_csv(caminho)


def preparar():
    registros = preparar_prf(BRUTOS_PRF, PROCESSADOS, AUDITORIA)
    print(f"PRF preparada e reconciliada: {len(registros)} ocorrências.", flush=True)
    return registros


def integrar(registros):
    from src.proex.integracao import integrar_prf

    integrada = integrar_prf(registros, EXTERNOS, ALIASES, PROCESSADOS, AUDITORIA)
    print(f"Integração auditada: {sum(bool(linha['codigo_ibge']) for linha in integrada)}/{len(integrada)} "
          "ocorrências com vínculo municipal.", flush=True)
    return integrada


def explorar(registros):
    from src.proex.exploracao import gerar_resultados
    from src.proex.graficos import gerar_graficos

    tabelas = gerar_resultados(registros, RESULTADOS / "tabelas")
    gerar_graficos(tabelas, RESULTADOS / "graficos")
    print(f"Tabelas e gráficos em {RESULTADOS.relative_to(RAIZ)}.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comando", choices=("coletar", "preparar", "integrar", "explorar", "executar"),
                        help="executar roda preparação, integração e análise usando as fontes locais")
    comando = parser.parse_args().comando
    try:
        if comando == "coletar":
            manifesto = coletar_ibge(EXTERNOS)
            print(f"{len(manifesto)} fontes oficiais verificadas em {EXTERNOS.relative_to(RAIZ)}.")
        elif comando == "preparar":
            preparar()
        elif comando == "integrar":
            registros = conferir_base("prf_preparada.csv", "prf.json", "sha256_base_preparada")
            integrar([preparar_linha(linha, int(linha["ano"])) for linha in registros])
        elif comando == "explorar":
            explorar(conferir_base("prf_ibge_integrada.csv", "integracao.json", "sha256_base_integrada"))
        else:
            explorar(integrar(preparar()))
    except (OSError, ValueError, KeyError, BadZipFile, csv.Error) as erro:
        parser.exit(1, f"Etapa 02 interrompida: {erro}\n")


if __name__ == "__main__":
    main()
