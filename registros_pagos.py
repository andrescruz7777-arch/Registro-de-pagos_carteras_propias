# registros_pagos.py — versión estable SOLO Google Sheets, sin comprobante
# - Muestra obligaciones completas con AgGrid
# - Registra pagos (sin subir comprobante)
# - Guarda respaldo local en CSV
# - Registra fila en Google Sheets usando requests + access token
# - Valor del pago SIN decimales, visual con separador de miles
# - Medio de pago desde Medios_de_pago.xlsx -> OBSERVACIONES

import streamlit as st
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from st_aggrid import AgGrid, GridOptionsBuilder

from google.oauth2 import service_account
from google.auth.transport.requests import Request as GoogleRequest
import requests

st.set_page_config(
    page_title="Registro de Pagos - Carteras Propias Bogotá",
    layout="centered",
    page_icon="💰",
)
st.title("💰 Bienvenido al registro de pagos de carteras propias Bogotá")

# =======================================
# 📂 RUTAS LOCALES (repositorio raíz)
# =======================================
APP_DIR = Path(__file__).parent.resolve()
PATH_HC = APP_DIR / "HC_Carteras_propias.xlsx"
PATH_CONSOL = APP_DIR / "Consolidado_obligaciones _carteras_propias.xlsx"
PATH_BANCOS = APP_DIR / "Bancos_carteras_propias.xlsx"
PATH_MEDIOS = APP_DIR / "Medios_de_pago.xlsx"

# =======================================
# 🔐 GOOGLE SHEETS
# =======================================
SHEET_ID = "10gjxfIR3fG7uzJQvDL2lFCKX_drCqyaxm5Xf6XEseIY"

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

SHEET_COLUMNS = [
    "FECHA","DOCUMENTO","CAMPAÑA","REFERENCIA","N° COMPROBANTE",
    "VALOR PAGO TOTAL","VALOR PAGO POR CAMPAÑA","FECHA DE PAGO",
    "PUNTO DE PAGO","RESPONSABLE","DETALLE PORTAFOLIO",
    "MES DE APLICACIÓN PAGO","AÑO DE APLICACIÓN PAGO",
    "OBSERVACIONES","CONCILIACIÓN","OBSERVACIÓN","ITEM",
    "CONTACTO COLLECTIONS","OBLIGACION","ARCHIVO COMPROBANTE",
    "TIPO DE PAGO","LINK COMPROBANTE DRIVE"
]

@st.cache_resource
def get_creds():
    service_info = dict(st.secrets["gcp_service_account"])
    return service_account.Credentials.from_service_account_info(
        service_info, scopes=SCOPES
    )

def append_row_to_sheet(registro: dict):
    creds = get_creds()
    if not creds.valid:
        creds.refresh(GoogleRequest())

    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SHEET_ID}/values/A1:append"
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Content-Type": "application/json",
    }
    body = {
        "valueInputOption": "RAW",
        "insertDataOption": "INSERT_ROWS",
        "values": [[registro[col] for col in SHEET_COLUMNS]],
    }

    r = requests.post(url, headers=headers, json=body, timeout=10)
    if not (200 <= r.status_code < 300):
        raise RuntimeError(r.text)

# =======================================
# ⚙️ UTILIDADES
# =======================================
@st.cache_data(ttl=300)
def leer_excel(path: Path):
    return pd.read_excel(path, dtype=str).fillna("")

def normaliza(df):
    df = df.copy()
    df.columns = [c.strip().upper() for c in df.columns]
    return df

# =======================================
# 📥 CARGA DE BASES
# =======================================
df_hc = normaliza(leer_excel(PATH_HC))
df_consol = normaliza(leer_excel(PATH_CONSOL))
df_bancos = normaliza(leer_excel(PATH_BANCOS))
df_medios = normaliza(leer_excel(PATH_MEDIOS))

