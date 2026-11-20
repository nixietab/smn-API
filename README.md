# API del SMN

**Aviso:** Esta guía documenta la API interna utilizada por la aplicación oficial de Android del Servicio Meteorológico Nacional (ar.gob.smn v0.0.9). Al no contar con documentación ni contrato público oficial, los endpoints, esquemas y políticas de acceso pueden cambiar o dejar de funcionar sin previo aviso. Todo el comportamiento descrito fue verificado contra producción el 2026-09-28.


## Resumen rápido

- **URL base:** `https://apimobilecloud.smn.gob.ar/api`
- **Formato:** Todas las respuestas con cuerpo son JSON. Los nombres de los campos están en inglés y los textos descriptivos vienen en español.
- **Autenticación:** JWT anónimo que se obtiene sin cuenta de usuario. Los endpoints de búsqueda de lugares y coordenadas son públicos y no requieren token.
- **Indexación:** Todo se consulta mediante `location_smn_api_id` (numérico), no por coordenadas.
- **Estabilidad:** La API falla de forma intermitente con errores `502`, es indispensable implementar lógica de reintentos.

## Autenticación

### Obtener el token

```bash
BASE="https://apimobilecloud.smn.gob.ar/api"
PW='<APP_TOKEN>'

curl -sS -X POST "$BASE/users/create" \
  -H "Content-Type: application/json" \
  -d "{\"device_type\":\"ANDROID\",\"password\":\"$PW\"}"
# {"token":"eyJ...","username":"anonymous1867794","role":"USER_ANONYMOUS"}
```

- El valor APP_TOKEN se puede sacar del APK
- Los campos `push_token` y `receive_push` son opcionales en el payload y el servidor los ignora.
- El JWT está firmado con `HS512` y tiene una validez de **30 días**. El campo `role` de la respuesta JSON no existe dentro de los claims del token, ignoralo.
- Se envía en las peticiones protegidas mediante el header `Authorization: Bearer <token>`.

### Endpoints según autenticación

| Endpoint | Respuesta sin token |
| --- | --- |
| `/locations/search/{texto}` | `200 OK` (público) |
| `/locations/coord` | `200 OK` (público) |
| Todo lo demás | `403 Forbidden` con cuerpo vacío |

## Endpoints

### Buscar lugares

`GET /locations/search/{texto}`

```json
[
  {
    "location_smn_api_id": 4864,
    "location_name": "Ciudad Autónoma de Buenos Aires",
    "location_province": "CABA",
    "area_smn_api_id": 762
  }
]
```

- El parámetro va en el **path** y los espacios deben codificarse estrictamente con percent-encoding. Un signo `+` se interpreta de forma literal y devuelve `[]`.
- Es una búsqueda difusa que devuelve homónimos de otras provincias y estaciones meteorológicas (por ejemplo, `Buenos Aires` devuelve CABA, una aldea en Chubut y el Aeroparque). El orden devuelto por el servidor es arbitrario, por lo que conviene ordenar los resultados en el cliente (ver *Trampas conocidas*).
- No existe un campo separado para el departamento o partido: se incluye entre paréntesis al final de `location_name` (por ejemplo: `Aldea Buenos Aires Chico (Cushamen)`).
- Una respuesta `200 OK` con `[]` significa "sin coincidencias".

### Lugar más cercano a unas coordenadas

`GET /locations/coord?lat=-34.6&lon=-58.4`

Endpoint público. Devuelve el lugar del SMN más cercano a las coordenadas indicadas. La estructura de respuesta puede variar en los nombres de sus claves entre `location_smn_api_id` / `location_name` / `location_province` / `area_smn_api_id` o `id` / `name` / `province` / `ref.area_id`, por lo que conviene implementar un parseo tolerante a ambos formatos.

### Condiciones actuales

`GET /forecast/today/{id}`

Devuelve un objeto plano (no una lista de observaciones):

