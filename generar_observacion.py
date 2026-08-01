"""
Gráfico interactivo (Plotly) de la evolución de temperatura de las últimas
24h, usando el endpoint de observación convencional de AEMET (datos horarios,
casi en tiempo real - a diferencia de la climatología, que tiene días de retraso).
"""

import os
import json
import csv
import time
import requests
from datetime import datetime, timezone
import plotly.graph_objects as go
from zoneinfo import ZoneInfo
from datetime import timedelta

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("AEMET_API_KEY")
HEADERS = {"api_key": API_KEY}
URL_OBSERVACION = "https://opendata.aemet.es/opendata/api/observacion/convencional/todas"

RUTA_CACHE_OBSERVACION = "cache_observacion_{idema}.csv"

COLOR_LINEA = "rgb(153,60,29)"


def pedir_observacion(intentos=5):
    for intento in range(intentos):
        r = requests.get(URL_OBSERVACION, headers=HEADERS)

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
            return []

        datos_url = r.json().get("datos")
        if not datos_url:
            return []

        r2 = requests.get(datos_url)
        if r2.status_code != 200:
            print(f"  Error {r2.status_code} descargando datos reales")
            return []

        return r2.json()

    print("  Se agotaron los reintentos")
    return []


def cargar_cache_observacion(idema):
    ruta = RUTA_CACHE_OBSERVACION.format(idema=idema)
    lecturas = {}
    if os.path.exists(ruta):
        with open(ruta, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ta = float(row["ta"]) if row.get("ta") not in ("", None) else None
                prec = float(row["prec"]) if row.get("prec") not in ("", None) else None
                lecturas[row["fint"]] = {"ta": ta, "prec": prec}
    return lecturas


def guardar_cache_observacion(idema, lecturas):
    ruta = RUTA_CACHE_OBSERVACION.format(idema=idema)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fint", "ta", "prec"])
        for fint, fila in sorted(lecturas.items()):
            writer.writerow([fint, fila.get("ta", ""), fila.get("prec", "")])


def purgar_antiguas(lecturas, horas=25):
    limite = datetime.now(timezone.utc) - timedelta(hours=horas)
    lecturas_filtradas = {}
    for fint, ta in lecturas.items():
        fecha_utc = datetime.strptime(fint.split("+")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        if fecha_utc >= limite:
            lecturas_filtradas[fint] = ta
    return lecturas_filtradas


def generar_grafico(idema, nombre_estacion, lecturas_nuevas):
    cache = cargar_cache_observacion(idema)

    lecturas_estacion = [l for l in lecturas_nuevas if l.get("idema") == idema]
    for l in lecturas_estacion:
        fint = l.get("fint")
        ta = l.get("ta")
        prec = l.get("prec")
        if fint:
            cache[fint] = {"ta": ta, "prec": prec}

    cache = purgar_antiguas(cache)
    guardar_cache_observacion(idema, cache)

    fints_ordenados = sorted(cache.keys())

    horas, temperaturas, precipitaciones, textos_temp, textos_prec = [], [], [], [], []
    for fint in fints_ordenados:
        fila = cache[fint]
        fecha_utc = datetime.strptime(fint.split("+")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        fecha_local = fecha_utc.astimezone(ZoneInfo("Europe/Madrid"))
        horas.append(fecha_local)

        ta = fila.get("ta")
        temperaturas.append(ta)
        textos_temp.append(f"<b>{fecha_local.strftime('%H:%M')}</b><br>{ta:.1f}°C" if ta is not None else "")

        prec = fila.get("prec") or 0
        precipitaciones.append(prec)
        textos_prec.append(f"<b>{fecha_local.strftime('%H:%M')}</b><br>{prec:.1f} mm")

    # --- Gráfico de temperatura ---
    fig_temp = go.Figure()
    fig_temp.add_trace(go.Scatter(
        x=horas, y=temperaturas, mode="lines+markers",
        line=dict(color=COLOR_LINEA, width=2.2, shape="spline", smoothing=0.5),
        marker=dict(size=5),
        text=textos_temp, hoverinfo="text",
    ))
    fig_temp.update_layout(
        xaxis=dict(tickformat="%H:%M", showgrid=True, gridcolor="rgba(0,0,0,0.06)",
                    showline=True, linecolor="rgba(0,0,0,0.2)"),
        yaxis=dict(title="Temperatura (°C)", showgrid=True, gridcolor="rgba(0,0,0,0.06)"),
        plot_bgcolor="white", hovermode="x unified",
        hoverlabel=dict(bgcolor="#161f2b", bordercolor="#26313f",
                         font=dict(color="white", size=13, family="IBM Plex Mono, monospace")),
        margin=dict(l=60, r=20, t=20, b=40), autosize=True, dragmode=False,
    )

    # --- Gráfico de precipitación (barras) ---
    fig_prec = go.Figure()
    fig_prec.add_trace(go.Bar(
        x=horas, y=precipitaciones,
        marker=dict(color="rgb(91,155,216)"),
        text=textos_prec, hoverinfo="text",
    ))
    fig_prec.update_layout(
        xaxis=dict(tickformat="%H:%M", showgrid=True, gridcolor="rgba(0,0,0,0.06)",
                    showline=True, linecolor="rgba(0,0,0,0.2)"),
        yaxis=dict(title="Precipitación (mm)", showgrid=True, gridcolor="rgba(0,0,0,0.06)"),
        plot_bgcolor="white", hovermode="x unified",
        hoverlabel=dict(bgcolor="#161f2b", bordercolor="#26313f",
                         font=dict(color="white", size=13, family="IBM Plex Mono, monospace")),
        margin=dict(l=60, r=20, t=20, b=40), autosize=True, dragmode=False,
    )

    os.makedirs("graficas", exist_ok=True)

    config_comun = dict(include_plotlyjs="cdn", full_html=True,
                         config={"responsive": True, "displayModeBar": False, "scrollZoom": False},
                         default_width="100%", default_height="100%")

    fig_temp.write_html(f"graficas/observacion_{idema}.html", **config_comun)
    fig_prec.write_html(f"graficas/observacion_prec_{idema}.html", **config_comun)

    print(f"Guardado observacion_{idema}.html y observacion_prec_{idema}.html ({len(horas)} lecturas acumuladas)")

if __name__ == "__main__":
    with open("estaciones.json", encoding="utf-8") as f:
        estaciones = json.load(f)

    print("Descargando observación convencional...")
    lecturas = pedir_observacion()
    print(f"{len(lecturas)} lecturas totales recibidas")

    for idema, info in estaciones.items():
        nombre = info["nombre"]
        print(f"\n=== Generando observación de {nombre} ({idema}) ===")
        generar_grafico(idema, nombre, lecturas)
