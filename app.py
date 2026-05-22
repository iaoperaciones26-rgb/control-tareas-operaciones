import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

st.set_page_config(layout="wide")

st.title("📊 Control Tareas Operaciones")

# =============================
# CONEXIÓN
# =============================
creds_dict = st.secrets["gcp_service_account"]

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

sheet = client.open("BD_TAREAS_OPERACIONES").worksheet("tareas")

# BITÁCORA
try:
    log_sheet = client.open("BD_TAREAS_OPERACIONES").worksheet("bitacora")
except:
    log_sheet = client.open("BD_TAREAS_OPERACIONES").add_worksheet("bitacora", 100, 10)

# =============================
# LISTA RESPONSABLES
# =============================
responsables_lista = [
    "Herman Jaramillo",
    "Simon Gabela",
    "Sandy Perez",
    "Alexis Cevallos",
    "Stalin Villalva",
    "Andres Proaño",
    "Clara Arteaga",
    "Javier Ruiz",
    "Julio Montenegro",
    "Ivan Rodriguez",
    "Martha Narvaez"
]

# =============================
# ESTADOS
# =============================
estados = [
    "NUEVO",
    "EN PROCESO",
    "EN REVISION",
    "REVISION FINAL",
    "FINALIZADO"
]

# =============================
# FUNCIONES
# =============================
def calcular_avance(estado):
    mapa = {
        "NUEVO": 0,
        "EN PROCESO": 25,
        "EN REVISION": 50,
        "REVISION FINAL": 75,
        "FINALIZADO": 100
    }
    return mapa.get(estado, 0)

def registrar_bitacora(id_tarea, accion):
    log_sheet.append_row([
        id_tarea,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        accion
    ])

def actualizar_estado(id_tarea, nuevo_estado):
    registros = sheet.get_all_records()

    for i, fila in enumerate(registros):
        if fila["id"] == id_tarea:
            sheet.update_cell(i + 2, 4, nuevo_estado)
            registrar_bitacora(id_tarea, f"Cambio a {nuevo_estado}")
            break

# =============================
# CARGAR DATOS
# =============================
data = sheet.get_all_records()
df = pd.DataFrame(data)

# =============================
# HEADER
# =============================
col1, col2 = st.columns([1, 2])

with col1:
    if st.button("➕ Nueva tarea"):
        st.session_state["mostrar_form"] = True

with col2:
    vista = st.radio("", ["📋 Lista", "📌 Kanban"], horizontal=True)

if "mostrar_form" not in st.session_state:
    st.session_state["mostrar_form"] = False

# =============================
# FORMULARIO
# =============================
if st.session_state["mostrar_form"]:

    st.subheader("➕ Nueva tarea")

    with st.form("form_tarea"):

        tarea = st.text_input("Nombre de tarea")

        responsable = st.selectbox("Responsable", responsables_lista)

        prioridad = st.selectbox("Prioridad", ["Alta", "Media", "Baja"])

        fecha_compromiso = st.date_input("Fecha compromiso")

        estado = st.selectbox("Estado", estados)

        st.markdown("### 👥 Revisores")

        r1 = st.text_input("Revisor 1")
        e1 = st.selectbox("Estado R1", ["Pendiente", "Validado", "Devuelto"])

        r2 = st.text_input("Revisor 2")
        e2 = st.selectbox("Estado R2", ["Pendiente", "Validado", "Devuelto"])

        r3 = st.text_input("Revisor 3")
        e3 = st.selectbox("Estado R3", ["Pendiente", "Validado", "Devuelto"])

        colf1, colf2 = st.columns(2)

        submit = colf1.form_submit_button("Guardar")
        cancelar = colf2.form_submit_button("Cancelar")

        if submit:
            nuevo_id = f"OPE{len(df)+1:05d}"

            sheet.append_row([
                nuevo_id,
                tarea,
                responsable,
                estado,
                prioridad,
                datetime.now().strftime("%Y-%m-%d"),
                str(fecha_compromiso),
                r1, e1,
                r2, e2,
                r3, e3
            ])

            registrar_bitacora(nuevo_id, "Creación de tarea")

            st.success("✅ Tarea creada")
            st.session_state["mostrar_form"] = False
            st.rerun()

        if cancelar:
            st.session_state["mostrar_form"] = False
            st.rerun()

