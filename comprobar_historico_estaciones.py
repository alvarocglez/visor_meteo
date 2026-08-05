"""
Comprueba cuántos años de histórico climatológico diario tiene cada estación
en AEMET, consultando solo un puñado de años concretos hacia atrás en vez de
descargar todo. Útil para decidir cuántos ANIOS_HISTORICOS usar por estación
antes de generar las gráficas.
"""

import os
import time
import requests
from datetime import date
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("AEMET_API_KEY")
HEADERS = {"api_key": API_KEY}
BASE_URL = "https://opendata.aemet.es/opendata/api/valores/climatologicos/diarios/datos"

ESTACIONES_A_COMPROBAR = {
    "1223P": "Lena, Ronzón",
    "2734D": "Astorga",   # ajusta el idema si no es el correcto
    #"5612X": "Lora de Estepa",    # ajusta el idema si no es el correcto
}

# Años concretos que vamos a probar, de más antiguo a más reciente
ANIOS_A_PROBAR = [2010]


def hay_datos_en_anio(idema, anio):
    fecha_ini = f"{anio}-01-01T00:00:00UTC"
    fecha_fin = f"{anio}-01-31T23:59:59UTC"  # solo un mes, para comprobar rápido
    url = f"{BASE_URL}/fechaini/{fecha_ini}/fechafin/{fecha_fin}/estacion/{idema}"

    r = requests.get(url, headers=HEADERS)
    if r.status_code == 429:
        print("  Límite alcanzado, esperando 65s...")
        time.sleep(65)
        return hay_datos_en_anio(idema, anio)

    if r.status_code != 200:
        return False

    datos_url = r.json().get("datos")
    if not datos_url:
        return False

    r2 = requests.get(datos_url)
    if r2.status_code != 200:
        return False

    registros = r2.json()
    return len(registros) > 0


if __name__ == "__main__":
    for idema, nombre in ESTACIONES_A_COMPROBAR.items():
        print(f"\n=== {nombre} ({idema}) ===")
        primer_anio_con_datos = None
        for anio in ANIOS_A_PROBAR:
            tiene_datos = hay_datos_en_anio(idema, anio)
            print(f"  {anio}: {'sí hay datos' if tiene_datos else 'sin datos'}")
            if tiene_datos and primer_anio_con_datos is None:
                primer_anio_con_datos = anio
            time.sleep(1.5)

        if primer_anio_con_datos:
            anios_disponibles = date.today().year - primer_anio_con_datos
            print(f"  -> Aproximadamente {anios_disponibles} años de histórico disponibles"
                  f" (desde ~{primer_anio_con_datos})")
        else:
            print("  -> No se encontraron datos en ninguno de los años probados")