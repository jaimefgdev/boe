# Cambios

## 0.1.1 (2026-10-08)

- Los días con número extraordinario (por ejemplo, el 14-03-2020) el sumario incluye las disposiciones de todos los
  números del día; nuevos `Sumario.numeros` y `Disposicion.numero`.
- Se leen también los niveles que la API anida dentro de un campo `texto` cuando solo tienen un elemento (antes se
  perdían algunas disposiciones).
- BORME: se incluye la sección segunda (anuncios y avisos legales), cuyos apartados quedan en `Disposicion.epigrafe`.
- Los errores de red (sin conexión, tiempo agotado) se lanzan como `ErrorBOE`.

## 0.1.0 (2026-10-08)

- Primera versión: sumarios del BOE y del BORME, búsqueda y fichas de legislación consolidada, análisis, índice y
  texto de bloques con todas sus versiones, tablas auxiliares y línea de comandos `boe`.