col_doc_asesor = next(c for c in df_hc.columns if "DOCUMENTO" in c)
col_nom_asesor = next(c for c in df_hc.columns if "NOMBRE" in c or "RESPONSABLE" in c)
col_cc_deudor = next(c for c in df_consol.columns if "DEUDOR" in c or "DOCUMENTO" in c)
col_oblig = next(c for c in df_consol.columns if "OBLIG" in c)
col_campana = next(c for c in df_consol.columns if "CAMPA" in c)
col_banco = df_bancos.columns[0]
col_medio = df_medios.columns[0]

# =======================================
# 🧑‍💼 ASESOR
# =======================================
cedula_asesor = st.text_input("👉 Cédula del asesor:")
if not cedula_asesor:
    st.stop()

fila_asesor = df_hc[df_hc[col_doc_asesor] == cedula_asesor]
if fila_asesor.empty:
    st.error("Asesor no encontrado")
    st.stop()

nombre_asesor = fila_asesor.iloc[0][col_nom_asesor]
st.success(f"Hola {nombre_asesor}")

# =======================================
# 👤 CLIENTE
# =======================================
cedula_cliente = st.text_input("🔍 Cédula del cliente:")
if not cedula_cliente:
    st.stop()

df_cliente = df_consol[df_consol[col_cc_deudor] == cedula_cliente]
if df_cliente.empty:
    st.warning("Sin obligaciones")
    st.stop()

AgGrid(df_cliente, height=300)

seleccionadas = st.multiselect(
    "Obligaciones a cubrir",
    df_cliente[col_oblig].tolist()
)
if not seleccionadas:
    st.stop()

campana = st.selectbox(
    "Campaña",
    sorted(df_consol[col_campana].unique())
)

# =======================================
# 💵 DATOS DEL PAGO
# =======================================
referencia = st.text_input("Referencia")
nro_comprobante = st.text_input("Número de comprobante")
tipo_pago = st.selectbox("Tipo de pago", ["Pago total","Pago a cuotas","Abono","Novación"])

valor_pago = st.number_input(
    "💰 Valor del pago",
    min_value=0,
    step=1000,
    format="%d"
)

# Visual bonito (solo display)
st.caption(f"Valor ingresado: $ {valor_pago:,.0f}".replace(",", "."))

fecha_pago = st.date_input("Fecha de pago", value=date.today())
banco = st.selectbox("Banco / Punto de pago", sorted(df_bancos[col_banco].unique()))
medio_pago = st.selectbox("Medio de pago", sorted(df_medios[col_medio].unique()))

# =======================================
# ✅ REGISTRO
# =======================================
if st.button("✅ Registrar pago"):
    registro = {
        "FECHA": datetime.now().strftime("%d/%m/%Y"),
        "DOCUMENTO": cedula_cliente,
        "CAMPAÑA": campana,
        "REFERENCIA": referencia,
        "N° COMPROBANTE": nro_comprobante,
        "VALOR PAGO TOTAL": valor_pago,
        "VALOR PAGO POR CAMPAÑA": valor_pago,
        "FECHA DE PAGO": fecha_pago.strftime("%Y-%m-%d"),
        "PUNTO DE PAGO": banco,
        "RESPONSABLE": nombre_asesor,
        "DETALLE PORTAFOLIO": "PRODUCTO ÚNICO" if len(seleccionadas)==1 else "MULTIPRODUCTO",
        "MES DE APLICACIÓN PAGO": fecha_pago.strftime("%B").upper(),
        "AÑO DE APLICACIÓN PAGO": fecha_pago.year,
        "OBSERVACIONES": medio_pago,
        "CONCILIACIÓN": "",
        "OBSERVACIÓN": "",
        "ITEM": "",
        "CONTACTO COLLECTIONS": "",
        "OBLIGACION": ", ".join(seleccionadas),
        "ARCHIVO COMPROBANTE": "",
        "TIPO DE PAGO": tipo_pago,
        "LINK COMPROBANTE DRIVE": "",
    }

    append_row_to_sheet(registro)
    st.success("✅ Pago registrado correctamente")
    st.balloons()
