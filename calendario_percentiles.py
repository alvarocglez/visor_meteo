"""
Calendario anual de percentiles de temperatura máxima, para una estación dada.
Solo lee datos ya descargados (caché) - no llama a la API de AEMET.
"""

import sys
import os
import json
import numpy as np
import matplotlib.pyplot as plt
from datetime import date

from aemet_datos import ruta_cache_historico, ruta_cache_anio_actual, cargar_cache
from climatologia import construir_muestras_por_dia, percentil, dia_del_anio_normalizado, VENTANA_DIAS


def color_por_percentil(p):
    """Interpola azul -> gris -> amarillo según percentil 0-100."""
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
            return tuple((c0[i] + (c1[i] - c0[i]) * t) / 255 for i in range(3))
    return (0.5, 0.5, 0.5)


def dibujar_calendario(percentiles_dia, nombre_estacion, idema):
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
                 f"{nombre_estacion} ({idema}) — ventana ±{VENTANA_DIAS} días",
                 fontsize=12)

    grad = np.linspace(0, 100, 256)
    colores = np.array([color_por_percentil(p) for p in grad])
    cax = fig.add_axes([0.35, 0.04, 0.3, 0.02])
    cax.imshow(colores.reshape(1, -1, 3), aspect="auto", extent=[0, 100, 0, 1])
    cax.set_yticks([])
    cax.set_xticks([0, 25, 50, 75, 100])
    cax.set_xlabel("Percentil (frío para la época → cálido para la época)", fontsize=8)

    plt.tight_layout()
    
    os.makedirs("graficas", exist_ok=True)
    nombre_archivo = f"graficas/calendario_percentiles_{idema}.png"
    plt.savefig(nombre_archivo, dpi=150, bbox_inches="tight")
    print(f"Guardado como {nombre_archivo}")
    plt.close(fig)


def generar_grafico(idema, nombre_estacion):
    historico_tmax = cargar_cache(ruta_cache_historico(idema))
    actual_tmax = cargar_cache(ruta_cache_anio_actual(idema))

    muestras_por_dia = construir_muestras_por_dia(historico_tmax)

    percentiles_dia = {}
    for f, tmax in actual_tmax.items():
        md = dia_del_anio_normalizado(f)
        distribucion = muestras_por_dia.get(md, [])
        percentiles_dia[f] = percentil(tmax, distribucion)

    dibujar_calendario(percentiles_dia, nombre_estacion, idema)


if __name__ == "__main__":
    with open("estaciones.json", encoding="utf-8") as f:
        estaciones = json.load(f)

    if len(sys.argv) > 1:
        idemas = [sys.argv[1]]
    else:
        idemas = list(estaciones.keys())

    for idema in idemas:
        nombre = estaciones[idema]["nombre"]
        print(f"\n=== Generando calendario de {nombre} ({idema}) ===")
        generar_grafico(idema, nombre)
