import json
from aemet_datos import obtener_historico, actualizar_cache_anio_actual

with open("estaciones.json", encoding="utf-8") as f:
    estaciones = json.load(f)

for idema, info in estaciones.items():
    print(f"\n=== Actualizando {info['nombre']} ({idema}) ===")
    obtener_historico(idema, primer_anio=info.get("primer_anio"))
    actualizar_cache_anio_actual(idema)