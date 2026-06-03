import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
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

try:
    spreadsheet = conectar()
    sheet = spreadsheet.worksheet("tareas")
except Exception as e:
    st.error("❌ Error conectando con Google Sheets. Intenta recargar la app.")
    st.stop()

# =============================
# BITÁCORA
# =============================
try:
    log_sheet = spreadsheet.worksheet("bitacora")
except:
    log_sheet = spreadsheet.add_worksheet("bitacora", 100, 10)

# =============================
# CACHE
# =============================
@st.cache_data(ttl=60)
def cargar_datos(refresh_key):
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
if "refresh_key" not in st.session_state:
    st.session_state["refresh_key"] = 0

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

def actualizar_estado(id_tarea, nuevo_estado):

    df_local = cargar_datos(st.session_state["refresh_key"])

    fila_index = df_local.index[df_local["id"] == id_tarea]

    if len(fila_index) == 0:
        st.error("No se encontró la tarea")
        return

    fila_excel = fila_index[0] + 2

    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Mapeo de columnas (ajusta si cambiaste orden)
    col_map = {
        "NUEVO": "H",
        "EN PROCESO": "I",
        "EN REVISION": "J",
        "REVISION FINAL": "K",
        "FINALIZADO": "L"
    }

    # 1. Actualizar estado
    sheet.update(f"D{fila_excel}", [[nuevo_estado]])

    # 2. Guardar fecha de etapa
    if nuevo_estado in col_map:
        sheet.update(f"{col_map[nuevo_estado]}{fila_excel}", [[ahora]])

    registrar_bitacora(id_tarea, f"Cambio a {nuevo_estado}")

    st.session_state["refresh_key"] += 1
    
def calcular_tiempos(df):

    # 🛑 Si está vacío → no hacer nada
    if df.empty:
        return df

    ahora = pd.to_datetime(datetime.now())

    # Columnas de fechas
    cols_fechas = [
        "fecha_nuevo",
        "fecha_en_proceso",
        "fecha_en_revision",
        "fecha_revision_final",
        "fecha_finalizado"
    ]

    # Convertir solo si existen
    for col in cols_fechas:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # 🛑 Validar antes de calcular
    if "fecha_nuevo" not in df.columns:
        return df

    # ⏱ Tiempo total
    df["tiempo_total_dias"] = (ahora - df["fecha_nuevo"]).dt.days

    # ⏱ Tiempo por etapa
    df["tiempo_etapa_dias"] = 0

    for i, row in df.iterrows():

        if row["estado"] == "NUEVO":
            inicio = row.get("fecha_nuevo")

        elif row["estado"] == "EN PROCESO":
            inicio = row.get("fecha_en_proceso")

        elif row["estado"] == "EN REVISION":
            inicio = row.get("fecha_en_revision")

        elif row["estado"] == "REVISION FINAL":
            inicio = row.get("fecha_revision_final")

        elif row["estado"] == "FINALIZADO":
            inicio = row.get("fecha_finalizado")

        else:
            inicio = None

        if pd.notnull(inicio):
            df.at[i, "tiempo_etapa_dias"] = (ahora - inicio).days

    return df
    
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
# FILTRO GLOBAL
# =============================
filtro = st.text_input("🔍 Buscar...", placeholder="Ej: Martha, Informe, etc.")

# =============================
# DATA
# =============================
df = cargar_datos(st.session_state["refresh_key"])
if df.empty:
    st.info("📭 No hay tareas registradas aún. Puedes crear una nueva tarea.")

df = calcular_tiempos(df)

if not df.empty:
    df["avance"] = df["estado"].apply(calcular_avance)

# =============================
# DASHBOARD KPIs
# =============================

if not df.empty:

    hoy = pd.to_datetime(datetime.now())

    # 📊 Avance general
    avance_general = int(df["avance"].mean())

    # ⚠️ Tareas vencidas
    df["fecha_compromiso_dt"] = pd.to_datetime(df["fecha_compromiso"], errors="coerce")
    vencidas = df[
        (df["fecha_compromiso_dt"] < hoy) &
        (df["estado"] != "FINALIZADO")
    ].shape[0]

    # 🔄 Tareas en proceso
    en_proceso = df[
        df["estado"].isin(["EN PROCESO","EN REVISION","REVISION FINAL"])
    ].shape[0]

    # 🔥 Alta prioridad
    alta = df[df["prioridad"] == "Alta"].shape[0]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("📊 Avance general", f"{avance_general}%")
    col2.metric("⚠️ Vencidas", vencidas, delta="Crítico" if vencidas > 0 else "OK")
    col3.metric("🔄 En proceso", en_proceso)
    col4.metric("🔥 Alta prioridad", alta)
    
# =============================
# FORMULARIO
# =============================
if st.session_state["form"]:
    with st.form("form_tarea"):

        tarea = st.text_input("Tarea")
        responsables = st.multiselect("Responsables",responsables_lista)
        prioridad = st.selectbox("Prioridad",["Alta","Media","Baja"])
        fecha = st.date_input("Fecha compromiso")

        if st.form_submit_button("Guardar"):
            nuevo_id = f"OPE{len(df)+1:05d}"

            ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            sheet.append_row([
                nuevo_id,
                tarea,
                ", ".join(responsables),
                "NUEVO",
                prioridad,
                ahora,
                str(fecha),
                ahora,   # fecha_nuevo
                "",      # fecha_en_proceso
                "",      # fecha_en_revision
                "",      # fecha_revision_final
                ""       # fecha_finalizado
            ])
        
            registrar_bitacora(nuevo_id, "Creación")

            st.session_state["refresh_key"] += 1

            st.session_state["form"] = False
            st.rerun()

