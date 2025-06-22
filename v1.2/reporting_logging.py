import json
import csv
import os
import datetime
import time 
from tkinter import messagebox # Para mostrar mensajes si app_gui está disponible
import sys
import threading
import shutil

# Importar Constantes
import constants

# Determinar la ubicación de la carpeta de reportes y el archivo de estado diario
if getattr(sys, 'frozen', False):
    # Si estamos en un ejecutable
    application_path = os.path.dirname(sys.executable)
else:
    # Si estamos en modo desarrollo
    application_path = os.path.dirname(os.path.abspath(__file__))

CARPETA_REPORTES = os.path.join(application_path, constants.CARPETA_REPORTES)
ARCHIVO_ESTADO_DIARIO = os.path.join(application_path, constants.ARCHIVO_ESTADO_DIARIO)

# Crear la carpeta de reportes si no existe
if not os.path.exists(CARPETA_REPORTES):
    try:
        os.makedirs(CARPETA_REPORTES)
        print(f"Carpeta '{CARPETA_REPORTES}' creada.")
    except OSError as e:
        print(f"Error al crear la carpeta de reportes '{CARPETA_REPORTES}': {e}")

# --- Variables Globales del Módulo ---
contador_accesos_hoy = 0
eventos_acceso_hoy = [] 
intentos_fallidos_hoy = [] 
fecha_actual_para_conteo = datetime.date.today().strftime("%Y-%m-%d")

# Estos diccionarios son leídos/escritos por este módulo como parte del estado diario,
# pero su lógica principal de actualización (incrementar contadores, aplicar bloqueos)
# residirá en state_machine_logic.py. Este módulo los persiste.
intentos_fallidos_por_uid = {} 
accesos_recientes_uid = {}   

app_gui_ref_reporting = None # Referencia a la instancia de la GUI

def asignar_app_gui_referencia_reporting(gui_instance):
    """Permite que el módulo principal o la GUI asigne la instancia de la GUI."""
    global app_gui_ref_reporting
    app_gui_ref_reporting = gui_instance

# ==============================================================================
# FUNCIONES DE MANEJO DE ESTADO DIARIO Y REPORTES
# ==============================================================================

def cargar_estado_diario():
    global contador_accesos_hoy, eventos_acceso_hoy, intentos_fallidos_hoy, fecha_actual_para_conteo
    global intentos_fallidos_por_uid, accesos_recientes_uid
    
    fecha_hoy_str = datetime.date.today().strftime("%Y-%m-%d")
    
    if os.path.exists(ARCHIVO_ESTADO_DIARIO):
        try:
            with open(ARCHIVO_ESTADO_DIARIO, 'r') as f:
                estado_guardado = json.load(f)
            
            if estado_guardado.get("fecha") == fecha_hoy_str:
                contador_accesos_hoy = estado_guardado.get("contador_accesos", 0)
                eventos_acceso_hoy = estado_guardado.get("eventos_accesos_exitosos", [])
                intentos_fallidos_hoy = estado_guardado.get("intentos_accesos_fallidos", [])
                intentos_fallidos_por_uid = estado_guardado.get("intentos_fallidos_por_uid", {}) 
                accesos_recientes_uid = estado_guardado.get("accesos_recientes_uid", {})       
                
                ahora_ts = time.time()
                intentos_fallidos_por_uid = {uid:data for uid,data in intentos_fallidos_por_uid.items() if data.get("desbloqueo_hasta",0) > ahora_ts}
                accesos_recientes_uid = {uid:ts for uid,ts in accesos_recientes_uid.items() if (ahora_ts - ts) < constants.TIEMPO_COOLDOWN_ACCESO_S}
                
                print("Estado diario cargado para hoy.")
            else: 
                print(f"Nuevo día detectado. Fecha guardada: {estado_guardado.get('fecha')}, Fecha hoy: {fecha_hoy_str}")
                if estado_guardado.get("fecha"): 
                    generar_reporte_final_dia(estado_guardado.get("fecha"), 
                                              estado_guardado.get("contador_accesos",0),
                                              estado_guardado.get("eventos_accesos_exitosos",[]),
                                              estado_guardado.get("intentos_accesos_fallidos",[]))
                contador_accesos_hoy = 0; eventos_acceso_hoy = []; intentos_fallidos_hoy = []
                intentos_fallidos_por_uid = {}; accesos_recientes_uid = {}
        except (json.JSONDecodeError, IOError, TypeError) as e:
            print(f"Error al leer {ARCHIVO_ESTADO_DIARIO} o archivo corrupto: {e}. Empezando de cero para hoy.")
            contador_accesos_hoy = 0; eventos_acceso_hoy = []; intentos_fallidos_hoy = []
            intentos_fallidos_por_uid = {}; accesos_recientes_uid = {}
    else:
        print(f"{ARCHIVO_ESTADO_DIARIO} no encontrado. Empezando de cero para hoy.")
        contador_accesos_hoy = 0; eventos_acceso_hoy = []; intentos_fallidos_hoy = []
        intentos_fallidos_por_uid = {}; accesos_recientes_uid = {}

    fecha_actual_para_conteo = fecha_hoy_str
    guardar_estado_diario() 

