import streamlit as st
import pandas as pd
import gspread
import streamlit.components.v1 as components
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import io

# 🔥 SIEMPRE PRIMERO
st.set_page_config(layout="wide")

# =============================
# LOGIN STATE
# =============================
if "login_ok" not in st.session_state:
    st.session_state["login_ok"] = False

# =============================
# LOGIN SIMPLE
# =============================
if not st.session_state["login_ok"]:

    st.title("🔐 Acceso al sistema")

    password = st.text_input("Ingrese contraseña", type="password")

    if st.button("Ingresar"):

        if password == "OPE2026":
            st.session_state["login_ok"] = True
            st.rerun()
        else:
            st.error("❌ Contraseña incorrecta")

    st.stop()  # 🔥 bloquea toda la app

# =============================
# APP PRINCIPAL
# =============================
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
    df["tiempo_total_dias"] = (
        ahora - pd.to_datetime(df["fecha_creacion"], errors="coerce")
    ).dt.days

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
# MODAL CREAR TAREA
# =============================
@st.dialog("🆕 Nueva tarea")
def abrir_crear_tarea():

    tarea = st.text_input("Tarea")

    responsables = st.multiselect(
        "Responsables",
        responsables_lista
    )

    prioridad = st.selectbox(
        "Prioridad",
        ["Alta","Media","Baja"]
    )

    fecha = st.date_input("Fecha compromiso")

    # 🔘 BOTONES
    col1, col2 = st.columns(2)

    with col1:
        guardar = st.button("💾 Guardar", use_container_width=True)

    # 💾 GUARDAR
    if guardar:

        if not tarea.strip():
            st.warning("⚠️ Debes ingresar una tarea")
            st.stop()

        # 🔥 GENERAR ID CORRECTO (NO DEPENDE DE FILTRO)
        df_ids = cargar_datos(st.session_state["refresh_key"])
        
        if not df_ids.empty:
            max_id = df_ids["id"].str.replace("OPE", "").astype(int).max()
            nuevo_id = f"OPE{max_id + 1:05d}"
        else:
            nuevo_id = "OPE00001"
            
        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        sheet.append_row([
            nuevo_id,
            tarea,
            ", ".join(responsables),
            "NUEVO",
            prioridad,
            ahora,
            str(fecha),
            ahora,
            "",
            "",
            "",
            ""
        ])

        registrar_bitacora(nuevo_id, "Creación")

        st.session_state["refresh_key"] += 1
        st.session_state["form"] = False

        st.success("Tarea creada")
        st.rerun()
     
# =============================
# HEADER
# =============================
col1, col2 = st.columns([1,2])

with col1:
    if st.button("➕ Nueva tarea"):
        st.session_state["form"] = True

with col2:
    vista = st.radio("",["📋 Lista","📌 Kanban"],horizontal=True)

# 🔥 LLAMADOR MODAL CREAR TAREA
if st.session_state["form"]:
    abrir_crear_tarea()
    st.session_state["form"] = False  # 🔥 RESET AUTOMÁTICO

# =============================
# FILTRO GLOBAL
# =============================
filtro = st.text_input("🔍 Buscar...", placeholder="Tarea o Responsable")

# =============================
# DATA
# =============================
df = cargar_datos(st.session_state["refresh_key"])
df_original = df.copy()

if df.empty:
    st.info("📭 No hay tareas registradas aún. Puedes crear una nueva tarea.")

df = calcular_tiempos(df)

if not df.empty:
    df["avance"] = df["estado"].apply(calcular_avance)

# =============================
# 🔍 FILTRO GLOBAL
# =============================
if filtro:
    filtro_lower = filtro.lower()

    df = df[
        df["tarea"].str.lower().str.contains(filtro_lower, na=False) |
        df["responsable"].str.lower().str.contains(filtro_lower, na=False)
    ]

# =============================
# 📥 DESCARGA INTELIGENTE
# =============================
buffer = io.BytesIO()

logs = pd.DataFrame(log_sheet.get_all_records())

# 🔥 lógica inteligente
if df.empty and not df_original.empty:
    descarga_df = df_original
elif len(df) == len(df_original):
    descarga_df = df_original
else:
    descarga_df = df

with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
    
    descarga_df.to_excel(writer, index=False, sheet_name='Tareas')
    
    if not logs.empty:
        logs.to_excel(writer, index=False, sheet_name='Bitacora')

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
                        if colA.button("⬅️", key=f"back_{row['id']}_{_}"):
                            st.session_state["tarea_sel"] = row["id"]
                            st.session_state["modal_open"] = True
                            st.session_state["estado_objetivo"] = estados[i-1]
                   
                    # ➡️
                    if i < len(estados)-1:
                        if colC.button("➡️", key=f"next_{row['id']}_{_}"):
                            st.session_state["tarea_sel"] = row["id"]
                            st.session_state["modal_open"] = True
                            st.session_state["estado_objetivo"] = estados[i+1]
                        
