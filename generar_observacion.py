"""
Gráfico interactivo (Plotly) de la evolución de variables meteorológicas de
las últimas 24h, usando el endpoint de observación convencional de AEMET
(datos horarios, casi en tiempo real - a diferencia de la climatología, que
tiene días de retraso).

Genera un HTML independiente por variable (graficas/observacion/<var>_<idema>.html)
para poder seleccionarlas desde un desplegable en la web sin recargar todo.
"""

import os
import json
import csv
import time
import requests
from datetime import datetime, timezone, timedelta
import plotly.graph_objects as go
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
load_dotenv()

API_KEY = os.environ.get("AEMET_API_KEY")
HEADERS = {"api_key": API_KEY}
URL_OBSERVACION = "https://opendata.aemet.es/opendata/api/observacion/convencional/todas"

# --- Rutas de caché y salida, organizadas en subcarpetas ---
CACHE_OBSERVACION_DIR = "cache/observacion"
GRAFICAS_OBSERVACION_DIR = "graficas/observacion"
GRAFICAS_RESUMENES_DIR = "graficas/resumenes"

RUTA_CACHE_OBSERVACION = CACHE_OBSERVACION_DIR + "/{idema}.csv"

CAMPOS_OBSERVACION = ["ta", "prec", "hr", "vv", "dv", "pres_nmar"]

# Configuración de cada variable graficable: tipo de gráfico, color, título de
# eje, formato del valor en el tooltip y cómo transformar el dato bruto.
VARIABLES = {
    "ta": dict(
        tipo="linea", color="rgb(153,60,29)", eje="Temperatura (°C)",
        fmt=lambda v: f"{v:.1f}°C",
    ),
    "prec": dict(
        tipo="barras", color="rgb(91,155,216)", eje="Precipitación (mm)",
        fmt=lambda v: f"{v:.1f} mm", transformar=lambda v: v or 0,
    ),
    "hr": dict(
        tipo="linea", color="rgb(37,99,168)", eje="Humedad (%)",
        fmt=lambda v: f"{v:.0f}%",
    ),
    "vv": dict(
        tipo="linea", color="rgb(15,120,90)", eje="Viento (m/s)",
        fmt=lambda v: f"{v:.1f} m/s",
    ),
    "pres_nmar": dict(
        tipo="linea", color="rgb(110,80,160)", eje="Presión (hPa, nivel del mar)",
        fmt=lambda v: f"{v:.0f} hPa",
    ),
}


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
                fila = {}
                for campo in CAMPOS_OBSERVACION:
                    valor = row.get(campo, "")
                    fila[campo] = float(valor) if valor not in ("", None) else None
                lecturas[row["fint"]] = fila
    return lecturas


def guardar_cache_observacion(idema, lecturas):
    ruta = RUTA_CACHE_OBSERVACION.format(idema=idema)
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["fint"] + CAMPOS_OBSERVACION)
        for fint, fila in sorted(lecturas.items()):
            writer.writerow([fint] + [fila.get(c, "") for c in CAMPOS_OBSERVACION])


