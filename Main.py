# -*- coding: utf-8 -*-
"""
App de entrenamiento — para Monita
Streamlit. Un solo archivo.
"""

import json
import os
import statistics
from calendar import monthrange
from datetime import date, timedelta

import pandas as pd
import streamlit as st

# ============================================================
# CONFIG GENERAL
# ============================================================

st.set_page_config(page_title="Tu plan, Monita", page_icon="🌱", layout="wide")

ARCHIVO_LOCAL = "registro.json"

# ---- Puerta de acceso (solo si hay clave definida en los secrets) ----------
_CLAVE = ""
try:
    _CLAVE = st.secrets["app"].get("clave", "")
except Exception:
    _CLAVE = ""

if _CLAVE:
    if "acceso_ok" not in st.session_state:
        st.session_state.acceso_ok = False
    if not st.session_state.acceso_ok:
        st.title("Hola Monita")
        ingresada = st.text_input("Clave", type="password")
        if ingresada and ingresada == _CLAVE:
            st.session_state.acceso_ok = True
            st.rerun()
        elif ingresada:
            st.error("No es esa.")
        st.stop()

COLOR_1 = "#7C4D8B"
COLOR_2 = "#E8A0BF"
COLOR_3 = "#F5EAF2"

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: #FFFDFE; }}
    h1, h2, h3 {{ color: {COLOR_1}; }}
    .caja {{
        background-color: {COLOR_3};
        border-left: 6px solid {COLOR_2};
        padding: 16px 20px;
        border-radius: 8px;
        margin-bottom: 14px;
    }}
    .caja-fuerte {{
        background-color: {COLOR_1};
        color: white;
        padding: 18px 22px;
        border-radius: 10px;
        margin-bottom: 14px;
    }}
    .caja-fuerte h3 {{ color: white; margin-top: 0; }}
    .chiquito {{ font-size: 0.86rem; color: #6B5B66; }}

    /* calendario */
    .cal-wrap {{ display:grid; grid-template-columns: repeat(7, 1fr); gap:4px; max-width:420px; }}
    .cal-h {{ text-align:center; font-size:0.72rem; color:#8A7A85; padding:4px 0; }}
    .cal-d {{
        text-align:center; font-size:0.82rem; padding:7px 0;
        border-radius:8px; background:#F7F3F6; color:#4A3F46;
    }}
    .cal-vacia {{ background:transparent; }}
    .cal-regla {{ background:{COLOR_1}; color:white; font-weight:600; }}
    .cal-prevista {{ background:transparent; border:2px dashed {COLOR_2}; color:{COLOR_1}; }}
    .cal-hoy {{ box-shadow: 0 0 0 2px #4A3F46 inset; }}
    .leyenda {{ font-size:0.78rem; color:#6B5B66; margin-top:10px; }}
    .pill {{ display:inline-block; width:12px; height:12px; border-radius:4px; vertical-align:-1px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ============================================================
# 1. CALENDARIO REAL (UPC 2026-2) — FECHAS REFERENCIALES
# ============================================================
# Las fechas son una guía, no una cárcel. Si una semana se corre, se corre.

BLOQUES = [
    {
        "nombre": "Vacaciones — bloque fuerte",
        "inicio": date(2026, 7, 27),
        "fin": date(2026, 8, 23),
        "escenario": "vacaciones",
        "resumen": "Es la etapa con más tiempo libre del año, así que es donde más se avanza. "
                   "Acá se entrena más seguido y se aprovecha para dejar bien fina la técnica.",
    },
    {
        "nombre": "Ciclo normal — primera parte",
        "inicio": date(2026, 8, 24),
        "fin": date(2026, 10, 4),
        "escenario": "semestre",
        "resumen": "Empiezan las clases. Bajamos a 3 días fijos y el objetivo cambia: "
                   "ya no es entrenar más, es que cada sesión rinda más.",
    },
    {
        "nombre": "Parciales — semanas suaves",
        "inicio": date(2026, 10, 5),
        "fin": date(2026, 10, 18),
        "escenario": "examenes",
        "resumen": "Parciales UPC del 11 al 18 de octubre. Acá la prioridad son los exámenes. "
                   "El gym baja a 1 o 2 días cortitos, solo para no perder lo ganado.",
    },
    {
        "nombre": "Ciclo normal — segunda parte",
        "inicio": date(2026, 10, 19),
        "fin": date(2026, 11, 29),
        "escenario": "semestre",
        "resumen": "Segunda ola de progreso, la más larga del año. Acá es donde se ven los cambios "
                   "de verdad si se sostiene.",
    },
    {
        "nombre": "Finales — cierre del año",
        "inicio": date(2026, 11, 30),
        "fin": date(2026, 12, 15),
        "escenario": "examenes",
        "resumen": "Finales del 6 al 15 de diciembre. Mismo esquema que parciales: 1 o 2 días, "
                   "cortito, sin exigirte. Cerramos el año sin desgastarte.",
    },
]

FIN_MACRO = BLOQUES[-1]["fin"]
INICIO_MACRO = BLOQUES[0]["inicio"]

# ============================================================
# 2. RUTINAS POR ESCENARIO
# ============================================================
# "Esfuerzo" está escrito en cristiano: cuántas reps te deberían sobrar.

ESFUERZO = {
    "pesado_suave": "Te deben sobrar 2-3 reps (no lo lleves al límite)",
    "pesado_medio": "Te deben sobrar 2 reps",
    "pesado_duro": "Te debe sobrar 1 rep, máximo 2",
    "maquina": "Casi al límite: te sobra 1 rep o ninguna",
    "maquina_suave": "Te debe sobrar 1 rep",
    "facil": "Cómodo: te sobran 3-4 reps",
    "cardio": "Ritmo en el que todavía podrías hablar entrecortado",
}

CARDIO_PIERNA = ("Caminadora en pendiente o escaladora", "20-25 min", ESFUERZO["cardio"], "—")
CARDIO_CORTO = ("Caminadora en pendiente (opcional)", "15-20 min", ESFUERZO["cardio"], "—")

RUTINAS = {
    "vacaciones": {
        # lun, mar, mié, jue, sáb
        "dias_semana": [0, 1, 2, 3, 5],
        "dias": [
            {
                "titulo": "Día 1 — Cuádriceps (parte de adelante de la pierna)",
                "dia_sugerido": "Lunes",
                "ejercicios": [
                    ("Sentadilla", "4 x 8", ESFUERZO["pesado_suave"], "2:30 a 3 min"),
                    ("Prensa", "4 x 8-10", ESFUERZO["pesado_medio"], "2 min"),
                    ("Extensión de cuádriceps", "4 x 8", ESFUERZO["maquina"], "60-90 seg"),
                    CARDIO_PIERNA,
                ],
                "nota": "La sentadilla es el ejercicio más técnico de todo el plan. "
                        "Si un día no la sientes bien, baja peso y hazla limpia, sin drama. "
                        "El cardio va al final, nunca antes de la pierna.",
            },
            {
                "titulo": "Día 2 — Espalda y bíceps",
                "dia_sugerido": "Martes",
                "ejercicios": [
                    ("Jalón al pecho / dominadas asistidas", "4 x 8-10", ESFUERZO["pesado_medio"], "2 min"),
                    ("Remo en máquina o mancuerna", "4 x 10", ESFUERZO["pesado_duro"], "90 seg a 2 min"),
                    ("Curl de bíceps", "3 x 10-12", ESFUERZO["maquina"], "60-90 seg"),
                    CARDIO_CORTO,
                ],
                "nota": "Día corto, de los más llevaderos de la semana.",
            },
            {
                "titulo": "Día 3 — Glúteo y femoral (la prioridad del plan)",
                "dia_sugerido": "Miércoles",
                "ejercicios": [
                    ("Peso muerto rumano", "4 x 8", ESFUERZO["pesado_suave"], "2:30 a 3 min"),
                    ("Hip thrust (o puente de glúteo si hay cola)", "4 x 8", ESFUERZO["pesado_medio"], "2:30 min"),
                    ("Curl femoral en máquina", "4 x 10-12", ESFUERZO["maquina"], "60-90 seg"),
                    ("Patada de glúteo en polea", "3 x 12-15", ESFUERZO["maquina_suave"], "60-90 seg"),
                    ("Hiperextensión con mancuerna", "3 x 10-12", ESFUERZO["maquina_suave"], "60 seg"),
                    ("Elevación de piernas colgada", "3 x 12-15", ESFUERZO["maquina_suave"], "60 seg"),
                    ("Plancha o rueda abdominal", "3 x 30-40 seg", ESFUERZO["maquina_suave"], "60 seg"),
                    CARDIO_PIERNA,
                ],
                "nota": "Este es EL día. Si una semana solo pudieras entrenar una vez, sería esta.",
            },
            {
                "titulo": "Día 4 — Pecho y bíceps",
                "dia_sugerido": "Jueves",
                "ejercicios": [
                    ("Press de banca (barra, mancuerna o máquina)", "4 x 8-10", ESFUERZO["pesado_medio"], "2 min"),
                    ("Aperturas o press inclinado", "3 x 10-12", ESFUERZO["maquina_suave"], "90 seg"),
                    ("Curl martillo", "3 x 10-12", ESFUERZO["maquina"], "60 seg"),
                    ("Elevación de piernas colgada", "3 x 12-15", ESFUERZO["maquina_suave"], "60 seg"),
                    ("Plancha o rueda abdominal", "3 x 30-40 seg", ESFUERZO["maquina_suave"], "60 seg"),
                    CARDIO_CORTO,
                ],
                "nota": "El día más liviano. Sirve para no perder lo del tren superior.",
            },
            {
                "titulo": "Día 5 — Extra de glúteo/femoral (opcional)",
                "dia_sugerido": "Sábado",
                "ejercicios": [
                    ("Hip thrust", "4 x 10", ESFUERZO["pesado_medio"], "2:30 min"),
                    ("Curl femoral en máquina", "4 x 12", ESFUERZO["maquina"], "60-90 seg"),
                    ("Patada de glúteo en polea", "3 x 15", ESFUERZO["maquina_suave"], "60 seg"),
                    CARDIO_PIERNA,
                ],
                "nota": "Este día es 100% opcional. Si el sábado se da, se usa acá o solo para cardio. "
                        "Si no se da, la semana igual está completa y bien hecha.",
            },
        ],
    },
    "semestre": {
        # lun, mar, mié
        "dias_semana": [0, 1, 2],
        "dias": [
            {
                "titulo": "Día 1 — Cuádriceps (parte de adelante de la pierna)",
                "dia_sugerido": "Lunes",
                "ejercicios": [
                    ("Sentadilla", "4 x 8", ESFUERZO["pesado_suave"], "2:30 a 3 min"),
                    ("Prensa", "4 x 8-10", ESFUERZO["pesado_medio"], "2 min"),
                    ("Extensión de cuádriceps", "4 x 8", ESFUERZO["maquina"], "60-90 seg"),
                    CARDIO_PIERNA,
                ],
                "nota": "Si el gym está lleno y no hay rack libre, la prensa cubre casi todo lo mismo.",
            },
            {
                "titulo": "Día 2 — Espalda y bíceps",
                "dia_sugerido": "Martes",
                "ejercicios": [
                    ("Jalón al pecho / dominadas asistidas", "4 x 8-10", ESFUERZO["pesado_medio"], "2 min"),
                    ("Remo en máquina o mancuerna", "4 x 10", ESFUERZO["pesado_duro"], "90 seg a 2 min"),
                    ("Curl de bíceps", "3 x 10-12", ESFUERZO["maquina"], "60-90 seg"),
                    ("Aperturas o press de banca (opcional)", "3 x 10-12", ESFUERZO["maquina_suave"], "90 seg"),
                    CARDIO_CORTO,
                ],
                "nota": "El press de banca de acá es lo único que mantiene el pecho en semana de clases. "
                        "Si andas apurada, es lo primero que se recorta.",
            },
            {
                "titulo": "Día 3 — Glúteo y femoral (la prioridad del plan)",
                "dia_sugerido": "Miércoles",
                "ejercicios": [
                    ("Peso muerto rumano", "4 x 8", ESFUERZO["pesado_suave"], "2:30 a 3 min"),
                    ("Hip thrust", "4 x 8", ESFUERZO["pesado_medio"], "2:30 min"),
                    ("Curl femoral en máquina", "4 x 10-12", ESFUERZO["maquina"], "60-90 seg"),
                    ("Patada de glúteo en polea", "3 x 12-15", ESFUERZO["maquina_suave"], "60-90 seg"),
                    ("Elevación de piernas colgada", "3 x 12-15", ESFUERZO["maquina_suave"], "60 seg"),
                    ("Plancha o rueda abdominal", "3 x 30-40 seg", ESFUERZO["maquina_suave"], "60 seg"),
                    CARDIO_PIERNA,
                ],
                "nota": "Con 3 días, este es el que más pesa en el resultado final. "
                        "Si el sábado se da, se repite este día o se hace solo cardio. Nunca algo nuevo.",
            },
        ],
    },
    "examenes": {
        "dias_semana": [0, 3],
        "dias": [
            {
                "titulo": "Día único — lo esencial",
                "dia_sugerido": "El día que puedas (1 o 2 veces en la semana)",
                "ejercicios": [
                    ("Peso muerto rumano", "3 x 8", ESFUERZO["facil"], "2:30 min"),
                    ("Hip thrust", "3 x 8", ESFUERZO["facil"], "2:30 min"),
                    ("Curl femoral en máquina", "3 x 10", ESFUERZO["pesado_medio"], "60-90 seg"),
                    ("Sentadilla o prensa (la que prefieras ese día)", "3 x 8", ESFUERZO["facil"], "2 min"),
                    ("Cardio", "No esta semana", "Descansa de eso", "—"),
                ],
                "nota": "45 minutos y afuera. No trates de compensar en un día lo que no hiciste en la semana: "
                        "eso solo te deja cansada para estudiar y no suma nada.",
            },
        ],
    },
}

# ============================================================
# 3. PERSISTENCIA
# ============================================================
# Intenta guardar en Google Sheets (si hay credenciales en st.secrets).
# Si no las hay, cae a un archivo local. La app funciona en ambos casos.

try:
    import gspread
    from google.oauth2.service_account import Credentials
    GSPREAD_OK = True
except Exception:
    GSPREAD_OK = False

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

ESTRUCTURA_VACIA = {"entrenos": [], "reglas": [], "fecha_regla": None}


@st.cache_resource(show_spinner=False)
def conectar_sheet():
    """Abre el Sheet una sola vez. Devuelve (libro, motivo_del_fallo)."""
    if not GSPREAD_OK:
        return None, "Falta instalar gspread y google-auth (revisa requirements.txt)."
    try:
        cred = dict(st.secrets["gcp_service_account"])
        nombre = st.secrets["app"]["sheet_nombre"]
    except Exception:
        return None, "No hay credenciales configuradas en Secrets."

    try:
        creds = Credentials.from_service_account_info(cred, scopes=SCOPES)
    except Exception as e:
        return None, f"La private_key está mal pegada en Secrets. ({e})"

    try:
        cliente = gspread.authorize(creds)
        libro = cliente.open(nombre)
    except Exception as e:
        nombre_err = type(e).__name__
        if "SpreadsheetNotFound" in nombre_err:
            return None, (f"No encuentro un Sheet llamado «{nombre}». Revisa el nombre exacto "
                          f"y que esté compartido como Editor con el correo de la cuenta "
                          f"de servicio ({cred.get('client_email', '?')}).")
        return None, f"No pude conectar. ({nombre_err}: {e})"

    # gspread 6.x: update() usa (values, range_name). Se pasan por nombre.
    try:
        existentes = [h.title for h in libro.worksheets()]
        if "entrenos" not in existentes:
            h = libro.add_worksheet(title="entrenos", rows=800, cols=2)
            h.update(values=[["fecha", "nota"]], range_name="A1:B1")
        if "reglas" not in existentes:
            h = libro.add_worksheet(title="reglas", rows=200, cols=2)
            h.update(values=[["inicio", "fin"]], range_name="A1:B1")
    except Exception as e:
        return None, f"Conecté, pero no pude crear las pestañas. ({e})"

    return libro, None


LIBRO, MOTIVO_FALLO = conectar_sheet()


def _leer_local():
    if os.path.exists(ARCHIVO_LOCAL):
        try:
            with open(ARCHIVO_LOCAL, "r", encoding="utf-8") as f:
                d = json.load(f)
            base = dict(ESTRUCTURA_VACIA)
            base.update(d)
            return base
        except Exception:
            pass
    return dict(ESTRUCTURA_VACIA)


def _escribir_local():
    try:
        with open(ARCHIVO_LOCAL, "w", encoding="utf-8") as f:
            json.dump(st.session_state.datos, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def cargar_datos():
    if LIBRO is not None:
        try:
            entrenos = [x.strip() for x in LIBRO.worksheet("entrenos").col_values(1)[1:] if x.strip()]
            filas = LIBRO.worksheet("reglas").get_all_values()[1:]
            reglas = []
            for r in filas:
                if r and r[0].strip():
                    reglas.append({
                        "inicio": r[0].strip(),
                        "fin": (r[1].strip() if len(r) > 1 and r[1].strip() else None),
                    })
            return {"entrenos": entrenos, "reglas": reglas, "fecha_regla": None}
        except Exception as e:
            st.warning(f"No pude leer la nube, uso lo guardado en el equipo. ({e})")
    return _leer_local()


def marcar_entreno(fecha_iso):
    if LIBRO is not None:
        try:
            LIBRO.worksheet("entrenos").append_row([fecha_iso, ""])
            return True
        except Exception as e:
            st.error(f"No se pudo guardar: {e}")
            return False
    return _escribir_local()


def borrar_entreno(fecha_iso):
    if LIBRO is not None:
        try:
            hoja = LIBRO.worksheet("entrenos")
            celda = hoja.find(fecha_iso)
            if celda:
                hoja.delete_rows(celda.row)
            return True
        except Exception as e:
            st.error(f"No se pudo borrar: {e}")
            return False
    return _escribir_local()


def guardar_regla(inicio_iso, fin_iso=None):
    if LIBRO is not None:
        try:
            hoja = LIBRO.worksheet("reglas")
            celda = hoja.find(inicio_iso)
            if celda:
                hoja.update_cell(celda.row, 2, fin_iso or "")
            else:
                hoja.append_row([inicio_iso, fin_iso or ""])
            return True
        except Exception as e:
            st.error(f"No se pudo guardar: {e}")
            return False
    return _escribir_local()


def borrar_regla(inicio_iso):
    if LIBRO is not None:
        try:
            hoja = LIBRO.worksheet("reglas")
            celda = hoja.find(inicio_iso)
            if celda:
                hoja.delete_rows(celda.row)
            return True
        except Exception as e:
            st.error(f"No se pudo borrar: {e}")
            return False
    return _escribir_local()


if "datos" not in st.session_state:
    st.session_state.datos = cargar_datos()

datos = st.session_state.datos
datos.setdefault("entrenos", [])
datos.setdefault("reglas", [])

# Compatibilidad con la versión anterior (una sola fecha suelta)
if datos.get("fecha_regla") and not any(r["inicio"] == datos["fecha_regla"] for r in datos["reglas"]):
    datos["reglas"].append({"inicio": datos["fecha_regla"], "fin": None})
    datos["fecha_regla"] = None

# ============================================================
# 4. FECHAS Y LÓGICA DE BLOQUES
# ============================================================

NOMBRE_DIA = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIA_CORTO = ["L", "M", "M", "J", "V", "S", "D"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "setiembre", "octubre", "noviembre", "diciembre"]


def fecha_bonita(f):
    return f"{NOMBRE_DIA[f.weekday()]} {f.day} de {MESES[f.month - 1]}"


def lunes_de(f):
    return f - timedelta(days=f.weekday())


def bloque_de(f):
    for b in BLOQUES:
        if b["inicio"] <= f <= b["fin"]:
            return b
    if f < INICIO_MACRO:
        return BLOQUES[0]
    return None


def semana_dentro_del_bloque(f, bloque):
    dias = (f - bloque["inicio"]).days
    total = (bloque["fin"] - bloque["inicio"]).days + 1
    return max(1, dias // 7 + 1), max(1, (total + 6) // 7)


def exigencia_de_la_semana(sem, total_sem, escenario):
    if escenario == "examenes":
        return ("Semana suave", "Nada cerca del límite. Te deben sobrar 3-4 reps siempre.")
    if sem == 1:
        return ("Reacomodo", "Semana de volver al ritmo. Sin récords, sin apuro.")
    if sem == total_sem:
        return ("Bajada", "Última del bloque: quita 1 serie de los ejercicios de máquina y llega entera al siguiente.")
    if sem >= total_sem - 1:
        return ("Semana fuerte", "El punto más exigente. Acá sí se aprieta un poco.")
    return ("Progreso", "Sube un poquito el peso o una rep respecto a la semana pasada.")


# ============================================================
# 5. CICLO — CÁLCULOS
# ============================================================

DURACION_REGLA_DEF = 5


def reglas_ordenadas():
    fechas = []
    for r in datos["reglas"]:
        try:
            fechas.append((date.fromisoformat(r["inicio"]),
                           date.fromisoformat(r["fin"]) if r.get("fin") else None))
        except Exception:
            continue
    return sorted(fechas, key=lambda x: x[0])


def stats_ciclo():
    """Devuelve (largo_promedio, min, max, n_ciclos). None si no alcanza el dato."""
    ini = [a for a, _ in reglas_ordenadas()]
    if len(ini) < 2:
        return None
    difs = [(ini[i + 1] - ini[i]).days for i in range(len(ini) - 1)]
    difs = [d for d in difs if 15 <= d <= 90]  # descarta registros raros
    if not difs:
        return None
    return (round(statistics.mean(difs)), min(difs), max(difs), len(difs))


def dias_de_regla_registrados():
    """Set de todos los días que estuvo con la regla."""
    dias = set()
    for ini, fin in reglas_ordenadas():
        f = fin if fin else ini + timedelta(days=DURACION_REGLA_DEF - 1)
        d = ini
        while d <= f and (d - ini).days < 15:
            dias.add(d)
            d += timedelta(days=1)
    return dias


def ventana_prevista():
    """Rango estimado de la próxima regla. Ancho según qué tan irregular sea."""
    ini = [a for a, _ in reglas_ordenadas()]
    if not ini:
        return None
    s = stats_ciclo()
    if s is None:
        return None
    prom, mn, mx, _ = s
    ultimo = ini[-1]
    centro = ultimo + timedelta(days=prom)
    margen = max(2, (mx - mn) // 2)
    return (centro - timedelta(days=margen), centro + timedelta(days=margen), centro)


# ============================================================
# 6. SIDEBAR Y CABECERA
# ============================================================

with st.sidebar:
    st.markdown("### Tu plan")
    hoy = st.date_input("Ver el plan del día", value=date.today(), format="DD/MM/YYYY")
    st.markdown("---")
    st.markdown(
        "<div class='chiquito'>Las fechas son referencias, no reglas. "
        "Si una semana se corre, se corre y ya. Lo único que importa de verdad "
        "es que la mayoría de semanas se cumplan.</div>",
        unsafe_allow_html=True,
    )
    if st.button("Actualizar datos", use_container_width=True):
        st.session_state.pop("datos", None)
        st.cache_resource.clear()
        st.rerun()

    if LIBRO is None:
        st.caption("Modo local — los datos no se están sincronizando.")
        with st.expander("¿Por qué?"):
            st.caption(MOTIVO_FALLO or "Motivo desconocido.")
    else:
        st.caption("Datos sincronizados.")

bloque = bloque_de(hoy)

if bloque is None:
    st.title("Terminaste el plan, Monita")
    st.markdown(
        "<div class='caja-fuerte'><h3>Se acabó el macrociclo</h3>"
        "Del 27 de julio al 15 de diciembre, completo. Cuando quieras armamos el siguiente."
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

escenario = bloque["escenario"]
sem_actual, sem_totales = semana_dentro_del_bloque(hoy, bloque)
tag_sem, desc_sem = exigencia_de_la_semana(sem_actual, sem_totales, escenario)

st.title("Hola Monita")
st.markdown(
    f"<div class='caja'>Hoy es {fecha_bonita(hoy)}. Estás en <b>{bloque['nombre']}</b>, "
    f"semana {sem_actual} de {sem_totales}.<br>"
    f"<b>{tag_sem}:</b> {desc_sem}</div>",
    unsafe_allow_html=True,
)

tabs = st.tabs([
    "Qué toca hoy",
    "La rutina completa",
    "El mapa del plan",
    "Cómo vas",
    "Tu ciclo",
    "Comida",
    "Dudas de palabras raras",
])

COLS_TABLA = ["Ejercicio", "Series x reps", "Qué tan fuerte", "Descanso entre series"]

# ============================================================
# TAB 1 — QUÉ TOCA HOY
# ============================================================

with tabs[0]:
    rutina = RUTINAS[escenario]
    dias_activos = rutina["dias_semana"]
    wd = hoy.weekday()

    if escenario == "examenes":
        dia_hoy, toca = rutina["dias"][0], True
    elif wd in dias_activos:
        idx = dias_activos.index(wd)
        dia_hoy, toca = rutina["dias"][min(idx, len(rutina["dias"]) - 1)], True
    else:
        dia_hoy, toca = None, False

    if toca:
        st.markdown(
            f"<div class='caja-fuerte'><h3>{dia_hoy['titulo']}</h3>{dia_hoy['nota']}</div>",
            unsafe_allow_html=True,
        )
        st.dataframe(pd.DataFrame(dia_hoy["ejercicios"], columns=COLS_TABLA),
                     use_container_width=True, hide_index=True)
    else:
        st.markdown(
            "<div class='caja-fuerte'><h3>Hoy toca descansar</h3>"
            "En serio. El músculo no crece en el gym, crece descansando. "
            "Un día libre bien tomado vale más que uno forzado.</div>",
            unsafe_allow_html=True,
        )
        st.markdown("**Si igual quieres moverte:** una caminata larga o 20 min de caminadora suave y nada más.")

    st.markdown("---")
    st.markdown("### Marca que entrenaste")
    c1, c2 = st.columns([1, 2])
    with c1:
        if st.button("Sí, entrené hoy", use_container_width=True, type="primary"):
            iso = hoy.isoformat()
            if iso not in datos["entrenos"]:
                if marcar_entreno(iso):
                    datos["entrenos"].append(iso)
                    st.success("Anotado, Makisita. Bien ahí.")
            else:
                st.info("Ese día ya estaba marcado.")
    with c2:
        if hoy.isoformat() in datos["entrenos"]:
            if st.button("Borrar la marca de hoy", use_container_width=True):
                if borrar_entreno(hoy.isoformat()):
                    datos["entrenos"].remove(hoy.isoformat())
                    st.rerun()

# ============================================================
# TAB 2 — RUTINA COMPLETA
# ============================================================

with tabs[1]:
    st.markdown("### Tu rutina, en los tres escenarios de la vida real")
    st.markdown(
        "<div class='caja'>No hay una sola rutina: hay tres, según cuánto tiempo tengas esa semana. "
        "Las tres están bien hechas. La de exámenes no es la versión mala, es la correcta para esa semana.</div>",
        unsafe_allow_html=True,
    )

    etiquetas = {
        "vacaciones": "Vacaciones — 4 o 5 días",
        "semestre": "Ciclo normal — 3 días",
        "examenes": "Exámenes o semanas locas — 1 o 2 días",
    }
    sel = st.radio("Elige el escenario", list(etiquetas.keys()),
                   format_func=lambda k: etiquetas[k],
                   index=list(etiquetas.keys()).index(escenario),
                   horizontal=True)

    if sel == escenario:
        st.success("Este es el escenario en el que estás ahora mismo.")

    for d in RUTINAS[sel]["dias"]:
        with st.expander(f"{d['titulo']}  ·  {d['dia_sugerido']}", expanded=(sel == "examenes")):
            st.dataframe(pd.DataFrame(d["ejercicios"], columns=COLS_TABLA),
                         use_container_width=True, hide_index=True)
            st.markdown(f"<div class='chiquito'>{d['nota']}</div>", unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        "<div class='caja'><b>Sobre los abdominales, para que no te vendan humo:</b> hacer abs "
        "no quema la grasa de la barriga. Eso no existe: la grasa baja de forma general, no por zona. "
        "Los abs igual valen la pena por fuerza de core y por cómo se ve la zona, pero la cintura "
        "la define lo que comes, no las planchas.</div>",
        unsafe_allow_html=True,
    )

# ============================================================
# TAB 3 — MAPA DEL PLAN
# ============================================================

with tabs[2]:
    st.markdown("### De acá a diciembre, todo el mapa")

    filas = []
    for b in BLOQUES:
        filas.append({
            "Etapa": b["nombre"],
            "Desde": fecha_bonita(b["inicio"]).capitalize(),
            "Hasta": fecha_bonita(b["fin"]).capitalize(),
            "Semanas": ((b["fin"] - b["inicio"]).days + 1) // 7,
            "Días por semana": {"vacaciones": "4-5", "semestre": "3", "examenes": "1-2"}[b["escenario"]],
            "": "◀ acá estás" if b is bloque else "",
        })
    st.dataframe(pd.DataFrame(filas), use_container_width=True, hide_index=True)

    for b in BLOQUES:
        with st.expander(b["nombre"], expanded=(b is bloque)):
            st.write(b["resumen"])

    st.markdown("---")
    st.markdown(
        "<div class='caja'><b>Y si entran las prácticas:</b> si en algún momento te toca estudiar "
        "y trabajar a la vez, esas semanas se tratan como semana de exámenes aunque el calendario "
        "diga otra cosa. 1 o 2 días, lo esencial, y punto. El plan se acomoda a tu vida, no al revés.</div>",
        unsafe_allow_html=True,
    )

# ============================================================
# TAB 4 — CÓMO VAS
# ============================================================

with tabs[3]:
    st.markdown("### Cómo vas, Monita")

    entrenos_d = sorted({date.fromisoformat(e) for e in datos["entrenos"]})
    lun = lunes_de(hoy)
    esta_sem = [e for e in entrenos_d if lun <= e <= lun + timedelta(days=6)]
    pasada = [e for e in entrenos_d if lun - timedelta(days=7) <= e < lun]
    meta = {"vacaciones": 4, "semestre": 3, "examenes": 1}[escenario]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Esta semana", f"{len(esta_sem)} / {meta}")
    c2.metric("Semana pasada", len(pasada))
    c3.metric("Total del plan", len([e for e in entrenos_d if e >= INICIO_MACRO]))
    c4.metric("Días hasta cerrar", max(0, (FIN_MACRO - hoy).days))

    st.markdown("#### Avance de esta etapa")
    total_b = (bloque["fin"] - bloque["inicio"]).days + 1
    trans = max(0, min(total_b, (hoy - bloque["inicio"]).days + 1))
    st.progress(trans / total_b)
    st.caption(f"{trans} de {total_b} días de «{bloque['nombre']}». "
               f"Te quedan {max(0, total_b - trans)} días en esta etapa.")

    st.markdown("#### Avance del plan completo")
    total_m = (FIN_MACRO - INICIO_MACRO).days + 1
    trans_m = max(0, min(total_m, (hoy - INICIO_MACRO).days + 1))
    st.progress(trans_m / total_m)
    st.caption(f"{round(trans_m / total_m * 100)}% del camino de julio a diciembre.")

    if len(esta_sem) >= meta:
        st.success("Semana cumplida. Ya está, lo demás es bonus. Bien hecho, bb.")
    elif len(esta_sem) > 0:
        st.info(f"Vas {len(esta_sem)}. Te faltan {meta - len(esta_sem)} para cerrar la semana.")

    if entrenos_d:
        st.markdown("#### Últimas 12 semanas")
        conteo = {}
        for e in entrenos_d:
            k = lunes_de(e)
            conteo[k] = conteo.get(k, 0) + 1
        semanas = [lun - timedelta(weeks=i) for i in range(11, -1, -1)]
        st.bar_chart(
            pd.DataFrame({"Entrenos": [conteo.get(s, 0) for s in semanas]},
                         index=[f"{s.day}/{s.month}" for s in semanas]),
            color=COLOR_2,
        )
        with st.expander("Ver todos los días marcados"):
            st.write(", ".join(fecha_bonita(e) for e in reversed(entrenos_d[-40:])))

    st.markdown("---")
    st.markdown(
        "<div class='caja'><b>Lo que es realista esperar de acá a diciembre:</b> vas a ver "
        "mejoras claras de fuerza y de técnica en peso muerto rumano y sentadilla, desarrollo "
        "progresivo del femoral, y mantenimiento del resto. Comiendo por debajo de tu gasto, "
        "eso es exactamente lo esperable y no es poco. Cambiar la composición del cuerpo es cosa "
        "de meses, no de semanas: esto es un tramo del camino, no la meta.</div>",
        unsafe_allow_html=True,
    )

# ============================================================
# TAB 5 — TU CICLO (registro tipo calendario, ciclos irregulares)
# ============================================================

with tabs[4]:
    st.markdown("### Tu ciclo")
    st.markdown(
        "<div class='caja'>Tu cuerpo no rinde igual todos los días del mes, y eso no es falta de "
        "ganas ni de disciplina. Acá vas marcando los días que te viene y la app sola va aprendiendo "
        "tu ritmo. Como el tuyo es irregular, no te va a dar una fecha exacta: te da un rango, "
        "que es lo honesto.</div>",
        unsafe_allow_html=True,
    )

    # ---- Registro rápido -------------------------------------------------
    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("**Marcar que me vino**")
        f_ini = st.date_input("Primer día", value=hoy, format="DD/MM/YYYY", key="ini_regla")
        aun = st.checkbox("Todavía me está viniendo", value=True)
        f_fin = None
        if not aun:
            f_fin = st.date_input("Último día", value=hoy, format="DD/MM/YYYY", key="fin_regla")
        if st.button("Guardar", type="primary", use_container_width=True):
            iso_i = f_ini.isoformat()
            iso_f = f_fin.isoformat() if f_fin else None
            if guardar_regla(iso_i, iso_f):
                existente = next((r for r in datos["reglas"] if r["inicio"] == iso_i), None)
                if existente:
                    existente["fin"] = iso_f
                else:
                    datos["reglas"].append({"inicio": iso_i, "fin": iso_f})
                st.success("Guardado.")
                st.rerun()

    with c2:
        regs = reglas_ordenadas()
        if regs:
            st.markdown("**Lo que llevas registrado**")
            for ini, fin in reversed(regs[-6:]):
                txt = fecha_bonita(ini).capitalize()
                if fin:
                    txt += f" → {fin.day}/{fin.month}"
                cc1, cc2 = st.columns([4, 1])
                cc1.write(txt)
                if cc2.button("✕", key=f"del_{ini.isoformat()}"):
                    if borrar_regla(ini.isoformat()):
                        datos["reglas"] = [r for r in datos["reglas"] if r["inicio"] != ini.isoformat()]
                        st.rerun()
        else:
            st.info("Todavía no hay nada registrado. Marca la última vez que te vino y de ahí "
                    "empieza a tener sentido.")

    st.markdown("---")

    # ---- Calendario ------------------------------------------------------
    dias_regla = dias_de_regla_registrados()
    prev = ventana_prevista()

    cnav1, cnav2 = st.columns([1, 3])
    with cnav1:
        offset = st.number_input("Mes", -6, 6, 0, help="0 es el mes actual")
    mes_base = hoy.month - 1 + int(offset)
    anio_cal = hoy.year + mes_base // 12
    mes_cal = mes_base % 12 + 1

    st.markdown(f"#### {MESES[mes_cal - 1].capitalize()} {anio_cal}")

    primer = date(anio_cal, mes_cal, 1)
    ndias = monthrange(anio_cal, mes_cal)[1]
    celdas = ["<div class='cal-h'>%s</div>" % d for d in DIA_CORTO]
    for _ in range(primer.weekday()):
        celdas.append("<div class='cal-d cal-vacia'></div>")
    for d in range(1, ndias + 1):
        f = date(anio_cal, mes_cal, d)
        clases = ["cal-d"]
        if f in dias_regla:
            clases.append("cal-regla")
        elif prev and prev[0] <= f <= prev[1]:
            clases.append("cal-prevista")
        if f == hoy:
            clases.append("cal-hoy")
        celdas.append(f"<div class='{' '.join(clases)}'>{d}</div>")
    st.markdown(f"<div class='cal-wrap'>{''.join(celdas)}</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='leyenda'><span class='pill' style='background:{COLOR_1}'></span> días marcados "
        f"&nbsp;&nbsp;<span class='pill' style='border:2px dashed {COLOR_2}'></span> rango en el que "
        f"podría venirte</div>",
        unsafe_allow_html=True,
    )

    # ---- Lectura del momento actual --------------------------------------
    st.markdown("---")
    regs = reglas_ordenadas()
    s = stats_ciclo()

    if not regs:
        st.markdown(
            "<div class='caja'>Cuando tengas dos o tres registros, acá te va a aparecer en qué parte "
            "del ciclo estás y qué esperar de tu energía esos días.</div>",
            unsafe_allow_html=True,
        )
    else:
        ultimo = regs[-1][0]
        dia_ciclo = (hoy - ultimo).days + 1
        largo_ref = s[0] if s else 28

        if hoy in dias_regla:
            fase = "Estás con la regla"
            msg = ("Si te sientes mal, no entrenas y no pasa nada. Si te sientes bien, entrena normal: "
                   "no hay ninguna razón para no hacerlo, y a mucha gente hasta le baja el cólico moverse. "
                   "Tú decides, sin culpa por ninguno de los dos lados.")
        elif dia_ciclo <= largo_ref // 2:
            fase = "Primera mitad"
            msg = ("Suele ser la parte donde mejor te vas a sentir y donde más rinde el cuerpo. "
                   "Si vas a intentar subir peso en el peso muerto rumano o el hip thrust, "
                   "estos días son buen momento.")
        elif dia_ciclo <= largo_ref // 2 + 3:
            fase = "Mitad del ciclo"
            msg = ("Días de buen rendimiento. Un detalle: por el tema hormonal la rodilla y el tobillo "
                   "pueden estar un poquito más laxos, así que en sentadilla cuida que la rodilla no "
                   "se te vaya hacia adentro. Nada alarmante, solo atención.")
        elif dia_ciclo <= largo_ref - 4:
            fase = "Segunda mitad"
            msg = ("Puede que te sientas más pesada, con más calor y más hambre. Es normal. Mantén el "
                   "plan, pero si el peso de siempre se siente más duro, bájalo un poquito y ya.")
        else:
            fase = "Podría venirte pronto"
            msg = ("Acá es donde más se suele sentir la caída: más cansancio, menos paciencia, todo pesa "
                   "más. No midas tu progreso estos días, te da una foto falsa. Deja 3-4 reps en "
                   "recámara en todo y cumple la sesión sin heroísmos.")

        st.markdown(f"<div class='caja-fuerte'><h3>Día {dia_ciclo} — {fase}</h3>{msg}</div>",
                    unsafe_allow_html=True)

        if s:
            prom, mn, mx, n = s
            m1, m2, m3 = st.columns(3)
            m1.metric("Tu ciclo suele durar", f"{prom} días")
            m2.metric("Ha variado entre", f"{mn}-{mx} días")
            m3.metric("Ciclos registrados", n)
            if prev:
                st.caption(f"Según lo que llevas registrado, la próxima podría caer entre el "
                           f"{prev[0].day}/{prev[0].month} y el {prev[1].day}/{prev[1].month}. "
                           f"Es un estimado, no una fecha.")
            if mx - mn > 8:
                st.caption("Tus ciclos varían bastante entre sí, así que el rango es ancho a propósito. "
                           "Mientras más registres, más se va a afinar.")
        else:
            st.caption("Con un registro más ya puedo calcular cada cuánto te viene.")

    st.markdown(
        "<div class='chiquito'>Un aviso honesto: la evidencia sobre programar el entrenamiento según "
        "el ciclo todavía es floja y mixta. Por eso esto no te cambia la rutina, solo te da contexto "
        "para saber cuándo apretar y cuándo no. Y si tomas anticonceptivos hormonales, esta parte "
        "aplica bastante menos.</div>",
        unsafe_allow_html=True,
    )

# ============================================================
# TAB 6 — COMIDA
# ============================================================

with tabs[5]:
    st.markdown("### Comida")
    st.markdown(
        "<div class='caja'>Primero lo importante: acá no hay nada prohibido y no vas a pesar comida "
        "ni contar nada. Es tu primera vez con algo así, y las dietas que arrancan siendo estrictas "
        "son justamente las que se abandonan en tres semanas. La idea es que esto lo puedas sostener "
        "meses, no que sea perfecto una semana.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### La única regla que importa de verdad")
    st.markdown(
        "<div class='caja-fuerte'>En cada una de tus comidas tiene que haber <b>algo de proteína</b> "
        "(pollo, huevo, atún, queso, yogurt griego) y <b>algo de verdura</b>. Todo lo demás se acomoda "
        "solo. Si solo cumples esto y nada más de esta pestaña, ya estás haciendo el 80% del trabajo.</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        "El punto de la proteína es que, cuando comes menos, el cuerpo puede sacar energía de la grasa "
        "o del músculo. La proteína y el gym son lo que le dicen cuál de los dos usar. Por eso insistimos "
        "tanto con eso y tan poco con lo demás."
    )

    st.markdown("#### Cómo armar el plato, sin pesar nada")
    st.dataframe(
        pd.DataFrame([
            ("Proteína", "Del tamaño de la palma de tu mano", "Pollo, huevo, atún, queso, yogurt griego"),
            ("Verdura", "Que ocupe la mitad del plato", "Ensalada, brócoli, zapallito, tomate, la verdura de la sopa"),
            ("Arroz / papa / fideos", "Un puño cerrado", "Sí, entra arroz. No lo vamos a sacar"),
            ("Grasa", "Un chorrito o un puñadito", "Aceite de oliva, almendras, palta si te provoca"),
        ], columns=["Qué", "Cuánto", "Ejemplos"]),
        use_container_width=True, hide_index=True,
    )
    st.caption("Cuatro comidas al día como máximo, que es lo que te funciona. No hay que comer 6 veces "
               "ni desayunar temprano ni nada de eso.")

    st.markdown("---")
    st.markdown("#### Un día normal, así de simple")

    dias_ej = {
        "Día tipo 1": [
            ("Desayuno", "Pan con pollo (el de siempre) + un huevo revuelto + jugo de papaya",
             "El huevo es todo lo que le agregamos. Sube la proteína y te llena más."),
            ("Almuerzo", "Sopa de pollo con harta presa + arroz (un puño)",
             "La sopa te llena con poco. Es de tus mejores aliadas."),
            ("Lonche", "Yogurt griego Vakimu + un puñadito de almendras",
             "Si el yogurt solo te aburre, échale la papaya picada encima."),
            ("Cena", "Pescado blanco a la plancha o al horno + ensalada grande",
             "Frito de vez en cuando también entra, no todos los días."),
        ],
        "Día tipo 2": [
            ("Desayuno", "2 huevos revueltos con queso + pan + café o infusión",
             "El queso te gusta, así que se queda. Es proteína también."),
            ("Almuerzo", "Tallarines verdes con pollo a la plancha + ensalada",
             "Los tallarines verdes se quedan. Solo asegúrate de que haya pollo al lado."),
            ("Lonche", "Yogurt griego o un puñado de almendras",
             "Lo que te provoque ese día."),
            ("Cena", "Pollo al horno + verduras salteadas + papa sancochada",
             "La papa sancochada es la misma papa, solo que rinde mucho más."),
        ],
        "Día tipo 3": [
            ("Desayuno", "Yogurt griego Vakimu + almendras + papaya",
             "El más rápido de todos, para días con clase temprano."),
            ("Almuerzo", "Arroz + pollo + ensalada con aceite de oliva",
             "El almuerzo peruano de siempre. Solo cuidando el tamaño del arroz."),
            ("Lonche", "Pan con queso o con pollo",
             "Un lonche de verdad, no una hoja de lechuga."),
            ("Cena", "Sopa de pollo o crema de verduras + un huevo duro",
             "Cena liviana pero que llena. Buenísima para días de frío."),
        ],
    }
    sel_dia = st.radio("Mira uno", list(dias_ej.keys()), horizontal=True)
    st.dataframe(pd.DataFrame(dias_ej[sel_dia], columns=["Comida", "Qué comes", "Por qué así"]),
                 use_container_width=True, hide_index=True)

    st.markdown(
        "<div class='chiquito'>Estos tres días son ejemplos, no una obligación. Si repites el mismo "
        "esquema toda la semana porque es más fácil, está perfecto — de hecho, suele funcionar mejor.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("---")
    st.markdown("#### Los comodines")
    st.markdown(
        "<div class='caja'>Tienes <b>3 comodines a la semana</b>: pizza hawaiana, papas fritas, torta, "
        "empanada, el cine con canchita y hot dog, lo que sea. No son trampas ni un premio que te ganas: "
        "están puestos en el plan a propósito, porque una dieta sin ellos no la aguanta nadie. "
        "Los usas y sigues como si nada.<br><br>"
        "Un truco que ayuda: si sabes que el sábado hay pizza, ese día almuerza más liviano y con harta "
        "proteína. No es castigo, es que llegues sin hambre de lobo.</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### Cuando te viene el antojo de dulce")
    st.markdown(
        "Esos días previos y durante la regla el antojo de chocolate no es falta de fuerza de voluntad, "
        "es hormonal y le pasa a todas. Pelearte con eso solo termina en comer el triple después. "
        "Lo que sí funciona:"
    )
    st.markdown(
        "- Cómete el dulce, pero **después** de una comida con proteína, no en ayunas. Te llena mucho antes.\n"
        "- Que sea una porción servida en un plato, no la bolsa o la caja entera en la mano.\n"
        "- Yogurt griego con un poco de chocolate o cacao encima tapa el antojo bastante bien y suma proteína.\n"
        "- Si igual comiste torta de más ese día, no compenses al día siguiente. Sigues con tu día normal y ya está."
    )

    st.markdown("#### Cambios chiquitos que rinden más de lo que parece")
    st.dataframe(
        pd.DataFrame([
            ("Tiras de pollo empanizadas", "Al horno o freidora de aire, no en aceite", "Mismo sabor, mucho menos aceite"),
            ("Papa frita", "Papa al horno o sancochada casi siempre; frita como comodín", "Es la misma papa"),
            ("Jugo de papaya", "Papaya en trozos", "Llena más y te dura más el rato"),
            ("Gaseosa", "Agua, agua con limón o infusión fría", "Es el cambio que más rinde de toda la lista"),
            ("Pan con pollo solo", "Pan con pollo + huevo o queso", "Con proteína te aguanta hasta el almuerzo"),
        ], columns=["En vez de", "Prueba", "Por qué"]),
        use_container_width=True, hide_index=True,
    )

    st.markdown("---")
    st.markdown("#### Cómo saber si va bien")
    st.markdown(
        "No te peses todos los días: el peso sube y baja por agua, por la regla, por lo que comiste ayer, "
        "y te vuelve loca. Pésate **una vez por semana, el mismo día y en ayunas**, y mira el mes completo, "
        "no la semana. Bajar entre medio kilo y algo así por semana es un ritmo bueno y sostenible. "
        "Más rápido que eso normalmente significa perder músculo, que es justo lo que estamos evitando."
    )
    st.markdown(
        "<div class='caja'>Y si una semana no baja nada: no pasa nada. Estás entrenando pierna en serio, "
        "y el músculo retiene agua cuando empiezas a entrenar fuerte. La ropa y el espejo te van a contar "
        "la historia mucho antes que la balanza.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<div class='chiquito'>Esto es una guía general para acompañar el entrenamiento, no una "
        "indicación médica ni nutricional personalizada. Si en algún momento te sientes mareada, "
        "sin energía todo el día, o quieres afinarlo de verdad, una consulta con nutricionista lo "
        "ajusta mejor que cualquier app.</div>",
        unsafe_allow_html=True,
    )

# ============================================================
# TAB 7 — GLOSARIO
# ============================================================

with tabs[6]:
    st.markdown("### Palabras que aparecen y que nadie te explicó nunca")

    glosario = [
        ("«Te deben sobrar 2 reps»",
         "Es la forma medible de decir cuánto apretar. Terminas la serie sintiendo que podrías hacer "
         "2 más con buena técnica, y ahí paras. Reemplaza al «hasta que duela», que no significa nada "
         "y cambia según el día que tengas."),
        ("Ejercicio compuesto / pesado",
         "Los que mueven varias articulaciones a la vez: sentadilla, peso muerto rumano, hip thrust, "
         "prensa, press de banca. Cansan todo el cuerpo, no solo el músculo. Por eso en estos nunca "
         "vas al límite y descansas 2:30-3 minutos entre series."),
        ("Ejercicio de máquina / aislamiento",
         "Los que trabajan un músculo solito: curl femoral, extensión de cuádriceps, patada de polea, "
         "curl de bíceps. Cansan poco en general, así que acá sí vale llegar casi al límite. "
         "Con 60-90 segundos de descanso alcanza."),
        ("Volumen",
         "Cuánto trabajo total haces: series por ejercicio, ejercicios por sesión, sesiones por semana. "
         "Más volumen no siempre es mejor; es mejor solo si te recuperas de él."),
        ("Deload / semana suave",
         "Una semana a propósito más fácil, cada 4-6 semanas. No es perder el tiempo: es cuando el "
         "cuerpo termina de asimilar lo anterior. En tu plan las semanas de exámenes cumplen justo "
         "ese rol, así que el calendario de la U te lo regala solo."),
        ("Progresión",
         "Que semana a semana subas algo: un poquito de peso, una rep más, o la misma serie mejor "
         "ejecutada. Las tres cuentan. Y comiendo por debajo de tu gasto, sostener el peso ya es ganar."),
        ("Cardio LISS",
         "El cardio tranquilo y continuo: caminadora en pendiente o escaladora a un ritmo en el que "
         "todavía podrías hablar. Va siempre después de entrenar, nunca antes, para no llegar cansada "
         "a la sentadilla o al peso muerto."),
        ("Por qué el peso muerto rumano aparece siempre",
         "Porque es el que más te va a mover la aguja en glúteo y femoral, que es tu prioridad. "
         "Si algún día tienes que recortar la sesión, ese se queda."),
    ]
    for t, d in glosario:
        with st.expander(t):
            st.write(d)

    st.markdown("---")
    st.markdown(
        "<div class='caja-fuerte'>Y si algún día no tienes ganas, no pasa nada. Esto está armado "
        "para aguantar semanas malas sin romperse. Lo hice para que te sea fácil, no para que sea "
        "una obligación más.<br><br>t lobo, Makisita.</div>",
        unsafe_allow_html=True,
    )
