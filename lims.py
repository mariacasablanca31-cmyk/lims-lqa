import streamlit as st
import pandas as pd
import psycopg2
from sqlalchemy import create_engine
from datetime import date, datetime
import io
from docxtpl import DocxTemplate
from pathlib import Path
import bcrypt

# ============================================================
# BASE DE DATOS Y ENCRIPTACIÓN (POSTGRESQL - SUPABASE)
# ============================================================
DB_URL = st.secrets["DB_URL"]

def obtener_conexion():
    return psycopg2.connect(DB_URL)

def obtener_engine():
    # SQLAlchemy requiere este prefijo para funcionar con Pandas to_sql
    return create_engine(DB_URL.replace("postgresql://", "postgresql+psycopg2://"))

def ejecutar(conn, query, params=None):
    """Función de ayuda para ejecutar comandos SQL con psycopg2 simulando SQLite"""
    cur = conn.cursor()
    if params:
        cur.execute(query, params)
    else:
        cur.execute(query)
    return cur

def hash_clave(clave_plana):
    return bcrypt.hashpw(clave_plana.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def inicializar_bd():
    conn = obtener_conexion()
    
    ejecutar(conn, '''CREATE TABLE IF NOT EXISTS usuarios (
        id_usuario SERIAL PRIMARY KEY,
        usuario TEXT UNIQUE, password TEXT,
        nombre_real TEXT, rol TEXT)''')
        
    if ejecutar(conn, "SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0:
        ejecutar(conn, "INSERT INTO usuarios (usuario, password, nombre_real, rol) VALUES (%s, %s, %s, %s)", ('admin', hash_clave('admin123'), 'Director / Admin', 'Admin'))
        ejecutar(conn, "INSERT INTO usuarios (usuario, password, nombre_real, rol) VALUES (%s, %s, %s, %s)", ('maria', hash_clave('bio2026'), 'María Casablanca', 'Admin'))
        ejecutar(conn, "INSERT INTO usuarios (usuario, password, nombre_real, rol) VALUES (%s, %s, %s, %s)", ('nadia', hash_clave('tec2026'), 'Nadia (Técnica)', 'Tecnico'))
        ejecutar(conn, "INSERT INTO usuarios (usuario, password, nombre_real, rol) VALUES (%s, %s, %s, %s)", ('andrea', hash_clave('tec2026'), 'Andrea (Técnica)', 'Tecnico'))
    
    ejecutar(conn, '''CREATE TABLE IF NOT EXISTS clientes (
        id_cliente SERIAL PRIMARY KEY,
        cliente TEXT NOT NULL, cuit TEXT, contacto TEXT,
        telefono TEXT, direccion TEXT, email TEXT)''')
    
    ejecutar(conn, '''CREATE TABLE IF NOT EXISTS parametros (
        id_parametro SERIAL PRIMARY KEY,
        nombre TEXT NOT NULL, text_unidad TEXT, metodo TEXT,
        precio REAL, limite_deteccion TEXT, limite_caa TEXT)''')
    
    ejecutar(conn, '''CREATE TABLE IF NOT EXISTS muestras (
        id_muestra SERIAL PRIMARY KEY,
        id_cliente INTEGER, id_manual TEXT NOT NULL,
        tiene_precinto TEXT, codigo_precinto TEXT,
        matriz TEXT, fecha_ingreso TEXT, observaciones TEXT,
        FOREIGN KEY (id_cliente) REFERENCES clientes (id_cliente))''')
    
    ejecutar(conn, '''CREATE TABLE IF NOT EXISTS ordenes_trabajo (
        id_ot SERIAL PRIMARY KEY,
        id_muestra INTEGER, id_parametro INTEGER,
        resultado REAL, responsable TEXT,
        estado TEXT DEFAULT 'Pendiente',
        FOREIGN KEY (id_muestra)   REFERENCES muestras   (id_muestra),
        FOREIGN KEY (id_parametro) REFERENCES parametros (id_parametro))''')
    
    ejecutar(conn, '''CREATE TABLE IF NOT EXISTS historial_cambios (
        id_cambio SERIAL PRIMARY KEY,
        id_ot INTEGER, usuario_modificador TEXT,
        fecha_hora TEXT, valor_anterior REAL,
        valor_nuevo REAL, motivo TEXT,
        FOREIGN KEY (id_ot) REFERENCES ordenes_trabajo (id_ot))''')
    
    ejecutar(conn, '''CREATE TABLE IF NOT EXISTS facturas (
        id_factura SERIAL PRIMARY KEY,
        codigo_vinculacion TEXT UNIQUE, id_cliente INTEGER,
        fecha_lote TEXT, nro_factura_fiuner TEXT,
        estado_pago TEXT DEFAULT 'Pendiente',
        monto_total REAL, gastos_lqa REAL DEFAULT 0,
        FOREIGN KEY (id_cliente) REFERENCES clientes (id_cliente))''')
    
    conn.commit()
    conn.close()

inicializar_bd()

# ============================================================
# CONFIGURACIÓN DE PÁGINA
# ============================================================
st.set_page_config(
    page_title="LIMS LQA - FIUNER",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================
# CSS GLOBAL
# ============================================================
st.markdown("""
<style>
.welcome-banner { background: linear-gradient(135deg, #1e3a5f 0%, #2d6a9f 100%); border-radius: 14px; padding: 1.6rem 2rem; margin-bottom: 1.2rem; }
.welcome-banner h2 { margin:0 0 .3rem 0; font-size:1.35rem; font-weight:700; color:white !important; }
.welcome-banner p  { margin:0; font-size:.88rem; color:rgba(255,255,255,.82); }
.seg-table { width:100%; border-collapse:collapse; font-size:13px; }
.seg-table th { background: #f4f6f8; padding: 9px 14px; text-align: left; font-size: 11px; font-weight: 600; color: #5a6778; text-transform: uppercase; letter-spacing: .05em; border-bottom: 1px solid #e2e6ea; }
.seg-table td { padding:10px 14px; border-bottom:.5px solid #edf0f3; vertical-align:middle; }
.seg-table tr:last-child td { border-bottom:none; }
.seg-table tr:hover td { background:#fafbfc; }
.mid-id  { font-weight:600; font-size:13px; color:#1a2332; }
.mid-sub { font-size:11px; color:#8492a6; margin-top:2px; }
.ensayos-wrap { display:flex; flex-wrap:wrap; gap:5px; }
.tag-ok   { display:inline-flex; align-items:center; gap:4px; font-size:11px; font-weight:600; padding:3px 9px; border-radius:20px; white-space:nowrap; background:#d4edda; color:#155724; border:1px solid #b8dfc4; }
.tag-pend { display:inline-flex; align-items:center; gap:4px; font-size:11px; font-weight:600; padding:3px 9px; border-radius:20px; white-space:nowrap; background:#fce8e8; color:#7b1c1c; border:1px solid #f5b7b7; }
.badge-ok   { display:inline-flex; align-items:center; gap:4px; font-size:11px; font-weight:600; padding:4px 10px; border-radius:20px; background:#d4edda; color:#155724; border:1px solid #b8dfc4; }
.badge-pend { display:inline-flex; align-items:center; gap:4px; font-size:11px; font-weight:600; padding:4px 10px; border-radius:20px; background:#fce8e8; color:#7b1c1c; border:1px solid #f5b7b7; }
.resumen-strip { display:flex; gap:0; margin-bottom:12px; background:#f4f6f8; border-radius:10px; overflow:hidden; border:1px solid #e2e6ea; }
.res-item { flex:1; padding:10px 16px; text-align:center; border-right:1px solid #e2e6ea; }
.res-item:last-child { border-right:none; }
.res-num  { font-size:22px; font-weight:700; }
.res-lbl  { font-size:11px; color:#8492a6; margin-top:1px; }
.mosaic-card { border:1px solid #e2e6ea; border-radius:12px; padding:1.3rem 1rem 1.1rem; text-align:center; cursor:pointer; transition:box-shadow .15s, transform .13s; box-shadow:0 2px 6px rgba(0,0,0,.05); min-height:130px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:.35rem; }
.mosaic-card:hover { box-shadow:0 6px 18px rgba(0,0,0,.10); transform:translateY(-2px); }
.mosaic-emoji { font-size:2.2rem; line-height:1; }
.mosaic-title { font-size:.92rem; font-weight:600; color:#1a2332; margin:0; }
.mosaic-desc  { font-size:.76rem; color:#6b7a8d; margin:0; }
section[data-testid="stSidebar"] { background:#f7f9fc; }
@media (max-width:640px) { .mosaic-card { min-height:110px; padding:.9rem; } .mosaic-emoji { font-size:1.9rem; } .mosaic-title { font-size:.82rem; } .welcome-banner { padding:1.1rem; } .welcome-banner h2 { font-size:1.05rem; } .res-num { font-size:18px; } }
</style>
""", unsafe_allow_html=True)

# ============================================================
# SESIÓN
# ============================================================
for key, val in [('usuario_actual', None), ('rol', None), ('modulo_activo', 'Inicio')]:
    if key not in st.session_state:
        st.session_state[key] = val

# ============================================================
# LOGIN
# ============================================================
if st.session_state['usuario_actual'] is None:
    _, col_c, _ = st.columns([1, 1.2, 1])
    with col_c:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("### 🔒 LIMS LQA — FIUNER")
        st.caption("Laboratorio de Química Ambiental")
        with st.form("login_form"):
            u = st.text_input("Usuario")
            p = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Ingresar al Sistema", use_container_width=True):
                conn = obtener_conexion()
                res  = ejecutar(conn, "SELECT password, nombre_real, rol FROM usuarios WHERE usuario=%s", (u,)).fetchone()
                conn.close()
                
                if res and bcrypt.checkpw(p.encode('utf-8'), res[0].encode('utf-8')):
                    st.session_state['usuario_actual'] = u
                    st.session_state['nombre_real']    = res[1]
                    st.session_state['rol']            = res[2]
                    st.session_state['modulo_activo']  = "Inicio"
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas.")
    st.stop()

# ============================================================
# MÓDULOS DISPONIBLES POR ROL
# ============================================================
MODULOS_ADMIN = {
    "Inicio":                 ("🏠", "Panel principal"),
    "Gestión de Clientes":    ("👥", "Comitentes y contactos"),
    "Parámetros y Precios":   ("🔬", "Catálogo de ensayos"),
    "Recepción de Muestras":  ("💧", "Ingreso y precintos"),
    "Órdenes de Trabajo":     ("📋", "Asignación de análisis"),
    "Carga y Corrección":     ("✏️",  "Resultados y enmiendas"),
    "Consulta de Resultados": ("📊", "Archivo analítico"),
    "Finanzas y Facturación": ("💰", "Panel financiero 80/20"),
    "Generación de Informes": ("📄", "Protocolos Word"),
    "Auditoría (ISO)":        ("🛡️",  "Audit trail ISO 17025"),
    "Gestión de Usuarios":    ("🔐", "Usuarios y contraseñas"),
    "Mi Perfil":              ("👤", "Mis datos y contraseña"),
}
MODULOS_TECNICO = {
    "Inicio":                 ("🏠", "Panel principal"),
    "Carga y Corrección":     ("✏️",  "Resultados y enmiendas"),
    "Consulta de Resultados": ("📊", "Archivo analítico"),
    "Mi Perfil":              ("👤", "Mis datos y contraseña"),
}
modulos = MODULOS_ADMIN if st.session_state['rol'] == 'Admin' else MODULOS_TECNICO

# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("### 🧪 LIMS LQA")
    st.caption(f"*{st.session_state['nombre_real']}* · {st.session_state['rol']}")
    st.divider()
    for nombre_mod, (emoji, _) in modulos.items():
        activo = st.session_state['modulo_activo'] == nombre_mod
        label  = f"{emoji} *{nombre_mod}*" if activo else f"{emoji} {nombre_mod}"
        if st.button(label, key=f"sb_{nombre_mod}", use_container_width=True):
            st.session_state['modulo_activo'] = nombre_mod
            st.rerun()
    st.divider()
    if st.button("🚪 Cerrar Sesión", use_container_width=True):
        st.session_state['usuario_actual'] = None
        st.rerun()

modulo = st.session_state['modulo_activo']

# ============================================================
# HELPERS — tabla de seguimiento
# ============================================================
def render_tabla_seguimiento():
    conn   = obtener_conexion()
    df_seg = pd.read_sql_query("""
        SELECT DISTINCT m.id_muestra, m.id_manual AS muestra, c.cliente AS comitente, m.fecha_ingreso AS fecha, m.matriz
        FROM muestras m
        JOIN clientes c ON m.id_cliente = c.id_cliente
        JOIN ordenes_trabajo ot ON m.id_muestra = ot.id_muestra
        ORDER BY m.fecha_ingreso DESC
    """, conn)

    if df_seg.empty:
        st.info("📭 Aún no hay muestras con ensayos asignados.")
        conn.close()
        return

    total_pendientes, total_completas, cnt_ens_pend, cnt_ens_ok = 0, 0, 0, 0
    filas_html = ""

    for _, fila in df_seg.iterrows():
        id_m   = int(fila['id_muestra'])
        df_ens = pd.read_sql_query("""
            SELECT p.nombre, ot.estado FROM ordenes_trabajo ot
            JOIN parametros p ON ot.id_parametro = p.id_parametro
            WHERE ot.id_muestra = %s ORDER BY p.nombre
        """, conn, params=(id_m,))

        total   = len(df_ens)
        listos  = int((df_ens['estado'] == 'Completado').sum())
        pend    = total - listos
        completa = pend == 0

        cnt_ens_ok   += listos
        cnt_ens_pend += pend
        if completa: total_completas += 1
        else: total_pendientes += 1

        pills = ""
        for _, ens in df_ens.iterrows():
            ok    = ens['estado'] == 'Completado'
            clase = "tag-ok" if ok else "tag-pend"
            icon  = "✅" if ok else "🔴"
            pills += f'<span class="{clase}">{icon} {ens["nombre"]}</span>'

        badge = '<span class="badge-ok">✅ Completo</span>' if completa else f'<span class="badge-pend">🔴 {pend} pendiente{"s" if pend > 1 else ""}</span>'
        filas_html += f"""
        <tr>
          <td><div class="mid-id">{fila['muestra']}</div><div class="mid-sub">{fila['comitente']} · {fila['fecha']}</div></td>
          <td><div class="ensayos-wrap">{pills}</div></td>
          <td style="text-align:center">{badge}</td>
        </tr>"""

    conn.close()
    st.markdown(f"""
    <div class="resumen-strip">
      <div class="res-item"><div class="res-num" style="color:#7b1c1c">{total_pendientes}</div><div class="res-lbl">muestras en curso</div></div>
      <div class="res-item"><div class="res-num" style="color:#155724">{total_completas}</div><div class="res-lbl">muestras completas</div></div>
      <div class="res-item"><div class="res-num" style="color:#7b1c1c">{cnt_ens_pend}</div><div class="res-lbl">ensayos pendientes</div></div>
      <div class="res-item"><div class="res-num" style="color:#155724">{cnt_ens_ok}</div><div class="res-lbl">ensayos realizados</div></div>
    </div>
    <div style="background:white; border:1px solid #e2e6ea; border-radius:12px; overflow:hidden;">
      <table class="seg-table">
        <thead><tr><th style="width:180px">Muestra</th><th>Ensayos asignados</th><th style="width:130px; text-align:center">Estado</th></tr></thead>
        <tbody>{filas_html}</tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)

# ============================================================
# MÓDULO: INICIO
# ============================================================
if modulo == "Inicio":
    hora   = datetime.now().hour
    saludo = "Buenos días" if hora < 12 else ("Buenas tardes" if hora < 19 else "Buenas noches")
    st.markdown(f"""
    <div class="welcome-banner">
      <h2>👋 {saludo}, {st.session_state['nombre_real'].split()[0]}.</h2>
      <p>Sistema LIMS — Laboratorio de Química Ambiental · FIUNER &nbsp;|&nbsp; {date.today().strftime("%d/%m/%Y")}</p>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state['rol'] == 'Admin':
        conn = obtener_conexion()
        n_cli  = ejecutar(conn, "SELECT COUNT(*) FROM clientes").fetchone()[0]
        n_mues = ejecutar(conn, "SELECT COUNT(*) FROM muestras").fetchone()[0]
        n_pend = ejecutar(conn, "SELECT COUNT(*) FROM ordenes_trabajo WHERE estado='Pendiente'").fetchone()[0]
        n_comp = ejecutar(conn, "SELECT COUNT(*) FROM ordenes_trabajo WHERE estado='Completado'").fetchone()[0]
        n_fact = ejecutar(conn, "SELECT COALESCE(SUM(monto_total),0) FROM facturas").fetchone()[0]
        conn.close()
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Clientes", n_cli)
        c2.metric("Muestras", n_mues)
        c3.metric("⏳ Pendientes", n_pend)
        c4.metric("✅ Completados", n_comp)
        c5.metric("💰 Facturado", f"${n_fact:,.0f}")
        st.markdown("<br>", unsafe_allow_html=True)

    st.markdown("#### 🔍 Estado de muestras y ensayos")
    st.caption("Verde = realizado · Rojo = pendiente")
    render_tabla_seguimiento()

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("#### Módulos del sistema")
    mods_grilla = {k: v for k, v in modulos.items() if k != "Inicio"}
    nombres     = list(mods_grilla.keys())
    COLS        = 3
    for i in range(0, len(nombres), COLS):
        grupo = nombres[i: i + COLS]
        cols  = st.columns(COLS)
        for j, nombre_mod in enumerate(grupo):
            emoji, desc = mods_grilla[nombre_mod]
            with cols[j]:
                st.markdown(f"""
                <div class="mosaic-card">
                  <div class="mosaic-emoji">{emoji}</div>
                  <p class="mosaic-title">{nombre_mod}</p>
                  <p class="mosaic-desc">{desc}</p>
                </div>
                """, unsafe_allow_html=True)
                if st.button(f"Ir a {nombre_mod}", key=f"mosaic_{nombre_mod}", use_container_width=True):
                    st.session_state['modulo_activo'] = nombre_mod
                    st.rerun()

# ============================================================
# MÓDULO 1: GESTIÓN DE CLIENTES
# ============================================================
elif modulo == "Gestión de Clientes":
    st.header("👥 Gestión de Clientes")
    conn = obtener_conexion()
    
    tab_nuevo, tab_editar, tab_lista, tab_carga = st.tabs(["➕ Nuevo Cliente", "✏️ Editar / Borrar", "📋 Listado completo", "📥 Carga Masiva (Excel)"])
    
    with tab_nuevo:
        col1, col2 = st.columns([1, 2])
        with col1:
            with st.form("nuevo_cli", clear_on_submit=True):
                nom   = st.text_input("Razón Social *")
                cuit  = st.text_input("CUIT")
                cont  = st.text_input("Contacto")
                dir_c = st.text_input("Dirección")
                email = st.text_input("Email")
                tel   = st.text_input("Teléfono")
                if st.form_submit_button("💾 Guardar Cliente", use_container_width=True):
                    if nom:
                        ejecutar(conn, "INSERT INTO clientes (cliente, cuit, contacto, direccion, email, telefono) VALUES (%s,%s,%s,%s,%s,%s)", (nom, cuit, cont, dir_c, email, tel))
                        conn.commit()
                        st.success("✅ Cliente guardado correctamente.")
                        st.rerun()
                    else:
                        st.warning("⚠️ La razón social es obligatoria.")
                        
    with tab_editar:
        df_cl_edit = pd.read_sql_query("SELECT * FROM clientes", conn)
        if not df_cl_edit.empty:
            opciones_c = [f"{r['id_cliente']} - {r['cliente']}" for _, r in df_cl_edit.iterrows()]
            cli_sel = st.selectbox("Seleccionar Cliente a modificar:", opciones_c)
            id_c_sel = int(cli_sel.split(" - ")[0])
            datos_c = df_cl_edit[df_cl_edit['id_cliente'] == id_c_sel].iloc[0]
            
            col_e1, col_e2 = st.columns([2, 1])
            with col_e1:
                with st.form("editar_cli"):
                    e_nom   = st.text_input("Razón Social *", value=datos_c['cliente'])
                    e_cuit  = st.text_input("CUIT", value=datos_c['cuit'] if pd.notnull(datos_c['cuit']) else "")
                    e_cont  = st.text_input("Contacto", value=datos_c['contacto'] if pd.notnull(datos_c['contacto']) else "")
                    e_dir   = st.text_input("Dirección", value=datos_c['direccion'] if pd.notnull(datos_c['direccion']) else "")
                    e_email = st.text_input("Email", value=datos_c['email'] if pd.notnull(datos_c['email']) else "")
                    e_tel   = st.text_input("Teléfono", value=datos_c['telefono'] if pd.notnull(datos_c['telefono']) else "")
                    
                    if st.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                        if e_nom:
                            ejecutar(conn, "UPDATE clientes SET cliente=%s, cuit=%s, contacto=%s, direccion=%s, email=%s, telefono=%s WHERE id_cliente=%s", (e_nom, e_cuit, e_cont, e_dir, e_email, e_tel, id_c_sel))
                            conn.commit()
                            st.success("✅ Cliente actualizado correctamente.")
                            st.rerun()
                        else:
                            st.warning("⚠️ La razón social no puede quedar vacía.")
            with col_e2:
                st.warning("⚠️ Zona de Peligro")
                if st.button("🗑️ Borrar Cliente", type="primary", use_container_width=True):
                    check = ejecutar(conn, "SELECT COUNT(*) FROM muestras WHERE id_cliente=%s", (id_c_sel,)).fetchone()[0]
                    if check > 0:
                        st.error(f"❌ Imposible borrar: el cliente tiene {check} muestra(s) vinculada(s) en el historial.")
                    else:
                        ejecutar(conn, "DELETE FROM clientes WHERE id_cliente=%s", (id_c_sel,))
                        conn.commit()
                        st.success("✅ Cliente eliminado del sistema.")
                        st.rerun()
        else:
            st.info("📭 No hay clientes para editar.")

    with tab_lista:
        df_cl = pd.read_sql_query("SELECT id_cliente AS ID, cliente AS \"Razón Social\", cuit AS CUIT, contacto AS Contacto, email AS Email FROM clientes", conn)
        st.dataframe(df_cl, use_container_width=True, hide_index=True)
        
    with tab_carga:
        st.info("💡 Descargá la plantilla, completá los datos y subila acá para cargar múltiples clientes a la vez.")
        archivo_excel = st.file_uploader("Subir Plantilla de Clientes (.xlsx)", type=["xlsx"])
        if archivo_excel is not None:
            if st.button("Procesar y Cargar Clientes", type="primary"):
                try:
                    df_nuevos_clientes = pd.read_excel(archivo_excel)
                    df_nuevos_clientes.columns = df_nuevos_clientes.columns.str.strip().str.lower()
                    if 'cuir' in df_nuevos_clientes.columns:
                        df_nuevos_clientes = df_nuevos_clientes.rename(columns={'cuir': 'cuit'})
                    columnas_validas = ['cliente', 'cuit', 'contacto', 'telefono', 'email', 'direccion']
                    df_final = df_nuevos_clientes[columnas_validas]
                    
                    # Para enviar a la nube con Pandas usamos Engine
                    df_final.to_sql('clientes', con=obtener_engine(), if_exists='append', index=False)
                    st.success(f"✅ ¡Se cargaron {len(df_final)} clientes con éxito!")
                except Exception as e:
                    st.error(f"❌ Error al procesar el archivo. Detalle: {e}")
    conn.close()

# ============================================================
# MÓDULO 2: PARÁMETROS Y PRECIOS
# ============================================================
elif modulo == "Parámetros y Precios":
    st.header("🔬 Catálogo Analítico")
    conn = obtener_conexion()
    
    tab_nuevo, tab_editar, tab_lista, tab_importar = st.tabs(["➕ Nuevo Ensayo", "✏️ Editar / Borrar", "📋 Catálogo completo", "📥 Importar masivo"])
    with tab_nuevo:
        col1, col2 = st.columns([1, 2])
        with col1:
            with st.form("nuevo_par", clear_on_submit=True):
                n   = st.text_input("Análisis *")
                u   = st.text_input("Unidad de Medida (Ej: mg/L)")
                m   = st.text_input("Método de Referencia")
                ld  = st.text_input("Límite de Detección (Ej: 0.5)")
                caa = st.text_input("Límite Permitido CAA (Ej: 45.0)")
                p   = st.number_input("Precio ($)", min_value=0.0, step=100.0)
                if st.form_submit_button("💾 Registrar Ensayo", use_container_width=True):
                    if n:
                        ejecutar(conn, "INSERT INTO parametros (nombre, text_unidad, metodo, precio, limite_deteccion, limite_caa) VALUES (%s,%s,%s,%s,%s,%s)", (n, u, m, p, ld, caa))
                        conn.commit()
                        st.success(f"✅ Ensayo *{n}* registrado en el catálogo.")
                        st.rerun()
                    else:
                        st.warning("⚠️ El nombre del análisis es obligatorio.")
                        
    with tab_editar:
        df_par_edit = pd.read_sql_query("SELECT * FROM parametros", conn)
        if not df_par_edit.empty:
            opciones_p = [f"{r['id_parametro']} - {r['nombre']}" for _, r in df_par_edit.iterrows()]
            par_sel = st.selectbox("Seleccionar Ensayo a modificar:", opciones_p)
            id_p_sel = int(par_sel.split(" - ")[0])
            datos_p = df_par_edit[df_par_edit['id_parametro'] == id_p_sel].iloc[0]
            
            col_e1, col_e2 = st.columns([2, 1])
            with col_e1:
                with st.form("editar_par"):
                    e_n   = st.text_input("Análisis *", value=datos_p['nombre'])
                    e_u   = st.text_input("Unidad de Medida", value=datos_p['text_unidad'] if pd.notnull(datos_p['text_unidad']) else "")
                    e_m   = st.text_input("Método", value=datos_p['metodo'] if pd.notnull(datos_p['metodo']) else "")
                    e_ld  = st.text_input("Límite de Detección", value=datos_p['limite_deteccion'] if pd.notnull(datos_p['limite_deteccion']) else "")
                    e_caa = st.text_input("Límite CAA", value=datos_p['limite_caa'] if pd.notnull(datos_p['limite_caa']) else "")
                    e_p   = st.number_input("Precio ($)", min_value=0.0, value=float(datos_p['precio']), step=100.0)
                    
                    if st.form_submit_button("💾 Guardar Cambios", use_container_width=True):
                        if e_n:
                            ejecutar(conn, "UPDATE parametros SET nombre=%s, text_unidad=%s, metodo=%s, precio=%s, limite_deteccion=%s, limite_caa=%s WHERE id_parametro=%s", (e_n, e_u, e_m, e_p, e_ld, e_caa, id_p_sel))
                            conn.commit()
                            st.success("✅ Parámetro actualizado correctamente.")
                            st.rerun()
                        else:
                            st.warning("⚠️ El nombre del análisis no puede quedar vacío.")
            with col_e2:
                st.warning("⚠️ Zona de Peligro")
                if st.button("🗑️ Borrar Ensayo", type="primary", use_container_width=True):
                    check = ejecutar(conn, "SELECT COUNT(*) FROM ordenes_trabajo WHERE id_parametro=%s", (id_p_sel,)).fetchone()[0]
                    if check > 0:
                        st.error(f"❌ Imposible borrar: el ensayo está asignado a {check} orden(es) de trabajo en el historial.")
                    else:
                        ejecutar(conn, "DELETE FROM parametros WHERE id_parametro=%s", (id_p_sel,))
                        conn.commit()
                        st.success("✅ Ensayo eliminado del catálogo.")
                        st.rerun()
        else:
            st.info("📭 No hay ensayos para editar.")

    with tab_lista:
        df_pp = pd.read_sql_query("SELECT nombre AS \"Determinación\", text_unidad AS \"Unidad\", metodo AS \"Método\", limite_deteccion AS \"LD\", limite_caa AS \"CAA\", precio AS \"Precio ($)\" FROM parametros", conn)
        st.dataframe(df_pp, use_container_width=True, hide_index=True)
        
    with tab_importar:
        st.info("💡 Subí un archivo de Excel (.xlsx).")
        archivo_excel = st.file_uploader("Subir Catálogo en Excel", type=["xlsx"])
        if archivo_excel is not None:
            try:
                df_nuevos = pd.read_excel(archivo_excel)
                st.write(f"Se encontraron {len(df_nuevos)} ensayos. Vista previa:")
                st.dataframe(df_nuevos, use_container_width=True)
                if st.button("💾 Guardar todos en la base de datos", type="primary", use_container_width=True):
                    df_nuevos.to_sql('parametros', con=obtener_engine(), if_exists='append', index=False)
                    st.success("✅ ¡Excelente! Todos los parámetros se cargaron correctamente.")
            except Exception as e:
                st.error(f"❌ Hubo un error al leer o guardar el archivo. Detalle técnico: {e}")    
    conn.close()

# ============================================================
# MÓDULO 3: RECEPCIÓN DE MUESTRAS
# ============================================================
elif modulo == "Recepción de Muestras":
    st.header("💧 Recepción de Muestras")
    conn  = obtener_conexion()
    df_cl = pd.read_sql_query("SELECT id_cliente, cliente FROM clientes", conn)

    if df_cl.empty:
        st.warning("⚠️ No hay clientes registrados. Cargá un cliente primero desde *Gestión de Clientes*.")
    else:
        col1, col2 = st.columns([1, 2])
        with col1:
            dict_c = dict(zip(df_cl['cliente'], df_cl['id_cliente']))
            c_sel  = st.selectbox("Comitente *", list(dict_c.keys()))
            id_man = st.text_input("ID Manual de Muestra *")
            prec   = st.radio("¿Tiene precinto?", ["No", "Sí"], horizontal=True)
            cod_p  = st.text_input("N° de Precinto") if prec == "Sí" else "Sin precinto"
            matriz = st.selectbox("Matriz", ["Agua Superficial", "Efluente Industrial", "Efluente Cloacal"])
            fecha  = st.date_input("Fecha de Ingreso")
            obs    = st.text_area("Observaciones")
            if st.button("📥 Registrar Ingreso de Muestra", use_container_width=True, type="primary"):
                if not id_man.strip():
                    st.warning("⚠️ El ID manual de la muestra es obligatorio.")
                else:
                    ejecutar(conn, "INSERT INTO muestras (id_cliente, id_manual, tiene_precinto, codigo_precinto, matriz, fecha_ingreso, observaciones) VALUES (%s,%s,%s,%s,%s,%s,%s)", (dict_c[c_sel], id_man.strip(), prec, cod_p, matriz, str(fecha), obs))
                    conn.commit()
                    st.success(f"✅ Muestra *{id_man.strip()}* registrada exitosamente.")
                    st.toast(f"🧪 Muestra {id_man.strip()} cargada", icon="✅")
                    st.rerun()
        with col2:
            st.dataframe(pd.read_sql_query("""SELECT m.id_manual AS "Muestra", c.cliente AS "Comitente", m.matriz AS "Matriz", m.fecha_ingreso AS "Fecha", m.codigo_precinto AS "Precinto" FROM muestras m JOIN clientes c ON m.id_cliente = c.id_cliente ORDER BY m.id_muestra DESC LIMIT 20""", conn), hide_index=True, use_container_width=True)
    conn.close()

# ============================================================
# MÓDULO 4: ÓRDENES DE TRABAJO
# ============================================================
elif modulo == "Órdenes de Trabajo":
    st.header("📋 Órdenes de Trabajo (OT)")
    conn  = obtener_conexion()
    df_m  = pd.read_sql_query("SELECT m.id_muestra, m.id_manual, c.cliente FROM muestras m JOIN clientes c ON m.id_cliente = c.id_cliente", conn)
    df_pp = pd.read_sql_query("SELECT id_parametro, nombre FROM parametros", conn)

    st.subheader("Asignar ensayos a muestra")
    if df_m.empty: st.info("📭 No hay muestras registradas aún.")
    elif df_pp.empty: st.info("📭 No hay ensayos en el catálogo.")
    else:
        m_s  = st.selectbox("Seleccionar Muestra:", [f"{r['id_manual']} - {r['cliente']}" for _, r in df_m.iterrows()])
        id_m = df_m[df_m['id_manual'] == m_s.split(" - ")[0]]['id_muestra'].iloc[0]
        asig = pd.read_sql_query("SELECT p.nombre FROM ordenes_trabajo ot JOIN parametros p ON ot.id_parametro = p.id_parametro WHERE ot.id_muestra=%s", conn, params=(int(id_m),))
        if not asig.empty: st.info(f"ℹ️ Ensayos ya asignados a esta muestra: *{', '.join(asig['nombre'].tolist())}*")

        with st.form("asignar_analisis"):
            p_s = st.multiselect("Seleccioná los ensayos a agregar:", df_pp['nombre'].tolist())
            if st.form_submit_button("🔗 Vincular ensayos a la muestra", use_container_width=True):
                if not p_s: st.warning("⚠️ Seleccioná al menos un ensayo.")
                else:
                    agregados = []
                    for p in p_s:
                        id_p = df_pp[df_pp['nombre'] == p]['id_parametro'].iloc[0]
                        if ejecutar(conn, "SELECT COUNT(*) FROM ordenes_trabajo WHERE id_muestra=%s AND id_parametro=%s", (int(id_m), int(id_p))).fetchone()[0] == 0:
                            ejecutar(conn, "INSERT INTO ordenes_trabajo (id_muestra, id_parametro) VALUES (%s,%s)", (int(id_m), int(id_p)))
                            agregados.append(p)
                    conn.commit()
                    if agregados:
                        st.success(f"✅ Ensayos asignados a *{m_s.split(' - ')[0]}*: {', '.join(agregados)}")
                    else:
                        st.warning("⚠️ Todos los ensayos seleccionados ya estaban asignados.")
                    st.rerun()

    st.divider()
    if st.session_state['rol'] == 'Admin':
        st.subheader("Generar documento OT")
        df_ready = pd.read_sql_query("SELECT DISTINCT c.id_cliente, c.cliente FROM muestras m JOIN clientes c ON m.id_cliente = c.id_cliente JOIN ordenes_trabajo ot ON m.id_muestra = ot.id_muestra", conn)
        if not df_ready.empty:
            col_c, col_f = st.columns(2)
            with col_c:
                cli_sel = st.selectbox("Comitente:", df_ready['cliente'].tolist())
                id_c    = df_ready[df_ready['cliente'] == cli_sel]['id_cliente'].iloc[0]
            with col_f:
                fechas = pd.read_sql_query("SELECT DISTINCT fecha_ingreso FROM muestras WHERE id_cliente=%s", conn, params=(int(id_c),))
                f_sel = st.selectbox("Fecha del lote:", fechas['fecha_ingreso'].tolist())
            if st.button("📄 Generar Documento Word"):
                datos_c  = pd.read_sql_query("SELECT * FROM clientes WHERE id_cliente=%s", conn, params=(int(id_c),)).iloc[0]
                df_lote  = pd.read_sql_query("SELECT id_muestra, id_manual, codigo_precinto FROM muestras WHERE id_cliente=%s AND fecha_ingreso=%s", conn, params=(int(id_c), str(f_sel)))
                muestras_ctx = []; total = 0.0
                for _, m in df_lote.iterrows():
                    df_a = pd.read_sql_query("SELECT p.nombre, p.precio FROM ordenes_trabajo ot JOIN parametros p ON ot.id_parametro = p.id_parametro WHERE ot.id_muestra=%s", conn, params=(int(m['id_muestra']),))
                    muestras_ctx.append({'id_manual': m['id_manual'], 'precinto': m['codigo_precinto'], 'analisis': ", ".join(df_a['nombre'].tolist())})
                    total += df_a['precio'].sum()
                try:
                    tpl = DocxTemplate("plantilla_informe.docx")
                    tpl.render({'cliente': datos_c['cliente'], 'cuit': datos_c['cuit'], 'contacto': datos_c['contacto'], 'direccion': datos_c['direccion'], 'email': datos_c['email'], 'fecha': f_sel, 'total': f"${total:,.2f}", 'muestras': muestras_ctx})
                    buf = io.BytesIO(); tpl.save(buf)
                    st.success("✅ Documento generado correctamente.")
                    st.download_button("⬇️ Descargar Documento", buf.getvalue(), f"OT_{cli_sel}.docx", type="primary")
                except Exception as e:
                    st.error(f"❌ Error al generar el documento: {e}")
    conn.close()

# ============================================================
# MÓDULO 5: CARGA Y CORRECCIÓN
# ============================================================
elif modulo == "Carga y Corrección":
    st.header("✏️ Carga de Resultados")
    conn   = obtener_conexion()
    t1, t2 = st.tabs(["📥 Carga Diaria", "🔏 Corrección ISO"])

    with t1:
        df_pen = pd.read_sql_query("SELECT ot.id_ot, m.id_manual, p.nombre, p.text_unidad, c.cliente FROM ordenes_trabajo ot JOIN muestras m ON ot.id_muestra = m.id_muestra JOIN parametros p ON ot.id_parametro = p.id_parametro JOIN clientes c ON m.id_cliente = c.id_cliente WHERE ot.estado = 'Pendiente' ORDER BY m.fecha_ingreso DESC", conn)
        if not df_pen.empty:
            st.markdown("Seleccioná el ensayo específico que querés cargar:")
            opciones = [f"Muestra: {r['id_manual']} ({r['cliente']}) ➔ Ensayo: {r['nombre']}" for _, r in df_pen.iterrows()]
            sel_ensayo = st.selectbox("Ensayo Pendiente:", opciones)
            idx = opciones.index(sel_ensayo)
            datos_ensayo = df_pen.iloc[idx]
            id_ot_seleccionado = int(datos_ensayo['id_ot'])
            unidad = datos_ensayo['text_unidad']
            nombre = datos_ensayo['nombre']
            with st.form("carga_individual"):
                valor_ingresado = st.number_input(f"Valor en [{unidad}]", format="%.3f")
                if st.form_submit_button("✅ Firmar este Resultado", use_container_width=True):
                    ejecutar(conn, "UPDATE ordenes_trabajo SET resultado=%s, estado='Completado', responsable=%s WHERE id_ot=%s", (valor_ingresado, st.session_state['nombre_real'], id_ot_seleccionado))
                    conn.commit()
                    st.success(f"✅ Resultado de {nombre} guardado y firmado.")
                    st.rerun()
        else:
            st.info("No hay ensayos pendientes para cargar en este momento.")

    with t2:
        df_comp = pd.read_sql_query("SELECT ot.id_ot, m.id_manual, p.nombre, ot.resultado FROM ordenes_trabajo ot JOIN muestras m ON ot.id_muestra = m.id_muestra JOIN parametros p ON ot.id_parametro = p.id_parametro WHERE ot.estado = 'Completado'", conn)
        if df_comp.empty: st.info("📭 No hay resultados completados para corregir aún.")
        else:
            sel   = st.selectbox("Resultado a enmendar:", [f"OT {r['id_ot']} - {r['id_manual']} - {r['nombre']} (Actual: {r['resultado']})" for _, r in df_comp.iterrows()])
            id_ot = int(sel.split(" ")[1])
            v_ant = df_comp[df_comp['id_ot'] == id_ot]['resultado'].iloc[0]
            with st.form("enmienda"):
                v_nue = st.number_input("Nuevo Valor:", format="%.3f")
                mot   = st.text_area("Justificación obligatoria (ISO 17025) *")
                if st.form_submit_button("🔏 Aplicar Corrección Auditada", use_container_width=True):
                    if mot.strip():
                        ejecutar(conn, "INSERT INTO historial_cambios (id_ot, usuario_modificador, fecha_hora, valor_anterior, valor_nuevo, motivo) VALUES (%s,%s,%s,%s,%s,%s)", (id_ot, st.session_state['nombre_real'], datetime.now().strftime("%Y-%m-%d %H:%M"), v_ant, v_nue, mot))
                        ejecutar(conn, "UPDATE ordenes_trabajo SET resultado=%s, responsable=%s WHERE id_ot=%s", (v_nue, st.session_state['nombre_real'], id_ot))
                        conn.commit()
                        st.success("✅ Corrección registrada.")
                        st.rerun()
                    else:
                        st.error("❌ La justificación es obligatoria.")
    conn.close()

# ============================================================
# MÓDULO 6: CONSULTA DE RESULTADOS
# ============================================================
elif modulo == "Consulta de Resultados":
    st.header("📊 Archivo de Resultados")
    conn = obtener_conexion()
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        df_cli_f = pd.read_sql_query("SELECT DISTINCT c.cliente FROM clientes c JOIN muestras m ON c.id_cliente=m.id_cliente", conn)
        filtro_cli = st.selectbox("Filtrar por comitente:", ["Todos"] + df_cli_f['cliente'].tolist())
    with col_f2:
        filtro_fecha = st.date_input("Desde fecha:", value=None)

    query  = "SELECT m.fecha_ingreso AS \"Fecha\", c.cliente AS \"Comitente\", m.id_manual AS \"Muestra\", p.nombre AS \"Determinación\", ot.resultado AS \"Valor\", p.text_unidad AS \"Unidad\", p.limite_deteccion AS \"LD\", p.limite_caa AS \"CAA\", ot.responsable AS \"Firma\" FROM ordenes_trabajo ot JOIN muestras m ON ot.id_muestra = m.id_muestra JOIN clientes c ON m.id_cliente = c.id_cliente JOIN parametros p ON ot.id_parametro = p.id_parametro WHERE ot.estado = 'Completado'"
    params = []
    if filtro_cli != "Todos":
        query  += " AND c.cliente = %s"; params.append(filtro_cli)
    if filtro_fecha:
        query  += " AND m.fecha_ingreso >= %s"; params.append(str(filtro_fecha))
    query += " ORDER BY m.fecha_ingreso DESC"

    df_res = pd.read_sql_query(query, conn, params=params)
    if df_res.empty: st.info("📭 No hay resultados que coincidan con los filtros aplicados.")
    else: st.dataframe(df_res, use_container_width=True, hide_index=True)
    conn.close()

# ============================================================
# MÓDULO 7: FINANZAS Y FACTURACIÓN
# ============================================================
elif modulo == "Finanzas y Facturación":
    st.header("💰 Panel Financiero")
    conn     = obtener_conexion()
    df_fac   = pd.read_sql_query("SELECT * FROM facturas", conn)
    tot_hist = df_fac['monto_total'].sum() if not df_fac.empty else 0.0
    tot_gas  = df_fac['gastos_lqa'].sum()  if not df_fac.empty else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Facturado", f"${tot_hist:,.2f}")
    c2.metric("Producido FIUNER (20%)", f"${tot_hist * 0.2:,.2f}")
    c3.metric("Fondo LQA (80%)", f"${tot_hist * 0.8:,.2f}")
    c4.metric("Saldo Real LQA", f"${(tot_hist * 0.8) - tot_gas:,.2f}", f"-${tot_gas:,.2f} gastos")
    st.divider()

    tab_crear, tab_gest = st.tabs(["➕ Crear Vínculo OT-EXT", "🔄 Actualizar Pagos y Gastos"])
    with tab_crear:
        df_f = pd.read_sql_query("SELECT DISTINCT c.id_cliente, c.cliente FROM muestras m JOIN clientes c ON m.id_cliente=c.id_cliente", conn)
        if not df_f.empty:
            cc1, cc2 = st.columns(2)
            with cc1:
                c_sel = st.selectbox("Comitente", df_f['cliente'].tolist())
                id_c  = df_f[df_f['cliente'] == c_sel]['id_cliente'].iloc[0]
            with cc2:
                fechas = pd.read_sql_query("SELECT DISTINCT fecha_ingreso FROM muestras WHERE id_cliente=%s", conn, params=(int(id_c),))
                f_sel  = st.selectbox("Fecha del Lote", fechas['fecha_ingreso'].tolist())
            monto_lote = pd.read_sql_query("SELECT p.precio FROM muestras m JOIN ordenes_trabajo ot ON m.id_muestra=ot.id_muestra JOIN parametros p ON ot.id_parametro=p.id_parametro WHERE m.id_cliente=%s AND m.fecha_ingreso=%s", conn, params=(int(id_c), f_sel))['precio'].sum()
            with st.form("vincular"):
                cod_v = st.text_input("Código de Vinculación (Ej: OT-EXT-001) *")
                if st.form_submit_button("🔗 Vincular y Generar Factura Interna", use_container_width=True):
                    if cod_v.strip():
                        try:
                            ejecutar(conn, "INSERT INTO facturas (codigo_vinculacion, id_cliente, fecha_lote, monto_total) VALUES (%s,%s,%s,%s)", (cod_v.strip(), id_c, f_sel, monto_lote))
                            conn.commit()
                            st.success(f"✅ Vínculo creado exitosamente.")
                            st.rerun()
                        except: st.error("❌ Ese código de vinculación ya existe en el sistema.")
    with tab_gest:
        if not df_fac.empty:
            sel_f = st.selectbox("Seleccionar OT de Vinculación:", df_fac['codigo_vinculacion'].tolist())
            datos_f = df_fac[df_fac['codigo_vinculacion'] == sel_f].iloc[0]
            with st.form("actualizar_f"):
                ca1, ca2 = st.columns(2)
                with ca1:
                    nro_f = st.text_input("N° de Factura", value=datos_f['nro_factura_fiuner'] if pd.notnull(datos_f['nro_factura_fiuner']) else "")
                    est_p = st.selectbox("Estado de Pago", ["Pendiente", "Pagado"], index=1 if datos_f['estado_pago'] == "Pagado" else 0)
                with ca2:
                    gastos = st.number_input("Gasto de este Lote ($)", value=float(datos_f['gastos_lqa']), step=1000.0)
                if st.form_submit_button("💾 Actualizar Registro", use_container_width=True):
                    ejecutar(conn, "UPDATE facturas SET nro_factura_fiuner=%s, estado_pago=%s, gastos_lqa=%s WHERE codigo_vinculacion=%s", (nro_f, est_p, gastos, sel_f))
                    conn.commit()
                    st.success(f"✅ Registro actualizado.")
                    st.rerun()
            st.dataframe(df_fac[['codigo_vinculacion', 'fecha_lote', 'nro_factura_fiuner', 'estado_pago', 'monto_total', 'gastos_lqa']], use_container_width=True, hide_index=True)
    conn.close()

# ============================================================
# MÓDULO 8: GENERACIÓN DE INFORMES
# ============================================================
elif modulo == "Generación de Informes":
    st.header("📄 Generación de Protocolos")
    conn  = obtener_conexion()
    df_i  = pd.read_sql_query("SELECT DISTINCT m.id_muestra, m.id_manual, c.cliente, m.fecha_ingreso, m.matriz FROM muestras m JOIN clientes c ON m.id_cliente=c.id_cliente JOIN ordenes_trabajo ot ON m.id_muestra=ot.id_muestra WHERE ot.estado='Completado'", conn)
    if not df_i.empty:
        m_sel = st.selectbox("Seleccionar Muestra lista para informar:", [f"{r['id_manual']} - {r['cliente']}" for _, r in df_i.iterrows()])
        id_m  = int(df_i[df_i['id_manual'] == m_sel.split(" - ")[0]]['id_muestra'].iloc[0])
        datos = df_i[df_i['id_muestra'] == id_m].iloc[0]
        res_pv = pd.read_sql_query("SELECT p.nombre AS \"Determinación\", ot.resultado AS \"Valor\", p.text_unidad AS \"Unidad\", p.limite_caa AS \"Límite CAA\" FROM ordenes_trabajo ot JOIN parametros p ON ot.id_parametro=p.id_parametro WHERE ot.id_muestra=%s AND ot.estado='Completado'", conn, params=(id_m,))
        st.dataframe(res_pv, use_container_width=True, hide_index=True)
        if st.button("📄 Generar Informe Word", type="primary"):
            try:
                res = pd.read_sql_query("SELECT p.nombre, ot.resultado, p.text_unidad, p.limite_deteccion, p.limite_caa FROM ordenes_trabajo ot JOIN parametros p ON ot.id_parametro=p.id_parametro WHERE ot.id_muestra=%s AND ot.estado='Completado'", conn, params=(id_m,))
                tpl = DocxTemplate("plantilla_informe.docx")
                tpl.render({'solicitante': datos['cliente'], 'muestra_id': datos['id_manual'], 'fecha': datos['fecha_ingreso'], 'matriz': datos['matriz'], 'resultados': [{'parametro': r['nombre'], 'valor': r['resultado'], 'unidad': r['text_unidad'], 'ld': r['limite_deteccion'], 'caa': r['limite_caa']} for _, r in res.iterrows()]})
                buf = io.BytesIO(); tpl.save(buf)
                st.success(f"✅ Protocolo generado.")
                st.download_button("⬇️ Descargar Protocolo Word", buf.getvalue(), f"Protocolo_{datos['id_manual']}.docx", type="primary")
            except Exception as e: st.error(f"❌ Error al generar: {e}")
    conn.close()

# ============================================================
# MÓDULO 9: AUDITORÍA ISO 17025
# ============================================================
elif modulo == "Auditoría (ISO)":
    st.header("🛡️ Auditoría — Audit Trail ISO 17025")
    conn     = obtener_conexion()
    df_audit = pd.read_sql_query("SELECT hc.fecha_hora AS \"Fecha / Hora\", hc.usuario_modificador AS \"Modificado por\", m.id_manual AS \"Ref. Muestra\", p.nombre AS \"Análisis\", hc.valor_anterior AS \"Valor Anterior\", hc.valor_nuevo AS \"Valor Nuevo\", hc.motivo AS \"Justificación\" FROM historial_cambios hc JOIN ordenes_trabajo ot ON hc.id_ot = ot.id_ot JOIN muestras m ON ot.id_muestra = m.id_muestra JOIN parametros p ON ot.id_parametro = p.id_parametro ORDER BY hc.id_cambio DESC", conn)
    st.dataframe(df_audit, use_container_width=True, hide_index=True)
    conn.close()

# ============================================================
# MÓDULO 10: GESTIÓN DE USUARIOS
# ============================================================
elif modulo == "Gestión de Usuarios":
    st.header("🔐 Gestión de Usuarios y Accesos")
    if st.session_state['rol'] != 'Admin':
        st.error("Acceso denegado.")
        st.stop()
    conn = obtener_conexion()
    t_nuevo, t_editar, t_lista = st.tabs(["➕ Nuevo Usuario", "✏️ Editar / Cambiar Clave", "📋 Lista de Usuarios"])
    with t_nuevo:
        with st.form("nuevo_usuario", clear_on_submit=True):
            c1, c2 = st.columns(2)
            u_nom, u_real = c1.text_input("Usuario (Login) *"), c1.text_input("Nombre y Apellido *")
            u_pass, u_rol = c2.text_input("Contraseña *", type="password"), c2.selectbox("Rol", ["Tecnico", "Admin"])
            if st.form_submit_button("💾 Crear Usuario", type="primary"):
                if u_nom and u_real and u_pass:
                    try:
                        ejecutar(conn, "INSERT INTO usuarios (usuario, password, nombre_real, rol) VALUES (%s,%s,%s,%s)", (u_nom.strip().lower(), hash_clave(u_pass), u_real.strip(), u_rol))
                        conn.commit(); st.success(f"✅ Usuario creado."); st.rerun()
                    except: st.error("❌ El usuario ya existe.")
    with t_editar:
        df_usr = pd.read_sql_query("SELECT id_usuario, usuario, nombre_real, rol FROM usuarios", conn)
        if not df_usr.empty:
            usr_sel = st.selectbox("Seleccionar Usuario:", [f"{r['id_usuario']} - {r['usuario']} ({r['nombre_real']})" for _, r in df_usr.iterrows()])
            id_u_sel = int(usr_sel.split(" - ")[0])
            datos_u = df_usr[df_usr['id_usuario'] == id_u_sel].iloc[0]
            with st.form("editar_usuario"):
                e_real = st.text_input("Nombre y Apellido Real *", value=datos_u['nombre_real'])
                e_rol = st.selectbox("Rol", ["Tecnico", "Admin"], index=0 if datos_u['rol'] == 'Tecnico' else 1)
                e_pass = st.text_input("Nueva Contraseña (dejá en blanco si no cambiás)", type="password")
                if st.form_submit_button("💾 Guardar Cambios"):
                    if e_real:
                        if e_pass: ejecutar(conn, "UPDATE usuarios SET nombre_real=%s, rol=%s, password=%s WHERE id_usuario=%s", (e_real.strip(), e_rol, hash_clave(e_pass), id_u_sel))
                        else: ejecutar(conn, "UPDATE usuarios SET nombre_real=%s, rol=%s WHERE id_usuario=%s", (e_real.strip(), e_rol, id_u_sel))
                        conn.commit(); st.success("✅ Actualizado."); st.rerun()
            if st.button("🗑️ Borrar Usuario", type="primary"):
                if datos_u['usuario'] == st.session_state['usuario_actual'] or datos_u['usuario'] == 'admin':
                    st.error("❌ No podés borrarte a vos mismo ni al admin principal.")
                else:
                    ejecutar(conn, "DELETE FROM usuarios WHERE id_usuario=%s", (id_u_sel,))
                    conn.commit(); st.success("✅ Eliminado."); st.rerun()
    with t_lista:
        st.dataframe(df_usr[['id_usuario', 'usuario', 'nombre_real', 'rol']], use_container_width=True, hide_index=True)
    conn.close()

# ============================================================
# MÓDULO 11: MI PERFIL
# ============================================================
elif modulo == "Mi Perfil":
    st.header("👤 Mi Perfil")
    st.markdown(f"**Usuario (Login):** `{st.session_state['usuario_actual']}`\n\n**Nombre Real:** {st.session_state['nombre_real']}\n\n**Rol en el sistema:** {st.session_state['rol']}")
    st.divider()
    st.subheader("🔑 Cambiar mi contraseña")
    with st.form("cambiar_mi_pass"):
        c1, c2 = st.columns(2)
        pass_actual = c1.text_input("Contraseña Actual *", type="password")
        pass_nueva, pass_conf = c2.text_input("Nueva Contraseña *", type="password"), c2.text_input("Repetir Nueva Contraseña *", type="password")
        if st.form_submit_button("Actualizar mi Contraseña", type="primary"):
            if not pass_actual or not pass_nueva or not pass_conf: st.warning("⚠️ Completá los tres campos.")
            elif pass_nueva != pass_conf: st.error("❌ Las contraseñas nuevas no coinciden.")
            else:
                conn = obtener_conexion()
                res = ejecutar(conn, "SELECT password FROM usuarios WHERE usuario=%s", (st.session_state['usuario_actual'],)).fetchone()
                if res and bcrypt.checkpw(pass_actual.encode('utf-8'), res[0].encode('utf-8')):
                    ejecutar(conn, "UPDATE usuarios SET password=%s WHERE usuario=%s", (hash_clave(pass_nueva), st.session_state['usuario_actual']))
                    conn.commit(); st.success("✅ ¡Tu contraseña fue actualizada!")
                else: st.error("❌ Contraseña actual incorrecta.")
                conn.close()