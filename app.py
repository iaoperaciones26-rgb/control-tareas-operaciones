import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

st.set_page_config(layout="wide")

st.title("📊 Control Tareas Operaciones")

# =============================
# ESTILO TARJETAS
# =============================
st.markdown("""
<style>
div.stButton > button {
    background-color: #e9ecef;
    color: black;
    border-radius: 12px;
    padding: 15px;
    text-align: left;
    font-size: 14px;
    border: none;
    margin-bottom: 10px;
}
div.stButton > button:hover {
    background-color: #dfe3e6;
}
</style>
""", unsafe_allow_html=True)

# =============================
# CONEXIÓN
# =============================
creds_dict = st.secrets["gcp_service_account"]

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

@st.cache_resource
def conectar():
    client = gspread.authorize(creds)
    return client.open("BD_TAREAS_OPERACIONES")

spreadsheet = conectar()
sheet = spreadsheet.worksheet("tareas")

# BITÁCORA
try:
    log_sheet = spreadsheet.worksheet("bitacora")
except:
    log_sheet = spreadsheet.add_worksheet("bitacora", 100, 10)

# =============================
# CACHE DATOS (CLAVE)
# =============================
@st.cache_data(ttl=5)
def cargar_datos():
    return pd.DataFrame(sheet.get_all_records())

# =============================
# LISTAS
# =============================
responsables_lista = [
    "Herman Jaramillo","Simon Gabela","Sandy Perez","Alexis Cevallos",
    "Stalin Villalva","Andres Proaño","Clara Arteaga","Javier Ruiz",
    "Julio Montenegro","Ivan Rodriguez","Martha Narvaez"
]

estados = [
    "NUEVO","EN PROCESO","EN REVISION","REVISION FINAL","FINALIZADO"
]

# =============================
# SESSION STATE
# =============================
if "form" not in st.session_state:
    st.session_state["form"] = False

if "tarea_sel" not in st.session_state:
    st.session_state["tarea_sel"] = None

# =============================
# FUNCIONES
# =============================
def calcular_avance(estado):
    return {
        "NUEVO":0,"EN PROCESO":25,"EN REVISION":50,
        "REVISION FINAL":75,"FINALIZADO":100
    }.get(estado,0)

def registrar_bitacora(id_tarea, accion):
    log_sheet.append_row([
        id_tarea,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        accion
    ])
    st.cache_data.clear()

def actualizar_estado(id_tarea, nuevo_estado):
    registros = sheet.get_all_records()
    for i, fila in enumerate(registros):
        if fila["id"] == id_tarea:
            time.sleep(0.3)
            sheet.update_cell(i+2,4,nuevo_estado)
            break
    st.cache_data.clear()

# =============================
# DATA
# =============================
df = cargar_datos()

if not df.empty:
    df["avance"] = df["estado"].apply(calcular_avance)

# =============================
# HEADER
# =============================
col1,col2 = st.columns([1,2])

with col1:
    if st.button("➕ Nueva tarea"):
        st.session_state["form"] = True

with col2:
    vista = st.radio("",["📋 Lista","📌 Kanban"],horizontal=True)

# =============================
# FORMULARIO
# =============================
if st.session_state["form"]:

    with st.form("form"):

        tarea = st.text_input("Tarea")
        responsables = st.multiselect("Responsables",responsables_lista)
        prioridad = st.selectbox("Prioridad",["Alta","Media","Baja"])
        fecha = st.date_input("Fecha compromiso")
        estado = st.selectbox("Estado",estados)

        r1 = st.text_input("Revisor 1")
        e1 = st.selectbox("Estado R1",["Pendiente","Validado","Devuelto"])
        r2 = st.text_input("Revisor 2")
        e2 = st.selectbox("Estado R2",["Pendiente","Validado","Devuelto"])
        r3 = st.text_input("Revisor 3")
        e3 = st.selectbox("Estado R3",["Pendiente","Validado","Devuelto"])

        c1,c2 = st.columns(2)

        if c1.form_submit_button("Guardar"):
            nuevo_id = f"OPE{len(df)+1:05d}"

            sheet.append_row([
                nuevo_id,
                tarea,
                ", ".join(responsables),
                estado,
                prioridad,
                datetime.now().strftime("%Y-%m-%d"),
                str(fecha),
                r1,e1,r2,e2,r3,e3
            ])

            registrar_bitacora(nuevo_id,"Creación")
            st.session_state["form"]=False
            st.rerun()

        if c2.form_submit_button("Cancelar"):
            st.session_state["form"]=False
            st.rerun()