```json
{
  "updated_date": "2026-09-28 19:00:00",
  "updated_date_string": "lunes 28 de septiembre",
  "temperature": 19.2,
  "feels_like": null,
  "humidity": 84.0,
  "pressure": 1006.8,
  "visibility": 10.0,
  "wind_speed": 6.0,
  "wind_deg": 135.0,
  "wind_direction": "Sudeste",
  "weather_description": "Nublado",
  "weather_icon_id": 43,
  "station_name": "BUENOS AIRES OBSERVATORIO",
  "station_distance": 6.38,
  "location_smn_api_id": 4864,
  "location_name": "Ciudad Autónoma de Buenos Aires",
  "location_province": "CABA",
  "area_smn_api_id": 762,
  "antartida": false
}
```

- `feels_like` (sensación térmica) casi siempre viene en `null`. Si la necesitas la tenes que calcular vos
- Usá `updated_date` para obtener la marca temporal completa, ya que `updated_date_string` solo contiene la fecha sin hora.
- Una temperatura de `0` es una medición real, no un dato faltante.
- **Posibles respuestas:**
  1. Objeto JSON válido (`200 OK`).
  2. **`404 Not Found` vacío:** el `id` no existe.
  3. **`200 OK` vacío:** el `id` existe, pero la localidad no tiene estación asociada o no hay observaciones activas.
  4. Error de red o `5xx`.
  
  En los casos 2 y 3, la estrategia recomendada es iterar y probar con el siguiente candidato obtenido en `/locations/search`.

### Pronóstico semanal

`GET /forecast/weekly/{id}`

La respuesta puede venir envuelta en `{"forecasts": [...]}` o directamente como un array JSON raíz, con un elemento por día:

```json
{
  "forecast_date": "2026-09-29",
  "temp_min": 12,
  "temp_max": 21,
  "early_morning": null,
  "morning": {
    "temperature": 15,
    "weather_description": "Despejado",
    "wind_direction": "Norte",
    "wind_deg": 360,
    "rain_probability_range": [0, 10],
    "wind_speed_range": [10, 20],
    "wind_gust_range": [30, 40]
  },
  "afternoon": {},
  "night": {}
}
```

- Franjas horarias: `early_morning` (madrugada), `morning` (mañana), `afternoon` (tarde) y `night` (noche). Cualquiera de ellas puede venir en `null` (por ejemplo, las franjas que ya transcurrieron en el día actual).
- Los campos `*_range` representan `[min, max]` y pueden venir como `[null, null]`.

### Alertas meteorológicas por área

`GET /locations/areas/map`

Devuelve alrededor de 171 áreas geográficas (avisos generales a 24–72 horas). Para conocer las alertas vigentes de una localidad, buscá el objeto cuyo `id` coincida con el `area_smn_api_id` del lugar.

```json
{
  "id": 762,
  "name": "...",
  "level": "NO_AVISO",
  "level_alert": "...",
  "level_warning": "...",
  "level_cold": "SIN_EFECTO",
  "level_heat": "SIN_EFECTO",
  "alerts": ["..."],
  "warnings": ["..."],
  "alerts_events": [{}],
  "warnings_events": [{}],
  "geometry": {},
  "provinces": [
    {
      "id": 1,
      "name": "...",
      "departments": [{ "id": 1, "name": "..." }]
    }
  ]
}
```

- Los campos `level_*` utilizan códigos internos en lugar de texto libre: `NO_AVISO`, `SIN_EFECTO`, `ALERTA_RIESGO_POTENCIAL`, `ALERTA_PELIGROSO`. Los dos primeros indican ausencia de alerta.
- Los arrays `alerts_events` y `warnings_events` están alineados por índice con `alerts` y `warnings`, respectivamente.

### Alertas a corto plazo (ACP)

`GET /forecast/map`

Devuelve el estado general del mapa (unos 177 puntos de temperatura en `geojson.features`) e incluye los avisos a corto plazo (fenómenos severos puntuales detectados por radar, válidos por 1 a 3 horas) dentro de `short_term_alerts`:

```json
"short_term_alerts": {
  "type": "FeatureCollection",
  "features": [
    {
      "properties": {
        "title": "...",
        "zones": "SANTIAGO DEL ESTERO: Jimenez - Rio Hondo. - TUCUMAN: ...",
        "duration": "Publicado a las 17:58 Aviso válido por 2h"
      },
      "geometry": {}
    }
  ]
}
```