def purgar_antiguas(lecturas, horas=25):
    limite = datetime.now(timezone.utc) - timedelta(hours=horas)
    lecturas_filtradas = {}
    for fint, fila in lecturas.items():
        fecha_utc = datetime.strptime(fint.split("+")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        if fecha_utc >= limite:
            lecturas_filtradas[fint] = fila
    return lecturas_filtradas


def _config_comun():
    return dict(
        include_plotlyjs="cdn", full_html=True,
        config={"responsive": True, "displayModeBar": False, "scrollZoom": False},
        default_width="100%", default_height="100%",
    )


def _generar_html_variable(idema, campo, cfg, horas, valores):
    transformar = cfg.get("transformar", lambda v: v)
    valores_t = [transformar(v) for v in valores]
    textos = [
        f"<b>{h.strftime('%H:%M')}</b><br>{cfg['fmt'](v)}" if v is not None else ""
        for h, v in zip(horas, valores_t)
    ]

    fig = go.Figure()
    if cfg["tipo"] == "linea":
        fig.add_trace(go.Scatter(
            x=horas, y=valores_t, mode="lines+markers",
            line=dict(color=cfg["color"], width=3.2, shape="spline", smoothing=0.5),
            marker=dict(size=10),
            text=textos, hoverinfo="text",
        ))
    else:  # barras
        fig.add_trace(go.Bar(
            x=horas, y=valores_t,
            marker=dict(color=cfg["color"]),
            text=textos, hoverinfo="text",
        ))

    fig.update_layout(
        xaxis=dict(tickformat="%H:%M", showgrid=True, gridcolor="rgba(0,0,0,0.06)",
                    showline=True, linecolor="rgba(0,0,0,0.2)"),
        yaxis=dict(title=cfg["eje"], showgrid=True, gridcolor="rgba(0,0,0,0.06)"),
        plot_bgcolor="white", hovermode="x unified",
        hoverlabel=dict(bgcolor="#161f2b", bordercolor="#26313f",
                         font=dict(color="white", size=13, family="IBM Plex Mono, monospace")),
        margin=dict(l=60, r=20, t=20, b=40), autosize=True, dragmode=False,
    )

    os.makedirs(GRAFICAS_OBSERVACION_DIR, exist_ok=True)
    nombre_archivo = f"{GRAFICAS_OBSERVACION_DIR}/{campo}_{idema}.html"
    fig.write_html(nombre_archivo, **_config_comun())
    return nombre_archivo


def generar_grafico(idema, nombre_estacion, lecturas_nuevas):
    cache = cargar_cache_observacion(idema)

    lecturas_estacion = [l for l in lecturas_nuevas if l.get("idema") == idema]
    for l in lecturas_estacion:
        fint = l.get("fint")
        if fint:
            cache[fint] = {campo: l.get(campo) for campo in CAMPOS_OBSERVACION}

    cache = purgar_antiguas(cache)
    guardar_cache_observacion(idema, cache)
    generar_resumen(idema, cache)

    fints_ordenados = sorted(cache.keys())

    horas = []
    for fint in fints_ordenados:
        fecha_utc = datetime.strptime(fint.split("+")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        horas.append(fecha_utc.astimezone(ZoneInfo("Europe/Madrid")))

    archivos_generados = []
    for campo, cfg in VARIABLES.items():
        valores = [cache[fint].get(campo) for fint in fints_ordenados]
        archivo = _generar_html_variable(idema, campo, cfg, horas, valores)
        archivos_generados.append(archivo)

    print(f"Guardados {len(archivos_generados)} gráficos de {nombre_estacion} ({idema}): "
          f"{', '.join(archivos_generados)} — {len(horas)} lecturas acumuladas")


def direccion_texto(grados):
    if grados is None:
        return "—"
    direcciones = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    idx = round(grados / 45) % 8
    return direcciones[idx]


def _wind_chill(ta, vv_kmh):
    """Sensación térmica por frío + viento (fórmula NWS/Environment Canada).
    Solo válida y aplicable con ta <= 10°C y viento >= 4.8 km/h."""
    return (
        13.12 + 0.6215 * ta - 11.37 * vv_kmh ** 0.16
        + 0.3965 * ta * vv_kmh ** 0.16
    )


def _heat_index(ta, hr):
    """Sensación térmica por calor + humedad (fórmula de Rothfusz, NWS).
    Trabaja internamente en Fahrenheit, que es como está definida
    oficialmente, y devuelve el resultado convertido de nuevo a Celsius."""
    t_f = ta * 9 / 5 + 32
    hi_f = (
        -42.379 + 2.04901523 * t_f + 10.14333127 * hr
        - 0.22475541 * t_f * hr - 0.00683783 * t_f ** 2
        - 0.05481717 * hr ** 2 + 0.00122874 * t_f ** 2 * hr
        + 0.00085282 * t_f * hr ** 2 - 0.00000199 * t_f ** 2 * hr ** 2
    )
    return (hi_f - 32) * 5 / 9


def calcular_sensacion_termica(ta, vv, hr):
    """Devuelve la sensación térmica en °C según las fórmulas oficiales del
    NWS, eligiendo la que corresponda a la situación:
    - Frío + viento -> wind chill (ta <= 10°C, viento >= 4.8 km/h)
    - Calor + humedad -> heat index (ta >= 27°C)
    - En el resto de casos, o si faltan datos, la sensación es la propia
      temperatura del aire.
    """
    if ta is None:
        return None

    vv_kmh = vv * 3.6 if vv is not None else None

    if vv_kmh is not None and ta <= 10 and vv_kmh >= 4.8:
        return round(_wind_chill(ta, vv_kmh), 1)

    if hr is not None and ta >= 27:
        return round(_heat_index(ta, hr), 1)

    return round(ta, 1)


def generar_resumen(idema, cache):
    fints_ordenados = sorted(cache.keys())
    if not fints_ordenados:
        return

    ultimo_fint = fints_ordenados[-1]
    ultima_fila = cache[ultimo_fint]
    fecha_utc = datetime.strptime(ultimo_fint.split("+")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    fecha_local = fecha_utc.astimezone(ZoneInfo("Europe/Madrid"))

    fints_con_temp = [(fint, f["ta"]) for fint, f in cache.items() if f.get("ta") is not None]
    precipitaciones = [f["prec"] for f in cache.values() if f.get("prec") is not None]

    def _hora_local(fint):
        fu = datetime.strptime(fint.split("+")[0], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        return fu.astimezone(ZoneInfo("Europe/Madrid")).strftime("%H:%M")

    if fints_con_temp:
        fint_max, temp_max = max(fints_con_temp, key=lambda x: x[1])
        fint_min, temp_min = min(fints_con_temp, key=lambda x: x[1])
    else:
        fint_max = fint_min = temp_max = temp_min = None

    resumen = {
        "hora_actualizacion": fecha_local.strftime("%H:%M"),
        "temp_actual": ultima_fila.get("ta"),
        "sensacion_termica": calcular_sensacion_termica(
            ultima_fila.get("ta"), ultima_fila.get("vv"), ultima_fila.get("hr")
        ),
        "temp_max_24h": temp_max,
        "hora_max_24h": _hora_local(fint_max) if fint_max else None,
        "temp_min_24h": temp_min,
        "hora_min_24h": _hora_local(fint_min) if fint_min else None,
        "prec_24h": round(sum(precipitaciones), 1) if precipitaciones else 0,
        "humedad_actual": ultima_fila.get("hr"),
        "viento_velocidad": ultima_fila.get("vv"),
        "viento_direccion": direccion_texto(ultima_fila.get("dv")),
        "presion_nmar": ultima_fila.get("pres_nmar"),
    }

    os.makedirs(GRAFICAS_RESUMENES_DIR, exist_ok=True)
    with open(f"{GRAFICAS_RESUMENES_DIR}/{idema}.json", "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(f"Guardado resumen_{idema}.json")


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