def guardar_estado_diario():
    global contador_accesos_hoy, eventos_acceso_hoy, intentos_fallidos_hoy, fecha_actual_para_conteo
    global intentos_fallidos_por_uid, accesos_recientes_uid
    
    estado_a_guardar = {
        "fecha": fecha_actual_para_conteo,
        "contador_accesos": contador_accesos_hoy,
        "eventos_accesos_exitosos": eventos_acceso_hoy,
        "intentos_accesos_fallidos": intentos_fallidos_hoy,
        "intentos_fallidos_por_uid": intentos_fallidos_por_uid, 
        "accesos_recientes_uid": accesos_recientes_uid        
    }
    try:
        with open(ARCHIVO_ESTADO_DIARIO, 'w') as f:
            json.dump(estado_a_guardar, f, indent=4)
    except IOError as e:
        print(f"Error al guardar {ARCHIVO_ESTADO_DIARIO}: {e}")

def verificar_y_resetear_por_cambio_de_dia():
    global fecha_actual_para_conteo, contador_accesos_hoy, eventos_acceso_hoy, intentos_fallidos_hoy
    global intentos_fallidos_por_uid, accesos_recientes_uid, app_gui_ref_reporting
    
    fecha_hoy_str = datetime.date.today().strftime("%Y-%m-%d")
    if fecha_actual_para_conteo != fecha_hoy_str:
        print(f"Detectado cambio de día (en reporting_logging): {fecha_actual_para_conteo} -> {fecha_hoy_str}. Generando reporte y reseteando.")
        if fecha_actual_para_conteo: # Solo generar si había una fecha anterior válida
            generar_reporte_final_dia(fecha_actual_para_conteo, contador_accesos_hoy, eventos_acceso_hoy, intentos_fallidos_hoy)
        
        contador_accesos_hoy = 0
        eventos_acceso_hoy = []
        intentos_fallidos_hoy = []
        intentos_fallidos_por_uid.clear() 
        accesos_recientes_uid.clear()   
        fecha_actual_para_conteo = fecha_hoy_str 
        guardar_estado_diario() 
        
        if app_gui_ref_reporting and hasattr(app_gui_ref_reporting,'actualizar_reportes_en_gui'):
            app_gui_ref_reporting.actualizar_reportes_en_gui()
        return True 
    return False

def registrar_evento_acceso_exitoso(usuario_info):
    """
    Registra un evento de acceso exitoso.
    'usuario_info' es un diccionario con los datos del usuario que accedió.
    Actualiza contadores, logs en memoria y el archivo de estado diario.
    """
    global contador_accesos_hoy, eventos_acceso_hoy, accesos_recientes_uid, intentos_fallidos_por_uid, app_gui_ref_reporting
    
    # Esta verificación es importante para asegurar que los datos son para el día correcto
    verificar_y_resetear_por_cambio_de_dia()

    contador_accesos_hoy += 1
    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    evento = {
        "timestamp_acceso": timestamp_str,
        "nombre_usuario": usuario_info.get("nombre", "N/A"),
        "dni_usuario": usuario_info.get("dni", "N/A"),
        "nivel_usuario": usuario_info.get("nivel", "N/A"),
        "area_trabajo": usuario_info.get("area", "N/A"),
        "uid_rfid_usado": usuario_info.get("uid_rfid", "N/A_FACIAL_U_OTRO") 
    }
    eventos_acceso_hoy.append(evento)
    
    # Actualizar cooldown para este identificador de usuario
    id_para_cooldown = usuario_info.get("uid_rfid") or usuario_info.get("dni") or usuario_info.get("nombre", f"User_{timestamp_str}")
    accesos_recientes_uid[id_para_cooldown] = time.time()
    
    # Si el acceso fue exitoso, resetear contador de fallos para ese identificador (si es UID RFID)
    if usuario_info.get("uid_rfid") and usuario_info.get("uid_rfid") in intentos_fallidos_por_uid:
        print(f"Reseteando contador de fallos para UID '{usuario_info['uid_rfid']}' tras acceso exitoso.")
        del intentos_fallidos_por_uid[usuario_info["uid_rfid"]]
        
    guardar_estado_diario()
    print(f"Acceso exitoso registrado: {usuario_info.get('nombre', 'Usuario Desconocido')}. Total hoy: {contador_accesos_hoy}")
    
    if app_gui_ref_reporting and hasattr(app_gui_ref_reporting,'actualizar_reportes_en_gui'):
        app_gui_ref_reporting.actualizar_reportes_en_gui()

