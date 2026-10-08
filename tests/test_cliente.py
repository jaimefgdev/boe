from __future__ import annotations

import json
from datetime import date, datetime, timezone

import pytest
from conftest import TransporteFalso

from boe import BOE, Codigo, ErrorBOE, NoEncontrado


class TestSumario:
    def test_sumario_boe(self, boe: BOE, transporte: TransporteFalso) -> None:
        s = boe.sumario(date(2026, 10, 8))

        assert transporte.peticiones[0][0].endswith("/boe/sumario/20261008")
        assert (s.diario, s.fecha, s.numero, s.identificador) == ("BOE", date(2026, 10, 8), "250", "BOE-S-2026-250")
        assert s.url_pdf == "https://www.boe.es/boe/dias/2026/10/08/pdfs/BOE-S-2026-250.pdf"
        assert len(s.disposiciones) == 208

        d = s.disposiciones[0]
        assert d.identificador == "BOE-A-2026-20908"
        assert d.seccion == "I. Disposiciones generales"
        assert d.departamento == "MINISTERIO DE ASUNTOS EXTERIORES, UNIÓN EUROPEA Y COOPERACIÓN"
        assert d.epigrafe == "Acuerdos internacionales administrativos"
        assert d.url_html == "https://www.boe.es/diario_boe/txt.php?id=BOE-A-2026-20908"
        assert (d.pagina_inicial, d.pagina_final) == (133621, 133624)

    def test_secciones_y_filtros(self, boe: BOE) -> None:
        s = boe.sumario("2026-10-08")

        assert s.secciones()[0] == "I. Disposiciones generales"
        assert len(s.secciones()) == len(set(s.secciones()))
        assert all(d.seccion.startswith("III.") for d in s.de_seccion("III."))
        assert sum(len(s.de_seccion(nombre)) for nombre in s.secciones()) == len(s.disposiciones)
        assert s.buscar("VIVIENDA") == s.buscar("vivienda")
        assert all(
            "vivienda" in (d.titulo + (d.departamento or "") + (d.epigrafe or "")).lower() for d in s.buscar("vivienda")
        )

    def test_disposiciones_sin_epigrafe(self, boe: BOE) -> None:
        s = boe.sumario("20261008")
        sin_epigrafe = [d for d in s.disposiciones if d.epigrafe is None]
        assert sin_epigrafe
        assert all(d.departamento for d in sin_epigrafe)

    def test_sumario_borme(self, boe: BOE) -> None:
        s = boe.sumario_borme("2026-10-08")

        assert s.diario == "BORME"
        assert s.numero == "195"
        assert s.disposiciones[0].titulo == "ALBACETE"
        assert s.disposiciones[0].departamento is None
        assert s.disposiciones[0].seccion.startswith("SECCIÓN PRIMERA")

    def test_dia_sin_boe(self, boe: BOE) -> None:
        with pytest.raises(NoEncontrado, match="no existe") as error:
            boe.sumario("2026-10-04")
        assert error.value.codigo == 404


