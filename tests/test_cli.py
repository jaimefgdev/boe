from __future__ import annotations

import pytest
from conftest import TransporteFalso

from boe import cli


@pytest.fixture(autouse=True)
def sin_red(monkeypatch: pytest.MonkeyPatch) -> None:
    transporte = TransporteFalso()
    original = cli.BOE
    monkeypatch.setattr(cli, "BOE", lambda: original(transporte=transporte))


def test_sumario(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["sumario", "2026-10-08", "--seccion", "I.", "--buscar", "acuerdo"]) == 0
    salida = capsys.readouterr().out
    assert salida.startswith("BOE n.º 250, 08/10/2026:")
    assert "I. Disposiciones generales" in salida
    assert "BOE-A-2026-20908" in salida


def test_sumario_borme(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["sumario", "2026-10-08", "--borme"]) == 0
    assert "ALBACETE" in capsys.readouterr().out


def test_dia_sin_boe(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["sumario", "2026-10-04"]) == 1
    assert "no existe" in capsys.readouterr().err


def test_norma(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["norma", "BOE-A-2015-10565"]) == 0
    salida = capsys.readouterr().out
    assert "Ley 39/2015" in salida
    assert "Vigente: sí" in salida


def test_articulo(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["articulo", "BOE-A-2015-10565", "30"]) == 0
    assert capsys.readouterr().out.startswith("Artículo 30. Cómputo de plazos.")


def test_buscar_y_rangos(capsys: pytest.CaptureFixture[str]) -> None:
    assert cli.main(["buscar", "blanqueo"]) == 0
    assert "BOE-A-2014-4742" in capsys.readouterr().out
    assert cli.main(["rangos"]) == 0
    assert "1300  Ley" in capsys.readouterr().out