# =============================
# KANBAN (COMPACTO FINAL LIMPIO)
# =============================
if vista == "📌 Kanban":

    # 🛑 VALIDACIÓN PRIMERO
    if df.empty:
        st.warning("No hay tareas para mostrar en el tablero")

    else:
        cols = st.columns(len(estados))

        for i, estado in enumerate(estados):
            with cols[i]:
                st.markdown(f"### {estado}")

                tareas = df[df["estado"] == estado]

                for _, row in tareas.iterrows():

                    # 🎨 Color por prioridad
                    color = {
                        "Alta": "#ff4d4d",
                        "Media": "#ffc107",
                        "Baja": "#4CAF50"
                    }.get(row["prioridad"], "#ccc")

                    # 📌 TRUNCAR SOLO TÍTULO
                    tarea_txt = row["tarea"]
                    if len(tarea_txt) > 35:
                        tarea_txt = tarea_txt[:35] + "..."

                    # 🧩 CARD
                    st.markdown(f"""
                    <div style="
                        border-left:5px solid {color};
                        background-color:#262730;
                        padding:8px;
                        border-radius:8px;
                        margin-bottom:6px;
                        color:white;
                        font-size:13px;
                    ">
                        <b>{row['id']} | {tarea_txt}</b><br>
                        👤 {row['responsable']}<br>
                        📅 {row['fecha_compromiso']}<br>
                        📊 {row['avance']}% | ⏱ {row['tiempo_etapa_dias']}d | ⏳ {row['tiempo_total_dias']}d
                    </div>
                    """, unsafe_allow_html=True)

                    # 🔘 BOTONES
                    colA, colC = st.columns([1,1])

                    # ⬅️
                    if i > 0:
                        if colA.button("⬅️", key=f"back_{row['id']}"):
                            st.session_state["tarea_sel"] = row["id"]
                            st.session_state["modal_open"] = True
                            st.session_state["estado_objetivo"] = estados[i-1]
                   
                    # ➡️
                    if i < len(estados)-1:
                        if colC.button("➡️", key=f"next_{row['id']}"):
                            st.session_state["tarea_sel"] = row["id"]
                            st.session_state["modal_open"] = True
                            st.session_state["estado_objetivo"] = estados[i+1]
                        
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

    # 🔥 INDICADORES VISUALES
    st.markdown(f"### ⏱ Indicadores de tiempo")

    color_etapa = "#28a745" if t['tiempo_etapa_dias'] <= 2 else "#dc3545"
    color_total = "#28a745" if t['tiempo_total_dias'] <= 5 else "#dc3545"

    col_t1, col_t2 = st.columns(2)

    with col_t1:
        st.markdown(f"""
        <div style="background:#f8f9fa;padding:12px;border-radius:10px;text-align:center">
            <b>⏱ Tiempo en etapa</b><br>
            <span style="font-size:22px;color:{color_etapa}">
                {t['tiempo_etapa_dias']} días
            </span>
        </div>
        """, unsafe_allow_html=True)

    with col_t2:
        st.markdown(f"""
        <div style="background:#f8f9fa;padding:12px;border-radius:10px;text-align:center">
            <b>⏳ Tiempo total</b><br>
            <span style="font-size:22px;color:{color_total}">
                {t['tiempo_total_dias']} días
            </span>
        </div>
        """, unsafe_allow_html=True)

    # 🔧 FORMULARIO
    col1, col2 = st.columns(2)

    with col1:
        tarea_edit = st.text_input("Tarea", t["tarea"])

        responsables_actuales = [r.strip() for r in t["responsable"].split(",") if r.strip()]

        responsable_edit = st.multiselect(
            "Responsables",
            responsables_lista,
            default=responsables_actuales
        )

        # 🔥 ESTADO AUTOMÁTICO
        nuevo_estado = st.session_state.get("estado_objetivo", t["estado"])
        st.info(f"Estado a guardar: {nuevo_estado}")

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

    # 💾 GUARDAR CAMBIOS (ACTUALIZADO)
    if st.button("💾 Guardar cambios"):

        nuevo_estado = st.session_state.get("estado_objetivo", t["estado"])

        df_local = cargar_datos(st.session_state["refresh_key"])
        fila_index = df_local.index[df_local["id"] == t["id"]][0] + 2

        # 🔹 Actualizar datos principales
        sheet.update(f"A{fila_index}:G{fila_index}", [[
            t["id"],
            tarea_edit,
            ", ".join(responsable_edit),
            nuevo_estado,
            prioridad_edit,
            t["fecha_creacion"],
            str(fecha_edit)
        ]])

        # 🔹 Actualizar estado + fecha etapa + bitácora
        actualizar_estado(t["id"], nuevo_estado)

        st.success("Cambios guardados")

        # 🔹 Cerrar automático
        st.session_state["modal_open"] = False
        st.session_state["refresh_key"] += 1
        st.rerun()

    # ❌ CERRAR (puedes dejarlo por ahora)
    if st.button("Cerrar"):
        st.session_state["modal_open"] = False

    # 📝 OBSERVACIONES (AÚN SIN INTEGRAR)
    st.markdown("### 📝 Observación")

    obs = st.text_input("Nueva observación")

    if st.button("Guardar observación"):
        registrar_bitacora(t["id"], obs)
        st.success("Guardado")

        st.session_state["refresh_key"] += 1
        st.rerun()

    # 📜 HISTORIAL
    st.markdown("### 📜 Historial")

    logs = pd.DataFrame(log_sheet.get_all_records())

    if not logs.empty:
        logs.columns = ["ID", "Fecha / Hora", "Detalle"]

    hist = logs[logs["ID"] == t["id"]]

    st.dataframe(
        hist.reset_index(drop=True),
        use_container_width=True
    )