- `short_term_alerts` es un objeto `FeatureCollection`, no un array. Cuando no hay avisos vigentes, su array `features` viene vacío (`[]`).
- `duration` es una cadena de texto formateada en español, no un valor numérico.
- `zones` es un único string concatenado. Para filtrarlo por provincia o departamento, hay que dividirlo primero por los prefijos `PROVINCIA:` y luego separar los partidos/departamentos por `-`.

### Imágenes: radares, satélites y modelos WRF

`GET /radars/all`, `GET /satellites/all`, `GET /wrf/all`

Devuelven índices con URLs prefirmadas (alojadas en Cloudflare R2) que expiran a las **60 horas**.

- El identificador real del fotograma es el **último segmento** de la URL e incluye la marca temporal UTC de captura (ej.: `..._20260928_210612Z.png`). Ordenar alfabéticamente por este nombre garantiza el orden cronológico.
- El segmento anterior de la ruta es un hash de contenido que cambia en cada publicación; no debe usarse como identificador estable.
- En `/radars/all`, algunos radares pueden venir sin fotogramas disponibles (3 de 25 en las pruebas realizadas), por lo que conviene filtrarlos.
- En `/wrf/all`, cada corrida tiene la estructura `{"title": "00 UTC", "list": [...]}`. La clave con las URLs se llama `list`, no `urls`.

*Nota* Algunos archivos JPEG satelitales (TOP_C13_*) utilizan un submuestreo de croma no soportado por algunos decodificadores 

### Favoritos

Requiere token. A diferencia de otros endpoints, el cuerpo de las peticiones `POST` debe ser un **array JSON plano de IDs**, no un objeto.

Estas son las ubicaciones favoritas dentro de la app

| Método | Ruta | Cuerpo |
| --- | --- | --- |
| `GET` | `/locations/favorites` | N/A (cada ítem devuelve el booleano `has_pin`) |
| `POST` | `/locations/favorites/add` | `[4864]` |
| `POST` | `/locations/favorites/remove` | `[4864]` |
| `POST` | `/locations/favorites/pin` | `[4864]` |
| `POST` | `/locations/favorites/unpin` | `[4864]` |

Enviar un objeto como `{"ids": [4864]}` devuelve error `400 Bad Request`.


## Trampas conocidas

- **Rankear resultados de búsqueda:** Sin un ordenamiento propio, buscar `Rosario` devuelve primero un pueblo de Salta y buscar `Neuquen` devuelve una aldea antes que la capital provincial. Conviene puntuar priorizando coincidencia exacta de nombre, departamento y provincia, y penalizar nombres de estaciones (`Observatorio`, `Aeroparque`). Conservá siempre la lista completa para usarla como fallback en "/forecast/today".
- **Alias de ciudades:** Buscar `Capital Federal` devuelve `[]` aunque la ciudad exista. Conviene mapear este término localmente a `Ciudad Autónoma de Buenos Aires` antes de consultar la API.
- **Codificación estricto del path:** Usá percent-encoding estricto para cualquier carácter fuera de los alfanuméricos o `-_.~`.
- **Rutas con mensajes engañosos:** El endpoint `/forecast/wrf/all` responde `200` con un mensaje de error que culpa al header `Authorization`. La ruta real y funcional es `/wrf/all`.

## Intervalos de actualización recomendados

Para evitar sobrecargar el servicio y mantener un comportamiento similar al de la aplicación oficial, se sugieren los siguientes intervalos mínimos de polling:

- **Alertas a corto plazo (ACP):** cada 2 minutos.
- **Alertas meteorológicas por área:** cada 5 minutos.
- **Condiciones actuales:** cada 5 minutos.
- **Pronóstico semanal:** cada 15 minutos.

## Licencia

Esta documentación y los ejemplos incluidos se distribuyen bajo la licencia GPL 2.0. Este proyecto es independiente y no tiene afiliación, respaldo ni relación alguna con el Servicio Meteorológico Nacional (SMN) ni con el Gobierno de la República Argentina.