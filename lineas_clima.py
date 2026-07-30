"""
Genera una gráfica de líneas de la temperatura máxima del año actual (2026)
superpuesta sobre las bandas de percentiles climatológicos históricos.
"""

from datetime import date
import matplotlib.pyplot as plt
import numpy as np

# Importamos tus módulos existentes
import aemet_datos
import climatologia

IDEMA = "2422"  # Valladolid (o el código de la estación que quieras)


def calcular_bandas_percentiles(historico_tmax, percentiles_lista=[10, 25, 50, 75, 90]):
    """Calcula los percentiles deseados para cada día del año (mes, día)."""
    muestras = climatologia.construir_muestras_por_dia(historico_tmax)
    bandas = {p: {} for p in percentiles_lista}

    for md, valores in muestras.items():
        if valores:
            for p in percentiles_lista:
                bandas[p][md] = np.percentile(valores, p)

    return bandas


def generar_grafico_lineas(idema):
    # 1. Cargar datos usando tus funciones
    historico = aemet_datos.obtener_historico(idema)
    anio_actual = aemet_datos.actualizar_cache_anio_actual(idema)

    if not historico or not anio_actual:
        print("Faltan datos para generar el gráfico.")
        return

    # 2. Calcular los valores de las bandas de percentiles
    percentiles_target = [10, 25, 50, 75, 90]
    bandas = calcular_bandas_percentiles(historico, percentiles_target)

    # 3. Preparar el eje X (días del año actual 2026 ordenados)
    fechas_actuales = sorted(anio_actual.keys())
    
    # Extraemos las series correspondientes a cada día que tenemos en el año actual
    dias_md = [climatologia.dia_del_anio_normalizado(f) for f in fechas_actuales]
    tmax_2026 = [anio_actual[f] for f in fechas_actuales]

    p10 = [bandas[10][md] for md in dias_md]
    p25 = [bandas[25][md] for md in dias_md]
    p50 = [bandas[50][md] for md in dias_md]
    p75 = [bandas[75][md] for md in dias_md]
    p90 = [bandas[90][md] for md in dias_md]

    # 4. Construir la figura
    plt.figure(figsize=(12, 6), dpi=150)

    # --- Sombreados de percentiles (Fondo) ---
    # Franja extrema: P10 a P90 (Azul suave / Térmico)
    plt.fill_between(fechas_actuales, p10, p90, color='#e0e0e0', alpha=0.5, label='Rango P10-P90')
    
    # Franja central: P25 a P75 (Más marcada)
    plt.fill_between(fechas_actuales, p25, p75, color='#bdbdbd', alpha=0.6, label='Rango intercuartílico (P25-P75)')

    # Mediana histórica (P50)
    plt.plot(fechas_actuales, p50, color='#616161', linestyle='--', linewidth=1.5, label='Mediana histórica (P50)')

    # --- Línea del Año Actual (Frente) ---
    plt.plot(fechas_actuales, tmax_2026, color='#d32f2f', linewidth=2.5, label=f'Año {date.today().year}')

    # 5. Personalización gráfica
    plt.title(f"Evolución de T. Máxima {date.today().year} vs Climatología Histórica (Estación {idema})", fontsize=13, fontweight='bold', pad=15)
    plt.xlabel("Fecha", fontsize=10)
    plt.ylabel("Temperatura Máxima (°C)", fontsize=10)
    
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.legend(loc='upper left', frameon=True, facecolor='white', framealpha=0.9)
    plt.tight_layout()

    # Guardar la imagen
    nombre_salida = f"grafica_lineas_{idema}.png"
    plt.savefig(nombre_salida)
    print(f"¡Gráfica guardada exitosamente como {nombre_salida}!")
    plt.close()


if __name__ == "__main__":
    generar_grafico_lineas(IDEMA)
