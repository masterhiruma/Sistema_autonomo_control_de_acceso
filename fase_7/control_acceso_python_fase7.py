import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import serial
import time
import threading
from enum import Enum
import sqlite3
import datetime
import re 
import json 
import csv  
import os   

# --- CONFIGURACIÓN ---
PUERTO_SERIAL_ARDUINO = '/dev/ttyUSB0' 
VELOCIDAD_ARDUINO = 115200
TIMEOUT_SERIAL = 1
NOMBRE_BD = "sistema_acceso.db"
ARCHIVO_ESTADO_DIARIO = "estado_diario.json"
CARPETA_REPORTES = "reportes_acceso" 

# --- CONSTANTES DEL SISTEMA ---
UMBRAL_DETECCION_SP1_CM = 30.0
UMBRAL_DETECCION_SP2_CM = 30.0
TIEMPO_ESPERA_APERTURA_PUERTA_S = 2.0
TIEMPO_MAX_SP2_ACTIVO_S = 5.0
TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S = 10.0
TIEMPO_CIERRE_PUERTA_S = 1.0
TIMEOUT_PRESENTACION_RFID_S = 10.0
TIMEOUT_SIMULACION_QR_S = 15.0 
TIMEOUT_SIMULACION_FACIAL_S = 15.0 
MAX_INTENTOS_FALLIDOS_UID = 3
TIEMPO_BLOQUEO_UID_NIVEL = { 1: 5 * 60, 2: 10 * 60, 3: 24 * 60 * 60 }
TIEMPO_COOLDOWN_ACCESO_S = 5 * 60 

# --- ESTADOS DEL SISTEMA ---
class EstadoSistema(Enum):
    REPOSO = "REPOSO"
    ESPERANDO_VALIDACION_RFID = "ESPERANDO_VALIDACION_RFID"
    ESPERANDO_VALIDACION_QR = "ESPERANDO_VALIDACION_QR"
    ESPERANDO_VALIDACION_FACIAL = "ESPERANDO_VALIDACION_FACIAL"
    ABRIENDO_PUERTA = "ABRIENDO_PUERTA"
    PERSONA_CRUZANDO = "PERSONA_CRUZANDO"
    CERRANDO_PUERTA = "CERRANDO_PUERTA"
    ALERTA_ERROR_CRUCE = "ALERTA_ERROR_CRUCE"
    ACCESO_DENEGADO_TEMPORAL = "ACCESO_DENEGADO_TEMPORAL"
    SISTEMA_BLOQUEADO_UID = "UID_BLOQUEADO_TEMPORALMENTE"

# --- VARIABLES GLOBALES ---
datos_hardware = {
    "sp1_distancia": 999.0, "sp2_distancia": 999.0,
    "s1_estado": 1, "s2_estado": 1, "e_estado": 1, 
    "rfid_uid": "NADA", "ultimo_rfid_procesado_para_acceso": "NADA"
}
lock_datos_hardware = threading.Lock()
arduino_conectado = False; arduino_serial = None
hilo_listener_arduino_activo = True; hilo_maquina_estados_activo = True
estado_actual_sistema = EstadoSistema.REPOSO
puerta_logicamente_abierta = False
tiempo_inicio_estado_actual_s = 0; tiempo_puerta_abrio_s = 0; tiempo_sp2_detecto_primera_vez_s = 0
contador_accesos_hoy = 0; eventos_acceso_hoy = []; intentos_fallidos_hoy = []
fecha_actual_para_conteo = "" 
intentos_fallidos_por_uid = {}; accesos_recientes_uid = {} 
app_gui = None
protocolo_seleccionado_actual = {"rfid": True, "qr": False, "facial": False, "descripcion": "Solo RFID (Predeterminado)"}
estado_validacion_secuencial = {}

