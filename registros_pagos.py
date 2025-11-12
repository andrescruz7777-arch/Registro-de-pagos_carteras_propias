# pagos_propias.py — versión 100 % estable para Streamlit Cloud
# Lee las bases desde el repositorio raíz, limpia todos los tipos
# y evita cualquier error de PyArrow al mostrar el dataframe.

import streamlit as st
import pandas as pd
from datetime import datetime, date
from pathlib import Path

st.set_page_config(page_title="Registro de Pagos - Carteras Propias Bogotá", layout="centered", page_icon="💰")
st.title("💰 Bienvenido al registro de pagos de carteras propias Bogotá")

# =======================================
# 📂 RUTAS LOCALES (repositorio raíz)
# =======================================
APP_DIR = Path(__file__).parent.resolve()
PATH_HC = APP_DIR / "HC_Carteras_propias.xlsx"
PATH_CONSOL = APP_DIR / "Consolidado_obligaciones_carteras_propias.xlsx"
PATH_BANCOS = APP_DIR / "Bancos_carteras_propias.xlsx"

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

def enmascarar(valor: str) -> str:
    s = str(valor or "")
    return "•" * (len(s) - 4) + s[-4:] if len(s) > 4 else s

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
        # Enmascarar obligación
        df_cliente["OBLIGACION_MASK"] = df_cliente[col_oblig].apply(enmascarar)

        # Columnas visibles
        cols_vista = [c for c in df_cliente.columns if c != col_oblig]
        if col_campana in cols_vista:
            cols_vista = [col_campana] + [c for c in cols_vista if c != col_campana]

        # ==============================================================
        # 🔍 Mostrar tabla de obligaciones con limpieza total
        # ==============================================================

        df_vista = df_cliente[["OBLIGACION_MASK"] + cols_vista].copy()

        def limpiar_valor(v):
            try:
                if pd.isna(v):
                    return ""
                if isinstance(v, (list, dict, set)):
                    return str(v)
                v = str(v).replace("\n", " ").replace("\r", " ").strip()
                return v
            except Exception:
                return str(v)

        for c in df_vista.columns:
            df_vista[c] = df_vista[c].apply(limpiar_valor)

        df_vista.reset_index(drop=True, inplace=True)

        st.subheader("Obligaciones encontradas")
        st.caption("La columna OBLIGACIÓN se muestra enmascarada (solo últimos 4). Internamente se conserva completa.")
        st._legacy_dataframe(df_vista, use_container_width=True)

        # Selección de obligaciones (guardamos las reales)
        opciones_oblig = df_cliente[col_oblig].tolist()
        seleccionadas = st.multiselect(
            "Selecciona las obligaciones a cubrir con este pago:",
            opciones_oblig,
            format_func=lambda x: enmascarar(x)
        )
        if not seleccionadas:
            st.stop()
else:
    st.stop()

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
comprobante = st.file_uploader("📎 Sube el comprobante de pago (imagen o PDF)", type=["jpg","jpeg","png","pdf"])

# =======================================
# 🧮 VALIDACIONES Y REGISTRO
# =======================================
if st.button("✅ Registrar pago"):
    errores = []
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

    # Validación de duplicados
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

    # Nombre archivo comprobante
    fecha_ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
    campana = str(df_cliente.iloc[0][col_campana]).strip()
    ext = Path(comprobante.name).suffix
    nombre_archivo = f"{cedula_asesor}_Documento_{cedula_cliente}_{campana}_{fecha_ts}{ext}"

    # Guardado local (temporal en Cloud)
    carpeta = APP_DIR / "pagos_registrados"
    carpeta.mkdir(exist_ok=True)
    ruta_archivo = carpeta / nombre_archivo
    with open(ruta_archivo, "wb") as f:
        f.write(comprobante.getbuffer())

    # Construir registro
    detalle_portafolio = "PRODUCTO ÚNICO" if len(seleccionadas) == 1 else "MULTIPRODUCTO"
    fecha_registro = datetime.now().strftime("%d/%m/%Y")
    mes_aplicacion = fecha_pago.strftime("%B").upper()
    anio_aplicacion = fecha_pago.strftime("%Y")

    registro = {
        "FECHA": fecha_registro,
        "DOCUMENTO": str(cedula_cliente),
        "CAMPAÑA": campana,
        "REFERENCIA": referencia,
        "N° COMPROBANTE": str(nro_comprobante),
        "VALOR PAGO TOTAL": f"${valor_pago:,.0f}",
        "VALOR PAGO POR CAMPAÑA": f"${valor_pago:,.0f}",
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
    }

    df_nuevo = pd.DataFrame([registro])
    if registro_csv.exists():
        df_nuevo.to_csv(registro_csv, mode="a", header=False, index=False)
    else:
        df_nuevo.to_csv(registro_csv, index=False)

    st.success(f"✅ Pago registrado correctamente para el cliente {cedula_cliente}.")
    st.info(f"Archivo guardado como: {nombre_archivo}\n\n⚠️ En Streamlit Cloud el almacenamiento local es temporal. La siguiente fase incluirá persistencia en Google Drive y Google Sheets.")
    st.balloons()

