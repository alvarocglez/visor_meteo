"""
Consulta la predicción horaria de AEMET por municipio y resuelve el icono
de estado del cielo correspondiente a la hora actual, para mostrarlo en el
panel "ahora" de cada estación.

Es un dato de PREDICCIÓN (modelo numérico), no de observación directa de la
estación — AEMET no ofrece estado del cielo como variable observada. Los
modelos solo se actualizan 4 veces al día (00, 06, 12, 18 UTC), así que no
tiene sentido pedir esto con más frecuencia: se ejecuta desde un workflow
propio con cron cada 6h, separado de generar_observacion.py.
"""

import os
import json
import time
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("AEMET_API_KEY")
HEADERS = {"api_key": API_KEY}
URL_PREDICCION = "https://opendata.aemet.es/opendata/api/prediccion/especifica/municipio/horaria/{municipio}"

GRAFICAS_PREDICCION_DIR = "graficas/prediccion"

# --- Mapeo de código de estado del cielo de AEMET -> nombre de icono ---
# (set de iconos animados de Makin-Things/weather-icons, servido vía jsDelivr)
# Cada entrada es (icono_dia, icono_noche). Si solo hay un valor, se usa
# para ambos casos (no tiene variante día/noche en el set de iconos).
MAPA_ICONOS = {
    "11": ("clear-day", "clear-night"),
    "12": ("cloudy-1-day", "cloudy-1-night"),
    "17": ("cloudy-1-day", "cloudy-1-night"),
    "13": ("cloudy-2-day", "cloudy-2-night"),
    "14": ("cloudy-3-day", "cloudy-3-night"),
    "15": ("cloudy-3-day", "cloudy-3-night"),
    "16": ("cloudy", "cloudy"),
    "23": ("rainy-1-day", "rainy-1-night"),
    "43": ("rainy-1-day", "rainy-1-night"),
    "24": ("rainy-2-day", "rainy-2-night"),
    "44": ("rainy-2-day", "rainy-2-night"),
    "25": ("rainy-3-day", "rainy-3-night"),
    "45": ("rainy-3-day", "rainy-3-night"),
    "26": ("rainy-2", "rainy-2"),
    "46": ("rainy-2", "rainy-2"),
    "33": ("snowy-1-day", "snowy-1-night"),
    "71": ("snowy-1-day", "snowy-1-night"),
    "34": ("snowy-2-day", "snowy-2-night"),
    "72": ("snowy-2-day", "snowy-2-night"),
    "35": ("snowy-3", "snowy-3"),
    "36": ("snowy-3", "snowy-3"),
    "73": ("snowy-3", "snowy-3"),
    "74": ("snowy-3", "snowy-3"),
    "51": ("isolated-thunderstorms-day", "isolated-thunderstorms-night"),
    "61": ("isolated-thunderstorms-day", "isolated-thunderstorms-night"),
    "52": ("scattered-thunderstorms-day", "scattered-thunderstorms-night"),
    "62": ("scattered-thunderstorms-day", "scattered-thunderstorms-night"),
    "53": ("thunderstorms", "thunderstorms"),
    "54": ("thunderstorms", "thunderstorms"),
    "63": ("thunderstorms", "thunderstorms"),
    "64": ("thunderstorms", "thunderstorms"),
}
ICONO_DEFECTO = "cloudy"


def pedir_prediccion(municipio, intentos=5):
    url = URL_PREDICCION.format(municipio=municipio)

    for intento in range(intentos):
        r = requests.get(url, headers=HEADERS)

        if r.status_code == 429:
            espera = 65
            print(f"  Límite alcanzado, esperando {espera}s...")
            time.sleep(espera)
            continue

        if r.status_code >= 500:
            espera = 10 * (intento + 1)
            print(f"  Error {r.status_code} del servidor, esperando {espera}s...")
            time.sleep(espera)
            continue

        if r.status_code != 200:
            print(f"  Error {r.status_code}: {r.text[:200]}")
            return None

        datos_url = r.json().get("datos")
        if not datos_url:
            return None

        r2 = requests.get(datos_url)
        if r2.status_code != 200:
            print(f"  Error {r2.status_code} descargando datos reales")
            return None

        cuerpo = r2.json()
        return cuerpo[0] if cuerpo else None

    print("  Se agotaron los reintentos")
    return None


def _extraer_tramo_actual(estado_cielo_periodos, hora_actual):
    """De la lista de tramos horarios de estadoCielo, busca el que coincide
    con la hora actual. Cada tramo trae 'periodo' como una hora exacta de
    2 dígitos (ej "11"), 'value' con el código de AEMET (puede llevar sufijo
    'n' de noche) y 'descripcion' ya en texto, lista para usar."""
    hora_str = f"{hora_actual:02d}"
    for tramo in estado_cielo_periodos:
        if tramo.get("periodo") == hora_str:
            return tramo.get("value"), tramo.get("descripcion")
    return None, None


def resolver_icono(codigo):
    """Separa el sufijo 'n' (noche) del código y devuelve
    (nombre_icono, es_noche)."""
    es_noche = codigo.endswith("n")
    codigo_base = codigo[:-1] if es_noche else codigo

    iconos = MAPA_ICONOS.get(codigo_base)
    if iconos is None:
        icono = ICONO_DEFECTO
    else:
        icono = iconos[1] if es_noche else iconos[0]

    return icono, es_noche


def generar_prediccion(idema, nombre_estacion, municipio):
    prediccion = pedir_prediccion(municipio)
    if not prediccion:
        print(f"[{idema}] Sin predicción disponible, se omite.")
        return

    ahora = datetime.now(ZoneInfo("Europe/Madrid"))
    hoy_iso = ahora.strftime("%Y-%m-%d")

    dias = prediccion.get("prediccion", {}).get("dia", [])
    dia_hoy = next((d for d in dias if d.get("fecha", "").startswith(hoy_iso)), None)
    if dia_hoy is None:
        print(f"[{idema}] No se encontró el día de hoy en la predicción, se omite.")
        return

    tramos = dia_hoy.get("estadoCielo", [])
    codigo, descripcion_aemet = _extraer_tramo_actual(tramos, ahora.hour)
    if codigo is None:
        print(f"[{idema}] No se encontró tramo horario para las {ahora.hour}h, se omite.")
        return

    icono, es_noche = resolver_icono(codigo)

    salida = {
        "icono": icono,
        "descripcion": descripcion_aemet,
        "es_noche": es_noche,
        "actualizado": ahora.strftime("%Y-%m-%d %H:%M"),
    }

    os.makedirs(GRAFICAS_PREDICCION_DIR, exist_ok=True)
    with open(f"{GRAFICAS_PREDICCION_DIR}/{idema}.json", "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)
    print(f"[{idema}] {nombre_estacion}: {descripcion_aemet} ({icono})")


if __name__ == "__main__":
    with open("estaciones.json", encoding="utf-8") as f:
        estaciones = json.load(f)

    for idema, info in estaciones.items():
        municipio = info.get("municipio")
        if not municipio:
            print(f"[{idema}] Sin código de municipio en estaciones.json, se omite.")
            continue
        print(f"\n=== Generando predicción de {info['nombre']} ({idema}) ===")
        generar_prediccion(idema, info["nombre"], municipio)
        time.sleep(1.5)