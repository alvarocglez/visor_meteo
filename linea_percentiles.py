"""
Gráfico de línea: temperatura máxima real del año en curso, sobre un fondo
con las bandas de percentil (10-90 y 25-75) y la mediana histórica.
"""

import sys
import os
import json
from datetime import date, timedelta
import matplotlib.pyplot as plt

from aemet_datos import ruta_cache_historico, ruta_cache_anio_actual, cargar_cache
from climatologia import construir_muestras_por_dia, dia_del_anio_normalizado, valor_percentil


def generar_grafico(idema, nombre_estacion):
    historico_tmax = cargar_cache(ruta_cache_historico(idema))
    actual_tmax = cargar_cache(ruta_cache_anio_actual(idema))

    muestras_por_dia = construir_muestras_por_dia(historico_tmax)

    anio = date.today().year
    dias = [date(anio, 1, 1) + timedelta(days=i) for i in range(365)]

    p10, p25, p50, p75, p90 = [], [], [], [], []
    for f in dias:
        md = dia_del_anio_normalizado(f)
        distribucion = muestras_por_dia.get(md, [])
        p10.append(valor_percentil(distribucion, 10))
        p25.append(valor_percentil(distribucion, 25))
        p50.append(valor_percentil(distribucion, 50))
        p75.append(valor_percentil(distribucion, 75))
        p90.append(valor_percentil(distribucion, 90))

    tmax_real = [actual_tmax.get(f) for f in dias]

    fig, ax = plt.subplots(figsize=(16, 6))

    ax.fill_between(dias, p10, p90, color="#a8c8e8", alpha=0.4, label="Rango 10-90%")
    ax.fill_between(dias, p25, p75, color="#5f9fd6", alpha=0.5, label="Rango 25-75%")
    ax.plot(dias, p50, color="#2c5f8a", linewidth=1, linestyle="--", label="Mediana histórica")
    ax.plot(dias, tmax_real, color="#c0392b", linewidth=1.8, label=f"Tmax real {anio}")

    ax.set_title(f"Temperatura máxima diaria vs climatología histórica\n{nombre_estacion} ({idema})")
    ax.set_ylabel("Temperatura (°C)")
    ax.legend(loc="upper left", fontsize=9)
    ax.grid(True, linestyle="--", alpha=0.4)
    fig.autofmt_xdate()

    plt.tight_layout()
    os.makedirs("graficas", exist_ok=True)
    nombre_archivo = f"graficas/calendario_percentiles_{idema}.png"
    plt.savefig(nombre_archivo, dpi=150, bbox_inches="tight")
    print(f"Guardado como {nombre_archivo}")
    plt.close(fig)


if __name__ == "__main__":
    with open("estaciones.json", encoding="utf-8") as f:
        estaciones = json.load(f)

    if len(sys.argv) > 1:
        idemas = [sys.argv[1]]
    else:
        idemas = list(estaciones.keys())

    for idema in idemas:
        nombre = estaciones[idema]["nombre"]
        print(f"\n=== Generando gráfico de líneas de {nombre} ({idema}) ===")
        generar_grafico(idema, nombre)