# =============================
# RECARGAR DATOS
# =============================
data = sheet.get_all_records()
df = pd.DataFrame(data)

if not df.empty:
    df["avance"] = df["estado"].apply(calcular_avance)

# =============================
# KPI
# =============================
st.subheader("📊 Resumen general")

total = len(df)
en_proceso = len(df[df["estado"] == "EN PROCESO"])
finalizadas = len(df[df["estado"] == "FINALIZADO"])

hoy = pd.to_datetime(datetime.now().date())
df["fecha_compromiso_dt"] = pd.to_datetime(df["fecha_compromiso"], errors="coerce")

vencidas = len(df[(df["fecha_compromiso_dt"] < hoy) & (df["estado"] != "FINALIZADO")])

k1, k2, k3, k4 = st.columns(4)

k1.metric("Total tareas", total)
k2.metric("En proceso", en_proceso)
k3.metric("Finalizadas", finalizadas)
k4.metric("Vencidas", vencidas)

# =============================
# FILTROS
# =============================
st.subheader("🔍 Filtros")

f1, f2 = st.columns(2)

estado_filtro = f1.selectbox("Estado", ["Todos"] + estados)
resp_filtro = f2.text_input("Responsable")

if estado_filtro != "Todos":
    df = df[df["estado"] == estado_filtro]

if resp_filtro:
    df = df[df["responsable"].str.contains(resp_filtro, case=False, na=False)]

# =============================
# ALERTA SEMÁFORO
# =============================
def semaforo(row):
    fecha = pd.to_datetime(row["fecha_compromiso"], errors="coerce")

    if pd.isnull(fecha):
        return "⚪"

    if fecha < hoy and row["estado"] != "FINALIZADO":
        return "🔴"
    elif (fecha - hoy).days <= 2:
        return "🟡"
    else:
        return "🟢"

df["alerta"] = df.apply(semaforo, axis=1)

# =============================
# VISTA LISTA
# =============================
if vista == "📋 Lista":

    st.subheader("📋 Vista Lista")

    columnas = [
        "alerta",
        "id", "tarea", "responsable",
        "estado", "prioridad",
        "fecha_compromiso", "avance"
    ]

    st.dataframe(df[columnas], use_container_width=True)

# =============================
# VISTA KANBAN
# =============================
else:

    st.subheader("📌 Kanban")

    cols = st.columns(len(estados))

    for i, estado in enumerate(estados):
        with cols[i]:
            st.markdown(f"### {estado}")

            tareas_estado = df[df["estado"] == estado]

            for _, row in tareas_estado.iterrows():

                color_prioridad = {
                    "Alta": "#ff4d4d",
                    "Media": "#ffc107",
                    "Baja": "#4CAF50"
                }

                color = color_prioridad.get(row.get("prioridad", ""), "#cccccc")

                fecha = pd.to_datetime(row.get("fecha_compromiso"), errors="coerce")

                if pd.notnull(fecha):
                    if fecha < hoy and row["estado"] != "FINALIZADO":
                        borde = "3px solid red"
                    else:
                        borde = "1px solid #ddd"
                else:
                    borde = "1px solid #ddd"

                st.markdown(f"""
                <div style='background:#ffffff;
                padding:10px;
                border-radius:10px;
                margin-bottom:10px;
                border-left:8px solid {color};
                border:{borde};
                '>
                <b>{row['id']}</b><br>
                {row['tarea']}<br>
                👤 {row['responsable']}<br>
                ⭐ {row['prioridad']}<br>
                📅 {row['fecha_compromiso']}<br>
                📊 {row['avance']}%
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns(2)

                if i > 0:
                    if c1.button("⬅️", key=f"b_{row['id']}"):
                        actualizar_estado(row["id"], estados[i - 1])
                        st.rerun()

                if i < len(estados) - 1:
                    if c2.button("➡️", key=f"n_{row['id']}"):
                        actualizar_estado(row["id"], estados[i + 1])
                        st.rerun()
