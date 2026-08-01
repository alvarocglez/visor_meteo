"""
Gráfico de línea interactivo (Plotly): temperatura real del año en curso
sobre las bandas de percentil histórico (10-90 y 25-75), con la mediana
como referencia. Solo lee datos ya descargados (caché) - no llama a la
API de AEMET.
"""

import os
import sys
import json
from datetime import date, timedelta
import plotly.graph_objects as go

from aemet_datos import ruta_cache_historico, ruta_cache_anio_actual, cargar_cache
from climatologia import construir_muestras_por_dia, dia_del_anio_normalizado, valor_percentil, VENTANA_DIAS

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

# Misma paleta que el calendario: azul frío -> gris -> rojo cálido
COLOR_BANDA_ANCHA = "rgba(91,155,216,0.18)"   # 10-90, azul muy suave
COLOR_BANDA_ESTRECHA = "rgba(91,155,216,0.32)"  # 25-75, azul algo más intenso
COLOR_MEDIANA = "rgb(120,130,140)"
COLOR_REAL = "rgb(153,60,29)"  # el mismo tono cálido que el extremo de la escala


def generar_grafico(idema, nombre_estacion, campo="tmax"):
    historico = cargar_cache(ruta_cache_historico(idema))
    actual = cargar_cache(ruta_cache_anio_actual(idema))

    muestras_por_dia = construir_muestras_por_dia(historico, campo=campo)
    etiqueta_campo = "máxima" if campo == "tmax" else "mínima"

    anio = date.today().year
    dias = [date(anio, 1, 1) + timedelta(days=i) for i in range(365)]

    p10, p25, p50, p75, p90 = [], [], [], [], []
    valor_real, texto_hover = [], []

    for f in dias:
        md = dia_del_anio_normalizado(f)
        distribucion = muestras_por_dia.get(md, [])

        v10 = valor_percentil(distribucion, 10)
        v25 = valor_percentil(distribucion, 25)
        v50 = valor_percentil(distribucion, 50)
        v75 = valor_percentil(distribucion, 75)
        v90 = valor_percentil(distribucion, 90)

        p10.append(v10)
        p25.append(v25)
        p50.append(v50)
        p75.append(v75)
        p90.append(v90)

        v_real = actual.get(f, {}).get(campo)
        valor_real.append(v_real)

        if v_real is not None and v50 is not None:
            desviacion = v_real - v50
            signo = "+" if desviacion >= 0 else ""
            texto_hover.append(
                f"<b>{f.strftime('%d %b %Y')}</b><br>"
                f"T{campo[1:]} real   {v_real:.1f}°C<br>"
                f"vs mediana  {signo}{desviacion:.1f}°C<br>"
                f"<br>"
                f"P10 · P50 · P90<br>"
                f"{v10:.1f}° · {v50:.1f}° · {v90:.1f}°"
            )
        else:
            texto_hover.append(f"<b>{f.strftime('%d %b %Y')}</b><br>Sin dato")

    fig = go.Figure()

    # Banda 10-90 (fill entre p90 y p10)
    fig.add_trace(go.Scatter(
        x=dias, y=p90, mode="lines", line=dict(width=0),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=dias, y=p10, mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor=COLOR_BANDA_ANCHA,
        name="Rango 10-90%", hoverinfo="skip",
    ))

    # Banda 25-75
    fig.add_trace(go.Scatter(
        x=dias, y=p75, mode="lines", line=dict(width=0),
        showlegend=False, hoverinfo="skip",
    ))
    fig.add_trace(go.Scatter(
        x=dias, y=p25, mode="lines", line=dict(width=0),
        fill="tonexty", fillcolor=COLOR_BANDA_ESTRECHA,
        name="Rango 25-75%", hoverinfo="skip",
    ))

    # Mediana histórica
    fig.add_trace(go.Scatter(
        x=dias, y=p50, mode="lines",
        line=dict(color=COLOR_MEDIANA, width=1.3, dash="dash"),
        name="Mediana histórica", hoverinfo="skip",
    ))

    # Temperatura real, con el tooltip enriquecido
    fig.add_trace(go.Scatter(
        x=dias, y=valor_real, mode="lines",
        line=dict(color=COLOR_REAL, width=2.2, shape="spline", smoothing=0.6),
        name=f"T{campo[1:]} {anio}",
        text=texto_hover, hoverinfo="text",
    ))

    fig.update_layout(
        xaxis=dict(
            tickformat="%b", dtick="M1",
            showgrid=True, gridcolor="rgba(0,0,0,0.06)",
            showline=True, linecolor="rgba(0,0,0,0.2)",
        ),
        yaxis=dict(
            title="Temperatura (°C)",
            showgrid=True, gridcolor="rgba(0,0,0,0.06)",
            zeroline=False,
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="#161f2b",
            bordercolor="#26313f",
            font=dict(color="white", size=13, family="IBM Plex Mono, monospace"),
            align="left",
        ),
        margin=dict(l=60, r=20, t=50, b=40),
        autosize=True,
    )

    os.makedirs("graficas", exist_ok=True)
    nombre_archivo = f"graficas/linea_percentiles_{campo}_{idema}.html"
    fig.write_html(
        nombre_archivo,
        include_plotlyjs="cdn",
        full_html=True,
        config={"responsive": True, "displayModeBar": False},
    )
    print(f"Guardado como {nombre_archivo}")


if __name__ == "__main__":
    with open("estaciones.json", encoding="utf-8") as f:
        estaciones = json.load(f)

    campo = "tmin" if "--tmin" in sys.argv else "tmax"
    args_idema = [a for a in sys.argv[1:] if not a.startswith("--")]
    idemas = args_idema if args_idema else list(estaciones.keys())

    for idema in idemas:
        nombre = estaciones[idema]["nombre"]
        print(f"\n=== Generando gráfico de líneas interactivo de {nombre} ({idema}), campo={campo} ===")
        generar_grafico(idema, nombre, campo=campo)