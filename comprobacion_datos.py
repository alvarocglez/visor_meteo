"""
Script de comprobación rápida: consulta directamente a AEMET cuál es el
dato de observación más reciente disponible para una estación, sin pasar
por caché ni por el resto del flujo del proyecto.
"""

import os
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("AEMET_API_KEY")
IDEMA = "2507Y"  # cambia aquí si quieres comprobar otra estación

r = requests.get(
    "https://opendata.aemet.es/opendata/api/observacion/convencional/todas",
    headers={"api_key": API_KEY}
)

if r.status_code != 200:
    print(f"Error {r.status_code} en la primera petición: {r.text[:300]}")
    raise SystemExit

datos_url = r.json().get("datos")
if not datos_url:
    print("Respuesta sin URL de datos:", r.json())
    raise SystemExit

r2 = requests.get(datos_url)
if r2.status_code != 200:
    print(f"Error {r2.status_code} descargando datos reales")
    raise SystemExit

lecturas = r2.json()
lecturas_estacion = [l for l in lecturas if l.get("idema") == IDEMA]
lecturas_estacion.sort(key=lambda x: x["fint"])

print(f"Total lecturas de la estación {IDEMA}: {len(lecturas_estacion)}")

if lecturas_estacion:
    ultima = lecturas_estacion[-1]
    fecha_utc = datetime.strptime(ultima["fint"].split("+")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    fecha_local = fecha_utc.astimezone(ZoneInfo("Europe/Madrid"))

    print("Última lectura (UTC):", ultima["fint"])
    print("Última lectura (hora local España):", fecha_local.strftime("%Y-%m-%d %H:%M"))
    print("Temperatura de esa lectura:", ultima.get("ta"), "°C")
else:
    print("No hay lecturas para esta estación en la respuesta de AEMET.")

print("Hora actual (local España):", datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M"))