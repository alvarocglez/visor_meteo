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


def color_por_anomalia(anomalia, rango=8):
    """Azul (frío/negativo) - blanco (0) - rojo (cálido/positivo).
    Reutiliza la misma familia de color que color_por_percentil para que
    ambas escalas del tooltip sean visualmente coherentes con el heatmap."""
    t = max(-rango, min(rango, anomalia))
    frac = (t + rango) / (2 * rango) * 100  # 0..100
    return color_por_percentil(frac)


def _span_color(texto, rgb):
    r, g, b = rgb
    return f'<span style="color: rgb({r},{g},{b}); font-weight: 600;">{texto}</span>'


def _calcular_dato_campo(f, actual, muestras_por_dia, campo):
    """Devuelve (valor, percentil, anomalia) para un campo (tmax/tmin) en una fecha,
    o (None, None, None) si no hay dato suficiente."""
    valor = actual.get(f, {}).get(campo)
    if valor is None:
        return None, None, None

    md = dia_del_anio_normalizado(f)
    distribucion = muestras_por_dia.get(md, [])
    p = percentil(valor, distribucion)
    if p is None:
        return valor, None, None

    p50 = valor_percentil(distribucion, 50)
    anomalia = valor - p50 if p50 is not None else None
    return valor, p, anomalia