def registrar_intento_fallido(uid_presentado, usuario_info_si_conocido, motivo_fallo, contar_para_bloqueo_insistencia=True):
    """
    Registra un intento de acceso fallido.
    Actualiza logs y maneja la lógica de bloqueo por insistencia si aplica.
    Devuelve True si se aplicó un bloqueo como resultado de este fallo, False en caso contrario.
    """
    global intentos_fallidos_hoy, intentos_fallidos_por_uid, app_gui_ref_reporting
    
    verificar_y_resetear_por_cambio_de_dia()

    timestamp_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    nombre_detectado_log = "Desconocido"
    dni_detectado_log = "N/A"
    
    if usuario_info_si_conocido:
        nombre_detectado_log = usuario_info_si_conocido.get("nombre", "Desconocido (Info Parcial)")
        dni_detectado_log = usuario_info_si_conocido.get("dni", "N/A (Info Parcial)")

    intento = {
        "timestamp_intento": timestamp_str,
        "uid_rfid_presentado": uid_presentado if uid_presentado else "N/A",
        "nombre_usuario_detectado": nombre_detectado_log, 
        "dni_usuario_detectado": dni_detectado_log,
        "motivo_fallo": motivo_fallo
    }
    intentos_fallidos_hoy.append(intento)
    se_produjo_bloqueo_ahora = False
    
    # El bloqueo por insistencia se liga al identificador primario (UID RFID si existe, sino DNI, sino Nombre)
    id_para_bloqueo = uid_presentado 
    if not id_para_bloqueo and usuario_info_si_conocido: 
        id_para_bloqueo = usuario_info_si_conocido.get("dni") or usuario_info_si_conocido.get("nombre")

    if contar_para_bloqueo_insistencia and id_para_bloqueo and id_para_bloqueo not in ["NADA", "N/A"]:
        if id_para_bloqueo not in intentos_fallidos_por_uid:
            intentos_fallidos_por_uid[id_para_bloqueo] = {"contador": 0, "nivel_bloqueo": 0, "desbloqueo_hasta": 0}
        
        data_bloqueo_id = intentos_fallidos_por_uid[id_para_bloqueo]
        
        # Solo contar si no está actualmente bloqueado (o el bloqueo ya pasó)
        if data_bloqueo_id.get("desbloqueo_hasta", 0) <= time.time():
            data_bloqueo_id["contador"] += 1
            print(f"Intento fallido (contado p/bloqueo) ID '{id_para_bloqueo}'. Conteo: {data_bloqueo_id['contador']}")
            
            if data_bloqueo_id["contador"] >= constants.MAX_INTENTOS_FALLIDOS_UID:
                nivel_actual = data_bloqueo_id.get("nivel_bloqueo", 0)
                nuevo_nivel = min(nivel_actual + 1, 3) # Max nivel de bloqueo 3
                
                data_bloqueo_id["nivel_bloqueo"] = nuevo_nivel
                duracion_bloqueo_s = constants.TIEMPO_BLOQUEO_UID_NIVEL[nuevo_nivel] 
                data_bloqueo_id["desbloqueo_hasta"] = time.time() + duracion_bloqueo_s
                data_bloqueo_id["contador"] = 0 # Resetear contador para este nivel de bloqueo
                
                desbloqueo_dt = datetime.datetime.fromtimestamp(data_bloqueo_id["desbloqueo_hasta"])
                print(f"ID '{id_para_bloqueo}' bloqueado hasta {desbloqueo_dt.strftime('%Y-%m-%d %H:%M:%S')} (Nivel {nuevo_nivel}).")
                se_produjo_bloqueo_ahora = True
    else:
        print(f"Intento fallido (NO contado p/bloqueo) ID '{id_para_bloqueo if id_para_bloqueo else 'N/A'}'. Motivo: {motivo_fallo}")
        
    guardar_estado_diario()
    if app_gui_ref_reporting and hasattr(app_gui_ref_reporting,'actualizar_reportes_en_gui'):
        app_gui_ref_reporting.actualizar_reportes_en_gui()
    return se_produjo_bloqueo_ahora

