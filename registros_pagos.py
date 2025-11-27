# registros_pagos.py — versión estable:
# - Muestra obligaciones completas con AgGrid
# - Registra pagos
# - Guarda comprobante localmente (en el servidor)
# - Registra fila en Google Sheets (sin usar Drive)

import streamlit as st
import pandas as pd
from datetime import datetime, date
from pathlib import Path
from st_aggrid import AgGrid, GridOptionsBuilder

from google.oauth2 import service_account
from googleapiclient.discovery import build

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

# =======================================
# 🔐 GOOGLE SHEETS (solo Sheets, sin Drive)
# =======================================
SHEET_ID = "10gjxfIR3fG7uzJQvDL2lFCKX_drCqyaxm5Xf6XEseIY"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
]

# Orden de columnas tal como está en el Sheet
SHEET_COLUMNS = [
    "FECHA",
    "DOCUMENTO",
    "CAMPAÑA",
    "REFERENCIA",
    "N° COMPROBANTE",
    "VALOR PAGO TOTAL",
    "VALOR PAGO POR CAMPAÑA",
    "FECHA DE PAGO",
    "PUNTO DE PAGO",
    "RESPONSABLE",
    "DETALLE PORTAFOLIO",
    "MES DE APLICACIÓN PAGO",
    "AÑO DE APLICACIÓN PAGO",
    "OBSERVACIONES",
    "CONCILIACIÓN",
    "OBSERVACIÓN",
    "ITEM",
    "CONTACTO COLLECTIONS",
    "OBLIGACION",
    "ARCHIVO COMPROBANTE",
    "TIPO DE PAGO",
    "LINK COMPROBANTE DRIVE",  # quedará vacío por ahora
]

@st.cache_resource
def get_sheets_service():
    """
    Carga las credenciales desde st.secrets["gcp_service_account"]
    y construye el servicio de Google Sheets.
    """
    service_info = dict(st.secrets["gcp_service_account"])
    creds = service_account.Credentials.from_service_account_info(
        service_info,
        scopes=SCOPES,
    )
    sheets_service = build("sheets", "v4", credentials=creds)
    return sheets_service

# =======================================
# ⚙️ FUNCIONES BASE
# =======================================
@st.cache_data(ttl=300)
def leer_excel_local(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"No se encontró el archivo: {path.name}")
    return pd.read_excel(path, dtype=str).fillna("")

def normaliza(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().upper().replace("\n", " ").replace("  ", " ") for c in df.columns]
    return df

# =======================================
# 📥 CARGA DE BASES
# =======================================
try:
    df_hc = normaliza(leer_excel_local(PATH_HC))
    df_consol = normaliza(leer_excel_local(PATH_CONSOL))
    df_bancos = normaliza(leer_excel_local(PATH_BANCOS))
except Exception as e:
    st.error(f"❌ Error al cargar las bases locales: {e}")
    st.stop()

# Detección flexible de columnas
col_doc_asesor = next((c for c in df_hc.columns if "DOCUMENTO" in c or c in ["CC","CÉDULA","CEDULA"]), None)
col_nom_asesor = next((c for c in df_hc.columns if "RESPONSABLE" in c or "NOMBRE" in c), None)
col_cc_deudor = next((c for c in df_consol.columns if "DEUDOR" in c or c in ["CEDULA","CÉDULA","DOCUMENTO"]), None)
col_oblig = next((c for c in df_consol.columns if "OBLIG" in c), None)
col_campana = next((c for c in df_consol.columns if "CAMPA" in c or "CARTERA" in c), None)

if not all([col_doc_asesor, col_nom_asesor, col_cc_deudor, col_oblig, col_campana]):
    st.error("❌ Verifica que las bases tengan: DOCUMENTO/NOMBRE (HC) y CEDULA_DEUDOR/OBLIGACION/CAMPAÑA (Consolidado).")
    st.stop()

# =======================================
# 🧑‍💼 VALIDACIÓN DE ASESOR
# =======================================
st.subheader("Identificación del asesor")
cedula_asesor = st.text_input("👉 Para continuar, digite la cédula de un asesor:")

