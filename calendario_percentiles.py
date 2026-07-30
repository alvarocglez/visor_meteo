"""
Calendario anual de percentiles de temperatura máxima.
Estación: Valladolid (2422) - AEMET

Para cada día del año en curso, calcula en qué percentil se sitúa su
temperatura máxima respecto a la climatología histórica de ese mismo día
(usando una ventana de +/- VENTANA_DIAS días alrededor, para tener muestra
suficiente), y lo dibuja como un calendario coloreado.
"""

import os
import csv
import time
import requests
import numpy as np
import matplotlib.pyplot as plt
from datetime import date, timedelta

API_KEY = os.environ.get("AEMET_API_KEY")

IDEMA = "2422"          # Valladolid
NOMBRE_ESTACION = "Valladolid"
ANIOS_HISTORICOS = 30      # años de climatología a usar (excluyendo el actual)
VENTANA_DIAS = 10          # ventana +/- días para agrupar muestra por día del año
MUESTRA_MINIMA = 15        # si un día no llega a esta muestra, se amplía la ventana

BASE_URL = "https://opendata.aemet.es/opendata/api/valores/climatologicos/diarios/datos"
HEADERS = {"api_key": API_KEY}

CACHE_HISTORICO = f"cache_historico_{IDEMA}.csv"
CACHE_ANIO_ACTUAL = f"cache_anio_actual_{IDEMA}_{date.today().year}.csv"
FORZAR_REDESCARGA = False  # pon True si quieres ignorar la caché y volver a pedir todo a AEMET


def pedir_datos(fecha_ini, fecha_fin, intentos=5):
    url = f"{BASE_URL}/fechaini/{fecha_ini}T00:00:00UTC/fechafin/{fecha_fin}T23:59:59UTC/estacion/{IDEMA}"

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


def descargar_historico(anios):
    """Descarga ~`anios` años de histórico, en tramos de 6 meses
    (límite real de la API diaria de AEMET)."""
    hoy = date.today()
    fin = date(hoy.year - 1, 12, 31)  # hasta el año pasado completo
    inicio_total = date(fin.year - anios + 1, 1, 1)

    registros = []
    cursor = inicio_total
    while cursor <= fin:
        # tramo de 6 meses: 1 ene-30 jun, o 1 jul-31 dic
        if cursor.month <= 6:
            tramo_fin = date(cursor.year, 6, 30)
        else:
            tramo_fin = date(cursor.year, 12, 31)
        tramo_fin = min(tramo_fin, fin)

        print(f"Descargando histórico {cursor} a {tramo_fin}...")
        registros += pedir_datos(cursor.isoformat(), tramo_fin.isoformat())
        time.sleep(1.5)  # AEMET limita peticiones por minuto

        cursor = tramo_fin + timedelta(days=1)
    return registros


def actualizar_cache_anio_actual():
    """Si ya existe caché del año actual, descarga solo los días que faltan desde
    la última fecha guardada hasta hoy, y los añade. Si no existe, descarga todo el año."""
    hoy = date.today()

    if os.path.exists(CACHE_ANIO_ACTUAL):
        actual_tmax = cargar_cache(CACHE_ANIO_ACTUAL)
        if actual_tmax:
            ultima_fecha = max(actual_tmax.keys())
            desde = ultima_fecha + timedelta(days=1)
        else:
            desde = date(hoy.year, 1, 1)
    else:
        actual_tmax = {}
        desde = date(hoy.year, 1, 1)

    if desde > hoy:
        print("La caché ya está al día, no hay nada nuevo que descargar.")
        return actual_tmax

    print(f"Descargando datos nuevos de {desde} a {hoy}...")
    registros_nuevos = []
    cursor = desde
    while cursor <= hoy:
        if cursor.month <= 6:
            tramo_fin = date(cursor.year, 6, 30)
        else:
            tramo_fin = date(cursor.year, 12, 31)
        tramo_fin = min(tramo_fin, hoy)

        registros_nuevos += pedir_datos(cursor.isoformat(), tramo_fin.isoformat())
        time.sleep(1.5)

        cursor = tramo_fin + timedelta(days=1)

    nuevos_tmax = parsear_tmax(registros_nuevos)
    print(f"Registros nuevos válidos: {len(nuevos_tmax)}")

    actual_tmax.update(nuevos_tmax)  # los nuevos sobrescriben si hay solape
    if nuevos_tmax:
        guardar_cache(actual_tmax, CACHE_ANIO_ACTUAL)
    return actual_tmax


