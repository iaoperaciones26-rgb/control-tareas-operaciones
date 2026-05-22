import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import time
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(layout="wide")

st.title("📊 Control Tareas Operaciones")

# =============================
# ESTILO TARJETAS + HOVER
# =============================
st.markdown("""
<style>
div.stButton > button {
    background-color: transparent;
    border: none;
}

.card-kanban {
    background-color:#e9ecef;
    padding:15px;
    border-radius:12px;
    margin-bottom:-35px;
    color:black;
    box-shadow: 0 2px 6px rgba(0,0,0,0.1);
    transition: all 0.2s ease-in-out;
}

.card-kanban:hover {
    transform: scale(1.02);
    box-shadow: 0 6px 18px rgba(0,0,0,0.2);
    cursor: pointer;
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
# CACHE
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

if "modal_open" not in st.session_state:
    st.session_state["modal_open"] = False

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
    with st.form("form_tarea"):

        tarea = st.text_input("Tarea")
        responsables = st.multiselect("Responsables",responsables_lista)
        prioridad = st.selectbox("Prioridad",["Alta","Media","Baja"])
        fecha = st.date_input("Fecha compromiso")
        estado = st.selectbox("Estado",estados)

        if st.form_submit_button("Guardar"):
            nuevo_id = f"OPE{len(df)+1:05d}"

            sheet.append_row([
                nuevo_id,
                tarea,
                ", ".join(responsables),
                estado,
                prioridad,
                datetime.now().strftime("%Y-%m-%d"),
                str(fecha)
            ])

            registrar_bitacora(nuevo_id,"Creación")
            st.session_state["form"]=False
            st.rerun()

# =============================
# KANBAN
# =============================
if vista == "📌 Kanban":

    cols = st.columns(len(estados))

    for i, estado in enumerate(estados):
        with cols[i]:
            st.markdown(f"### {estado}")

            tareas = df[df["estado"] == estado]

            for _, row in tareas.iterrows():

                color = {
                    "Alta": "#ff4d4d",
                    "Media": "#ffc107",
                    "Baja": "#4CAF50"
                }.get(row["prioridad"], "#ccc")

                cont = st.container()

                with cont:

                    st.markdown(f"""
                    <div class="card-kanban">
                        <b>{row['id']} | {row['tarea']}</b><br><br>
                        👤 {row['responsable']}<br>
                        ⭐ {row['prioridad']}<br>
                        📅 {row['fecha_compromiso']}<br>
                        📊 {row['avance']}%
                    </div>
                    """, unsafe_allow_html=True)

                    colA, colB, colC = st.columns([1,2,1])

                    if i > 0:
                        if colA.button("⬅️", key=f"back_{row['id']}"):
                            actualizar_estado(row["id"], estados[i-1])
                            st.rerun()

                    if i < len(estados)-1:
                        if colC.button("➡️", key=f"next_{row['id']}"):
                            actualizar_estado(row["id"], estados[i+1])
                            st.rerun()

                    if st.button(" ", key=f"k{row['id']}", use_container_width=True):
                        st.session_state["tarea_sel"] = row["id"]
                        st.session_state["modal_open"] = True

                    st.markdown(
                        f"<div style='height:6px;background:{color};margin-bottom:10px;border-radius:5px'></div>",
                        unsafe_allow_html=True
                    )

# =============================
# LISTA
# =============================
else:

    st.subheader("📋 Lista de tareas")

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_selection(selection_mode="single", use_checkbox=False)

    grid_response = AgGrid(
        df,
        gridOptions=gb.build(),
        update_mode=GridUpdateMode.MODEL_CHANGED,
        fit_columns_on_grid_load=True
    )

    selected = grid_response["selected_rows"]

    if selected is not None and len(selected) > 0:
        fila = selected.iloc[0]
        st.session_state["tarea_sel"] = fila["id"]
        st.session_state["modal_open"] = True

# =============================
# DETALLE
# =============================
if st.session_state["modal_open"]:

    st.markdown("---")
    st.subheader(f"📌 Detalle: {st.session_state['tarea_sel']}")

    t = df[df["id"] == st.session_state["tarea_sel"]].iloc[0]

    col1, col2 = st.columns(2)

    with col1:
        tarea_edit = st.text_input("Tarea", t["tarea"])
        responsable_edit = st.text_input("Responsables", t["responsable"])
        estado_edit = st.selectbox("Estado", estados, index=estados.index(t["estado"]))

    with col2:
        prioridad_edit = st.selectbox(
            "Prioridad",
            ["Alta","Media","Baja"],
            index=["Alta","Media","Baja"].index(t["prioridad"])
        )

        fecha_edit = st.date_input(
            "Fecha compromiso",
            pd.to_datetime(t["fecha_compromiso"], errors="coerce")
        )

    if st.button("💾 Guardar cambios"):

        registros = sheet.get_all_records()

        for i, fila in enumerate(registros):
            if fila["id"] == t["id"]:

                sheet.update(f"A{i+2}:G{i+2}", [[
                    t["id"],
                    tarea_edit,
                    responsable_edit,
                    estado_edit,
                    prioridad_edit,
                    t["fecha_creacion"],
                    str(fecha_edit)
                ]])

                registrar_bitacora(t["id"], f"Cambio a {estado_edit}")
                st.success("Cambios guardados")
                st.cache_data.clear()
                st.rerun()

    if st.button("Cerrar"):
        st.session_state["modal_open"] = False

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
