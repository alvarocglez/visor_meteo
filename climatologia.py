"""
Cálculos de climatología: agrupa temperaturas históricas por día del año
y calcula percentiles. No descarga nada ni dibuja nada — solo recibe datos
ya cargados (dict {date: tmax}) y devuelve resultados calculados.
"""

VENTANA_DIAS = 10          # ventana +/- días para agrupar muestra por día del año
MUESTRA_MINIMA = 15        # si un día no llega a esta muestra, se amplía la ventana


def dia_del_anio_normalizado(f):
    """Devuelve (mes, dia) ignorando el año, para poder comparar climatologías."""
    return (f.month, f.day)


def distancia_dias_calendario(mes_dia_a, mes_dia_b):
    """Distancia en días entre dos (mes,dia) dentro de un año de 366 días, circular."""
    from datetime import date
    base = date(2020, 1, 1)  # año bisiesto de referencia
    da = (date(2020, mes_dia_a[0], mes_dia_a[1]) - base).days
    db = (date(2020, mes_dia_b[0], mes_dia_b[1]) - base).days
    dist = abs(da - db)
    return min(dist, 366 - dist)


def construir_muestras_por_dia(datos_dict, campo="tmax", ventana_dias=VENTANA_DIAS, muestra_minima=MUESTRA_MINIMA):
    """Agrupa los valores históricos de `campo` por día del año (mes,dia).
    Empieza con ventana +/- ventana_dias y la amplía si la muestra es escasa."""
    dias_unicos = sorted({dia_del_anio_normalizado(f) for f in datos_dict})
    lista_fechas = [(f, fila.get(campo)) for f, fila in datos_dict.items() if fila.get(campo) is not None]
    muestras = {}
    for md in dias_unicos:
        ventana = ventana_dias
        valores = []
        while ventana <= 60:
            valores = [
                v for f, v in lista_fechas
                if distancia_dias_calendario(md, dia_del_anio_normalizado(f)) <= ventana
            ]
            if len(valores) >= muestra_minima:
                break
            ventana += 5
        muestras[md] = valores
    return muestras


def percentil(valor, distribucion):
    """Porcentaje de valores de la distribución que quedan por debajo de `valor`."""
    if not distribucion:
        return None
    return sum(1 for v in distribucion if v < valor) / len(distribucion) * 100

def valor_percentil(distribucion, p):
    """Valor de la distribución que corresponde al percentil p (0-100),
    con interpolación lineal entre los dos valores más cercanos."""
    if not distribucion:
        return None
    datos = sorted(distribucion)
    if len(datos) == 1:
        return datos[0]
    posicion = (p / 100) * (len(datos) - 1)
    indice_bajo = int(posicion)
    indice_alto = min(indice_bajo + 1, len(datos) - 1)
    fraccion = posicion - indice_bajo
    return datos[indice_bajo] + (datos[indice_alto] - datos[indice_bajo]) * fraccion
