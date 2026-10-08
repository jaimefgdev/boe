"""Cliente de la API de datos abiertos del BOE: sumarios del BOE y del BORME y legislación consolidada."""

__version__ = "0.1.1"

from .cliente import BOE, ErrorBOE, NoEncontrado
from .modelos import (
    Analisis,
    Bloque,
    Codigo,
    Disposicion,
    EntradaIndice,
    Norma,
    Referencia,
    Sumario,
    Version,
)

__all__ = [
    "BOE",
    "Analisis",
    "Bloque",
    "Codigo",
    "Disposicion",
    "EntradaIndice",
    "ErrorBOE",
    "NoEncontrado",
    "Norma",
    "Referencia",
    "Sumario",
    "Version",
    "__version__",
]