# =============================
# LISTA
# =============================
else:

    # 🔥 HEADER LISTA + BOTÓN DESCARGA
    col_title, col_btn = st.columns([4,1])

    with col_title:
        st.subheader("📋 Lista de tareas")

    with col_btn:
        st.download_button(
            label="📥 Excel",
            data=buffer.getvalue(),
            file_name=f"control_operaciones_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )    
        
    # 📝 Agregar columna visible de observación
    if "ultima_observacion" in df.columns:
        df["Observación"] = df["ultima_observacion"].apply(
            lambda x: x[:60] + "..." if len(str(x)) > 60 else x
        )
    else:
        df["Observación"] = ""

    columnas_mostrar = [
        "id",
        "tarea",
        "responsable",
        "estado",
        "prioridad",
        "fecha_creacion",
        "fecha_compromiso",
        "avance",
        "Observación"
    ]
    
    df = df[[col for col in columnas_mostrar if col in df.columns]]

    if "avance" in df.columns:
        df["avance"] = df["avance"].apply(lambda x: f"{int(x)}%" if str(x).isdigit() else x)    
    
    # 📅 FORMATEAR FECHAS (SIN HORA)
    for col in ["fecha_creacion", "fecha_compromiso"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")
    
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
# DETALLE (MODAL HÍBRIDO ANCHO)
# =============================
@st.dialog("📌 Detalle de tarea")
def abrir_detalle():

    df_full = cargar_datos(st.session_state["refresh_key"])
    df_full = calcular_tiempos(df_full)
    
    t = df_full[df_full["id"] == st.session_state["tarea_sel"]].iloc[0]

    st.subheader(f"📌 Detalle: {st.session_state['tarea_sel']}")
    
    # =============================
    # 🔥 KPI (INDICADORES ARRIBA)
    # =============================
    st.markdown("### ⏱ Indicadores de tiempo")
    
    col_kpi1, col_kpi2 = st.columns(2)
    
    color_etapa = "#28a745" if t['tiempo_etapa_dias'] <= 2 else "#dc3545"
    color_total = "#28a745" if t['tiempo_total_dias'] <= 5 else "#dc3545"
    
    tiempo_etapa = 0 if pd.isna(t['tiempo_etapa_dias']) else int(t['tiempo_etapa_dias'])
    tiempo_total = 0 if pd.isna(t['tiempo_total_dias']) else int(t['tiempo_total_dias'])
    
    with col_kpi1:
        components.html(f"""
        <div style="background:#262730;padding:16px;border-radius:10px;text-align:center;color:white;">
            <div style="color:#adb5bd;font-size:13px;margin-bottom:6px;">
                ⏱ Tiempo en etapa
            </div>
            <div style="font-size:26px;font-weight:bold;color:{color_etapa};">
                {tiempo_etapa} días
            </div>
        </div>
        """, height=120)
    
    with col_kpi2:
        components.html(f"""
        <div style="background:#262730;padding:16px;border-radius:10px;text-align:center;color:white;">
            <div style="color:#adb5bd;font-size:13px;margin-bottom:6px;">
                ⏳ Tiempo total
            </div>
            <div style="font-size:26px;font-weight:bold;color:{color_total};">
                {tiempo_total} días
            </div>
        </div>
        """, height=120)
    
    st.markdown("---")
    
    # =============================
    # 🧩 INFORMACIÓN + GESTIÓN
    # =============================
    col1, col2 = st.columns(2)

    with col1:
        tarea_edit = st.text_input("Tarea", t["tarea"])

        responsables_actuales = [r.strip() for r in t["responsable"].split(",") if r.strip()]

        responsable_edit = st.multiselect(
            "Responsables",
            responsables_lista,
            default=responsables_actuales
        )

        estado_base = st.session_state.get("estado_objetivo", t["estado"])

        estado_manual = st.selectbox(
            "Estado",
            estados,
            index=estados.index(estado_base)
        )

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

    st.markdown("---")

    # =============================
    # 📝 OBSERVACIÓN (GRANDE)
    # =============================
    st.markdown("### 📝 Observación")
    obs = st.text_area(
        "Ingrese observación (obligatoria)",
        height=120
    )

    st.markdown("---")

    # =============================
    # 📜 HISTORIAL
    # =============================
    st.markdown("### 📜 Historial")
    
    logs = pd.DataFrame(log_sheet.get_all_records())
    
    if logs.empty:
        st.info("📝 Sin historial disponible para esta tarea")
    
    else:
        # 🔒 Asegurar nombres de columnas solo si no vienen correctos
        expected_cols = ["ID", "Fecha / Hora", "Detalle"]
    
        if len(logs.columns) == 3:
            # Normalizar nombres (por si en Sheet están diferentes)
            logs.columns = expected_cols
    
        else:
            st.warning("⚠️ Estructura inesperada en bitácora")
            st.stop()
    
        # 🔍 Filtrar por ID
        hist = logs[logs["ID"] == t["id"]]
    
        if hist.empty:
            st.info("📝 Esta tarea aún no tiene historial")
        else:
            st.dataframe(
                hist.reset_index(drop=True),
                use_container_width=True,
                height=200
            )
    
    st.markdown("<br>", unsafe_allow_html=True)

    # =============================
    # 💾 BOTÓN CENTRADO
    # =============================
    guardar = st.button("💾 Guardar cambios", use_container_width=True)

    # =============================
    # 💾 LÓGICA GUARDAR (TUYA)
    # =============================
    if guardar:

        if not obs.strip():
            st.warning("⚠️ Debes ingresar una observación antes de continuar")
            st.stop()

        nuevo_estado = estado_manual

        df_local = cargar_datos(st.session_state["refresh_key"])
        fila_index = df_local.index[df_local["id"] == t["id"]][0] + 2

        sheet.update(f"A{fila_index}:H{fila_index}", [[
            t["id"],
            tarea_edit,
            ", ".join(responsable_edit),
            nuevo_estado,
            prioridad_edit,
            t["fecha_creacion"],
            str(fecha_edit),
            obs
        ]])

        registrar_bitacora(
            t["id"],
            f"{nuevo_estado} | {obs}"
        )

        st.success("Cambios guardados")

        st.session_state["modal_open"] = False
        st.session_state["refresh_key"] += 1
        st.rerun()


# 🔥 LLAMADOR
if st.session_state["modal_open"]:
    abrir_detalle()
    st.session_state["modal_open"] = False