def generar_grafico(idema, nombre_estacion, campo="tmax"):
    historico = cargar_cache(ruta_cache_historico(idema))
    actual = cargar_cache(ruta_cache_anio_actual(idema))

    # Se calculan SIEMPRE ambos campos (tmax y tmin), independientemente de cuál
    # sea el "campo" activo que colorea el heatmap, porque el tooltip debe
    # mostrar ambos siempre.
    muestras_tmax = construir_muestras_por_dia(historico, campo="tmax")
    muestras_tmin = construir_muestras_por_dia(historico, campo="tmin")
    muestras_por_dia = muestras_tmax if campo == "tmax" else muestras_tmin

    # Matriz 12 (meses) x 31 (días), con None donde no hay dato
    z = [[None] * 31 for _ in range(12)]
    texto_hover = [[""] * 31 for _ in range(12)]
    texto_num = [[""] * 31 for _ in range(12)]

    for mes_idx in range(12):
        for dia_idx in range(DIAS_EN_MES[mes_idx]):
            f = date(date.today().year, mes_idx + 1, dia_idx + 1)

            v_max, p_max, a_max = _calcular_dato_campo(f, actual, muestras_tmax, "tmax")
            v_min, p_min, a_min = _calcular_dato_campo(f, actual, muestras_tmin, "tmin")

            # El color/valor numérico del cuadro sigue dependiendo del campo activo
            valor_activo, p_activo, _ = (v_max, p_max, a_max) if campo == "tmax" else (v_min, p_min, a_min)

            if valor_activo is None:
                texto_hover[mes_idx][dia_idx] = f"<b>{f.strftime('%d %b')}</b><br>Sin dato"
                continue
            if p_activo is None:
                texto_hover[mes_idx][dia_idx] = f"<b>{f.strftime('%d %b')}</b><br>Sin climatología suficiente"
                continue

            z[mes_idx][dia_idx] = p_activo
            texto_num[mes_idx][dia_idx] = f"{p_activo:.0f}"

            def _fmt(valor, p, anomalia):
                if valor is None:
                    return "sin dato"
                partes = f"{valor:.1f}°C"
                if anomalia is not None:
                    signo = "+" if anomalia >= 0 else ""
                    texto_anom = f"({signo}{anomalia:.1f}°)"
                    partes += "  " + _span_color(texto_anom, color_por_anomalia(anomalia))
                if p is not None:
                    texto_p = f"P{p:.0f}"
                    partes += "  · " + _span_color(texto_p, color_por_percentil(p))
                return partes

            texto_hover[mes_idx][dia_idx] = (
                f"<b>{f.strftime('%d %b %Y')}</b><br>"
                f"Máx  {_fmt(v_max, p_max, a_max)}<br>"
                f"Mín  {_fmt(v_min, p_min, a_min)}"
            )

    z_placeholder = [
        [1 if (d < DIAS_EN_MES[m] and z[m][d] is None) else None for d in range(31)]
        for m in range(12)
    ]

    fig = go.Figure()

    fig.add_trace(go.Heatmap(
        z=z_placeholder,
        x=list(range(1, 32)),
        y=MESES,
        colorscale=[[0, "#e8e8e4"], [1, "#e8e8e4"]],
        zmin=0, zmax=1,
        xgap=3, ygap=3,
        showscale=False,
        hoverinfo="skip",
    ))

    fig.add_trace(go.Heatmap(
        z=z,
        x=list(range(1, 32)),
        y=MESES,
        text=texto_num,
        texttemplate="%{text}",
        textfont=dict(size=11, family="Arial Black, sans-serif"),
        customdata=texto_hover,
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
        colorbar=dict(
            title="Percentil",
            thickness=15,
            orientation="h",
            x=0.5, xanchor="center",
            y=-0.12, yanchor="top",
            len=0.6,
        ),
    ))

    fig.update_layout(
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False, constrain="domain"),
        yaxis=dict(showgrid=False, zeroline=False, autorange="reversed", ticklabelstandoff=15, scaleanchor="x", scaleratio=1, constrain="domain"),
        plot_bgcolor="white",
        autosize=True,
        dragmode=False,
        margin=dict(l=60, r=20, t=20, b=70),
        hoverlabel=dict(
            bgcolor="#161f2b",
            bordercolor="#26313f",
            font=dict(color="white", size=13, family="IBM Plex Mono, monospace"),
            align="left",
        ),
    )

    # --- Tooltip que sigue al ratón + tooltip propio + ajuste responsive ---
    # Se oculta la caja nativa de Plotly (queda anclada a la celda) y se monta
    # un div propio posicionado en cada mousemove con la posición del cursor.
    # customdata (texto_hover) se sigue usando: se lee desde el evento
    # plotly_hover, solo que ya no se muestra con el hoverlayer nativo.
    div_id = f"calendario_{idema}_{campo}"

    post_script = f"""
    (function() {{
        var gd = document.getElementById('{div_id}');
        if (!gd) return;

        // Oculta la caja de hover nativa de Plotly
        var style = document.createElement('style');
        style.innerHTML = '#{div_id} .hoverlayer {{ display: none !important; }}';
        document.head.appendChild(style);

        // Crea el tooltip propio
        var tip = document.createElement('div');
        tip.style.position = 'fixed';
        tip.style.pointerEvents = 'none';
        tip.style.zIndex = 9999;
        tip.style.background = '#ffffff';
        tip.style.border = '1px solid #d8d8d4';
        tip.style.boxShadow = '0 2px 10px rgba(0,0,0,0.15)';
        tip.style.color = '#1a1a1a';
        tip.style.fontFamily = 'IBM Plex Mono, monospace';
        tip.style.fontSize = '13px';
        tip.style.padding = '8px 10px';
        tip.style.borderRadius = '4px';
        tip.style.lineHeight = '1.5';
        tip.style.display = 'none';
        document.body.appendChild(tip);

        var visible = false;

        gd.on('plotly_hover', function(data) {{
            if (!data.points || !data.points[0]) return;
            tip.innerHTML = data.points[0].customdata;
            tip.style.display = 'block';
            visible = true;
        }});

        gd.on('plotly_unhover', function() {{
            tip.style.display = 'none';
            visible = false;
        }});

        gd.addEventListener('mousemove', function(evt) {{
            if (!visible) return;
            var offsetX = 16;
            var offsetY = 16;
            var x = evt.clientX + offsetX;
            var y = evt.clientY + offsetY;

            // Evita que se salga por el borde derecho/inferior de la ventana
            var tipRect = tip.getBoundingClientRect();
            if (x + tipRect.width > window.innerWidth) {{
                x = evt.clientX - tipRect.width - offsetX;
            }}
            if (y + tipRect.height > window.innerHeight) {{
                y = evt.clientY - tipRect.height - offsetY;
            }}

            tip.style.left = x + 'px';
            tip.style.top = y + 'px';
        }});

        // Oculta los números del percentil en pantallas estrechas (móvil,
        // portátil con ventana partida) para que no se amontonen.
        function ajustarNumeros() {{
            var ancho = gd.offsetWidth;
            var umbral = 500;
            if (ancho < umbral) {{
                Plotly.restyle(gd, {{texttemplate: ''}}, [1]);
            }} else {{
                Plotly.restyle(gd, {{texttemplate: '%{{text}}'}}, [1]);
            }}
        }}

        ajustarNumeros();
        window.addEventListener('resize', ajustarNumeros);

        

        
    }})();
    """
    
    os.makedirs("graficas", exist_ok=True)
    nombre_archivo = f"graficas/calendario_percentiles_{campo}_{idema}.html"
    fig.write_html(
        nombre_archivo,
        include_plotlyjs="cdn",
        full_html=True,
        config={"responsive": True, "displayModeBar": False, "scrollZoom": False},
        default_width="100%",
        default_height="100%",
        div_id=div_id,
        post_script=post_script,
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