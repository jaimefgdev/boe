"""Respuestas reales de la API guardadas en tests/datos, servidas sin red."""

from __future__ import annotations

import os
import urllib.parse
from pathlib import Path

import pytest

from boe import BOE

DATOS = Path(__file__).parent / "datos"

# Ruta de la API -> fichero de tests/datos
RUTAS = {
    "boe/sumario/20261008": "sumario_boe_20261008.json",
    "borme/sumario/20261008": "sumario_borme_20261008.json",
    "boe/sumario/20261004": "sumario_boe_domingo.json",
    "boe/sumario/20200314": "sumario_boe_20200314.json",
    "legislacion-consolidada": "legislacion_busqueda.json",
    "legislacion-consolidada/id/BOE-A-2015-10565/metadatos": "metadatos_BOE-A-2015-10565.json",
    "legislacion-consolidada/id/BOE-A-2015-10565/analisis": "analisis_BOE-A-2015-10565.json",
    "legislacion-consolidada/id/BOE-A-2015-10565/texto/indice": "indice_BOE-A-2015-10565.json",
    "legislacion-consolidada/id/BOE-A-2015-10565/texto/bloque/a30": "bloque_BOE-A-2015-10565_a30.xml",
    "legislacion-consolidada/id/BOE-A-1900-1/metadatos": "no_existe.json",
}
for tabla in ("materias", "ambitos", "estados-consolidacion", "departamentos", "rangos"):
    RUTAS[f"datos-auxiliares/{tabla}"] = f"aux_{tabla}.json"
for tabla in ("relaciones-anteriores", "relaciones-posteriores"):
    RUTAS[f"datos-auxiliares/{tabla}"] = f"aux_{tabla}.json"


class TransporteFalso:
    """Sirve los ficheros de tests/datos y guarda las URL pedidas."""

    def __init__(self) -> None:
        self.peticiones: list[tuple[str, str]] = []

    def __call__(self, url: str, accept: str) -> tuple[int, bytes]:
        self.peticiones.append((url, accept))
        ruta = urllib.parse.urlsplit(url).path.removeprefix("/datosabiertos/api/")
        fichero = RUTAS.get(ruta)
        if fichero is None:
            return 500, b""
        cuerpo = (DATOS / fichero).read_bytes()
        estado = 404 if b"<code>404</code>" in cuerpo else 200
        return estado, cuerpo

    @property
    def ultima(self) -> dict[str, list[str]]:
        """Parámetros de la última petición."""
        return urllib.parse.parse_qs(urllib.parse.urlsplit(self.peticiones[-1][0]).query)


@pytest.fixture
def transporte() -> TransporteFalso:
    return TransporteFalso()


@pytest.fixture
def boe(transporte: TransporteFalso) -> BOE:
    return BOE(transporte=transporte)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.environ.get("BOE_RED") == "1":
        return
    saltar = pytest.mark.skip(reason="prueba con red: ejecutar con BOE_RED=1")
    for item in items:
        if "red" in item.keywords:
            item.add_marker(saltar)
