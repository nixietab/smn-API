#!/usr/bin/env python3
"""Ejemplo mínimo de la API del SMN: búsqueda, condiciones actuales,
pronóstico semanal, alertas por área, alertas a corto plazo e imágenes.

Uso:
    python3 smn_example.py [ciudad]
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote

BASE = "https://apimobilecloud.smn.gob.ar/api"
APP_TOKEN = os.environ["SMN_APP_TOKEN"]


def call(path, token=None, body=None, attempts=3):
    """Devuelve el JSON, o None si es 404 / 200 vacío. Reintenta en 5xx y errores de red."""
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode() if body is not None else None

    for i in range(attempts):
        req = urllib.request.Request(
            BASE + path, data=data, headers=headers,
            method="POST" if data is not None else "GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                raw = r.read()
                return json.loads(raw) if raw.strip() else None
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code < 500:
                raise
        except urllib.error.URLError:
            pass
        time.sleep(0.5 * 2 ** i)
    raise RuntimeError(f"falló {path} tras {attempts} intentos")


def get_token():
    r = call("/users/create", body={"device_type": "ANDROID", "password": APP_TOKEN})
    return r["token"]


def main():
    ciudad = sys.argv[1] if len(sys.argv) > 1 else "Bariloche"

    # búsqueda: pública, texto en el path con percent-encoding estricto
    # (quote con safe="" deja sin escapar solo A-Za-z0-9 y -_.~)
    results = call("/locations/search/" + quote(ciudad, safe="")) or []
    if not results:
        sys.exit("sin resultados")
    loc = results[0]  # ojo: el orden es arbitrario, en serio conviene rankear
    lid, area = loc["location_smn_api_id"], loc["area_smn_api_id"]
    print("Lugar:", loc["location_name"], f"({loc['location_province']})")

    token = get_token()

    # condiciones actuales
    today = call(f"/forecast/today/{lid}", token)
    if today:
        print(f"Ahora: {today['temperature']}°C, {today['weather_description']}, "
              f"humedad {today['humidity']}%")
    else:
        print("Sin observación para este id (probar el siguiente candidato)")

    # pronóstico semanal: array raíz o {"forecasts": [...]}
    weekly = call(f"/forecast/weekly/{lid}", token) or []
    days = weekly["forecasts"] if isinstance(weekly, dict) else weekly
    for d in days:
        print(d["forecast_date"], d["temp_min"], "-", d["temp_max"])

    # alertas por área: objeto cuyo id == area_smn_api_id
    areas = call("/locations/areas/map", token) or []
    mine = next((a for a in areas if a["id"] == area), None)
    if mine:
        print("Nivel de alerta:", mine["level"])

    # alertas a corto plazo (FeatureCollection; features vacío si no hay)
    fmap = call("/forecast/map", token) or {}
    feats = fmap.get("short_term_alerts", {}).get("features", [])
    print("Alertas a corto plazo vigentes:", len(feats))

    # imágenes: índices con URLs prefirmadas (también /satellites/all y /wrf/all)
    radars = call("/radars/all", token)
    print("radars/all:", type(radars).__name__, len(radars) if radars else 0)


if __name__ == "__main__":
    main()