def descargar_anio_actual():
    hoy = date.today()
    inicio = date(hoy.year, 1, 1)
    print(f"Descargando datos del año actual {inicio} a {hoy}...")

    registros = []
    cursor = inicio
    while cursor <= hoy:
        if cursor.month <= 6:
            tramo_fin = date(cursor.year, 6, 30)
        else:
            tramo_fin = date(cursor.year, 12, 31)
        tramo_fin = min(tramo_fin, hoy)

        registros += pedir_datos(cursor.isoformat(), tramo_fin.isoformat())
        time.sleep(1.5)

        cursor = tramo_fin + timedelta(days=1)
    return registros


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


def dia_del_anio_normalizado(f):
    """Devuelve (mes, dia) ignorando el año, para poder comparar climatologías."""
    return (f.month, f.day)


def distancia_dias_calendario(mes_dia_a, mes_dia_b):
    """Distancia en días entre dos (mes,dia) dentro de un año de 366 días, circular."""
    base = date(2020, 1, 1)  # año bisiesto de referencia
    da = (date(2020, mes_dia_a[0], mes_dia_a[1]) - base).days
    db = (date(2020, mes_dia_b[0], mes_dia_b[1]) - base).days
    dist = abs(da - db)
    return min(dist, 366 - dist)


def construir_muestras_por_dia(historico_tmax):
    """Agrupa las Tmax históricas por día del año (mes,dia).
    Empieza con ventana +/- VENTANA_DIAS y la amplía si la muestra es escasa."""
    dias_unicos = sorted({dia_del_anio_normalizado(f) for f in historico_tmax})
    lista_fechas = list(historico_tmax.items())
    muestras = {}
    for md in dias_unicos:
        ventana = VENTANA_DIAS
        valores = []
        while ventana <= 60:  # límite de seguridad para no diluir demasiado la climatología
            valores = [
                v for f, v in lista_fechas
                if distancia_dias_calendario(md, dia_del_anio_normalizado(f)) <= ventana
            ]
            if len(valores) >= MUESTRA_MINIMA:
                break
            ventana += 5
        muestras[md] = valores
    return muestras


def percentil(valor, distribucion):
    if not distribucion:
        return None
    arr = np.array(distribucion)
    return float((arr < valor).sum() / len(arr) * 100)


def color_por_percentil(p):
    """Interpola azul -> gris -> rojo según percentil 0-100."""
    stops = [
        (0, (24, 95, 165)),
        (25, (133, 183, 235)),
        (50, (241, 239, 232)),
        (75, (240, 153, 123)),
        (100, (230, 180, 20)),
        #(100, (153, 60, 29)),
    ]
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if p0 <= p <= p1:
            t = (p - p0) / (p1 - p0)
            return tuple((c0[i] + (c1[i] - c0[i]) * t) / 255 for i in range(3))
    return (0.5, 0.5, 0.5)