# ==============================================================================
# FUNCIONES DE LA BASE DE DATOS (SQLite)
# (COPIAR DE LA VERSIÓN ANTERIOR)
# ==============================================================================
def inicializar_bd():
    if not os.path.exists(CARPETA_REPORTES): os.makedirs(CARPETA_REPORTES)
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario INTEGER PRIMARY KEY AUTOINCREMENT, nombre_completo TEXT NOT NULL,
            dni TEXT UNIQUE NOT NULL, nivel_usuario TEXT NOT NULL CHECK(nivel_usuario IN ('Admin', 'Trabajador', 'Visitante')),
            area_trabajo TEXT, uid_rfid TEXT UNIQUE NOT NULL, horario_trabajo_inicio TEXT, horario_trabajo_fin TEXT,    
            CHECK ( (nivel_usuario = 'Trabajador' AND horario_trabajo_inicio IS NOT NULL AND horario_trabajo_fin IS NOT NULL) OR 
                    (nivel_usuario != 'Trabajador' AND horario_trabajo_inicio IS NULL AND horario_trabajo_fin IS NULL) ))''')
    conn.commit(); conn.close()
def agregar_usuario_bd(datos):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    try:
        cursor.execute('INSERT INTO usuarios (nombre_completo, dni, nivel_usuario, area_trabajo, uid_rfid, horario_trabajo_inicio, horario_trabajo_fin) VALUES (?, ?, ?, ?, ?, ?, ?)',
                       (datos['nombre'], datos['dni'], datos['nivel'], datos['area'], datos['uid_rfid'], datos.get('h_inicio'), datos.get('h_fin')))
        conn.commit(); return True, "Usuario agregado."
    except sqlite3.IntegrityError as e:
        if "dni" in str(e): return False, "Error: DNI ya registrado."
        if "uid_rfid" in str(e): return False, "Error: UID RFID ya registrado."
        return False, f"Error BD: {e}"
    finally: conn.close()
def obtener_usuario_por_rfid_bd(uid_rfid):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    cursor.execute("SELECT id_usuario, nombre_completo, dni, nivel_usuario, area_trabajo, horario_trabajo_inicio, horario_trabajo_fin FROM usuarios WHERE uid_rfid = ?", (uid_rfid,))
    data = cursor.fetchone(); conn.close()
    if data: return {"id_usuario": data[0], "nombre": data[1], "dni": data[2], "nivel": data[3], "area": data[4], "h_inicio": data[5], "h_fin": data[6], "uid_rfid": uid_rfid}
    return None
def obtener_usuario_por_id_bd(id_usuario):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    cursor.execute("SELECT id_usuario, nombre_completo, dni, nivel_usuario, area_trabajo, uid_rfid, horario_trabajo_inicio, horario_trabajo_fin FROM usuarios WHERE id_usuario = ?", (id_usuario,))
    data = cursor.fetchone(); conn.close()
    if data: return {"id_usuario": data[0], "nombre": data[1], "dni": data[2], "nivel": data[3], "area": data[4], "uid_rfid": data[5], "h_inicio": data[6], "h_fin": data[7]}
    return None
def verificar_uid_existente_bd(uid_rfid, excluir_id_usuario=None):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor(); query = "SELECT nombre_completo FROM usuarios WHERE uid_rfid = ?"; params = [uid_rfid]
    if excluir_id_usuario: query += " AND id_usuario != ?"; params.append(excluir_id_usuario)
    cursor.execute(query, tuple(params)); resultado = cursor.fetchone(); conn.close()
    return resultado[0] if resultado else None
def verificar_dni_existente_bd(dni, excluir_id_usuario=None):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor(); query = "SELECT nombre_completo FROM usuarios WHERE dni = ?"; params = [dni]
    if excluir_id_usuario: query += " AND id_usuario != ?"; params.append(excluir_id_usuario)
    cursor.execute(query, tuple(params)); resultado = cursor.fetchone(); conn.close()
    return resultado[0] if resultado else None
def obtener_todos_los_usuarios_bd():
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    cursor.execute("SELECT id_usuario, nombre_completo, dni, nivel_usuario, uid_rfid FROM usuarios ORDER BY nombre_completo")
    usuarios = cursor.fetchall(); conn.close(); return usuarios
def actualizar_usuario_bd(id_usuario, datos):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    try:
        cursor.execute('UPDATE usuarios SET nombre_completo = ?, dni = ?, nivel_usuario = ?, area_trabajo = ?, uid_rfid = ?, horario_trabajo_inicio = ?, horario_trabajo_fin = ? WHERE id_usuario = ?',
                       (datos['nombre'], datos['dni'], datos['nivel'], datos['area'], datos['uid_rfid'], datos.get('h_inicio'), datos.get('h_fin'), id_usuario))
        conn.commit(); return True, "Usuario actualizado."
    except sqlite3.IntegrityError as e:
        if "dni" in str(e): return False, "Error: Nuevo DNI ya existe."
        if "uid_rfid" in str(e): return False, "Error: Nuevo UID RFID ya existe."
        return False, f"Error BD al actualizar: {e}"
    finally: conn.close()
def borrar_usuario_bd(id_usuario):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    try: cursor.execute("DELETE FROM usuarios WHERE id_usuario = ?", (id_usuario,)); conn.commit(); return True, "Usuario borrado."
    except Exception as e: return False, f"Error al borrar: {e}"
    finally: conn.close()
# ==============================================================================
# FUNCIONES DE VALIDACIÓN DE HORARIOS
# (COPIAR DE LA VERSIÓN ANTERIOR)
# ==============================================================================
def verificar_horario_trabajador(h_inicio_str, h_fin_str):
    if not h_inicio_str or not h_fin_str: return False 
    ahora = datetime.datetime.now(); dia_semana_actual = ahora.weekday() 
    if not (0 <= dia_semana_actual <= 4): return False
    try:
        hora_actual = ahora.time()
        horario_inicio_bd = datetime.datetime.strptime(h_inicio_str, "%H:%M").time()
        horario_fin_bd = datetime.datetime.strptime(h_fin_str, "%H:%M").time()
        return horario_inicio_bd <= hora_actual < horario_fin_bd
    except ValueError: return False
def verificar_horario_visitante():
    ahora = datetime.datetime.now(); dia_semana_actual = ahora.weekday() 
    if dia_semana_actual != 2: return False 
    try:
        hora_actual = ahora.time()
        horario_visita_inicio = datetime.time(9, 0); horario_visita_fin = datetime.time(10, 0) 
        return horario_visita_inicio <= hora_actual < horario_visita_fin
    except Exception: return False
# ==============================================================================
# FUNCIONES DE MANEJO DE ESTADO DIARIO Y REPORTES
# (COPIAR DE LA VERSIÓN ANTERIOR)
# ==============================================================================
def cargar_estado_diario():
    global contador_accesos_hoy,eventos_acceso_hoy,intentos_fallidos_hoy,fecha_actual_para_conteo,intentos_fallidos_por_uid,accesos_recientes_uid
    fecha_hoy_str=datetime.date.today().strftime("%Y-%m-%d")
    if os.path.exists(ARCHIVO_ESTADO_DIARIO):
        try:
            with open(ARCHIVO_ESTADO_DIARIO,'r')as f:estado_guardado=json.load(f)
            if estado_guardado.get("fecha")==fecha_hoy_str:
                contador_accesos_hoy=estado_guardado.get("contador_accesos",0)
                eventos_acceso_hoy=estado_guardado.get("eventos_accesos_exitosos",[])
                intentos_fallidos_hoy=estado_guardado.get("intentos_accesos_fallidos",[])
                intentos_fallidos_por_uid=estado_guardado.get("intentos_fallidos_por_uid",{}) 
                accesos_recientes_uid=estado_guardado.get("accesos_recientes_uid",{})       
                ahora_ts=time.time()
                intentos_fallidos_por_uid={uid:data for uid,data in intentos_fallidos_por_uid.items()if data.get("desbloqueo_hasta",0)>ahora_ts}
                accesos_recientes_uid={uid:ts for uid,ts in accesos_recientes_uid.items()if(ahora_ts-ts)<TIEMPO_COOLDOWN_ACCESO_S}
                print("Estado diario cargado para hoy.")
            else: 
                print(f"Nuevo día. Fecha guardada: {estado_guardado.get('fecha')}, Hoy: {fecha_hoy_str}")
                if estado_guardado.get("fecha"): 
                    generar_reporte_final_dia(estado_guardado.get("fecha"),estado_guardado.get("contador_accesos",0),
                                              estado_guardado.get("eventos_accesos_exitosos",[]),estado_guardado.get("intentos_accesos_fallidos",[]))
                contador_accesos_hoy=0;eventos_acceso_hoy=[];intentos_fallidos_hoy=[];intentos_fallidos_por_uid={};accesos_recientes_uid={}
        except(json.JSONDecodeError,IOError,TypeError)as e:
            print(f"Error al leer {ARCHIVO_ESTADO_DIARIO}: {e}. Empezando de cero.")
            contador_accesos_hoy=0;eventos_acceso_hoy=[];intentos_fallidos_hoy=[];intentos_fallidos_por_uid={};accesos_recientes_uid={}
    else:
        print(f"{ARCHIVO_ESTADO_DIARIO} no encontrado. Empezando de cero para hoy.")
    fecha_actual_para_conteo=fecha_hoy_str
    guardar_estado_diario() 
def guardar_estado_diario():
    estado_a_guardar={"fecha":fecha_actual_para_conteo,"contador_accesos":contador_accesos_hoy,"eventos_accesos_exitosos":eventos_acceso_hoy,"intentos_accesos_fallidos":intentos_fallidos_hoy,"intentos_fallidos_por_uid":intentos_fallidos_por_uid,"accesos_recientes_uid":accesos_recientes_uid}
    try:
        with open(ARCHIVO_ESTADO_DIARIO,'w')as f:json.dump(estado_a_guardar,f,indent=4)
    except IOError as e:print(f"Error al guardar {ARCHIVO_ESTADO_DIARIO}: {e}")
def verificar_y_resetear_por_cambio_de_dia():
    global fecha_actual_para_conteo,contador_accesos_hoy,eventos_acceso_hoy,intentos_fallidos_hoy,intentos_fallidos_por_uid,accesos_recientes_uid
    fecha_hoy_str=datetime.date.today().strftime("%Y-%m-%d")
    if fecha_actual_para_conteo!=fecha_hoy_str:
        print("Cambio de día. Generando reporte y reseteando.")
        if fecha_actual_para_conteo:generar_reporte_final_dia(fecha_actual_para_conteo,contador_accesos_hoy,eventos_acceso_hoy,intentos_fallidos_hoy)
        contador_accesos_hoy=0;eventos_acceso_hoy=[];intentos_fallidos_hoy=[]
        intentos_fallidos_por_uid.clear();accesos_recientes_uid.clear()
        fecha_actual_para_conteo=fecha_hoy_str;guardar_estado_diario() 
        if app_gui and hasattr(app_gui,'actualizar_reportes_en_gui'):app_gui.actualizar_reportes_en_gui()
        return True 
    return False
def registrar_evento_acceso_exitoso(usuario_info):
    global contador_accesos_hoy,eventos_acceso_hoy,accesos_recientes_uid
    verificar_y_resetear_por_cambio_de_dia();contador_accesos_hoy+=1
    timestamp_str=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    evento={"timestamp_acceso":timestamp_str,"nombre_usuario":usuario_info["nombre"],"dni_usuario":usuario_info["dni"],"nivel_usuario":usuario_info["nivel"],"area_trabajo":usuario_info.get("area","N/A"),"uid_rfid_usado":usuario_info["uid_rfid"]}
    eventos_acceso_hoy.append(evento)
    accesos_recientes_uid[usuario_info["uid_rfid"]]=time.time()
    if usuario_info["uid_rfid"]in intentos_fallidos_por_uid:del intentos_fallidos_por_uid[usuario_info["uid_rfid"]]
    guardar_estado_diario()
    print(f"Acceso exitoso: {usuario_info['nombre']}. Total hoy: {contador_accesos_hoy}")
    if app_gui and hasattr(app_gui,'actualizar_reportes_en_gui'):app_gui.actualizar_reportes_en_gui()
def registrar_intento_fallido(uid_presentado,usuario_info_si_conocido,motivo_fallo,contar_para_bloqueo_insistencia=True):
    global intentos_fallidos_hoy,intentos_fallidos_por_uid
    verificar_y_resetear_por_cambio_de_dia()
    timestamp_str=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    intento={"timestamp_intento":timestamp_str,"uid_rfid_presentado":uid_presentado if uid_presentado else"N/A","nombre_usuario_detectado":usuario_info_si_conocido["nombre"]if usuario_info_si_conocido else"Desconocido","dni_usuario_detectado":usuario_info_si_conocido.get("dni","N/A")if usuario_info_si_conocido else"N/A","motivo_fallo":motivo_fallo}
    intentos_fallidos_hoy.append(intento);se_produjo_bloqueo_ahora=False
    if contar_para_bloqueo_insistencia and uid_presentado and uid_presentado!="NADA":
        if uid_presentado not in intentos_fallidos_por_uid:intentos_fallidos_por_uid[uid_presentado]={"contador":0,"nivel_bloqueo":0,"desbloqueo_hasta":0}
        data_bloqueo_uid=intentos_fallidos_por_uid[uid_presentado]
        if data_bloqueo_uid.get("desbloqueo_hasta",0)<=time.time():
            data_bloqueo_uid["contador"]+=1
            print(f"Intento fallido (contado p/bloqueo) UID {uid_presentado}. Conteo: {data_bloqueo_uid['contador']}")
            if data_bloqueo_uid["contador"]>=MAX_INTENTOS_FALLIDOS_UID:
                nivel_actual=data_bloqueo_uid.get("nivel_bloqueo",0);nuevo_nivel=min(nivel_actual+1,3) 
                data_bloqueo_uid["nivel_bloqueo"]=nuevo_nivel;duracion_bloqueo_s=TIEMPO_BLOQUEO_UID_NIVEL[nuevo_nivel]
                data_bloqueo_uid["desbloqueo_hasta"]=time.time()+duracion_bloqueo_s;data_bloqueo_uid["contador"]=0 
                desbloqueo_dt=datetime.datetime.fromtimestamp(data_bloqueo_uid["desbloqueo_hasta"])
                print(f"UID {uid_presentado} bloqueado hasta {desbloqueo_dt.strftime('%Y-%m-%d %H:%M:%S')} (Nivel {nuevo_nivel}).")
                se_produjo_bloqueo_ahora=True
    else:print(f"Intento fallido (NO contado p/bloqueo) UID {uid_presentado if uid_presentado else'N/A'}. Motivo: {motivo_fallo}")
    guardar_estado_diario()
    if app_gui and hasattr(app_gui,'actualizar_reportes_en_gui'):app_gui.actualizar_reportes_en_gui()
    return se_produjo_bloqueo_ahora
def generar_reporte_final_dia(fecha_str,contador_total,lista_eventos_exitosos,lista_eventos_fallidos,bajo_demanda=False):
    if not fecha_str or(not lista_eventos_exitosos and not lista_eventos_fallidos and contador_total==0 and not bajo_demanda):
        if bajo_demanda and app_gui:messagebox.showinfo("Info Reporte",f"No hay datos para generar reporte para {fecha_str}.")
        return
    nombre_archivo_json=os.path.join(CARPETA_REPORTES,f"reporte_{fecha_str}.json")
    reporte_data_json={"fecha_reporte":fecha_str,"total_accesos_exitosos_dia":contador_total,"log_accesos_exitosos":lista_eventos_exitosos or[],"log_intentos_fallidos":lista_eventos_fallidos or[]}
    error_json=None 
    try:
        with open(nombre_archivo_json,'w')as f_json:json.dump(reporte_data_json,f_json,indent=4)
        print(f"Reporte JSON generado: {nombre_archivo_json}")
        if bajo_demanda and app_gui:messagebox.showinfo("Reporte Generado",f"Reporte JSON generado:\n{nombre_archivo_json}")
    except IOError as e_json: 
        error_json=e_json 
        print(f"Error al generar reporte JSON: {error_json}")
        if bajo_demanda and app_gui:messagebox.showerror("Error Reporte",f"No se pudo generar el reporte JSON:\n{error_json}")
    nombre_archivo_csv_exitosos=os.path.join(CARPETA_REPORTES,f"reporte_accesos_exitosos_{fecha_str}.csv")
    if lista_eventos_exitosos:
        try:
            with open(nombre_archivo_csv_exitosos,'w',newline='',encoding='utf-8')as f_csv:
                writer=csv.DictWriter(f_csv,fieldnames=lista_eventos_exitosos[0].keys());writer.writeheader();writer.writerows(lista_eventos_exitosos)
            print(f"Reporte CSV (Exitosos) generado: {nombre_archivo_csv_exitosos}")
            if bajo_demanda and app_gui and not error_json: 
                 messagebox.showinfo("Reporte Generado",f"Reporte CSV (Exitosos) generado:\n{nombre_archivo_csv_exitosos}")
        except(IOError,IndexError)as e_csv_exitosos:print(f"Error/Info CSV (Exitosos): {e_csv_exitosos}")
    elif bajo_demanda:print(f"No hay accesos exitosos para reportar en CSV para {fecha_str}.")
    nombre_archivo_csv_fallidos=os.path.join(CARPETA_REPORTES,f"reporte_intentos_fallidos_{fecha_str}.csv")
    if lista_eventos_fallidos:
        try:
            with open(nombre_archivo_csv_fallidos,'w',newline='',encoding='utf-8')as f_csv:
                writer=csv.DictWriter(f_csv,fieldnames=lista_eventos_fallidos[0].keys());writer.writeheader();writer.writerows(lista_eventos_fallidos)
            print(f"Reporte CSV (Fallidos) generado: {nombre_archivo_csv_fallidos}")
            if bajo_demanda and app_gui and not error_json: 
                 messagebox.showinfo("Reporte Generado",f"Reporte CSV (Fallidos) generado:\n{nombre_archivo_csv_fallidos}")
        except(IOError,IndexError)as e_csv_fallidos:print(f"Error/Info CSV (Fallidos): {e_csv_fallidos}")
    elif bajo_demanda:print(f"No hay intentos fallidos para reportar en CSV para {fecha_str}.")

# ==============================================================================
# CLASE INTERFAZ GRÁFICA 
# ==============================================================================
class InterfazGrafica(tk.Tk):
    def __init__(self):
        super().__init__()
        self.uid_escaneado_para_formulario = tk.StringVar()
        self.modo_escaneo_rfid_para_registro = False 
        self.usuario_a_editar_id = None 
        self.title("Sistema de Control de Acceso - Fase 7 (Sim) v2") # v7.2
        self.geometry("950x780") 
        self.protocol("WM_DELETE_WINDOW", self.al_cerrar_ventana)
        self.notebook = ttk.Notebook(self)
        self.tab_principal = ttk.Frame(self.notebook)
        self.tab_gestion_usuarios = ttk.Frame(self.notebook)
        self.tab_reportes_diarios = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_principal, text='Panel Principal')
        self.notebook.add(self.tab_gestion_usuarios, text='Gestión de Usuarios')
        self.notebook.add(self.tab_reportes_diarios, text='Reportes Diarios')
        self.notebook.pack(expand=True, fill='both')
        self.crear_widgets_tab_principal()
        self.crear_widgets_tab_gestion_usuarios()
        self.crear_widgets_tab_reportes_diarios()
        self.actualizar_gui_periodicamente()

    def crear_widgets_tab_principal(self):
        frame_estado_sistema = ttk.LabelFrame(self.tab_principal, text="Estado del Sistema")
        frame_estado_sistema.pack(padx=10, pady=5, fill="x",ipady=5)
        self.lbl_estado_sistema_valor = ttk.Label(frame_estado_sistema, text=estado_actual_sistema.value, font=("Arial", 12, "bold"))
        self.lbl_estado_sistema_valor.pack(pady=2)
        self.lbl_modo_validacion_actual = ttk.Label(frame_estado_sistema, text=f"Modo Validación: {protocolo_seleccionado_actual['descripcion']}", font=("Arial", 10, "italic"))
        self.lbl_modo_validacion_actual.pack(pady=2)
        self.lbl_mensaje_acceso = ttk.Label(frame_estado_sistema, text="", font=("Arial", 10), foreground="blue", wraplength=700)
        self.lbl_mensaje_acceso.pack(pady=2)
        frame_estado_sensores = ttk.LabelFrame(self.tab_principal, text="Estado de Sensores e Interruptores")
        frame_estado_sensores.pack(padx=10, pady=5, fill="x")
        self.labels_estado_principal = {}
        nombres_labels = {"SP1 (cm):": "sp1_distancia", "SP2 (cm):": "sp2_distancia", "S1 (0=LOW):": "s1_estado", "S2 (0=LOW):": "s2_estado", "Emergencia (0=ACTIVA):": "e_estado", "Último UID RFID (Hardware):": "rfid_uid"}
        for i, (texto_label, clave_dato) in enumerate(nombres_labels.items()):
            lbl_texto = ttk.Label(frame_estado_sensores, text=texto_label); lbl_texto.grid(row=i, column=0, padx=5, pady=2, sticky="w")
            lbl_valor = ttk.Label(frame_estado_sensores, text="---", width=25); lbl_valor.grid(row=i, column=1, padx=5, pady=2, sticky="w")
            self.labels_estado_principal[clave_dato] = lbl_valor

    def crear_widgets_tab_gestion_usuarios(self):
        self.frame_formulario_usuario = ttk.LabelFrame(self.tab_gestion_usuarios, text="Registrar/Editar Usuario")
        self.frame_formulario_usuario.pack(padx=10, pady=10, fill="x")
        ttk.Label(self.frame_formulario_usuario, text="Nombre Completo:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_nombre = ttk.Entry(self.frame_formulario_usuario, width=40); self.entry_nombre.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_formulario_usuario, text="DNI:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_dni = ttk.Entry(self.frame_formulario_usuario, width=40); self.entry_dni.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_formulario_usuario, text="Nivel de Usuario:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.combo_nivel = ttk.Combobox(self.frame_formulario_usuario, values=["Admin", "Trabajador", "Visitante"], state="readonly", width=38); self.combo_nivel.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew"); self.combo_nivel.current(0) 
        self.combo_nivel.bind("<<ComboboxSelected>>", self.actualizar_campos_horario_form)
        ttk.Label(self.frame_formulario_usuario, text="Área de Trabajo:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.entry_area = ttk.Entry(self.frame_formulario_usuario, width=40); self.entry_area.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_formulario_usuario, text="UID RFID:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.entry_uid_rfid_registro = ttk.Entry(self.frame_formulario_usuario, textvariable=self.uid_escaneado_para_formulario, width=30); self.entry_uid_rfid_registro.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(self.frame_formulario_usuario, text="Escanear UID", command=self.iniciar_escaneo_rfid_para_formulario).grid(row=4, column=2, padx=5, pady=5, sticky="w")
        self.lbl_h_inicio = ttk.Label(self.frame_formulario_usuario, text="Horario Inicio (HH:MM):"); self.entry_h_inicio = ttk.Entry(self.frame_formulario_usuario, width=10)
        self.lbl_h_fin = ttk.Label(self.frame_formulario_usuario, text="Horario Fin (HH:MM):"); self.entry_h_fin = ttk.Entry(self.frame_formulario_usuario, width=10)
        self.lbl_h_inicio.grid(row=5, column=0, padx=5, pady=5, sticky="w"); self.entry_h_inicio.grid(row=5, column=1, padx=5, pady=5, sticky="w")
        self.lbl_h_fin.grid(row=6, column=0, padx=5, pady=5, sticky="w"); self.entry_h_fin.grid(row=6, column=1, padx=5, pady=5, sticky="w") 
        self.actualizar_campos_horario_form() 
        self.btn_guardar_usuario_form = ttk.Button(self.frame_formulario_usuario, text="Guardar Nuevo Usuario", command=self.accion_guardar_usuario_formulario); self.btn_guardar_usuario_form.grid(row=7, column=0, padx=5, pady=15, sticky="ew")
        self.btn_limpiar_form = ttk.Button(self.frame_formulario_usuario, text="Limpiar Formulario", command=self.limpiar_formulario_usuario); self.btn_limpiar_form.grid(row=7, column=1, padx=5, pady=15, sticky="ew")
        self.btn_cancelar_edicion = ttk.Button(self.frame_formulario_usuario, text="Cancelar Edición", command=self.cancelar_edicion_usuario, state=tk.DISABLED); self.btn_cancelar_edicion.grid(row=7, column=2, padx=5, pady=15, sticky="ew")
        frame_lista_usuarios = ttk.LabelFrame(self.tab_gestion_usuarios, text="Lista de Usuarios Registrados"); frame_lista_usuarios.pack(padx=10, pady=10, fill="both", expand=True)
        cols_usuarios = ("id", "nombre", "dni", "nivel", "uid_rfid")
        self.tree_usuarios = ttk.Treeview(frame_lista_usuarios, columns=cols_usuarios, show="headings", selectmode="browse")
        for col in cols_usuarios:
            ancho = 100; 
            if col == "id": ancho = 40
            elif col == "nombre": ancho = 200
            elif col == "uid_rfid": ancho = 120
            self.tree_usuarios.heading(col, text=col.replace("_", " ").title()); self.tree_usuarios.column(col, width=ancho, anchor="w")
        scrollbar_tree = ttk.Scrollbar(frame_lista_usuarios, orient="vertical", command=self.tree_usuarios.yview); self.tree_usuarios.configure(yscrollcommand=scrollbar_tree.set)
        self.tree_usuarios.pack(side="left", fill="both", expand=True); scrollbar_tree.pack(side="right", fill="y")
        self.tree_usuarios.bind("<<TreeviewSelect>>", self.al_seleccionar_usuario_lista)
        frame_botones_lista = ttk.Frame(self.tab_gestion_usuarios); frame_botones_lista.pack(padx=10, pady=5, fill="x")
        ttk.Button(frame_botones_lista, text="Cargar/Actualizar Lista", command=self.cargar_usuarios_al_treeview).pack(side=tk.LEFT, padx=5)
        self.btn_editar_usuario_lista = ttk.Button(frame_botones_lista, text="Editar Seleccionado", command=self.accion_editar_usuario_lista, state=tk.DISABLED); self.btn_editar_usuario_lista.pack(side=tk.LEFT, padx=5)
        self.btn_borrar_usuario_lista = ttk.Button(frame_botones_lista, text="Borrar Seleccionado", command=self.accion_borrar_usuario_lista, state=tk.DISABLED); self.btn_borrar_usuario_lista.pack(side=tk.LEFT, padx=5)
        self.cargar_usuarios_al_treeview()

    def crear_widgets_tab_reportes_diarios(self):
        frame_contador_reporte = ttk.LabelFrame(self.tab_reportes_diarios, text="Resumen y Generación")
        frame_contador_reporte.pack(padx=10, pady=10, fill="x")
        ttk.Label(frame_contador_reporte, text="Accesos Exitosos Hoy:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.lbl_contador_accesos_hoy = ttk.Label(frame_contador_reporte, text="0", font=("Arial", 12, "bold")); self.lbl_contador_accesos_hoy.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(frame_contador_reporte, text="Generar Reporte CSV/JSON del Día Actual", command=self.generar_reporte_dia_actual_manual).grid(row=0, column=2, padx=20, pady=5)
        frame_visualizacion_logs = ttk.LabelFrame(self.tab_reportes_diarios, text="Logs del Día Actual"); frame_visualizacion_logs.pack(padx=10, pady=10, fill="both", expand=True)
        notebook_logs = ttk.Notebook(frame_visualizacion_logs)
        tab_exitosos = ttk.Frame(notebook_logs)
        cols_exitosos = ("timestamp_acceso", "nombre_usuario", "dni_usuario", "nivel_usuario", "area_trabajo", "uid_rfid_usado")
        self.tree_accesos_exitosos = ttk.Treeview(tab_exitosos, columns=cols_exitosos, show="headings")
        for col in cols_exitosos: 
            ancho = 120
            if col == "timestamp_acceso": ancho = 160
            elif col == "nombre_usuario": ancho = 150
            self.tree_accesos_exitosos.heading(col, text=col.replace("_", " ").title()); self.tree_accesos_exitosos.column(col, width=ancho, anchor="w")
        self.tree_accesos_exitosos.pack(fill="both", expand=True); notebook_logs.add(tab_exitosos, text="Accesos Exitosos")
        tab_fallidos = ttk.Frame(notebook_logs)
        cols_fallidos = ("timestamp_intento", "uid_rfid_presentado", "nombre_usuario_detectado", "dni_usuario_detectado", "motivo_fallo")
        self.tree_intentos_fallidos = ttk.Treeview(tab_fallidos, columns=cols_fallidos, show="headings")
        for col in cols_fallidos: 
            ancho = 150
            if col == "motivo_fallo": ancho = 250
            self.tree_intentos_fallidos.heading(col, text=col.replace("_", " ").title()); self.tree_intentos_fallidos.column(col, width=ancho, anchor="w")
        self.tree_intentos_fallidos.pack(fill="both", expand=True); notebook_logs.add(tab_fallidos, text="Intentos Fallidos")
        notebook_logs.pack(expand=True, fill='both', padx=5, pady=5)

    def actualizar_campos_horario_form(self, event=None):
        nivel_seleccionado = self.combo_nivel.get(); estado_horario = tk.NORMAL if nivel_seleccionado == "Trabajador" else tk.DISABLED
        self.entry_h_inicio.config(state=estado_horario); self.entry_h_fin.config(state=estado_horario)
        if estado_horario == tk.DISABLED: self.entry_h_inicio.delete(0, tk.END); self.entry_h_fin.delete(0, tk.END)

    def iniciar_escaneo_rfid_para_formulario(self):
        self.uid_escaneado_para_formulario.set(""); self.modo_escaneo_rfid_para_registro = True 
        enviar_comando_a_arduino("SOLICITAR_LECTURA_RFID")
        if hasattr(self, 'lbl_mensaje_acceso'): self.lbl_mensaje_acceso.config(text="Acerque la tarjeta RFID al lector para formulario...")
        messagebox.showinfo("Escanear RFID", "Acerque la tarjeta RFID al lector.\nEl UID aparecerá en el campo UID del formulario.")

    def _procesar_rfid_llegado_para_formulario(self, uid_recibido): # CORREGIDO
        if not self.modo_escaneo_rfid_para_registro or uid_recibido == "NADA" or uid_recibido == self.uid_escaneado_para_formulario.get():
            return
        excluir_id = self.usuario_a_editar_id if self.usuario_a_editar_id else None
        usuario_existente_con_uid = verificar_uid_existente_bd(uid_recibido, excluir_id_usuario=excluir_id)
        decision_tomada_sobre_uid = False
        if usuario_existente_con_uid:
            respuesta = messagebox.askyesno("UID Existente", 
                                           f"El UID '{uid_recibido}' ya está registrado para '{usuario_existente_con_uid}'.\n"
                                           "¿Desea usar este UID de todas formas para el formulario actual, o intentar escanear otra tarjeta?")
            if respuesta: 
                self.uid_escaneado_para_formulario.set(uid_recibido)
                messagebox.showinfo("UID Asignado", f"UID '{uid_recibido}' asignado al formulario.\nRecuerde que este UID ya pertenece a otro usuario si no está editando a '{usuario_existente_con_uid}'.")
                decision_tomada_sobre_uid = True
            else: 
                self.uid_escaneado_para_formulario.set("") 
                messagebox.showinfo("Escaneo Cancelado", "Se ha limpiado el campo UID. Presione 'Escanear UID' para intentar con otra tarjeta.")
                decision_tomada_sobre_uid = True 
        else: 
            self.uid_escaneado_para_formulario.set(uid_recibido)
            messagebox.showinfo("UID Capturado", f"UID '{uid_recibido}' capturado para el registro.")
            decision_tomada_sobre_uid = True
        
        if decision_tomada_sobre_uid: 
            self.modo_escaneo_rfid_para_registro = False 
            if hasattr(self, 'lbl_mensaje_acceso'): 
                self.lbl_mensaje_acceso.config(text="")

    def validar_formulario_usuario(self, datos, es_edicion=False):
        if not datos["nombre"] or not datos["dni"] or not datos["uid_rfid"]: messagebox.showerror("Error Validación", "Nombre, DNI y UID RFID obligatorios."); return False
        valido_uid, msg_uid = self.validar_formato_uid(datos["uid_rfid"]); 
        if not valido_uid: messagebox.showerror("Error Validación", msg_uid); return False
        if not datos["dni"].isalnum() or len(datos["dni"]) < 5: messagebox.showerror("Error Validación", "DNI inválido."); return False
        if datos["nivel"] == "Trabajador":
            h_i, h_f = datos.get('h_inicio', ""), datos.get('h_fin', "")
            if not h_i or not h_f: messagebox.showerror("Error Validación", "Horarios obligatorios para Trabajador."); return False
            try: datetime.datetime.strptime(h_i, "%H:%M"); datetime.datetime.strptime(h_f, "%H:%M")
            except ValueError: messagebox.showerror("Error Validación", "Formato horario HH:MM para Trabajador."); return False
        excluir_id = self.usuario_a_editar_id if es_edicion else None
        dni_owner = verificar_dni_existente_bd(datos["dni"], excluir_id_usuario=excluir_id)
        if dni_owner: messagebox.showerror("Error Validación", f"DNI '{datos['dni']}' ya existe para '{dni_owner}'."); return False
        uid_owner = verificar_uid_existente_bd(datos["uid_rfid"], excluir_id_usuario=excluir_id)
        if uid_owner: messagebox.showerror("Error Validación", f"UID '{datos['uid_rfid']}' ya existe para '{uid_owner}'."); return False
        return True
    def accion_guardar_usuario_formulario(self):
        datos_f = {"nombre": self.entry_nombre.get().strip(), "dni": self.entry_dni.get().strip(), "nivel": self.combo_nivel.get(), "area": self.entry_area.get().strip(), "uid_rfid": self.uid_escaneado_para_formulario.get().strip().upper(), "h_inicio": self.entry_h_inicio.get().strip() if self.combo_nivel.get() == "Trabajador" else None, "h_fin": self.entry_h_fin.get().strip() if self.combo_nivel.get() == "Trabajador" else None}
        if self.usuario_a_editar_id: 
            if not self.validar_formulario_usuario(datos_f, es_edicion=True): return
            exito, msg = actualizar_usuario_bd(self.usuario_a_editar_id, datos_f)
        else: 
            if not self.validar_formulario_usuario(datos_f, es_edicion=False): return
            exito, msg = agregar_usuario_bd(datos_f)
        if exito: messagebox.showinfo("Éxito", msg); self.limpiar_formulario_usuario(); self.cargar_usuarios_al_treeview()
        else: messagebox.showerror("Error al Guardar", msg)
    def limpiar_formulario_usuario(self):
        self.usuario_a_editar_id = None; self.frame_formulario_usuario.config(text="Registrar Nuevo Usuario"); self.btn_guardar_usuario_form.config(text="Guardar Nuevo Usuario"); self.btn_cancelar_edicion.config(state=tk.DISABLED)
        self.entry_nombre.delete(0, tk.END); self.entry_dni.delete(0, tk.END); self.entry_area.delete(0, tk.END); self.uid_escaneado_para_formulario.set("")
        self.combo_nivel.current(0); self.actualizar_campos_horario_form(); self.entry_nombre.focus()
    def cancelar_edicion_usuario(self): self.limpiar_formulario_usuario()
    def cargar_usuarios_al_treeview(self):
        for i in self.tree_usuarios.get_children(): self.tree_usuarios.delete(i)
        for u in obtener_todos_los_usuarios_bd(): self.tree_usuarios.insert("", "end", values=u)
        self.btn_editar_usuario_lista.config(state=tk.DISABLED); self.btn_borrar_usuario_lista.config(state=tk.DISABLED)
    def al_seleccionar_usuario_lista(self, event=None):
        st = tk.NORMAL if self.tree_usuarios.focus() else tk.DISABLED; self.btn_editar_usuario_lista.config(state=st); self.btn_borrar_usuario_lista.config(state=st)
    def accion_editar_usuario_lista(self):
        sel = self.tree_usuarios.focus();
        if not sel: messagebox.showwarning("Sin Selección", "Seleccione usuario a editar."); return
        id_u = self.tree_usuarios.item(sel)['values'][0]; datos_u = obtener_usuario_por_id_bd(id_u)
        if not datos_u: messagebox.showerror("Error", "No se cargaron datos para edición."); return
        self.limpiar_formulario_usuario(); self.usuario_a_editar_id = id_u; self.frame_formulario_usuario.config(text=f"Editando Usuario ID: {id_u}"); self.btn_guardar_usuario_form.config(text="Guardar Cambios"); self.btn_cancelar_edicion.config(state=tk.NORMAL)
        self.entry_nombre.insert(0, datos_u.get("nombre", "")); self.entry_dni.insert(0, datos_u.get("dni", "")); self.combo_nivel.set(datos_u.get("nivel", "Admin")); self.entry_area.insert(0, datos_u.get("area", ""))
        self.uid_escaneado_para_formulario.set(datos_u.get("uid_rfid", "")); self.actualizar_campos_horario_form()
        if datos_u.get("nivel") == "Trabajador": self.entry_h_inicio.insert(0, datos_u.get("h_inicio", "")); self.entry_h_fin.insert(0, datos_u.get("h_fin", ""))
        self.notebook.select(self.tab_gestion_usuarios); self.entry_nombre.focus()
    def accion_borrar_usuario_lista(self):
        sel = self.tree_usuarios.focus();
        if not sel: messagebox.showwarning("Sin Selección", "Seleccione usuario a borrar."); return
        item = self.tree_usuarios.item(sel); id_u, nom_u = item['values'][0], item['values'][1]
        if messagebox.askyesno("Confirmar Borrado", f"¿Borrar usuario:\nID: {id_u}\nNombre: {nom_u}?"):
            ex, msg = borrar_usuario_bd(id_u); messagebox.showinfo("Resultado", msg) if ex else messagebox.showerror("Error", msg)
            if ex: self.cargar_usuarios_al_treeview()
    def actualizar_reportes_en_gui(self):
        if hasattr(self, 'lbl_contador_accesos_hoy'): self.lbl_contador_accesos_hoy.config(text=str(contador_accesos_hoy))
        if hasattr(self, 'tree_accesos_exitosos'):
            for i in self.tree_accesos_exitosos.get_children(): self.tree_accesos_exitosos.delete(i)
            for ev in eventos_acceso_hoy: vals = tuple(ev.get(c, "N/A") for c in self.tree_accesos_exitosos["columns"]); self.tree_accesos_exitosos.insert("", "end", values=vals)
        if hasattr(self, 'tree_intentos_fallidos'):
            for i in self.tree_intentos_fallidos.get_children(): self.tree_intentos_fallidos.delete(i)
            for ev in intentos_fallidos_hoy: vals = tuple(ev.get(c, "N/A") for c in self.tree_intentos_fallidos["columns"]); self.tree_intentos_fallidos.insert("", "end", values=vals)
    def generar_reporte_dia_actual_manual(self):
        verificar_y_resetear_por_cambio_de_dia(); generar_reporte_final_dia(fecha_actual_para_conteo, contador_accesos_hoy, eventos_acceso_hoy, intentos_fallidos_hoy, bajo_demanda=True)
    def validar_formato_uid(self, uid_str):
        if len(uid_str) != 8: return False, "UID debe tener 8 caracteres."
        if not re.match(r"^[0-9a-fA-F]+$", uid_str): return False, "UID solo hexadecimales."
        return True, ""
    def actualizar_gui_periodicamente(self):
        with lock_datos_hardware:
            for clave_dato, label_widget in self.labels_estado_principal.items():
                valor = datos_hardware.get(clave_dato, "Error")
                if clave_dato == "rfid_uid" and self.modo_escaneo_rfid_para_registro: 
                    if valor != "NADA" and valor != self.uid_escaneado_para_formulario.get(): 
                         self._procesar_rfid_llegado_para_formulario(valor) 
                elif isinstance(valor, float): label_widget.config(text=f"{valor:.1f}")
                else: label_widget.config(text=str(valor))
        if hasattr(self, 'lbl_estado_sistema_valor'): self.lbl_estado_sistema_valor.config(text=estado_actual_sistema.value)
        if hasattr(self, 'lbl_modo_validacion_actual'): self.lbl_modo_validacion_actual.config(text=f"Modo Validación: {protocolo_seleccionado_actual['descripcion']}")
        self.after(200, self.actualizar_gui_periodicamente)
    def al_cerrar_ventana(self):
        print("Cerrando aplicación..."); global hilo_listener_arduino_activo, hilo_maquina_estados_activo
        hilo_listener_arduino_activo = False; hilo_maquina_estados_activo = False
        verificar_y_resetear_por_cambio_de_dia() 
        if fecha_actual_para_conteo:
             print("Generando reporte final antes de salir...")
             generar_reporte_final_dia(fecha_actual_para_conteo, contador_accesos_hoy, 
                                       eventos_acceso_hoy, intentos_fallidos_hoy, bajo_demanda=False)
        if arduino_serial and arduino_serial.is_open: arduino_serial.close()
        self.destroy()

# --- FUNCIONES DE COMUNICACIÓN CON ARDUINO ---
def conectar_a_arduino():
    global arduino_serial, arduino_conectado
    try:
        arduino_serial = serial.Serial(PUERTO_SERIAL_ARDUINO, VELOCIDAD_ARDUINO, timeout=TIMEOUT_SERIAL)
        time.sleep(2)
        timeout_inicio = time.time()
        while time.time() - timeout_inicio < 10:
            if arduino_serial.in_waiting > 0:
                linea = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
                if linea == "ARDUINO_LISTO":
                    arduino_conectado = True; print("Arduino conectado y listo."); return True
            time.sleep(0.1)
        print("Error: No se recibió ARDUINO_LISTO de Arduino.")
        if arduino_serial and arduino_serial.is_open: arduino_serial.close()
        return False
    except serial.SerialException as e: print(f"Error al conectar: {e}"); return False
def enviar_comando_a_arduino(comando_str):
    if arduino_conectado and arduino_serial and arduino_serial.is_open:
        try: arduino_serial.write(f"COMANDO:{comando_str}\n".encode('utf-8'))
        except Exception as e: print(f"Error al enviar comando: {e}")
def escuchar_datos_arduino(): 
    global arduino_conectado, hilo_listener_arduino_activo
    print("Hilo listener de Arduino iniciado.")
    while hilo_listener_arduino_activo:
        if not arduino_conectado or not arduino_serial or not arduino_serial.is_open:
            time.sleep(1) 
            if hilo_listener_arduino_activo and not conectar_a_arduino(): time.sleep(4) 
            continue
        try:
            if arduino_serial.in_waiting > 0:
                linea_str = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
                if linea_str and linea_str.startswith("DATOS;"):
                    partes = linea_str.split(';')
                    if len(partes) == 7: 
                        with lock_datos_hardware:
                            try:
                                datos_hardware["sp1_distancia"] = float(partes[1].split(':')[1])
                                datos_hardware["sp2_distancia"] = float(partes[2].split(':')[1])
                                datos_hardware["s1_estado"] = int(partes[3].split(':')[1]) 
                                datos_hardware["s2_estado"] = int(partes[4].split(':')[1]) 
                                datos_hardware["e_estado"] = int(partes[5].split(':')[1])   
                                datos_hardware["rfid_uid"] = partes[6].split(':')[1] 
                            except (ValueError, IndexError) as e: print(f"Error parseo: {e} -> {linea_str}")
        except serial.SerialException as se:
            print(f"Error Serial listener: {se}"); arduino_conectado = False
            if arduino_serial and arduino_serial.is_open: arduino_serial.close()
        except Exception as e: print(f"Error listener: {e}"); time.sleep(1)
        time.sleep(0.01)
    print("Hilo listener de Arduino terminado.")

# ==============================================================================
# LÓGICA DE SELECCIÓN DE PROTOCOLO Y MÁQUINA DE ESTADOS
# ==============================================================================
def determinar_protocolo_activo(s1_estado_hw, s2_estado_hw):
    global protocolo_seleccionado_actual 
    protocolo_anterior_desc = protocolo_seleccionado_actual["descripcion"]
    if s1_estado_hw == 0 and s2_estado_hw == 0: protocolo_seleccionado_actual = {"rfid": True, "qr": True, "facial": False, "descripcion": "RFID + QR"}
    elif s1_estado_hw == 0 and s2_estado_hw == 1: protocolo_seleccionado_actual = {"rfid": True, "qr": False, "facial": True, "descripcion": "RFID + Facial"}
    elif s1_estado_hw == 1 and s2_estado_hw == 0: protocolo_seleccionado_actual = {"rfid": False, "qr": True, "facial": True, "descripcion": "QR + Facial"}
    elif s1_estado_hw == 1 and s2_estado_hw == 1: protocolo_seleccionado_actual = {"rfid": True, "qr": False, "facial": False, "descripcion": "Solo RFID"}
    if protocolo_seleccionado_actual["descripcion"] != protocolo_anterior_desc:
        print(f"Protocolo cambiado a: {protocolo_seleccionado_actual['descripcion']}")
        # La actualización del label en la GUI se hace en actualizar_gui_periodicamente
    return protocolo_seleccionado_actual

def cambiar_estado(nuevo_estado, mensaje_gui=""):
    global estado_actual_sistema, tiempo_inicio_estado_actual_s, app_gui
    if estado_actual_sistema != nuevo_estado:
        print(f"Cambiando estado de {estado_actual_sistema.value} a {nuevo_estado.value}")
        estado_actual_sistema = nuevo_estado
        tiempo_inicio_estado_actual_s = time.time()
    color_mensaje = "blue"
    if "Denegado" in mensaje_gui or "Error" in mensaje_gui or "bloqueado" in mensaje_gui or "ALERTA" in mensaje_gui: color_mensaje = "red"
    elif "Concedido" in mensaje_gui: color_mensaje = "green"
    if app_gui and hasattr(app_gui, 'lbl_mensaje_acceso'): 
        if mensaje_gui: app_gui.lbl_mensaje_acceso.config(text=mensaje_gui, foreground=color_mensaje)
        elif estado_actual_sistema not in [EstadoSistema.ACCESO_DENEGADO_TEMPORAL, EstadoSistema.SISTEMA_BLOQUEADO_UID]: 
             app_gui.lbl_mensaje_acceso.config(text="")

def logica_maquina_estados():
    global puerta_logicamente_abierta, tiempo_puerta_abrio_s, tiempo_sp2_detecto_primera_vez_s 
    global datos_hardware, app_gui, protocolo_seleccionado_actual, estado_validacion_secuencial
    
    print("Hilo de Máquina de Estados iniciado.")
    inicializar_bd(); cargar_estado_diario() 
    if app_gui and hasattr(app_gui, 'actualizar_reportes_en_gui'): app_gui.actualizar_reportes_en_gui()

    with lock_datos_hardware: 
        s1_prev = datos_hardware["s1_estado"]; s2_prev = datos_hardware["s2_estado"]
        # Determinar protocolo inicial y actualizar GUI
        protocolo_seleccionado_actual = determinar_protocolo_activo(s1_prev, s2_prev) 
        if app_gui and hasattr(app_gui, 'lbl_modo_validacion_actual'):
            app_gui.lbl_modo_validacion_actual.config(text=f"Modo Validación: {protocolo_seleccionado_actual['descripcion']}")


    while hilo_maquina_estados_activo:
        tiempo_actual_s = time.time()
        if verificar_y_resetear_por_cambio_de_dia(): 
            if app_gui and hasattr(app_gui, 'actualizar_reportes_en_gui'): app_gui.actualizar_reportes_en_gui()

        with lock_datos_hardware: 
            dist_sp1 = datos_hardware["sp1_distancia"]; dist_sp2 = datos_hardware["sp2_distancia"]
            uid_actual_arduino = datos_hardware["rfid_uid"]
            ultimo_rfid_procesado_acceso = datos_hardware["ultimo_rfid_procesado_para_acceso"]
            s1_hw = datos_hardware["s1_estado"]; s2_hw = datos_hardware["s2_estado"]

        if s1_hw != s1_prev or s2_hw != s2_prev: 
            protocolo_seleccionado_actual = determinar_protocolo_activo(s1_hw, s2_hw) 
            s1_prev, s2_prev = s1_hw, s2_hw
            # La GUI se actualiza en su propio ciclo (actualizar_gui_periodicamente)
            if estado_actual_sistema not in [EstadoSistema.REPOSO, EstadoSistema.ABRIENDO_PUERTA, EstadoSistema.PERSONA_CRUZANDO, EstadoSistema.CERRANDO_PUERTA]:
                 cambiar_estado(EstadoSistema.REPOSO, "Protocolo cambiado, reiniciando.")
        
        if estado_actual_sistema == EstadoSistema.REPOSO:
            enviar_comando_a_arduino("LED_VERDE_OFF"); enviar_comando_a_arduino("LED_ROJO_OFF")
            if ultimo_rfid_procesado_acceso != "NADA":
                with lock_datos_hardware: datos_hardware["ultimo_rfid_procesado_para_acceso"] = "NADA" 
            estado_validacion_secuencial.clear()
            if puerta_logicamente_abierta: cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Error: Puerta abierta, cerrando."); continue
            if 0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM:
                print(f"SP1 detectó. Protocolo: {protocolo_seleccionado_actual['descripcion']}")
                if protocolo_seleccionado_actual["rfid"]:
                    enviar_comando_a_arduino("SOLICITAR_LECTURA_RFID"); cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_RFID, "Presente su tarjeta RFID...")
                elif protocolo_seleccionado_actual["qr"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_QR, "Prepare su código QR...")
                elif protocolo_seleccionado_actual["facial"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_FACIAL, "Mire a la cámara...")
                else: cambiar_estado(EstadoSistema.ABRIENDO_PUERTA, "Acceso directo (prot. sin validación).") 
        
        elif estado_actual_sistema == EstadoSistema.ESPERANDO_VALIDACION_RFID:
            if not (0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM): cambiar_estado(EstadoSistema.REPOSO, "Usuario se retiró."); continue
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > TIMEOUT_PRESENTACION_RFID_S:
                uid_t = uid_actual_arduino if uid_actual_arduino!="NADA"and uid_actual_arduino!=ultimo_rfid_procesado_acceso else None
                registrar_intento_fallido(uid_t, None, "Timeout Presentación RFID"); cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Tiempo agotado RFID."); continue
            if uid_actual_arduino != "NADA" and uid_actual_arduino != ultimo_rfid_procesado_acceso:
                print(f"RFID Recibido para validación: {uid_actual_arduino}") # CORRECCIÓN AQUÍ
                with lock_datos_hardware: datos_hardware["ultimo_rfid_procesado_para_acceso"] = uid_actual_arduino
                d_b = intentos_fallidos_por_uid.get(uid_actual_arduino)
                if d_b and d_b.get("desbloqueo_hasta",0) > tiempo_actual_s:
                    t_r_b=int(d_b["desbloqueo_hasta"]-tiempo_actual_s); msg_b=f"UID {uid_actual_arduino} bloqueado. Intente en {max(0,t_r_b)//60}m {max(0,t_r_b)%60}s."
                    print(msg_b); registrar_intento_fallido(uid_actual_arduino,None,"Intento con UID bloqueado",False); cambiar_estado(EstadoSistema.SISTEMA_BLOQUEADO_UID,msg_b); continue 
                u_info = obtener_usuario_por_rfid_bd(uid_actual_arduino); acc_val = False; msg_den = "Acceso Denegado."; mot_fallo = "Tarjeta no reconocida"
                if u_info:
                    ts_ult_acc = accesos_recientes_uid.get(uid_actual_arduino)
                    if ts_ult_acc and (tiempo_actual_s - ts_ult_acc < TIEMPO_COOLDOWN_ACCESO_S):
                        t_r_c = int(TIEMPO_COOLDOWN_ACCESO_S - (tiempo_actual_s - ts_ult_acc)); msg_den = f"Acceso reciente ({u_info['nombre']}). Intente en {max(0,t_r_c)//60}m {max(0,t_r_c)%60}s."
                        mot_fallo = "Cooldown Anti-Passback activo"; registrar_intento_fallido(uid_actual_arduino,u_info,mot_fallo,False); enviar_comando_a_arduino("LED_ROJO_ON"); cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL,msg_den); continue 
                    mot_fallo = f"Nivel: {u_info['nivel']}" 
                    if u_info["nivel"] == "Admin": acc_val = True
                    elif u_info["nivel"] == "Trabajador":
                        if verificar_horario_trabajador(u_info["h_inicio"], u_info["h_fin"]): acc_val = True
                        else: msg_den = "Fuera de horario laboral."; mot_fallo += " - Fuera Horario"
                    elif u_info["nivel"] == "Visitante":
                        if verificar_horario_visitante(): acc_val = True
                        else: msg_den = "Fuera de horario de visita."; mot_fallo += " - Fuera Horario"
                if acc_val:
                    estado_validacion_secuencial["rfid_ok"] = True; estado_validacion_secuencial["usuario_validado_rfid"] = u_info
                    if protocolo_seleccionado_actual["qr"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_QR, "RFID OK. Prepare QR...")
                    elif protocolo_seleccionado_actual["facial"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_FACIAL, "RFID OK. Mire a cámara...")
                    else: registrar_evento_acceso_exitoso(u_info); enviar_comando_a_arduino("LED_VERDE_ON"); cambiar_estado(EstadoSistema.ABRIENDO_PUERTA, f"Acceso Concedido: {u_info['nombre']}")
                else: 
                    print(f"DENEGADO (RFID): {msg_den}"); se_bloq = registrar_intento_fallido(uid_actual_arduino,u_info,mot_fallo,True) 
                    if se_bloq:
                         d_b_a=intentos_fallidos_por_uid.get(uid_actual_arduino,{});t_r_bl=int(d_b_a.get("desbloqueo_hasta",tiempo_actual_s)-tiempo_actual_s)
                         msg_bl=f"UID {uid_actual_arduino} bloqueado. Intente en {max(0,t_r_bl)//60}m {max(0,t_r_bl)%60}s."
                         cambiar_estado(EstadoSistema.SISTEMA_BLOQUEADO_UID,msg_bl)
                    else: enviar_comando_a_arduino("LED_ROJO_ON"); cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL,msg_den)

        elif estado_actual_sistema == EstadoSistema.ESPERANDO_VALIDACION_QR:
            if not (0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM): cambiar_estado(EstadoSistema.REPOSO, "Usuario se retiró (esperando QR)."); estado_validacion_secuencial.clear(); continue
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > TIMEOUT_SIMULACION_QR_S:
                registrar_intento_fallido(estado_validacion_secuencial.get("usuario_validado_rfid",{}).get("uid_rfid"), estado_validacion_secuencial.get("usuario_validado_rfid"), "Timeout Simulación QR", False)
                cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Tiempo agotado para QR."); estado_validacion_secuencial.clear(); continue
            if not estado_validacion_secuencial.get("_qr_sim_asked", False):
                estado_validacion_secuencial["_qr_sim_asked"] = True
                print("SIMULACIÓN QR: Esperando 3s y decidiendo (True)...") # Simular éxito
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > 3: 
                qr_ok_simulado = True 
                print(f"SIMULACIÓN: QR {'Exitoso' if qr_ok_simulado else 'Fallido'}.")
                estado_validacion_secuencial["qr_ok"] = qr_ok_simulado; estado_validacion_secuencial.pop("_qr_sim_asked", None) 
                if qr_ok_simulado:
                    u_actual = estado_validacion_secuencial.get("usuario_validado_rfid")
                    if protocolo_seleccionado_actual["facial"] and not estado_validacion_secuencial.get("rfid_ok"): 
                        cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_FACIAL, "QR OK. Mire a cámara...")
                    else: 
                        if not u_actual: u_actual = {"nombre": "Usuario QR", "dni": "N/A_QR", "nivel": "Visitante", "area":"N/A", "uid_rfid": "QR_SIM_VALIDO"}
                        registrar_evento_acceso_exitoso(u_actual); enviar_comando_a_arduino("LED_VERDE_ON")
                        cambiar_estado(EstadoSistema.ABRIENDO_PUERTA, f"Acceso Concedido: {u_actual['nombre']} (QR OK)")
                else: 
                    registrar_intento_fallido(estado_validacion_secuencial.get("usuario_validado_rfid",{}).get("uid_rfid"), estado_validacion_secuencial.get("usuario_validado_rfid"), "Fallo Simulación QR", False)
                    enviar_comando_a_arduino("LED_ROJO_ON"); cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "QR Inválido (Simulado).")
        
        elif estado_actual_sistema == EstadoSistema.ESPERANDO_VALIDACION_FACIAL:
            if not (0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM): cambiar_estado(EstadoSistema.REPOSO, "Usuario se retiró (esperando Facial)."); estado_validacion_secuencial.clear(); continue
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > TIMEOUT_SIMULACION_FACIAL_S:
                registrar_intento_fallido(estado_validacion_secuencial.get("usuario_validado_rfid",{}).get("uid_rfid"), estado_validacion_secuencial.get("usuario_validado_rfid"), "Timeout Simulación Facial", False)
                cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Tiempo agotado para Facial."); estado_validacion_secuencial.clear(); continue
            if not estado_validacion_secuencial.get("_facial_sim_asked", False):
                estado_validacion_secuencial["_facial_sim_asked"] = True
                print("SIMULACIÓN FACIAL: Esperando 3s y decidiendo (True)...") # Simular éxito
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > 3:
                facial_ok_simulado = False
                print(f"SIMULACIÓN: Facial {'Exitoso' if facial_ok_simulado else 'Fallido'}.")
                estado_validacion_secuencial["facial_ok"] = facial_ok_simulado; estado_validacion_secuencial.pop("_facial_sim_asked", None)
                if facial_ok_simulado:
                    u_actual = estado_validacion_secuencial.get("usuario_validado_rfid")
                    if not u_actual: u_actual = {"nombre": "Usuario Facial/QR", "dni": "N/A_FC", "nivel": "Visitante", "area":"N/A", "uid_rfid": "FACIAL_SIM_VALIDO"}
                    registrar_evento_acceso_exitoso(u_actual); enviar_comando_a_arduino("LED_VERDE_ON")
                    cambiar_estado(EstadoSistema.ABRIENDO_PUERTA, f"Acceso Concedido: {u_actual['nombre']} (Facial OK)")
                else:
                    registrar_intento_fallido(estado_validacion_secuencial.get("usuario_validado_rfid",{}).get("uid_rfid"), estado_validacion_secuencial.get("usuario_validado_rfid"), "Fallo Simulación Facial", False)
                    enviar_comando_a_arduino("LED_ROJO_ON"); cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Facial Inválido (Simulado).")

        elif estado_actual_sistema == EstadoSistema.SISTEMA_BLOQUEADO_UID:
            if not (0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM): cambiar_estado(EstadoSistema.REPOSO, "Usuario se retiró durante bloqueo."); continue
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > 60: cambiar_estado(EstadoSistema.REPOSO, "Timeout UID_BLOQUEADO.")
        elif estado_actual_sistema == EstadoSistema.ACCESO_DENEGADO_TEMPORAL:
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > 2.5: 
                enviar_comando_a_arduino("LED_ROJO_OFF")
                if 0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM: 
                     estado_validacion_secuencial.clear() 
                     if protocolo_seleccionado_actual["rfid"]:
                         enviar_comando_a_arduino("SOLICITAR_LECTURA_RFID"); cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_RFID, "Presente su tarjeta RFID...")
                     elif protocolo_seleccionado_actual["qr"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_QR, "Prepare su código QR...")
                     elif protocolo_seleccionado_actual["facial"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_FACIAL, "Mire a la cámara...")
                     else: cambiar_estado(EstadoSistema.REPOSO)
                else: cambiar_estado(EstadoSistema.REPOSO, "Sistema en reposo.")
        elif estado_actual_sistema == EstadoSistema.ABRIENDO_PUERTA:
            if not puerta_logicamente_abierta: enviar_comando_a_arduino("ABRIR_PUERTA"); puerta_logicamente_abierta = True; tiempo_puerta_abrio_s = tiempo_actual_s; tiempo_sp2_detecto_primera_vez_s = 0
            sp1_libre = not (0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM); sp2_detecta = (0 < dist_sp2 < UMBRAL_DETECCION_SP2_CM)
            if sp1_libre and sp2_detecta: tiempo_sp2_detecto_primera_vez_s = tiempo_actual_s; cambiar_estado(EstadoSistema.PERSONA_CRUZANDO)
            elif tiempo_actual_s - tiempo_puerta_abrio_s > TIEMPO_ESPERA_APERTURA_PUERTA_S:
                if not sp1_libre: cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "SP1 obstruido. Cerrando.")
                else: cambiar_estado(EstadoSistema.PERSONA_CRUZANDO) 
            if puerta_logicamente_abierta and (tiempo_actual_s - tiempo_puerta_abrio_s > TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S): cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Timeout puerta abierta.")
        elif estado_actual_sistema == EstadoSistema.PERSONA_CRUZANDO:
            sp1_detecta_ahora = (0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM); sp2_detecta_ahora = (0 < dist_sp2 < UMBRAL_DETECCION_SP2_CM)
            if sp1_detecta_ahora and sp2_detecta_ahora: enviar_comando_a_arduino("LED_ROJO_PARPADEAR_ALERTA"); cambiar_estado(EstadoSistema.ALERTA_ERROR_CRUCE, "ALERTA: SP1 y SP2 activos!"); continue
            if sp2_detecta_ahora and tiempo_sp2_detecto_primera_vez_s == 0: tiempo_sp2_detecto_primera_vez_s = tiempo_actual_s
            if not sp2_detecta_ahora and tiempo_sp2_detecto_primera_vez_s != 0: cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Persona cruzó.")
            elif sp2_detecta_ahora and tiempo_sp2_detecto_primera_vez_s != 0 and (tiempo_actual_s - tiempo_sp2_detecto_primera_vez_s > TIEMPO_MAX_SP2_ACTIVO_S): cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "SP2 activo mucho tiempo.")
            if puerta_logicamente_abierta and (tiempo_actual_s - tiempo_puerta_abrio_s > TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S): cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Timeout puerta abierta.")
        elif estado_actual_sistema == EstadoSistema.ALERTA_ERROR_CRUCE:
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > 2.0: cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Alerta manejada.")
        elif estado_actual_sistema == EstadoSistema.CERRANDO_PUERTA:
            enviar_comando_a_arduino("LED_VERDE_OFF") 
            if puerta_logicamente_abierta: enviar_comando_a_arduino("CERRAR_PUERTA"); puerta_logicamente_abierta = False
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > TIEMPO_CIERRE_PUERTA_S: cambiar_estado(EstadoSistema.REPOSO, "Sistema en reposo.")
        
        time.sleep(0.1)
    print("Hilo de Máquina de Estados terminado.")

# --- FUNCIÓN PRINCIPAL ---
if __name__ == "__main__":
    app_gui = InterfazGrafica() 
    if not conectar_a_arduino():
        if app_gui: messagebox.showerror("Error Conexión", f"No se pudo conectar a Arduino en {PUERTO_SERIAL_ARDUINO}.\nCerrando."); app_gui.after(100, app_gui.destroy) 
        else: print(f"No se pudo conectar a Arduino en {PUERTO_SERIAL_ARDUINO}. Saliendo.")
        exit() 
    hilo_escucha = threading.Thread(target=escuchar_datos_arduino, daemon=True); hilo_escucha.start()
    hilo_estados = threading.Thread(target=logica_maquina_estados, daemon=True); hilo_estados.start()
    if app_gui: 
        try: app_gui.mainloop()
        except Exception as e_gui: print(f"Error GUI: {e_gui}")
    print("Saliendo..."); hilo_listener_arduino_activo = False; hilo_maquina_estados_activo = False
    time.sleep(0.2) 
    if 'hilo_escucha' in locals() and hilo_escucha.is_alive(): print("Esperando listener..."); hilo_escucha.join(timeout=1)
    if 'hilo_estados' in locals() and hilo_estados.is_alive(): print("Esperando estados..."); hilo_estados.join(timeout=1)
    print("Programa terminado.")