if cedula_asesor:
    fila_asesor = df_hc[df_hc[col_doc_asesor].astype(str).str.strip() == cedula_asesor.strip()]
    if fila_asesor.empty:
        st.error("No se encontró el asesor en la base HC.")
        st.stop()
    else:
        nombre_asesor = str(fila_asesor.iloc[0][col_nom_asesor]).strip()
        st.success(f"Hola {nombre_asesor}, ¿qué pagos deseas registrar el día de hoy?")
else:
    st.stop()

# =======================================
# 🔎 BÚSQUEDA DE CLIENTE Y OBLIGACIONES
# =======================================
st.markdown("---")
cedula_cliente = st.text_input("🔍 Ingresa la cédula del cliente:")

if cedula_cliente:
    df_cliente = df_consol[df_consol[col_cc_deudor].astype(str).str.strip() == cedula_cliente.strip()].copy()
    if df_cliente.empty:
        st.warning("No se encontraron obligaciones para esta cédula.")
        st.stop()
    else:
        # Mostrar obligaciones completas
        cols_vista = [col_oblig] + [c for c in df_cliente.columns if c != col_oblig]
        df_vista = df_cliente[cols_vista].copy()

        def limpiar_valor(v):
            try:
                if pd.isna(v):
                    return ""
                if isinstance(v, (list, dict, set)):
                    return str(v)
                return str(v).replace("\n", " ").replace("\r", " ").strip()
            except Exception:
                return str(v)

        for c in df_vista.columns:
            df_vista[c] = df_vista[c].apply(limpiar_valor)

        df_vista = df_vista.loc[:, ~df_vista.columns.duplicated()]
        df_vista.reset_index(drop=True, inplace=True)

        st.subheader("Obligaciones encontradas")
        st.caption("Las obligaciones se muestran completas.")
        gb = GridOptionsBuilder.from_dataframe(df_vista)
        gb.configure_pagination(enabled=True)
        gb.configure_default_column(editable=False, resizable=True, wrapText=True, autoHeight=True)
        grid_options = gb.build()

        AgGrid(
            df_vista,
            gridOptions=grid_options,
            height=300,
            theme="balham",
            fit_columns_on_grid_load=True
        )

        opciones_oblig = df_cliente[col_oblig].tolist()
        seleccionadas = st.multiselect(
            "Selecciona las obligaciones a cubrir con este pago:",
            opciones_oblig
        )
        if not seleccionadas:
            st.stop()
else:
    st.stop()

# =======================================
# 🗂️ SELECCIÓN DE CARTERA / CAMPAÑA
# =======================================
st.markdown("---")
st.subheader("Selección de cartera o campaña")

lista_campanas = sorted(df_consol[col_campana].dropna().unique())
campana_seleccionada = st.selectbox("🏷️ Selecciona la cartera/campaña:", lista_campanas)

# =======================================
# 💵 DATOS DEL PAGO
# =======================================
st.markdown("---")
st.subheader("Datos del pago")

referencia = st.text_input("📌 Referencia (número de factura o convenio):")
nro_comprobante = st.text_input("🧾 Número de comprobante o transacción:")
tipo_pago = st.selectbox("💠 Tipo de pago:", ["Pago total", "Pago a cuotas", "Abono", "Novación"])
valor_pago = st.number_input("💰 Valor total del pago:", min_value=0.0, step=1000.0, format="%.0f")
fecha_pago = st.date_input("📅 Fecha de pago:", max_value=date.today(), value=date.today())

# Banco / Punto de pago
col_banco = next((c for c in df_bancos.columns if "BANCO" in c or "PUNTO" in c), df_bancos.columns[0])
banco_sel = st.selectbox("🏦 Banco o punto de pago:", sorted(df_bancos[col_banco].dropna().unique()))

# =======================================
# 📎 CARGA DE COMPROBANTE
# =======================================
comprobante = st.file_uploader(
    "📎 Sube el comprobante de pago (imagen o PDF)",
    type=["jpg", "jpeg", "png", "pdf"]
)

