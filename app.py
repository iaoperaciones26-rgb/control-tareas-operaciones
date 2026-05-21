import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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
sheet = client.open("BD_TAREAS_OPERACIONES").sheet1

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
# CARGAR DATOS
# =============================
data = sheet.get_all_records()
df = pd.DataFrame(data)

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

def actualizar_estado(id_tarea, nuevo_estado):
    registros = sheet.get_all_records()

    for i, fila in enumerate(registros):
        if fila["id"] == id_tarea:
            sheet.update_cell(i + 2, 4, nuevo_estado)
            break

# =============================
# CREAR TAREA
# =============================
st.subheader("➕ Nueva tarea")

with st.form("form_tarea"):
    tarea = st.text_input("Nombre de tarea")
    responsable = st.text_input("Responsable")
    estado = st.selectbox("Estado", estados)

    submit = st.form_submit_button("Guardar")

    if submit:
        nuevo_id = f"OPE{len(df)+1:05d}"
        sheet.append_row([nuevo_id, tarea, responsable, estado])
        st.success("✅ Tarea creada")
        st.rerun()

# =============================
# RECARGAR DATOS
# =============================
data = sheet.get_all_records()
df = pd.DataFrame(data)

if not df.empty:
    df["% avance"] = df["estado"].apply(calcular_avance)

# =============================
# SELECTOR DE VISTA
# =============================
vista = st.radio(
    "Selecciona vista",
    ["📋 Lista", "📌 Kanban"],
    horizontal=True
)

# =============================
# VISTA LISTA (PRO)
# =============================
if vista == "📋 Lista":

    st.subheader("📋 Vista Lista")

    if not df.empty:
        df_view = df.copy()

        # orden columnas
        columnas = ["id", "tarea", "responsable", "estado", "% avance"]
        df_view = df_view[columnas]

        st.dataframe(df_view, use_container_width=True)

# =============================
# VISTA KANBAN
# =============================
else:

    st.subheader("📌 Tablero Kanban")

    cols = st.columns(len(estados))

    for i, estado in enumerate(estados):
        with cols[i]:
            st.markdown(f"### {estado}")

            tareas_estado = df[df["estado"] == estado]

            if tareas_estado.empty:
                st.write("—")
            else:
                for _, row in tareas_estado.iterrows():

                    st.markdown(
                        f"""
                        <div style='
                            background-color:#f0f2f6;
                            padding:10px;
                            margin-bottom:10px;
                            border-radius:10px;
                            border-left:5px solid #4CAF50;
                        '>
                            <b>{row['id']}</b><br>
                            {row['tarea']}<br>
                            👤 {row['responsable']}<br>
                            📊 {row['% avance']}%
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

                    col1, col2 = st.columns(2)

                    if i > 0:
                        if col1.button("⬅️", key=f"b_{row['id']}"):
                            actualizar_estado(row["id"], estados[i - 1])
                            st.rerun()

                    if i < len(estados) - 1:
                        if col2.button("➡️", key=f"n_{row['id']}"):
                            actualizar_estado(row["id"], estados[i + 1])
                            st.rerun()
