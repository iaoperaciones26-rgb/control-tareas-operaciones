import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

st.title("📊 Control Tareas Operaciones")

# Leer credenciales desde secrets
creds_dict = st.secrets["gcp_service_account"]

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)

# Abrir Google Sheets
sheet = client.open("BD_TAREAS_OPERACIONES").sheet1

# Leer datos
data = sheet.get_all_records()

df = pd.DataFrame(data)

st.write(df)
