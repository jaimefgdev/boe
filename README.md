# boe

[![CI](https://github.com/jaimefgdev/boe/actions/workflows/ci.yml/badge.svg)](https://github.com/jaimefgdev/boe/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/boe)](https://pypi.org/project/boe/)
[![Python](https://img.shields.io/pypi/pyversions/boe)](https://pypi.org/project/boe/)
[![Licencia: MIT](https://img.shields.io/badge/licencia-MIT-blue)](LICENSE)

Cliente en Python de la [API de datos abiertos del BOE](https://www.boe.es/datosabiertos/api/api.php):
**sumarios diarios del BOE y del BORME**, **legislación consolidada** (búsqueda, fichas, relaciones entre normas y
texto vigente artículo a artículo, con todas sus versiones) y **tablas auxiliares**. Sin dependencias.

```bash
pip install boe
```

```python
>>> from boe import BOE
>>> boe = BOE()

>>> sumario = boe.sumario("2026-10-08")
>>> sumario.numero, len(sumario.disposiciones)
('250', 208)
>>> for d in sumario.buscar("vivienda"):
...     print(d.identificador, d.titulo)

>>> ley = boe.norma("BOE-A-2015-10565")
>>> ley.titulo
'Ley 39/2015, de 1 de octubre, del Procedimiento Administrativo Común de las Administraciones Públicas.'
>>> ley.vigente, ley.fecha_vigencia
(True, datetime.date(2016, 10, 2))

>>> print(boe.articulo("BOE-A-2015-10565", 30).texto)
Artículo 30. Cómputo de plazos.
1. Salvo que por Ley o en el Derecho de la Unión Europea se disponga otro cómputo, cuando los plazos se señalen por horas...
```

## Qué incluye

| Método | Devuelve |
|---|---|
| `sumario(fecha)` / `sumario_borme(fecha)` | `Sumario` del día: número, PDF y la lista de `Disposicion` con sección, departamento, epígrafe, enlaces y páginas, incluidos los números extraordinarios del día (`numeros`). Filtros `de_seccion("III.")` y `buscar("texto")`. |
| `buscar(...)` | Lista de `Norma` de la legislación consolidada, con filtros por texto, título, rango, departamento, ámbito, materia, número oficial, vigencia y fechas, orden y paginación. |
| `norma(id)` | Ficha de una norma: rango, departamento, fechas, vigencia, derogación, ELI. |
| `analisis(id)` | Materias, notas y relaciones con otras normas (deroga, modifica, cita…). |
| `indice(id)` | Bloques de la norma: preámbulo, títulos, artículos, disposiciones. |
| `bloque(id, id_bloque)` / `articulo(id, n)` | Texto consolidado de un bloque con **todas sus versiones**; `.texto` da la vigente y `.en_fecha(fecha)` la que estaba en vigor ese día. |
| `texto_xml(id)` | Texto consolidado completo en el XML original. |
| `rangos()`, `departamentos()`, `materias()`, `ambitos()`… | Tablas auxiliares de códigos. |

Las fechas se pueden pasar como `date` o como texto `AAAA-MM-DD` o `AAAAMMDD`.

## Buscar legislación

```python
>>> boe.rangos()["1300"]
'Ley'
>>> for n in boe.buscar(titulo="vivienda", rango="1300", vigentes=True, publicadas_desde="2020-01-01", limite=5):
...     print(n.fecha_publicacion, n.numero_oficial, n.titulo)

>>> boe.buscar(numero_oficial="39/2015", rango="1300")[0].identificador
'BOE-A-2015-10565'
```

Por defecto se ordena por fecha de publicación, de la más reciente a la más antigua (`orden="-fecha_publicacion"`).
Para condiciones más complejas, `consulta` acepta la sintaxis propia de la API y se combina con el resto de filtros:

```python
>>> boe.buscar(consulta="materia@codigo:6658 or materia@codigo:4107", limite=10)
```

## Versiones de un artículo

```python
>>> from datetime import date
>>> art = boe.articulo("BOE-A-2015-10565", 30)
>>> [v.fecha_vigencia for v in art.versiones]
[datetime.date(2016, 10, 2)]
>>> art.en_fecha(date(2016, 1, 1)) is None   # todavía no estaba en vigor
True
```

## Errores

- `NoEncontrado`: la información no existe, por ejemplo un domingo (no hay BOE) o un identificador erróneo.
- `ErrorBOE`: cualquier otro error de la API (parámetros incorrectos, fallo del servidor, respuesta ilegible).
  `NoEncontrado` es una subclase, y ambas tienen el código HTTP en `.codigo`.

## Línea de comandos

```bash
boe sumario 2026-10-08 --seccion "I." --buscar vivienda
boe sumario 2026-10-08 --borme
boe buscar --titulo "procedimiento administrativo" --rango 1300 --vigentes
boe norma BOE-A-2015-10565
boe articulo BOE-A-2015-10565 30
boe rangos
```

## Desarrollo

```bash
pip install -e ".[dev]"
pytest                 # sin red: usa respuestas reales guardadas en tests/datos
BOE_RED=1 pytest       # además, comprueba la API real
ruff check . && ruff format --check . && mypy
```

## Licencia y datos

Código bajo licencia [MIT](LICENSE). Los datos son de la Agencia Estatal Boletín Oficial del Estado; su reutilización
está sujeta a las [condiciones de reutilización del BOE](https://www.boe.es/informacion/aviso_legal/index.php#reutilizacion).
Este proyecto no está afiliado al BOE.
