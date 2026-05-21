import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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
sheet = client.open("BD_TAREAS_OPERACIONES").sheet1

# =============================
# CARGAR DATOS
# =============================
data = sheet.get_all_records()
df = pd.DataFrame(data)

# =============================
# CREAR TAREA
# =============================
st.subheader("➕ Nueva tarea")

with st.form("form_tarea"):
    tarea = st.text_input("Nombre de tarea")
    responsable = st.text_input("Responsable")
    estado = st.selectbox("Estado", ["NUEVO", "EN PROCESO", "FINALIZADO"])

    submit = st.form_submit_button("Guardar")

    if submit:
        nuevo_id = f"OPE{len(df)+1:05d}"

        nueva_fila = [nuevo_id, tarea, responsable, estado]

        sheet.append_row(nueva_fila)

        st.success("✅ Tarea creada")
        st.experimental_rerun()

# =============================
# MOSTRAR TABLA
# =============================
st.subheader("📋 Listado de tareas")

data = sheet.get_all_records()
df = pd.DataFrame(data)

st.dataframe(df)
