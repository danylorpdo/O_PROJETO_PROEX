"""Conferência de coordenadas com a malha municipal de 2022."""

import shapefile
from shapely import STRtree
from shapely.geometry import Point, shape


class MalhaMunicipal:
    def __init__(self, caminho, municipios):
        self.codigos = []
        geometrias = []
        with shapefile.Reader(str(caminho), encoding="utf-8") as malha:
            for item in malha.iterShapeRecords():
                codigo = item.record["CD_MUN"]
                geometria = shape(item.shape.__geo_interface__)
                if item.record["SIGLA_UF"] != "PR" or not geometria.is_valid or geometria.is_empty:
                    raise ValueError(f"Geometria inválida do município {codigo}.")
                self.codigos.append(codigo)
                geometrias.append(geometria)
        if len(self.codigos) != len(municipios) or set(self.codigos) != set(municipios):
            raise ValueError("A malha e o cadastro de municípios divergem em cobertura ou unicidade.")
        self.indice = STRtree(geometrias)

    def localizar(self, latitude, longitude):
        if latitude in (None, "") or longitude in (None, ""):
            return None
        ponto = Point(float(longitude), float(latitude))
        return tuple(sorted(self.codigos[i] for i in self.indice.query(ponto, predicate="covered_by")))


def conferir_coordenadas(codigo, codigos_geograficos):
    if codigos_geograficos is None:
        return "coordenada_ausente"
    if not codigos_geograficos:
        return "fora_da_malha_pr_2022"
    if len(codigos_geograficos) > 1:
        return "sobre_limite_municipal"
    if codigo is None:
        return "sem_codigo_por_nome"
    return "confere" if codigo in codigos_geograficos else "diverge"
