"""
Gráfico de línea: temperatura máxima real del año en curso, sobre un fondo
con las bandas de percentil (10-90 y 25-75) y la mediana histórica.
"""

import sys
import os
import json
from datetime import date, timedelta
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from aemet_datos import ruta_cache_historico, ruta_cache_anio_actual, cargar_cache
from climatologia import construir_muestras_por_dia, dia_del_anio_normalizado, valor_percentil


def generar_grafico(idema, nombre_estacion, campo="tmax"):
    historico = cargar_cache(ruta_cache_historico(idema))
    actual = cargar_cache(ruta_cache_anio_actual(idema))

    muestras_por_dia = construir_muestras_por_dia(historico, campo=campo)

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

    valor_real = [actual.get(f, {}).get(campo) for f in dias]

    etiqueta_campo = "máxima" if campo == "tmax" else "mínima"

    fig, ax = plt.subplots(figsize=(16, 6))

    ax.fill_between(dias, p10, p90, color="#a8c8e8", alpha=0.4, label="Rango 10-90%")
    ax.fill_between(dias, p25, p75, color="#5f9fd6", alpha=0.5, label="Rango 25-75%")
    ax.plot(dias, p50, color="#2c5f8a", linewidth=1, linestyle="--", label="Mediana histórica")
    ax.plot(dias, valor_real, color="#c0392b", linewidth=1.8, label=f"T{etiqueta_campo[:3]} real {anio}")

    meses_es = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
                "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

    ax.set_title(f"Temperatura {etiqueta_campo} diaria vs climatología histórica\n{nombre_estacion} ({idema})")
    ax.set_ylabel("Temperatura (°C)")
    ax.legend(loc="upper left", fontsize=9)

    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.FuncFormatter(lambda x, pos: meses_es[mdates.num2date(x).month - 1]))
    ax.xaxis.set_minor_locator(mdates.WeekdayLocator(byweekday=mdates.MO))

    ax.grid(True, which="major", axis="x", linestyle="-", alpha=0.5, color="#888")
    ax.grid(True, which="major", axis="y", linestyle="--", alpha=0.3)
    ax.set_xlim(dias[0], dias[-1])

    plt.tight_layout()
    import os
    os.makedirs("graficas", exist_ok=True)
    nombre_archivo = f"graficas/linea_percentiles_{campo}_{idema}.png"
    plt.savefig(nombre_archivo, dpi=150, bbox_inches="tight")
    print(f"Guardado como {nombre_archivo}")
    plt.close(fig)


if __name__ == "__main__":
    with open("estaciones.json", encoding="utf-8") as f:
        estaciones = json.load(f)

    campo = "tmin" if "--tmin" in sys.argv else "tmax"
    args_idema = [a for a in sys.argv[1:] if not a.startswith("--")]
    idemas = args_idema if args_idema else list(estaciones.keys())

    for idema in idemas:
        nombre = estaciones[idema]["nombre"]
        print(f"\n=== Generando gráfico de líneas de {nombre} ({idema}), campo={campo} ===")
        generar_grafico(idema, nombre, campo=campo)
