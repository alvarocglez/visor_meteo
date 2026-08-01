import os
import requests
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

API_KEY = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJhbHZhcm9jYW5vZ29uekBnbWFpbC5jb20iLCJqdGkiOiIxZGQxMTg2ZS0yY2NkLTRlMzktOTU2MS1hN2VlMjgwMWNhODQiLCJleHAiOjE3OTQwNDE4NDAsImlzcyI6IkFFTUVUIiwiaWF0IjoxNzg1NDAxODQwLCJ1c2VySWQiOiIxZGQxMTg2ZS0yY2NkLTRlMzktOTU2MS1hN2VlMjgwMWNhODQiLCJyb2xlIjoiIn0.r0lef0EQoRlCLhHhD042SW2RivXFG3zQ4WNqW-_wav8"

r = requests.get(
    "https://opendata.aemet.es/opendata/api/observacion/convencional/todas",
    headers={"api_key": API_KEY}
)
datos_url = r.json()["datos"]
r2 = requests.get(datos_url)
lecturas = r2.json()

lecturas_valladolid = [l for l in lecturas if l.get("idema") == "2422"]
lecturas_valladolid.sort(key=lambda x: x["fint"])

ultima = lecturas_valladolid[-1]
fecha_utc = datetime.strptime(ultima["fint"].split("+")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
fecha_local = fecha_utc.astimezone(ZoneInfo("Europe/Madrid"))

print("Total lecturas de Valladolid:", len(lecturas_valladolid))
print("Última lectura (UTC):", ultima["fint"])
print("Última lectura (hora local España):", fecha_local.strftime("%Y-%m-%d %H:%M"))
print("Hora actual (local España):", datetime.now(ZoneInfo("Europe/Madrid")).strftime("%Y-%m-%d %H:%M"))