# =============================
# KPI
# =============================
st.subheader("📊 Resumen")

hoy = pd.to_datetime(datetime.now().date())
df["fecha_dt"] = pd.to_datetime(df["fecha_compromiso"],errors="coerce")

k1,k2,k3,k4 = st.columns(4)
k1.metric("Total",len(df))
k2.metric("Proceso",len(df[df["estado"]=="EN PROCESO"]))
k3.metric("Finalizadas",len(df[df["estado"]=="FINALIZADO"]))
k4.metric("Vencidas",len(df[(df["fecha_dt"]<hoy)&(df["estado"]!="FINALIZADO")]))

# =============================
# KANBAN
# =============================
if vista=="📌 Kanban":

    cols = st.columns(len(estados))

    for i,estado in enumerate(estados):
        with cols[i]:
            st.markdown(f"### {estado}")

            tareas = df[df["estado"]==estado]

            for _,row in tareas.iterrows():

                color = {
                    "Alta":"#ff4d4d",
                    "Media":"#ffc107",
                    "Baja":"#4CAF50"
                }.get(row["prioridad"],"#ccc")

                if st.button(
                    f"{row['id']}  |  {row['tarea']}\n👤 {row['responsable']}\n⭐ {row['prioridad']}  📅 {row['fecha_compromiso']}  📊 {row['avance']}%",
                    key=f"k{row['id']}",
                    use_container_width=True
                ):
                    st.session_state["tarea_sel"] = row["id"]

                st.markdown(
                    f"<div style='height:6px;background:{color};margin-top:-10px;margin-bottom:10px;border-radius:5px'></div>",
                    unsafe_allow_html=True
                )

                c1,c2 = st.columns(2)

                if i>0:
                    if c1.button("⬅️", key=f"b{row['id']}"):
                        actualizar_estado(row["id"], estados[i-1])
                        st.rerun()

                if i<len(estados)-1:
                    if c2.button("➡️", key=f"n{row['id']}"):
                        actualizar_estado(row["id"], estados[i+1])
                        st.rerun()

# =============================
# LISTA
# =============================
else:
    st.dataframe(df, use_container_width=True)

# =============================
# PANEL DETALLE
# =============================
if st.session_state["tarea_sel"]:

    st.markdown("---")
    st.subheader(f"📌 Detalle: {st.session_state['tarea_sel']}")

    t = df[df["id"] == st.session_state["tarea_sel"]].iloc[0]

    col1, col2 = st.columns(2)

    with col1:
        st.write(f"**Tarea:** {t['tarea']}")
        st.write(f"**Responsables:** {t['responsable']}")
        st.write(f"**Estado:** {t['estado']}")
        st.write(f"**Prioridad:** {t['prioridad']}")
        st.write(f"**Fecha:** {t['fecha_compromiso']}")

    with col2:
        st.write(f"R1: {t['revisor_1']} ({t['estado_r1']})")
        st.write(f"R2: {t['revisor_2']} ({t['estado_r2']})")
        st.write(f"R3: {t['revisor_3']} ({t['estado_r3']})")

    st.markdown("### 📝 Observación")

    obs = st.text_input("Nueva observación")

    if st.button("Guardar observación"):
        registrar_bitacora(t["id"], obs)
        st.success("Guardado")
        st.rerun()

    st.markdown("### 📜 Historial")

    logs = pd.DataFrame(log_sheet.get_all_records())
    hist = logs[logs.iloc[:,0] == t["id"]]

    st.dataframe(hist if not hist.empty else pd.DataFrame())
