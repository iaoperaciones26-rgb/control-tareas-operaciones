import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time

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

def actualizar_estado(id_tarea, nuevo_estado):
    registros = sheet.get_all_records()
    for i, fila in enumerate(registros):
        if fila["id"] == id_tarea:
            time.sleep(0.5)
            sheet.update_cell(i+2,4,nuevo_estado)
            break

# =============================
# DATA
# =============================
data = sheet.get_all_records()
df = pd.DataFrame(data)

# =============================
# HEADER
# =============================
col1,col2 = st.columns([1,2])

with col1:
    if st.button("➕ Nueva tarea"):
        st.session_state["form"]=True

with col2:
    vista = st.radio("",["📋 Lista","📌 Kanban"],horizontal=True)

if "form" not in st.session_state:
    st.session_state["form"]=False

# =============================
# FORMULARIO
# =============================
if st.session_state["form"]:

    st.subheader("Nueva tarea")

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
        guardar = c1.form_submit_button("Guardar")
        cancelar = c2.form_submit_button("Cancelar")

        if guardar:
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

        if cancelar:
            st.session_state["form"]=False
            st.rerun()

# =============================
# RECARGA
# =============================
df = pd.DataFrame(sheet.get_all_records())

if not df.empty:
    df["avance"]=df["estado"].apply(calcular_avance)

# =============================
# KPI
# =============================
st.subheader("Resumen")

hoy = pd.to_datetime(datetime.now().date())
df["fecha_dt"]=pd.to_datetime(df["fecha_compromiso"],errors="coerce")

k1,k2,k3,k4 = st.columns(4)
k1.metric("Total",len(df))
k2.metric("Proceso",len(df[df["estado"]=="EN PROCESO"]))
k3.metric("Finalizadas",len(df[df["estado"]=="FINALIZADO"]))
k4.metric("Vencidas",len(df[(df["fecha_dt"]<hoy)&(df["estado"]!="FINALIZADO")]))

# =============================
# FILTROS
# =============================
f1,f2 = st.columns(2)
estado_f = f1.selectbox("Estado",["Todos"]+estados)
resp_f = f2.text_input("Responsable")

if estado_f!="Todos":
    df=df[df["estado"]==estado_f]

if resp_f:
    df=df[df["responsable"].str.contains(resp_f,case=False,na=False)]

# =============================
# ALERTA
# =============================
def semaforo(row):
    f = pd.to_datetime(row["fecha_compromiso"],errors="coerce")
    if pd.isnull(f): return "⚪"
    if f<hoy and row["estado"]!="FINALIZADO": return "🔴"
    if (f-hoy).days<=2: return "🟡"
    return "🟢"

df["alerta"]=df.apply(semaforo,axis=1)

# =============================
# LISTA
# =============================
if vista=="📋 Lista":

    st.dataframe(df[[
        "alerta","id","tarea","responsable",
        "estado","prioridad","fecha_compromiso","avance"
    ]],use_container_width=True)

# =============================
# KANBAN
# =============================
else:

    cols = st.columns(len(estados))

    for i,estado in enumerate(estados):
        with cols[i]:
            st.markdown(f"### {estado}")

            tareas=df[df["estado"]==estado]

            for _,row in tareas.iterrows():

                color={"Alta":"#ff4d4d","Media":"#ffc107","Baja":"#4CAF50"}
                c=color.get(row["prioridad"],"#ccc")

                fecha=pd.to_datetime(row["fecha_compromiso"],errors="coerce")
                borde="3px solid red" if pd.notnull(fecha) and fecha<hoy and row["estado"]!="FINALIZADO" else "1px solid #ddd"

                obs=st.text_input(f"Obs {row['id']}",key=f"obs{row['id']}")

                st.markdown(f"""
                <div style='background:#e9ecef;padding:10px;border-radius:10px;
                border-left:8px solid {c};border:{borde};color:black'>
                <b>{row['id']}</b><br>
                {row['tarea']}<br>
                👤 {row['responsable']}<br>
                ⭐ {row['prioridad']}<br>
                📅 {row['fecha_compromiso']}<br>
                📊 {row['avance']}%
                </div>
                """,unsafe_allow_html=True)

                c1,c2=st.columns(2)

                if i>0:
                    if c1.button("⬅️",key=f"b{row['id']}"):
                        nuevo=estados[i-1]
                        actualizar_estado(row["id"],nuevo)
                        registrar_bitacora(row["id"],f"{nuevo} | {obs}")
                        st.rerun()

                if i<len(estados)-1:
                    if c2.button("➡️",key=f"n{row['id']}"):
                        nuevo=estados[i+1]
                        actualizar_estado(row["id"],nuevo)
                        registrar_bitacora(row["id"],f"{nuevo} | {obs}")
                        st.rerun()

# =============================
# HISTORIAL
# =============================
st.subheader("📜 Historial")

id_buscar=st.text_input("ID tarea")

if id_buscar:
    logs=pd.DataFrame(log_sheet.get_all_records())
    hist=logs[logs.iloc[:,0]==id_buscar]
    st.write(hist if not hist.empty else "Sin historial")
