#!/usr/bin/env python3
"""Lugar del SMN más cercano a unas coordenadas + condiciones actuales.

Uso:
    python3 smn_coord.py -34.6 -58.4

/locations/coord es público; /forecast/today necesita el token anónimo.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlencode

BASE = "https://apimobilecloud.smn.gob.ar/api"


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


def parse_coord(lat_s, lon_s):
    """Acepta coma decimal ("-34,6") y valida rangos."""
    lat = float(lat_s.replace(",", "."))
    lon = float(lon_s.replace(",", "."))
    if not -90 <= lat <= 90:
        raise ValueError(f"lat fuera de rango [-90, 90]: {lat}")
    if not -180 <= lon <= 180:
        raise ValueError(f"lon fuera de rango [-180, 180]: {lon}")
    return lat, lon


def parse_location(obj):
    """Parseo tolerante: la respuesta de /locations/coord puede venir con
    location_smn_api_id/location_name/location_province/area_smn_api_id
    o con id/name/province/ref.area_id (y, por las dudas, dentro de una lista)."""
    if isinstance(obj, list):
        obj = obj[0] if obj else None
    if not isinstance(obj, dict):
        return None

    def pick(*keys):
        for k in keys:
            if obj.get(k) is not None:
                return obj[k]
        return None

    ref = obj.get("ref") or {}
    loc = {
        "id": pick("location_smn_api_id", "id"),
        "name": pick("location_name", "name"),
        "province": pick("location_province", "province"),
        "area_id": pick("area_smn_api_id") if pick("area_smn_api_id") is not None else ref.get("area_id"),
    }
    return loc if loc["id"] is not None else None


def get_token():
    r = call("/users/create", body={"device_type": "ANDROID", "password": os.environ["SMN_APP_TOKEN"]})
    return r["token"]


def main():
    if len(sys.argv) != 3:
        sys.exit("uso: smn_coord.py <lat> <lon>")
    lat, lon = parse_coord(sys.argv[1], sys.argv[2])

    raw = call("/locations/coord?" + urlencode({"lat": lat, "lon": lon}))
    loc = parse_location(raw)
    if not loc:
        sys.exit(f"sin lugar para {lat},{lon} (respuesta: {raw!r})")
    print(f"Más cercano: {loc['name']} ({loc['province']}) id={loc['id']} area={loc['area_id']}")

    today = call(f"/forecast/today/{loc['id']}", get_token())
    if not today:
        sys.exit("ese lugar no tiene observación activa (404 o 200 vacío)")
    print(f"Estación: {today['station_name']} a {today['station_distance']} km")
    print(f"Ahora: {today['temperature']}°C, {today['weather_description']}, "
          f"humedad {today['humidity']}%, viento {today['wind_direction']} {today['wind_speed']} km/h")


if __name__ == "__main__":
    main()
