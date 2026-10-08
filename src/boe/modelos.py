"""Tipos de datos que devuelve el cliente."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class Codigo:
    """Valor de una tabla auxiliar del BOE (rango, departamento, ámbito...)."""

    codigo: str
    texto: str

    def __str__(self) -> str:
        return self.texto


@dataclass(frozen=True)
class Disposicion:
    """Una entrada del sumario del BOE o del BORME."""

    identificador: str
    titulo: str
    seccion: str
    departamento: str | None
    epigrafe: str | None
    """Epígrafe en el BOE; apartado en la sección segunda del BORME («CONVOCATORIAS DE JUNTAS»...)."""
    url_pdf: str | None
    url_html: str | None
    url_xml: str | None
    pagina_inicial: int | None = None
    pagina_final: int | None = None
    numero: str = ""
    """Número del diario en que se publicó (los días con número extraordinario hay más de uno)."""


@dataclass(frozen=True)
class Sumario:
    """
    Sumario de un día del BOE o del BORME.

    Algunos días se publica, además del ordinario, uno o varios números extraordinarios: ``numeros`` los
    recoge todos y ``disposiciones`` incluye las de todos ellos. ``numero``, ``identificador`` y ``url_pdf``
    son los del primer número del día.
    """

    diario: str
    fecha: date
    numero: str
    identificador: str
    url_pdf: str | None
    disposiciones: list[Disposicion] = field(default_factory=list)
    numeros: list[str] = field(default_factory=list)

    def secciones(self) -> list[str]:
        """Nombres de las secciones, en el orden del sumario."""
        return list(dict.fromkeys(d.seccion for d in self.disposiciones))

    def de_seccion(self, seccion: str) -> list[Disposicion]:
        """Disposiciones de una sección. Basta con el principio del nombre: «I.», «III.», «SECCIÓN PRIMERA»."""
        clave = seccion.casefold()
        return [d for d in self.disposiciones if d.seccion.casefold().startswith(clave)]

    def buscar(self, texto: str) -> list[Disposicion]:
        """Disposiciones cuyo título, departamento o epígrafe contienen el texto (sin distinguir mayúsculas)."""
        clave = texto.casefold()
        return [
            d
            for d in self.disposiciones
            if clave in d.titulo.casefold()
            or clave in (d.departamento or "").casefold()
            or clave in (d.epigrafe or "").casefold()
        ]


@dataclass(frozen=True)
class Norma:
    """Ficha de una norma de la colección de legislación consolidada."""

    identificador: str
    titulo: str
    rango: Codigo | None
    departamento: Codigo | None
    ambito: Codigo | None
    numero_oficial: str | None
    fecha_disposicion: date | None
    fecha_publicacion: date | None
    fecha_vigencia: date | None
    fecha_actualizacion: datetime | None
    vigencia_agotada: bool
    derogada: bool
    anulada: bool
    estado_consolidacion: Codigo | None
    url_eli: str | None
    url_html: str | None

    @property
    def vigente(self) -> bool:
        """
        True si la norma no está derogada, anulada ni con la vigencia agotada.

        La API solo da el estado de derogación y anulación en la ficha (:meth:`BOE.norma`); en los resultados de
        :meth:`BOE.buscar` se basa únicamente en la vigencia agotada.
        """
        return not (self.vigencia_agotada or self.derogada or self.anulada)


@dataclass(frozen=True)
class Referencia:
    """Relación con otra norma (deroga, modifica, cita...)."""

    id_norma: str
    relacion: Codigo
    texto: str


@dataclass(frozen=True)
class Analisis:
    """Materias, notas y relaciones de una norma con otras."""

    materias: list[Codigo]
    notas: list[str]
    anteriores: list[Referencia]
    posteriores: list[Referencia]


@dataclass(frozen=True)
class EntradaIndice:
    """Un bloque (artículo, título, disposición...) del índice de una norma."""

    id: str
    titulo: str
    fecha_actualizacion: date | None
    url: str


@dataclass(frozen=True)
class Version:
    """Una versión del texto de un bloque, con su fecha de vigencia."""

    id_norma: str
    fecha_publicacion: date | None
    fecha_vigencia: date | None
    xml: str

    @property
    def texto(self) -> str:
        """Texto plano de la versión, un párrafo por línea."""
        return texto_plano(self.xml)


@dataclass(frozen=True)
class Bloque:
    """Texto consolidado de un bloque de una norma, con todas sus versiones."""

    id: str
    tipo: str
    titulo: str
    versiones: list[Version]

    @property
    def vigente(self) -> Version | None:
        """Versión más reciente (la última de la lista), o None si el bloque no tiene texto."""
        return self.versiones[-1] if self.versiones else None

    @property
    def texto(self) -> str:
        """Texto plano de la versión más reciente."""
        version = self.vigente
        return version.texto if version else ""

    def en_fecha(self, fecha: date) -> Version | None:
        """Versión vigente en una fecha, o None si el bloque aún no existía."""
        candidatas = [v for v in self.versiones if v.fecha_vigencia is None or v.fecha_vigencia <= fecha]
        return candidatas[-1] if candidatas else None


# --- Conversión desde las respuestas de la API ---


def lista(valor: Any) -> list[Any]:
    """La API devuelve un objeto suelto o una lista según cuántos elementos haya; esto siempre da una lista."""
    if valor is None:
        return []
    return valor if isinstance(valor, list) else [valor]


def fecha(valor: str | None) -> date | None:
    """Fecha en formato AAAAMMDD, o None."""
    if not valor:
        return None
    return datetime.strptime(valor[:8], "%Y%m%d").date()


def fecha_hora(valor: str | None) -> datetime | None:
    """Fecha y hora UTC en formato AAAAMMDDTHHMMSSZ, o None."""
    if not valor:
        return None
    return datetime.strptime(valor, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)


def codigo(valor: Any) -> Codigo | None:
    if not isinstance(valor, dict) or "codigo" not in valor:
        return None
    return Codigo(str(valor["codigo"]), str(valor.get("texto", "")))


def entero(valor: Any) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def hijos(nodo: dict[str, Any], clave: str) -> list[Any]:
    """
    Hijos de un nodo del sumario.

    Cuando un nivel tiene un solo hijo, la API lo anida a veces dentro de un campo ``texto``
    (``{"seccion": {"texto": {"departamento": {...}}}}``); aquí se aceptan las dos formas.
    """
    resultado = lista(nodo.get(clave))
    texto = nodo.get("texto")
    if isinstance(texto, dict):
        resultado += lista(texto.get(clave))
    return resultado


def sumario_desde_json(datos: dict[str, Any]) -> Sumario:
    sumario = datos["sumario"]
    metadatos = sumario["metadatos"]
    diarios = sorted(lista(sumario.get("diario")), key=lambda d: entero(d.get("numero")) or 0)
    disposiciones: list[Disposicion] = []

    def anadir(items: list[Any], numero: str, seccion: str, departamento: str | None, epigrafe: str | None) -> None:
        for item in items:
            pdf = item.get("url_pdf") or {}
            disposiciones.append(
                Disposicion(
                    identificador=item["identificador"],
                    titulo=item.get("titulo", ""),
                    seccion=seccion,
                    departamento=departamento,
                    epigrafe=epigrafe,
                    url_pdf=pdf.get("texto") if isinstance(pdf, dict) else pdf,
                    url_html=item.get("url_html"),
                    url_xml=item.get("url_xml"),
                    pagina_inicial=entero(pdf.get("pagina_inicial")) if isinstance(pdf, dict) else None,
                    pagina_final=entero(pdf.get("pagina_final")) if isinstance(pdf, dict) else None,
                    numero=numero,
                )
            )

    def recorrer(
        nodo: dict[str, Any], numero: str, seccion: str, departamento: str | None, epigrafe: str | None
    ) -> None:
        anadir(hijos(nodo, "item"), numero, seccion, departamento, epigrafe)
        for hijo in hijos(nodo, "departamento"):
            recorrer(hijo, numero, seccion, hijo.get("nombre"), None)
        # «epigrafe» en el BOE; «apartado» en la sección segunda del BORME (balances, convocatorias...).
        for clave in ("epigrafe", "apartado"):
            for hijo in hijos(nodo, clave):
                recorrer(hijo, numero, seccion, departamento, hijo.get("nombre"))

    for diario in diarios:
        numero = str(diario.get("numero", ""))
        for seccion in lista(diario.get("seccion")):
            recorrer(seccion, numero, seccion.get("nombre", ""), None, None)

    primero = diarios[0] if diarios else {}
    sumario_diario = primero.get("sumario_diario", {})
    pdf = sumario_diario.get("url_pdf") or {}
    fecha_publicacion = fecha(metadatos.get("fecha_publicacion"))
    assert fecha_publicacion is not None
    return Sumario(
        diario=metadatos.get("publicacion", ""),
        fecha=fecha_publicacion,
        numero=str(primero.get("numero", "")),
        identificador=sumario_diario.get("identificador", ""),
        url_pdf=pdf.get("texto") if isinstance(pdf, dict) else pdf,
        disposiciones=disposiciones,
        numeros=[str(d.get("numero", "")) for d in diarios],
    )


def norma_desde_json(datos: dict[str, Any]) -> Norma:
    return Norma(
        identificador=datos["identificador"],
        titulo=datos.get("titulo", ""),
        rango=codigo(datos.get("rango")),
        departamento=codigo(datos.get("departamento")),
        ambito=codigo(datos.get("ambito")),
        numero_oficial=datos.get("numero_oficial"),
        fecha_disposicion=fecha(datos.get("fecha_disposicion")),
        fecha_publicacion=fecha(datos.get("fecha_publicacion")),
        fecha_vigencia=fecha(datos.get("fecha_vigencia")),
        fecha_actualizacion=fecha_hora(datos.get("fecha_actualizacion")),
        vigencia_agotada=datos.get("vigencia_agotada") == "S",
        derogada=datos.get("estatus_derogacion") == "S",
        anulada=datos.get("estatus_anulacion") == "S",
        estado_consolidacion=codigo(datos.get("estado_consolidacion")),
        url_eli=datos.get("url_eli"),
        url_html=datos.get("url_html_consolidada"),
    )


def analisis_desde_json(datos: Any) -> Analisis:
    raiz = lista(datos)[0] if lista(datos) else {}
    materias = [c for m in lista(raiz.get("materias")) if (c := codigo(m.get("materia"))) is not None]
    notas = [str(n) for bloque in lista(raiz.get("notas")) for n in lista(bloque.get("nota"))]

    def referencias(grupo: Any, clave: str) -> list[Referencia]:
        resultado = []
        for bloque in lista(grupo):
            for r in lista(bloque.get(clave)):
                relacion = codigo(r.get("relacion")) or Codigo("", "")
                resultado.append(Referencia(r.get("id_norma", ""), relacion, str(r.get("texto", "")).strip()))
        return resultado

    refs = raiz.get("referencias") or {}
    return Analisis(
        materias=materias,
        notas=notas,
        anteriores=referencias(refs.get("anteriores"), "anterior"),
        posteriores=referencias(refs.get("posteriores"), "posterior"),
    )


def indice_desde_json(datos: Any) -> list[EntradaIndice]:
    raiz = lista(datos)[0] if lista(datos) else {}
    return [
        EntradaIndice(
            id=b["id"],
            titulo=" ".join(str(b.get("titulo", "")).split()),
            fecha_actualizacion=fecha(b.get("fecha_actualizacion")),
            url=b.get("url", ""),
        )
        for b in lista(raiz.get("bloque"))
    ]


def bloque_desde_xml(raiz: ET.Element) -> Bloque:
    elemento = raiz.find("data/bloque")
    if elemento is None:
        raise ValueError("La respuesta no contiene ningún bloque")
    versiones = [
        Version(
            id_norma=v.get("id_norma", ""),
            fecha_publicacion=fecha(v.get("fecha_publicacion")),
            fecha_vigencia=fecha(v.get("fecha_vigencia")),
            xml=ET.tostring(v, encoding="unicode"),
        )
        for v in elemento.findall("version")
    ]
    return Bloque(
        id=elemento.get("id", ""),
        tipo=elemento.get("tipo", ""),
        titulo=" ".join(elemento.get("titulo", "").split()),
        versiones=versiones,
    )


def texto_plano(xml: str) -> str:
    """Texto de un fragmento XML del BOE: un párrafo por línea, sin etiquetas."""
    elemento = ET.fromstring(xml)
    parrafos = [" ".join("".join(p.itertext()).split()) for p in elemento.iter("p")]
    if not parrafos:
        parrafos = [" ".join("".join(elemento.itertext()).split())]
    return "\n".join(p for p in parrafos if p)