def dibujar_calendario(percentiles_dia):
    """percentiles_dia: dict {date: percentil}"""
    meses = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
             "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    dias_en_mes = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

    fig, ax = plt.subplots(figsize=(14, 7))
    lado = 1.0
    hueco = 0.15

    for mes_idx in range(12):
        for dia_idx in range(dias_en_mes[mes_idx]):
            f = date(date.today().year, mes_idx + 1, dia_idx + 1)
            p = percentiles_dia.get(f)
            x = dia_idx * (lado + hueco)
            y = (11 - mes_idx) * (lado + hueco)

            if p is None:
                color = (0.9, 0.9, 0.9)
                texto = ""
            else:
                color = color_por_percentil(p)
                texto = f"{p:.0f}"

            ax.add_patch(plt.Rectangle((x, y), lado, lado, facecolor=color,
                                        edgecolor="white", linewidth=0.5))
            if texto:
                brillo = sum(color) / 3
                color_texto = "white" if (p is not None and (p < 20 or p > 80)) else "#333333"
                ax.text(x + lado / 2, y + lado / 2, texto, ha="center", va="center",
                        fontsize=6, color=color_texto)

        ax.text(-1.2, (11 - mes_idx) * (lado + hueco) + lado / 2, meses[mes_idx],
                ha="right", va="center", fontsize=10)

    ax.set_xlim(-2, 31 * (lado + hueco))
    ax.set_ylim(-1, 12 * (lado + hueco))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title(f"Percentil de temperatura máxima diaria respecto a climatología histórica\n"
                 f"{NOMBRE_ESTACION} ({IDEMA}) — últimos {ANIOS_HISTORICOS} años, ventana ±{VENTANA_DIAS} días",
                 fontsize=12)

    # Leyenda de color
    grad = np.linspace(0, 100, 256)
    colores = np.array([color_por_percentil(p) for p in grad])
    cax = fig.add_axes([0.35, 0.04, 0.3, 0.02])
    cax.imshow(colores.reshape(1, -1, 3), aspect="auto", extent=[0, 100, 0, 1])
    cax.set_yticks([])
    cax.set_xticks([0, 25, 50, 75, 100])
    cax.set_xlabel("Percentil (frío para la época → cálido para la época)", fontsize=8)

    plt.tight_layout()
    plt.savefig("calendario_percentiles_tmax.png", dpi=150, bbox_inches="tight")
    print("Guardado como calendario_percentiles_tmax.png")
    plt.show()


def main():
    if os.path.exists(CACHE_HISTORICO) and not FORZAR_REDESCARGA:
        historico_tmax = cargar_cache(CACHE_HISTORICO)
    else:
        historico_raw = descargar_historico(ANIOS_HISTORICOS)
        historico_tmax = parsear_tmax(historico_raw)
        print(f"Registros históricos válidos: {len(historico_tmax)}")
        if historico_tmax:
            guardar_cache(historico_tmax, CACHE_HISTORICO)

    if not historico_tmax:
        print("\nNo se pudo descargar climatología histórica para esta estación.")
        print("Posibles causas:")
        print(" - La estación 2422 (Valladolid) puede tener un histórico corto en AEMET.")
        print(" - Prueba a reducir ANIOS_HISTORICOS (por ejemplo a 5).")
        print(" - Prueba con una estación cercana con más histórico, p.ej. Valladolid (2422)"
              " o Medina del Campo si existe en el listado de estaciones de AEMET.")
        return

    if len(historico_tmax) < 200:
        print(f"\nAviso: solo se han encontrado {len(historico_tmax)} registros históricos válidos.")
        print("El cálculo de percentiles puede ser poco fiable. Considera ampliar ANIOS_HISTORICOS")
        print("o usar una estación con más histórico disponible.\n")

    muestras_por_dia = construir_muestras_por_dia(historico_tmax)

    if os.path.exists(CACHE_ANIO_ACTUAL) and not FORZAR_REDESCARGA:
        actual_tmax = actualizar_cache_anio_actual()
    else:
        actual_raw = descargar_anio_actual()
        actual_tmax = parsear_tmax(actual_raw)
        print(f"Registros del año actual válidos: {len(actual_tmax)}")
        if actual_tmax:
            guardar_cache(actual_tmax, CACHE_ANIO_ACTUAL)

    percentiles_dia = {}
    for f, tmax in actual_tmax.items():
        md = dia_del_anio_normalizado(f)
        distribucion = muestras_por_dia.get(md, [])
        percentiles_dia[f] = percentil(tmax, distribucion)

    dibujar_calendario(percentiles_dia)


if __name__ == "__main__":
    main()