# =======================================
# 🧮 VALIDACIONES Y REGISTRO
# =======================================
if st.button("✅ Registrar pago"):
    errores = []
    if not campana_seleccionada:
        errores.append("Debes seleccionar una cartera o campaña.")
    if not referencia:
        errores.append("Referencia es obligatoria.")
    if not nro_comprobante:
        errores.append("Número de comprobante es obligatorio.")
    if valor_pago <= 0:
        errores.append("El valor del pago debe ser mayor que 0.")
    if not comprobante:
        errores.append("Debes subir el comprobante.")
    if not banco_sel:
        errores.append("Selecciona un banco o punto de pago.")

    if errores:
        st.error("⚠️ Corrige los siguientes errores:\n- " + "\n- ".join(errores))
        st.stop()

    # Validación de duplicados en CSV local
    registro_csv = APP_DIR / "registro_pagos.csv"
    if registro_csv.exists():
        df_reg = pd.read_csv(registro_csv, dtype=str).fillna("")
        existe = df_reg[
            (df_reg["DOCUMENTO"] == str(cedula_cliente)) &
            (df_reg["FECHA DE PAGO"] == fecha_pago.strftime("%Y-%m-%d")) &
            (df_reg["N° COMPROBANTE"] == str(nro_comprobante))
        ]
        if not existe.empty:
            st.warning("⚠️ Este pago ya fue registrado anteriormente (posible duplicado).")
            st.stop()

    # Nombre archivo comprobante (solo como referencia & respaldo local)
    fecha_ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    ext = Path(comprobante.name).suffix
    nombre_archivo = f"{cedula_asesor}_Documento_{cedula_cliente}_{campana_seleccionada}_{fecha_ts}{ext}"

    # Guardado local (respaldo temporal en el servidor de Streamlit)
    carpeta = APP_DIR / "pagos_registrados"
    carpeta.mkdir(exist_ok=True)
    ruta_archivo = carpeta / nombre_archivo
    with open(ruta_archivo, "wb") as f:
        f.write(comprobante.getbuffer())

    # Construir registro base (sin signo $ para que quede numérico en Sheets)
    detalle_portafolio = "PRODUCTO ÚNICO" if len(seleccionadas) == 1 else "MULTIPRODUCTO"
    fecha_registro = datetime.now().strftime("%d/%m/%Y")
    mes_aplicacion = fecha_pago.strftime("%B").upper()
    anio_aplicacion = fecha_pago.strftime("%Y")

    registro = {
        "FECHA": fecha_registro,
        "DOCUMENTO": str(cedula_cliente),
        "CAMPAÑA": campana_seleccionada,
        "REFERENCIA": referencia,
        "N° COMPROBANTE": str(nro_comprobante),
        "VALOR PAGO TOTAL": f"{valor_pago:.0f}",
        "VALOR PAGO POR CAMPAÑA": f"{valor_pago:.0f}",
        "FECHA DE PAGO": fecha_pago.strftime("%Y-%m-%d"),
        "PUNTO DE PAGO": banco_sel,
        "RESPONSABLE": nombre_asesor,
        "DETALLE PORTAFOLIO": detalle_portafolio,
        "MES DE APLICACIÓN PAGO": mes_aplicacion,
        "AÑO DE APLICACIÓN PAGO": anio_aplicacion,
        "OBSERVACIONES": "",
        "CONCILIACIÓN": "",
        "OBSERVACIÓN": "",
        "ITEM": "",
        "CONTACTO COLLECTIONS": "",
        "OBLIGACION": ", ".join(map(str, seleccionadas)),
        "ARCHIVO COMPROBANTE": nombre_archivo,
        "TIPO DE PAGO": tipo_pago,
        "LINK COMPROBANTE DRIVE": "",  # por ahora vacío
    }

    # Guardar respaldo local en CSV
    df_nuevo = pd.DataFrame([registro])
    if registro_csv.exists():
        df_nuevo.to_csv(registro_csv, mode="a", header=False, index=False)
    else:
        df_nuevo.to_csv(registro_csv, index=False)

    # =======================================
    # 📤 ENVÍO A GOOGLE SHEETS (sin Drive)
    # =======================================
    try:
        sheets_service = get_sheets_service()

        # Fila en el mismo orden que el Sheet
        fila = [[registro[col] for col in SHEET_COLUMNS]]

        sheets_service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range="A1",
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": fila},
        ).execute()

        st.success(f"✅ Pago registrado en Google Sheets para el cliente {cedula_cliente}.")
        st.info("📌 El comprobante se guardó solo como respaldo local en el servidor (no en Drive).")

    except Exception as e:
        st.error(
            "❌ El pago se guardó en el CSV local, pero hubo un problema al escribir en Google Sheets.\n\n"
            f"Detalle técnico Sheets: {e}"
        )

    st.balloons()