def generar_reporte_final_dia(fecha_str, contador_total, lista_eventos_exitosos, lista_eventos_fallidos, bajo_demanda=False):
    global app_gui_ref_reporting
    if not fecha_str or (not lista_eventos_exitosos and not lista_eventos_fallidos and contador_total == 0 and not bajo_demanda):
        if bajo_demanda and app_gui_ref_reporting:
            messagebox.showinfo("Info Reporte", f"No hay datos para generar reporte para {fecha_str}.")
        elif bajo_demanda: 
            print(f"No hay datos para generar reporte para {fecha_str}.")
        return

    # Asegurarse que la carpeta de reportes exista
    if not os.path.exists(CARPETA_REPORTES):
        try:
            os.makedirs(CARPETA_REPORTES)
        except OSError as e:
            print(f"Error creando carpeta de reportes '{CARPETA_REPORTES}': {e}")
            if bajo_demanda and app_gui_ref_reporting:
                messagebox.showerror("Error Reporte", f"No se pudo crear la carpeta de reportes:\n{e}")
            return

    nombre_archivo_json = os.path.join(CARPETA_REPORTES, f"reporte_{fecha_str}.json")
    reporte_data_json = {
        "fecha_reporte": fecha_str,
        "total_accesos_exitosos_dia": contador_total,
        "log_accesos_exitosos": lista_eventos_exitosos if lista_eventos_exitosos else [],
        "log_intentos_fallidos": lista_eventos_fallidos if lista_eventos_fallidos else []
    }
    error_json_report = None 
    try:
        with open(nombre_archivo_json, 'w') as f_json:
            json.dump(reporte_data_json, f_json, indent=4)
        print(f"Reporte JSON generado: {nombre_archivo_json}")
        if bajo_demanda and app_gui_ref_reporting:
            messagebox.showinfo("Reporte Generado", f"Reporte JSON generado:\n{nombre_archivo_json}")
    except IOError as e_json: 
        error_json_report = e_json 
        print(f"Error al generar reporte JSON: {error_json_report}")
        if bajo_demanda and app_gui_ref_reporting:
            messagebox.showerror("Error Reporte", f"No se pudo generar el reporte JSON:\n{error_json_report}")

    nombre_archivo_csv_exitosos = os.path.join(CARPETA_REPORTES, f"reporte_accesos_exitosos_{fecha_str}.csv")
    if lista_eventos_exitosos:
        try:
            with open(nombre_archivo_csv_exitosos, 'w', newline='', encoding='utf-8') as f_csv:
                fieldnames_exitosos = lista_eventos_exitosos[0].keys()
                writer = csv.DictWriter(f_csv, fieldnames=fieldnames_exitosos)
                writer.writeheader()
                writer.writerows(lista_eventos_exitosos)
            print(f"Reporte CSV (Exitosos) generado: {nombre_archivo_csv_exitosos}")
            if bajo_demanda and app_gui_ref_reporting and not error_json_report: 
                 messagebox.showinfo("Reporte Generado", f"Reporte CSV (Exitosos) generado:\n{nombre_archivo_csv_exitosos}")
        except (IOError, IndexError, AttributeError) as e_csv_exitosos: 
            print(f"Error/Info al generar CSV (Exitosos): {e_csv_exitosos}")
    elif bajo_demanda:
        print(f"No hay accesos exitosos para CSV para {fecha_str}.")

    nombre_archivo_csv_fallidos = os.path.join(CARPETA_REPORTES, f"reporte_intentos_fallidos_{fecha_str}.csv")
    if lista_eventos_fallidos:
        try:
            with open(nombre_archivo_csv_fallidos, 'w', newline='', encoding='utf-8') as f_csv:
                fieldnames_fallidos = lista_eventos_fallidos[0].keys()
                writer = csv.DictWriter(f_csv, fieldnames=fieldnames_fallidos)
                writer.writeheader()
                writer.writerows(lista_eventos_fallidos)
            print(f"Reporte CSV (Fallidos) generado: {nombre_archivo_csv_fallidos}")
            if bajo_demanda and app_gui_ref_reporting and not error_json_report: 
                 messagebox.showinfo("Reporte Generado", f"Reporte CSV (Fallidos) generado:\n{nombre_archivo_csv_fallidos}")
        except (IOError, IndexError, AttributeError) as e_csv_fallidos:
            print(f"Error/Info al generar CSV (Fallidos): {e_csv_fallidos}")
    elif bajo_demanda:
        print(f"No hay intentos fallidos para CSV para {fecha_str}.")