class TestLegislacion:
    def test_norma(self, boe: BOE) -> None:
        n = boe.norma("BOE-A-2015-10565")

        assert n.titulo.startswith("Ley 39/2015, de 1 de octubre")
        assert n.rango == Codigo("1300", "Ley")
        assert str(n.departamento) == "Jefatura del Estado"
        assert n.numero_oficial == "39/2015"
        assert n.fecha_publicacion == date(2015, 10, 2)
        assert n.fecha_vigencia == date(2016, 10, 2)
        assert n.fecha_actualizacion == datetime(2026, 9, 25, 8, 8, 15, tzinfo=timezone.utc)
        assert n.vigente
        assert n.url_eli == "https://www.boe.es/eli/es/l/2015/10/01/39"

    def test_norma_inexistente(self, boe: BOE) -> None:
        with pytest.raises(NoEncontrado):
            boe.norma("BOE-A-1900-1")

    def test_buscar_construye_la_consulta(self, boe: BOE, transporte: TransporteFalso) -> None:
        normas = boe.buscar(
            "teletrabajo",
            titulo="procedimiento administrativo",
            rango="1300",
            vigentes=True,
            publicadas_desde=date(2023, 1, 1),
            publicadas_hasta="2023-12-31",
            limite=3,
        )

        assert len(normas) == 3
        parametros = transporte.ultima
        consulta = json.loads(parametros["query"][0])
        assert consulta["query"]["query_string"]["query"] == (
            'texto:teletrabajo and titulo:"procedimiento administrativo" and rango@codigo:1300 and vigencia_agotada:N'
        )
        assert consulta["query"]["range"] == {"fecha_publicacion": {"gte": "20230101", "lte": "20231231"}}
        assert consulta["sort"] == [{"fecha_publicacion": "desc"}]
        assert parametros["limit"] == ["3"]
        assert "offset" not in parametros

    def test_buscar_sin_filtros_ni_orden(self, boe: BOE, transporte: TransporteFalso) -> None:
        boe.buscar(orden=None, actualizadas_desde="2026-10-01", desplazamiento=50)
        parametros = transporte.ultima
        assert "query" not in parametros
        assert parametros["from"] == ["20261001"]
        assert parametros["offset"] == ["50"]

    def test_buscar_con_consulta_propia(self, boe: BOE, transporte: TransporteFalso) -> None:
        boe.buscar(consulta="materia@codigo:6658 or materia@codigo:4107", orden="titulo")
        consulta = json.loads(transporte.ultima["query"][0])
        assert consulta["query"]["query_string"]["query"] == "(materia@codigo:6658 or materia@codigo:4107)"
        assert consulta["sort"] == [{"titulo": "asc"}]

    def test_analisis(self, boe: BOE) -> None:
        a = boe.analisis("BOE-A-2015-10565")

        assert a.materias == [Codigo("6499", "Seguridad Social")]
        assert a.notas[0].startswith("Entrada en vigor")
        assert a.anteriores[0].id_norma == "BOE-A-2011-4117"
        assert a.anteriores[0].relacion == Codigo("210", "DEROGA")
        assert a.posteriores

    def test_indice(self, boe: BOE) -> None:
        indice = boe.indice("BOE-A-2015-10565")

        assert indice[0].id == "preambulo"
        a1 = next(e for e in indice if e.id == "a1")
        assert a1.titulo == "Artículo 1"
        assert a1.fecha_actualizacion == date(2015, 10, 2)

    def test_bloque(self, boe: BOE, transporte: TransporteFalso) -> None:
        bloque = boe.articulo("BOE-A-2015-10565", 30)

        assert transporte.peticiones[-1][1] == "application/xml"
        assert (bloque.id, bloque.tipo, bloque.titulo) == ("a30", "precepto", "Artículo 30")
        assert len(bloque.versiones) == 1
        version = bloque.vigente
        assert version is not None
        assert version.fecha_vigencia == date(2016, 10, 2)
        lineas = bloque.texto.splitlines()
        assert lineas[0] == "Artículo 30. Cómputo de plazos."
        assert lineas[1].startswith("1. Salvo que por Ley")
        assert bloque.en_fecha(date(2016, 1, 1)) is None
        assert bloque.en_fecha(date(2020, 1, 1)) == version


class TestTablas:
    def test_tablas_auxiliares(self, boe: BOE) -> None:
        assert boe.rangos()["1300"] == "Ley"
        assert boe.ambitos() == {"1": "Estatal", "2": "Autonómico"}
        assert boe.estados_consolidacion()["3"] == "Finalizado"
        assert boe.relaciones_anteriores()["210"] == "DEROGA"
        assert boe.departamentos()["7723"] == "Jefatura del Estado"
        assert len(boe.materias()) == 20


class TestErrores:
    def test_error_del_servidor(self) -> None:
        boe = BOE(
            transporte=lambda url, accept: (
                500,
                b"<response><status><code>500</code><text>Fallo</text></status></response>",
            )
        )
        with pytest.raises(ErrorBOE, match="Fallo") as error:
            boe.rangos()
        assert error.value.codigo == 500

    def test_respuesta_no_json(self) -> None:
        boe = BOE(transporte=lambda url, accept: (200, b"<html>"))
        with pytest.raises(ErrorBOE, match="JSON"):
            boe.rangos()

    def test_estado_en_el_cuerpo(self) -> None:
        cuerpo = json.dumps({"status": {"code": "400", "text": "Parámetros incorrectos"}, "data": []}).encode()
        boe = BOE(transporte=lambda url, accept: (200, cuerpo))
        with pytest.raises(ErrorBOE, match="incorrectos") as error:
            boe.buscar("x")
        assert error.value.codigo == 400
        assert not isinstance(error.value, NoEncontrado)


@pytest.mark.red
class TestApiReal:
    """Comprueban que la API sigue respondiendo como esperan los modelos (BOE_RED=1 pytest)."""

    def test_sumario_y_norma(self) -> None:
        boe = BOE()
        assert boe.sumario("2026-10-08").disposiciones
        assert boe.norma("BOE-A-2015-10565").numero_oficial == "39/2015"
        assert "Cómputo de plazos" in boe.articulo("BOE-A-2015-10565", 30).texto
        assert boe.buscar(numero_oficial="39/2015", rango="1300")[0].identificador == "BOE-A-2015-10565"
