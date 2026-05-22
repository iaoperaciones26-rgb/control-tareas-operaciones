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
        if fila["ID"] == id_tarea:
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
        responsable = st.text_input("Responsable")

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
    df["% avance"] = df["Estado"].apply(calcular_avance)

# =============================
# FILTROS
# =============================
st.subheader("🔍 Filtros")

f1, f2 = st.columns(2)

estado_filtro = f1.selectbox("Estado", ["Todos"] + estados)
resp_filtro = f2.text_input("Responsable")

if estado_filtro != "Todos":
    df = df[df["Estado"] == estado_filtro]

if resp_filtro:
    df = df[df["Responsable"].str.contains(resp_filtro, case=False)]

# =============================
# VISTA LISTA
# =============================
if vista == "📋 Lista":

    st.subheader("📋 Vista Lista")

    columnas = [
        "ID", "Tarea", "Responsable",
        "Estado", "Prioridad",
        "Fecha_Compromiso", "% avance"
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

            tareas_estado = df[df["Estado"] == estado]

            for _, row in tareas_estado.iterrows():

                st.markdown(f"""
                <div style='background:#f0f2f6;padding:10px;border-radius:10px;margin-bottom:10px'>
                <b>{row['ID']}</b><br>
                {row['Tarea']}<br>
                👤 {row['Responsable']}<br>
                ⭐ {row['Prioridad']}<br>
                📅 {row['Fecha_Compromiso']}<br>
                📊 {row['% avance']}%
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns(2)

                if i > 0:
                    if c1.button("⬅️", key=f"b_{row['ID']}"):
                        actualizar_estado(row["ID"], estados[i - 1])
                        st.rerun()

                if i < len(estados) - 1:
                    if c2.button("➡️", key=f"n_{row['ID']}"):
                        actualizar_estado(row["ID"], estados[i + 1])
                        st.rerun()