# --- Bloque de prueba ---
if __name__ == '__main__':
    # Definir constantes necesarias para pruebas si no se importan de constants.py
    class constants_stub:
        ARCHIVO_ESTADO_DIARIO = "estado_diario_test.json" # Usar un archivo de prueba diferente
        CARPETA_REPORTES = "reportes_acceso_test"
        MAX_INTENTOS_FALLIDOS_UID = 3
        TIEMPO_BLOQUEO_UID_NIVEL = {1: 5, 2: 10, 3: 20} # Tiempos cortos para prueba en segundos
        TIEMPO_COOLDOWN_ACCESO_S = 10 # Segundos
    
    # Sobrescribir las constantes globales para la prueba
    ARCHIVO_ESTADO_DIARIO = constants_stub.ARCHIVO_ESTADO_DIARIO
    CARPETA_REPORTES = constants_stub.CARPETA_REPORTES
    MAX_INTENTOS_FALLIDOS_UID = constants_stub.MAX_INTENTOS_FALLIDOS_UID
    TIEMPO_BLOQUEO_UID_NIVEL = constants_stub.TIEMPO_BLOQUEO_UID_NIVEL
    TIEMPO_COOLDOWN_ACCESO_S = constants_stub.TIEMPO_COOLDOWN_ACCESO_S


    print(f"Ejecutando pruebas del módulo reporting_logging.py (con archivo: {ARCHIVO_ESTADO_DIARIO})...")
    if not os.path.exists(CARPETA_REPORTES): os.makedirs(CARPETA_REPORTES) # Asegurar que la carpeta de test exista
    
    # Limpiar archivo de estado de prueba si existe, para un inicio limpio
    if os.path.exists(ARCHIVO_ESTADO_DIARIO): os.remove(ARCHIVO_ESTADO_DIARIO)

    cargar_estado_diario() # Debería crear uno nuevo para hoy o cargar si ya existe
    print(f"Estado inicial: Fecha={fecha_actual_para_conteo}, Contador={contador_accesos_hoy}")

    info_user1 = {"nombre": "Usuario Uno", "dni": "111", "nivel": "Admin", "area": "Sistemas", "uid_rfid": "UID001"}
    info_user2 = {"nombre": "Usuario Dos (Trabajador)", "dni": "222", "nivel": "Trabajador", "area": "Ops", "uid_rfid": "UID002"}

    registrar_evento_acceso_exitoso(info_user1)
    time.sleep(1)
    registrar_intento_fallido("UID003", None, "Tarjeta No Reconocida")
    registrar_evento_acceso_exitoso(info_user2)

    print("\n--- Probando Bloqueo por Insistencia ---")
    for i in range(MAX_INTENTOS_FALLIDOS_UID + 1):
        bloqueado = registrar_intento_fallido("UID003", None, f"Fallo Intento {i+1}")
        print(f"Intento {i+1} para UID003. Bloqueado: {bloqueado}")
        if bloqueado: break
    
    print("\n--- Probando Cooldown ---")
    id_user1_cooldown = info_user1.get("uid_rfid") or info_user1.get("dni") or info_user1.get("nombre")
    print(f"Primer acceso de {info_user1['nombre']} ya registrado. Tiempo actual: {time.time()}")
    print(f"accesos_recientes_uid: {accesos_recientes_uid}")
    # Simular un intento de re-acceso inmediato (debería estar en cooldown)
    # Esto normalmente se haría en la máquina de estados, aquí solo probamos el registro
    if id_user1_cooldown in accesos_recientes_uid and \
       (time.time() - accesos_recientes_uid[id_user1_cooldown] < TIEMPO_COOLDOWN_ACCESO_S):
        print(f"Simulando intento de {info_user1['nombre']} DENTRO del cooldown.")
        registrar_intento_fallido(info_user1["uid_rfid"], info_user1, "Cooldown Anti-Passback", contar_para_bloqueo_insistencia=False)
    else:
        print(f"Simulando intento de {info_user1['nombre']} FUERA del cooldown (o primer acceso).")
        registrar_evento_acceso_exitoso(info_user1) # No debería pasar si el cooldown es corto y el primer acceso fue reciente

    print(f"\nContador final hoy: {contador_accesos_hoy}")
    print(f"Eventos exitosos hoy: {len(eventos_acceso_hoy)}")
    print(f"Intentos fallidos hoy: {len(intentos_fallidos_hoy)}")
    
    print("\nGenerando reporte manual para hoy (prueba)...")
    generar_reporte_final_dia(fecha_actual_para_conteo, contador_accesos_hoy, eventos_acceso_hoy, intentos_fallidos_hoy, bajo_demanda=True)
    
    print("\nPruebas de reporting_logging.py finalizadas.")