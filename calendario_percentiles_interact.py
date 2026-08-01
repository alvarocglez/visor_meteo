"""
Calendario anual de percentiles de temperatura, interactivo (Plotly).
Solo lee datos ya descargados (caché) - no llama a la API de AEMET.
"""

import os
import sys
import json
from datetime import date
import plotly.graph_objects as go

from aemet_datos import ruta_cache_historico, ruta_cache_anio_actual, cargar_cache
from climatologia import construir_muestras_por_dia, percentil, valor_percentil, dia_del_anio_normalizado, VENTANA_DIAS
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
DIAS_EN_MES = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def color_por_percentil(p):
    stops = [
        (0, (24, 95, 165)),
        (25, (133, 183, 235)),
        (50, (241, 239, 232)),
        (75, (240, 153, 123)),
        (100, (153, 60, 29)),
    ]
    for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
        if p0 <= p <= p1:
            t = (p - p0) / (p1 - p0)
            return tuple(round(c0[i] + (c1[i] - c0[i]) * t) for i in range(3))
    return (200, 200, 200)


def generar_grafico(idema, nombre_estacion, campo="tmax"):
    historico = cargar_cache(ruta_cache_historico(idema))
    actual = cargar_cache(ruta_cache_anio_actual(idema))

    muestras_por_dia = construir_muestras_por_dia(historico, campo=campo)
    etiqueta_campo = "máxima" if campo == "tmax" else "mínima"

    # Matriz 12 (meses) x 31 (días), con None donde no hay dato
    z = [[None] * 31 for _ in range(12)]
    texto_hover = [[""] * 31 for _ in range(12)]
    texto_num = [[""] * 31 for _ in range(12)]

    for mes_idx in range(12):
        for dia_idx in range(DIAS_EN_MES[mes_idx]):
            f = date(date.today().year, mes_idx + 1, dia_idx + 1)
            valor = actual.get(f, {}).get(campo)

            fila = 11 - mes_idx  # fila 0 = diciembre arriba... lo invertimos luego

            if valor is None:
                texto_hover[mes_idx][dia_idx] = f"{f.strftime('%d %b')}<br>Sin dato"
                continue

            md = dia_del_anio_normalizado(f)
            distribucion = muestras_por_dia.get(md, [])
            p = percentil(valor, distribucion)

            if p is None:
                texto_hover[mes_idx][dia_idx] = f"{f.strftime('%d %b')}<br>Sin climatología suficiente"
                continue

            p10 = valor_percentil(distribucion, 10)
            p50 = valor_percentil(distribucion, 50)
            p90 = valor_percentil(distribucion, 90)

            z[mes_idx][dia_idx] = p
            texto_num[mes_idx][dia_idx] = f"{p:.0f}"
            texto_hover[mes_idx][dia_idx] = (
                f"<b>{f.strftime('%d %b %Y')}</b><br>"
                f"T{campo[1:]} real  {valor:.1f}°C<br>"
                f"Percentil     {p:.0f}<br>"
                f"<br>"
                f"P10 · P50 · P90<br>"
                f"{p10:.1f}° · {p50:.1f}° · {p90:.1f}°"
            )

    fig = go.Figure(data=go.Heatmap(
        z=z,
        x=list(range(1, 32)),
        y=MESES,
        text=texto_num,
        texttemplate="%{text}",
        textfont=dict(size=13, family="Arial Black, sans-serif"),        customdata=texto_hover,
        hovertemplate="%{customdata}<extra></extra>",
        colorscale=[
            [0.0, "rgb(24,95,165)"],
            [0.25, "rgb(133,183,235)"],
            [0.5, "rgb(241,239,232)"],
            [0.75, "rgb(240,153,123)"],
            [1.0, "rgb(153,60,29)"],
        ],
        zmin=0, zmax=100,
        xgap=3, ygap=3,
        colorbar=dict(title="Percentil", thickness=15),
    ))

    fig.update_layout(
        title=f"Percentil de temperatura {etiqueta_campo} diaria — {nombre_estacion} ({idema})<br>"
              f"<sup>ventana ±{VENTANA_DIAS} días</sup>",
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, autorange="reversed"),
        plot_bgcolor="white",
        autosize=True,
        margin=dict(l=60, r=20, t=80, b=20),
        hoverlabel=dict(
            bgcolor="#161f2b",
            bordercolor="#26313f",
            font=dict(color="white", size=13, family="IBM Plex Mono, monospace"),
            align="left",
        ),
    )

    os.makedirs("graficas", exist_ok=True)
    nombre_archivo = f"graficas/calendario_percentiles_{campo}_{idema}.html"
    fig.write_html(
        nombre_archivo,
        include_plotlyjs="cdn",
        full_html=True,
        config={"responsive": True},
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
        print(f"\n=== Generando calendario interactivo de {nombre} ({idema}), campo={campo} ===")
        generar_grafico(idema, nombre, campo=campo)