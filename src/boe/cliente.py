"""Cliente de la API de datos abiertos del BOE (https://www.boe.es/datosabiertos/api/api.php)."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime
from typing import Any
from xml.etree import ElementTree as ET

from . import __version__
from .modelos import (
    Analisis,
    Bloque,
    EntradaIndice,
    Norma,
    Sumario,
    analisis_desde_json,
    bloque_desde_xml,
    indice_desde_json,
    norma_desde_json,
    sumario_desde_json,
)

URL_BASE = "https://www.boe.es/datosabiertos/api"

# Recibe la URL completa y la cabecera Accept; devuelve (código HTTP, cuerpo).
Transporte = Callable[[str, str], tuple[int, bytes]]


class ErrorBOE(RuntimeError):
    """La API del BOE devolvió un error o una respuesta que no se pudo leer."""

    def __init__(self, mensaje: str, codigo: int | None = None) -> None:
        super().__init__(mensaje)
        self.codigo = codigo


class NoEncontrado(ErrorBOE):
    """La información pedida no existe (por ejemplo, un día sin BOE o un identificador erróneo)."""


def _transporte_urllib(timeout: float, user_agent: str) -> Transporte:
    def transporte(url: str, accept: str) -> tuple[int, bytes]:
        peticion = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": user_agent})
        try:
            with urllib.request.urlopen(peticion, timeout=timeout) as respuesta:
                return respuesta.status, respuesta.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    return transporte


def _aaaammdd(valor: date | str) -> str:
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%Y%m%d")
    return valor.replace("-", "")


def _valor_busqueda(valor: str) -> str:
    """Las frases de varias palabras van entre comillas en la sintaxis de búsqueda de la API."""
    valor = valor.replace('"', "")
    return f'"{valor}"' if " " in valor else valor


class BOE:
    """
    Cliente de la API de datos abiertos del Boletín Oficial del Estado.

    >>> from boe import BOE
    >>> boe = BOE()
    >>> sumario = boe.sumario("2026-10-08")          # doctest: +SKIP
    >>> ley = boe.norma("BOE-A-2015-10565")           # doctest: +SKIP
    >>> print(boe.bloque("BOE-A-2015-10565", "a30").texto)  # doctest: +SKIP
    """

    def __init__(
        self,
        *,
        timeout: float = 30.0,
        user_agent: str | None = None,
        url_base: str = URL_BASE,
        transporte: Transporte | None = None,
    ) -> None:
        self.url_base = url_base.rstrip("/")
        self._transporte = transporte or _transporte_urllib(
            timeout, user_agent or f"boe-python/{__version__} (+https://github.com/jaimefgdev/boe)"
        )

    # --- Peticiones ---

    def _pedir(self, ruta: str, accept: str, parametros: dict[str, Any] | None = None) -> bytes:
        url = f"{self.url_base}/{ruta.lstrip('/')}"
        if parametros:
            url += "?" + urllib.parse.urlencode({k: v for k, v in parametros.items() if v is not None})
        estado, cuerpo = self._transporte(url, accept)
        if estado == 200:
            return cuerpo
        mensaje = _mensaje_error(cuerpo) or f"Error HTTP {estado}"
        if estado == 404:
            raise NoEncontrado(mensaje, estado)
        raise ErrorBOE(mensaje, estado)

    def _json(self, ruta: str, parametros: dict[str, Any] | None = None) -> Any:
        cuerpo = self._pedir(ruta, "application/json", parametros)
        try:
            respuesta = json.loads(cuerpo)
        except ValueError as e:
            raise ErrorBOE("La respuesta de la API no es JSON válido") from e
        estado = str(respuesta.get("status", {}).get("code", "200"))
        if estado != "200":
            texto = respuesta.get("status", {}).get("text", "")
            if estado == "404":
                raise NoEncontrado(texto, 404)
            raise ErrorBOE(texto, int(estado) if estado.isdigit() else None)
        return respuesta.get("data")

    def _xml(self, ruta: str) -> ET.Element:
        cuerpo = self._pedir(ruta, "application/xml")
        try:
            return ET.fromstring(cuerpo)
        except ET.ParseError as e:
            raise ErrorBOE("La respuesta de la API no es XML válido") from e

    # --- Sumarios ---

    def sumario(self, fecha: date | str) -> Sumario:
        """
        Sumario del BOE de un día (``date`` o texto ``AAAA-MM-DD`` / ``AAAAMMDD``).

        Raises:
            NoEncontrado: Si ese día no se publicó el BOE (por ejemplo, un domingo).
        """
        return sumario_desde_json(self._json(f"boe/sumario/{_aaaammdd(fecha)}"))

    def sumario_borme(self, fecha: date | str) -> Sumario:
        """
        Sumario del BORME (Boletín Oficial del Registro Mercantil) de un día.

        Raises:
            NoEncontrado: Si ese día no se publicó el BORME.
        """
        return sumario_desde_json(self._json(f"borme/sumario/{_aaaammdd(fecha)}"))

    # --- Legislación consolidada ---

    def buscar(
        self,
        texto: str | None = None,
        *,
        titulo: str | None = None,
        rango: str | None = None,
        departamento: str | None = None,
        ambito: str | None = None,
        materia: str | None = None,
        numero_oficial: str | None = None,
        vigentes: bool = False,
        publicadas_desde: date | str | None = None,
        publicadas_hasta: date | str | None = None,
        actualizadas_desde: date | str | None = None,
        actualizadas_hasta: date | str | None = None,
        orden: str | None = "-fecha_publicacion",
        limite: int = 50,
        desplazamiento: int = 0,
        consulta: str | None = None,
    ) -> list[Norma]:
        """
        Busca normas en la colección de legislación consolidada.

        Args:
            texto: Palabras o frase en el texto completo de la norma.
            titulo: Palabras o frase en el título.
            rango, departamento, ambito, materia: Códigos de las tablas auxiliares
                (por ejemplo ``rango="1300"`` para leyes; ver :meth:`rangos`).
            numero_oficial: Número oficial, como ``"39/2015"``.
            vigentes: Solo normas con la vigencia no agotada.
            publicadas_desde, publicadas_hasta: Rango de fechas de publicación.
            actualizadas_desde, actualizadas_hasta: Rango de fechas de la última actualización.
            orden: Campo de ordenación; con ``-`` delante, descendente. ``None`` para el orden de la API.
            limite: Número máximo de resultados (-1 para todos).
            desplazamiento: Primer resultado a devolver, para paginar.
            consulta: Condición en la sintaxis propia de la API (``campo:valor`` con ``and``/``or``),
                que se combina con el resto de filtros.
        """
        condiciones = []
        for campo, valor in (
            ("texto", texto),
            ("titulo", titulo),
            ("rango@codigo", rango),
            ("departamento@codigo", departamento),
            ("ambito@codigo", ambito),
            ("materia@codigo", materia),
            ("numero_oficial", numero_oficial),
        ):
            if valor:
                condiciones.append(f"{campo}:{_valor_busqueda(valor)}")
        if vigentes:
            condiciones.append("vigencia_agotada:N")
        if consulta:
            condiciones.append(f"({consulta})")

        query: dict[str, Any] = {}
        if condiciones:
            query["query_string"] = {"query": " and ".join(condiciones)}
        rango_fechas = {}
        if publicadas_desde or publicadas_hasta:
            rango_fechas["fecha_publicacion"] = _rango(publicadas_desde, publicadas_hasta)
        if rango_fechas:
            query["range"] = rango_fechas

        cuerpo: dict[str, Any] = {}
        if query:
            cuerpo["query"] = query
        if orden:
            campo_orden = orden.lstrip("-")
            cuerpo["sort"] = [{campo_orden: "desc" if orden.startswith("-") else "asc"}]

        parametros: dict[str, Any] = {
            "from": _aaaammdd(actualizadas_desde) if actualizadas_desde else None,
            "to": _aaaammdd(actualizadas_hasta) if actualizadas_hasta else None,
            "query": json.dumps(cuerpo, ensure_ascii=False) if cuerpo else None,
            "offset": desplazamiento or None,
            "limit": limite,
        }
        return [norma_desde_json(n) for n in self._json_lista("legislacion-consolidada", parametros)]

    def norma(self, identificador: str) -> Norma:
        """
        Ficha de una norma consolidada (por ejemplo ``"BOE-A-2015-10565"``).

        Raises:
            NoEncontrado: Si no existe en la colección de legislación consolidada.
        """
        datos = self._json_lista(f"legislacion-consolidada/id/{identificador}/metadatos")
        if not datos:
            raise NoEncontrado(f"No existe la norma {identificador}", 404)
        return norma_desde_json(datos[0])

    def analisis(self, identificador: str) -> Analisis:
        """Materias, notas y relaciones (deroga, modifica...) de una norma consolidada."""
        return analisis_desde_json(self._json(f"legislacion-consolidada/id/{identificador}/analisis"))

    def indice(self, identificador: str) -> list[EntradaIndice]:
        """Bloques (preámbulo, títulos, artículos, disposiciones...) de una norma consolidada."""
        return indice_desde_json(self._json(f"legislacion-consolidada/id/{identificador}/texto/indice"))

    def bloque(self, identificador: str, id_bloque: str) -> Bloque:
        """
        Texto consolidado de un bloque, con todas sus versiones.

        Los identificadores de bloque salen de :meth:`indice`; los artículos son ``a1``, ``a2``...

        >>> print(BOE().bloque("BOE-A-2015-10565", "a30").texto)  # doctest: +SKIP
        """
        return bloque_desde_xml(self._xml(f"legislacion-consolidada/id/{identificador}/texto/bloque/{id_bloque}"))

    def articulo(self, identificador: str, numero: int | str) -> Bloque:
        """Atajo de :meth:`bloque` para artículos: ``articulo("BOE-A-2015-10565", 30)``."""
        return self.bloque(identificador, f"a{numero}")

    def texto_xml(self, identificador: str) -> str:
        """Texto consolidado completo de una norma, en el XML original de la API."""
        return ET.tostring(self._xml(f"legislacion-consolidada/id/{identificador}/texto"), encoding="unicode")

    # --- Tablas auxiliares ---

    def materias(self) -> dict[str, str]:
        """Códigos y nombres de las materias (vocabulario controlado para buscar por tema)."""
        return self._tabla("materias")

    def ambitos(self) -> dict[str, str]:
        return self._tabla("ambitos")

    def estados_consolidacion(self) -> dict[str, str]:
        return self._tabla("estados-consolidacion")

    def departamentos(self) -> dict[str, str]:
        return self._tabla("departamentos")

    def rangos(self) -> dict[str, str]:
        """Rangos normativos: ``{"1300": "Ley", "1340": "Real Decreto", ...}``."""
        return self._tabla("rangos")

    def relaciones_anteriores(self) -> dict[str, str]:
        return self._tabla("relaciones-anteriores")

    def relaciones_posteriores(self) -> dict[str, str]:
        return self._tabla("relaciones-posteriores")

    # --- Ayudas ---

    def _tabla(self, nombre: str) -> dict[str, str]:
        datos = self._json(f"datos-auxiliares/{nombre}")
        return {str(k): str(v) for k, v in (datos or {}).items()}

    def _json_lista(self, ruta: str, parametros: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        datos = self._json(ruta, parametros)
        if datos is None or datos == "":
            return []
        return datos if isinstance(datos, list) else [datos]


def _rango(desde: date | str | None, hasta: date | str | None) -> dict[str, str]:
    rango = {}
    if desde:
        rango["gte"] = _aaaammdd(desde)
    if hasta:
        rango["lte"] = _aaaammdd(hasta)
    return rango


def _mensaje_error(cuerpo: bytes) -> str | None:
    """Texto del error que manda la API (en XML aunque se pida JSON)."""
    try:
        return str(json.loads(cuerpo)["status"]["text"])
    except (ValueError, KeyError, TypeError):
        pass
    try:
        texto = ET.fromstring(cuerpo).findtext("status/text")
    except ET.ParseError:
        return None
    return texto.strip() if texto else None
