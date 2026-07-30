"""
Funciones de descarga y caché de datos climatológicos diarios de AEMET.
Solo se encarga de conseguir datos (de la API o de disco) - no calcula
climatología ni dibuja nada. Parametrizado por estación (idema), para
poder reutilizarse con cualquier número de estaciones.
"""

import os
import csv
import time
import requests
from datetime import date, timedelta

API_KEY = os.environ.get("AEMET_API_KEY")

BASE_URL = "https://opendata.aemet.es/opendata/api/valores/climatologicos/diarios/datos"
HEADERS = {"api_key": API_KEY}

ANIOS_HISTORICOS = 30  # años de climatología a usar (excluyendo el actual)


def ruta_cache_historico(idema):
    return f"cache_historico_{idema}.csv"


def ruta_cache_anio_actual(idema):
    return f"cache_anio_actual_{idema}_{date.today().year}.csv"


def pedir_datos(idema, fecha_ini, fecha_fin, intentos=5):
    """Pide a AEMET los datos climatológicos diarios de una estación entre dos fechas
    (AEMET limita cada petición a un máximo de 6 meses). Reintenta ante 429 (límite
    de peticiones) y ante errores 5xx (fallos transitorios del servidor)."""
    url = f"{BASE_URL}/fechaini/{fecha_ini}T00:00:00UTC/fechafin/{fecha_fin}T23:59:59UTC/estacion/{idema}"

    for intento in range(intentos):
        r = requests.get(url, headers=HEADERS)

        if r.status_code == 429:
            espera = 65
            print(f"  Límite alcanzado, esperando {espera}s antes de reintentar...")
            time.sleep(espera)
            continue

        if r.status_code >= 500:
            espera = 10 * (intento + 1)
            print(f"  Error {r.status_code} del servidor de AEMET, esperando {espera}s"
                  f" antes de reintentar (intento {intento + 1}/{intentos})...")
            time.sleep(espera)
            continue

        if r.status_code != 200:
            print(f"  Error {r.status_code} pidiendo {fecha_ini} a {fecha_fin}: {r.text[:200]}")
            return []

        cuerpo = r.json()
        datos_url = cuerpo.get("datos")
        if not datos_url:
            print(f"  Sin datos para {fecha_ini} a {fecha_fin}. Respuesta: {cuerpo}")
            return []

        r2 = requests.get(datos_url)

        if r2.status_code >= 500:
            espera = 10 * (intento + 1)
            print(f"  Error {r2.status_code} del servidor de AEMET (datos), esperando {espera}s"
                  f" antes de reintentar (intento {intento + 1}/{intentos})...")
            time.sleep(espera)
            continue

        if r2.status_code != 200:
            print(f"  Error {r2.status_code} descargando datos reales de {fecha_ini} a {fecha_fin}")
            return []

        registros = r2.json()
        print(f"  -> {len(registros)} registros recibidos")
        return registros

    print(f"  Se agotaron los reintentos para {fecha_ini} a {fecha_fin}")
    return []


def parsear_tmax(registros):
    """Convierte la lista de registros de AEMET en un dict {date: tmax_float}."""
    salida = {}
    for r in registros:
        fecha_raw = r.get("fecha")
        tmax_raw = r.get("tmax")
        if not fecha_raw or not tmax_raw:
            continue
        try:
            tmax = float(tmax_raw.replace(",", "."))
            f = date.fromisoformat(fecha_raw)
            salida[f] = tmax
        except (ValueError, TypeError):
            continue
    return salida


def guardar_cache(tmax_dict, ruta):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fecha", "tmax"])
        for fecha, tmax in sorted(tmax_dict.items()):
            writer.writerow([fecha.isoformat(), tmax])
    print(f"Guardado en caché: {ruta} ({len(tmax_dict)} registros)")


def cargar_cache(ruta):
    tmax_dict = {}
    with open(ruta, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for fila in reader:
            tmax_dict[date.fromisoformat(fila["fecha"])] = float(fila["tmax"])
    print(f"Cargado desde caché: {ruta} ({len(tmax_dict)} registros)")
    return tmax_dict


def _tramos_de_seis_meses(inicio, fin):
    """Genera tramos (inicio, fin) de máximo 6 meses cada uno, entre dos fechas."""
    cursor = inicio
    while cursor <= fin:
        if cursor.month <= 6:
            tramo_fin = date(cursor.year, 6, 30)
        else:
            tramo_fin = date(cursor.year, 12, 31)
        tramo_fin = min(tramo_fin, fin)
        yield cursor, tramo_fin
        cursor = tramo_fin + timedelta(days=1)


def descargar_historico(idema, anios=ANIOS_HISTORICOS):
    """Descarga ~`anios` años de histórico de una estación, en tramos de 6 meses."""
    hoy = date.today()
    fin = date(hoy.year - 1, 12, 31)  # hasta el año pasado completo
    inicio_total = date(fin.year - anios + 1, 1, 1)

    registros = []
    for tramo_inicio, tramo_fin in _tramos_de_seis_meses(inicio_total, fin):
        print(f"Descargando histórico {tramo_inicio} a {tramo_fin}...")
        registros += pedir_datos(idema, tramo_inicio.isoformat(), tramo_fin.isoformat())
        time.sleep(1.5)  # AEMET limita peticiones por minuto
    return registros


def actualizar_cache_anio_actual(idema):
    """Si ya existe caché del año actual para esta estación, descarga solo los días
    que faltan desde la última fecha guardada hasta hoy, y los añade. Si no existe,
    descarga todo el año."""
    hoy = date.today()
    ruta = ruta_cache_anio_actual(idema)

    if os.path.exists(ruta):
        actual_tmax = cargar_cache(ruta)
        if actual_tmax:
            ultima_fecha = max(actual_tmax.keys())
            desde = ultima_fecha + timedelta(days=1)
        else:
            desde = date(hoy.year, 1, 1)
    else:
        actual_tmax = {}
        desde = date(hoy.year, 1, 1)

    if desde > hoy:
        print(f"[{idema}] La caché ya está al día, no hay nada nuevo que descargar.")
        return actual_tmax

    print(f"[{idema}] Descargando datos nuevos de {desde} a {hoy}...")
    registros_nuevos = []
    for tramo_inicio, tramo_fin in _tramos_de_seis_meses(desde, hoy):
        registros_nuevos += pedir_datos(idema, tramo_inicio.isoformat(), tramo_fin.isoformat())
        time.sleep(1.5)

    nuevos_tmax = parsear_tmax(registros_nuevos)
    print(f"[{idema}] Registros nuevos válidos: {len(nuevos_tmax)}")

    actual_tmax.update(nuevos_tmax)  # los nuevos sobrescriben si hay solape
    if nuevos_tmax:
        guardar_cache(actual_tmax, ruta)
    return actual_tmax


def obtener_historico(idema, forzar_redescarga=False):
    """Devuelve el histórico de una estación como {date: tmax}, usando caché si existe."""
    ruta = ruta_cache_historico(idema)
    if os.path.exists(ruta) and not forzar_redescarga:
        return cargar_cache(ruta)

    registros = descargar_historico(idema)
    historico_tmax = parsear_tmax(registros)
    print(f"[{idema}] Registros históricos válidos: {len(historico_tmax)}")
    if historico_tmax:
        guardar_cache(historico_tmax, ruta)
    return historico_tmax
