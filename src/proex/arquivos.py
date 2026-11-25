"""Caminhos e persistência para as etapas do pipeline."""

import csv
import json
import os
from hashlib import file_digest
from pathlib import Path
from tempfile import NamedTemporaryFile

RAIZ = Path(__file__).resolve().parents[2]
BRUTOS_PRF = RAIZ / "work"
EXTERNOS = RAIZ / "dados" / "externos" / "ibge"
PROCESSADOS = RAIZ / "dados" / "processados"
RESULTADOS = RAIZ / "resultados" / "etapa02"


def hash_arquivo(caminho):
    with caminho.open("rb") as arquivo:
        return file_digest(arquivo, "sha256").hexdigest()


def ler_json(caminho):
    return json.loads(caminho.read_bytes())


def salvar_bytes(caminho, conteudo):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=caminho.parent, delete=False) as temporario:
        nome = Path(temporario.name)
        try:
            temporario.write(conteudo)
            temporario.close()
            os.replace(nome, caminho)
        finally:
            nome.unlink(missing_ok=True)


def salvar_json(caminho, dados):
    salvar_bytes(caminho, (json.dumps(dados, ensure_ascii=False, indent=2) + "\n").encode())


def salvar_csv(caminho, campos, linhas):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        dir=caminho.parent, mode="w", encoding="utf-8-sig", newline="", delete=False
    ) as temporario:
        nome = Path(temporario.name)
        try:
            escritor = csv.DictWriter(temporario, fieldnames=campos, delimiter=";")
            escritor.writeheader()
            escritor.writerows(linhas)
            temporario.close()
            os.replace(nome, caminho)
        finally:
            nome.unlink(missing_ok=True)


def ler_csv(caminho):
    with caminho.open(encoding="utf-8-sig", newline="") as arquivo:
        return list(csv.DictReader(arquivo, delimiter=";"))
