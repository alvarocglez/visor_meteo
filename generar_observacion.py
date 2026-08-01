"""
Gráfico interactivo (Plotly) de la evolución de temperatura de las últimas
24h, usando el endpoint de observación convencional de AEMET (datos horarios,
casi en tiempo real - a diferencia de la climatología, que tiene días de retraso).
"""

import os
import json
import time
import requests
from datetime import datetime, timezone
import plotly.graph_objects as go
from zoneinfo import ZoneInfo

API_KEY = os.environ.get("AEMET_API_KEY")
HEADERS = {"api_key": API_KEY}
URL_OBSERVACION = "https://opendata.aemet.es/opendata/api/observacion/convencional/todas"

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


def generar_grafico(idema, nombre_estacion, lecturas):
    lecturas_estacion = [l for l in lecturas if l.get("idema") == idema]
    lecturas_estacion.sort(key=lambda x: x.get("fint", ""))

    horas, temperaturas, textos = [], [], []
    for l in lecturas_estacion:
        fecha_raw = l.get("fint")
        temp = l.get("ta")
        if not fecha_raw or temp is None:
            continue
        fecha_limpia = fecha_raw.split("+")[0]
        fecha_utc = datetime.strptime(fecha_limpia, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        fecha_local = fecha_utc.astimezone(ZoneInfo("Europe/Madrid"))
        horas.append(fecha_local)
        temperaturas.append(temp)
        textos.append(f"<b>{fecha_local.strftime('%H:%M')}</b><br>{temp:.1f}°C")

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=horas, y=temperaturas, mode="lines+markers",
        line=dict(color=COLOR_LINEA, width=2.2, shape="spline", smoothing=0.5),
        marker=dict(size=5),
        text=textos, hoverinfo="text",
    ))

    fig.update_layout(
        xaxis=dict(
            tickformat="%H:%M",
            showgrid=True, gridcolor="rgba(0,0,0,0.06)",
            showline=True, linecolor="rgba(0,0,0,0.2)",
        ),
        yaxis=dict(
            title="Temperatura (°C)",
            showgrid=True, gridcolor="rgba(0,0,0,0.06)",
        ),
        plot_bgcolor="white",
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#161f2b", bordercolor="#26313f",
            font=dict(color="white", size=13, family="IBM Plex Mono, monospace"),
        ),
        margin=dict(l=60, r=20, t=20, b=40),
        autosize=True,
    )

    os.makedirs("graficas", exist_ok=True)
    nombre_archivo = f"graficas/observacion_{idema}.html"
    fig.write_html(
        nombre_archivo, include_plotlyjs="cdn", full_html=True,
        config={"responsive": True},
        default_width="100%", default_height="100%",
    )
    print(f"Guardado como {nombre_archivo} ({len(horas)} lecturas)")


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
