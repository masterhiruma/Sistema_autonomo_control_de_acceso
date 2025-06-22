import time
import datetime
import cv2    
import face_recognition 
from pyzbar.pyzbar import decode as decode_qr # Para QR
import os   
import threading # Para el lock si es necesario para variables de este módulo

from enum import Enum
import numpy as np # Necesario para convexHull si se usa

class EstadoSistema(Enum):
    REPOSO = "REPOSO"
    ESPERANDO_VALIDACION_RFID = "ESPERANDO_VALIDACION_RFID"
    ESPERANDO_VALIDACION_QR_REAL = "ESPERANDO_VALIDACION_QR_REAL" # Para QR real
    ESPERANDO_VALIDACION_FACIAL = "ESPERANDO_VALIDACION_FACIAL"
    ABRIENDO_PUERTA = "ABRIENDO_PUERTA"
    PERSONA_CRUZANDO = "PERSONA_CRUZANDO"
    CERRANDO_PUERTA = "CERRANDO_PUERTA"
    ALERTA_ERROR_CRUCE = "ALERTA_ERROR_CRUCE"
    ACCESO_DENEGADO_TEMPORAL = "ACCESO_DENEGADO_TEMPORAL"
    SISTEMA_BLOQUEADO_UID = "UID_BLOQUEADO_TEMPORALMENTE"
    EMERGENCIA_ACTIVA = "EMERGENCIA_ACTIVA" # Para Fase 8
# --- Importar nuestros módulos y constantes ---
try:
   # from enum_estados import EstadoSistema # Asumiendo que Enum está en su propio archivo o aquí
    import constants
    import arduino_comms # Para enviar_comando_a_arduino y acceder a datos_hardware
    import db_manager    
    import validation_logic 
    import reporting_logging 
    import facial_recognition_utils 
    import global_state # FIX: Importar el estado global
except ImportError as e:
    print(f"Error CRÍTICO al importar módulos en state_machine_logic.py: {e}")
    # Definir stubs muy básicos para que el linter no falle catastróficamente si faltan
    class EstadoSistema: REPOSO="S_REPOSO"; ESPERANDO_VALIDACION_RFID="S_RFID"; ESPERANDO_VALIDACION_QR_REAL="S_QR"; ESPERANDO_VALIDACION_FACIAL="S_FACIAL"; ABRIENDO_PUERTA="S_ABRIENDO"; PERSONA_CRUZANDO="S_CRUZANDO"; CERRANDO_PUERTA="S_CERRANDO"; ALERTA_ERROR_CRUCE="S_ALERTA"; ACCESO_DENEGADO_TEMPORAL="S_DENEGADO"; SISTEMA_BLOQUEADO_UID="S_BLOQUEADO_UID"; EMERGENCIA_ACTIVA="S_EMERGENCIA"
    class constants: UMBRAL_DETECCION_SP1_CM=30; TIMEOUT_PRESENTACION_RFID_S=10; TIMEOUT_RECONOCIMIENTO_FACIAL_S=15;TIMEOUT_SIMULACION_QR_S=3; INDICE_CAMARA=0; FACTOR_REDUCCION_FRAME_FACIAL=0.5;TOLERANCIA_FACIAL=0.6;TIEMPO_ESPERA_APERTURA_PUERTA_S=2;TIEMPO_MAX_SP2_ACTIVO_S=5;TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S=10;TIEMPO_CIERRE_PUERTA_S=1; CARPETA_REPORTES="."; TIEMPO_COOLDOWN_ACCESO_S=30; MAX_INTENTOS_FALLIDOS_UID=3; TIEMPO_BLOQUEO_UID_NIVEL={1:300, 2:600, 3:86400}
    class arduino_comms: datos_hardware={"sp1_distancia":999,"e_estado":1,"s1_estado":1,"s2_estado":1,"rfid_uid":"NADA","ultimo_rfid_procesado_para_acceso":"NADA"}; lock_datos_hardware=threading.Lock(); enviar_comando_a_arduino=print; is_arduino_conectado=lambda: False; get_datos_hardware_copia=lambda:arduino_comms.datos_hardware
    class db_manager: obtener_usuario_por_rfid_bd=lambda x:None; obtener_usuario_por_nombre_bd=lambda x:None; inicializar_bd=print
    class validation_logic: verificar_horario_trabajador=lambda x,y:False; verificar_horario_visitante=lambda:False
    class reporting_logging: registrar_intento_fallido=lambda a,b,c,d=True:False; registrar_evento_acceso_exitoso=print; cargar_estado_diario=print; verificar_y_resetear_por_cambio_de_dia=lambda:False; intentos_fallidos_por_uid={}; accesos_recientes_uid={}
    class facial_recognition_utils: encodings_faciales_cargados_global=[]; cargar_encodings_faciales_al_inicio=print

# --- Variables Globales Específicas de este Módulo (Lógica de Estados) ---
estado_actual_sistema = EstadoSistema.REPOSO
puerta_logicamente_abierta = False 
tiempo_inicio_estado_actual_s = 0.0
tiempo_puerta_abrio_s = 0.0        
tiempo_sp2_detecto_primera_vez_s = 0.0 
cap_camara = None 

protocolo_seleccionado_actual = {"rfid": True, "qr": False, "facial": False, "descripcion": "Solo RFID (Predeterminado)"}
estado_validacion_secuencial = {} # Ej: {"rfid_ok": True, "usuario_validado_info": {datos_del_usuario_rfid}}

cap_camara = None 
hilo_maquina_estados = None # Referencia al hilo que ejecuta logica_maquina_estados
hilo_maquina_estados_activo = False 
frame_procesados_sin_deteccion = 0 # Para no saturar la consola con "no rostros/no QR"


# Variables para el modo emergencia
estado_previo_a_emergencia = None
puerta_estaba_abierta_logicamente_antes_emergencia = False
video_writer_emergencia = None 
grabando_video_emergencia = False 
nombre_archivo_video_emergencia = ""

app_gui_ref_fsm = None # Referencia a la instancia de la GUI, se asigna desde main_app
ui_queue = None # <-- Cola para enviar actualizaciones a la GUI

def asignar_cola_ui(q):
    """Inyecta la cola de comunicación con la GUI."""
    global ui_queue
    ui_queue = q

def asignar_app_gui_referencia_fsm(gui_instance):
    global app_gui_ref_fsm
    app_gui_ref_fsm = gui_instance

# ==============================================================================
# FUNCIONES DE CONTROL DE ESTADO Y PROTOCOLO
# ==============================================================================
def determinar_protocolo_activo(s1_estado_hw, s2_estado_hw): 
    global protocolo_seleccionado_actual 
    protocolo_anterior_desc = protocolo_seleccionado_actual["descripcion"]
    if s1_estado_hw == 0 and s2_estado_hw == 0: protocolo_seleccionado_actual = {"rfid": True, "qr": True, "facial": False, "descripcion": "RFID + QR"}
    elif s1_estado_hw == 0 and s2_estado_hw == 1: protocolo_seleccionado_actual = {"rfid": True, "qr": False, "facial": True, "descripcion": "RFID + Facial"}
    elif s1_estado_hw == 1 and s2_estado_hw == 0: protocolo_seleccionado_actual = {"rfid": False, "qr": True, "facial": True, "descripcion": "QR + Facial"}
    elif s1_estado_hw == 1 and s2_estado_hw == 1: protocolo_seleccionado_actual = {"rfid": False, "qr": False, "facial": True, "descripcion": "Solo Reconocimiento Facial"}
    
    if protocolo_seleccionado_actual["descripcion"] != protocolo_anterior_desc: 
        print(f"Protocolo de validación cambiado a: {protocolo_seleccionado_actual['descripcion']}")
        if ui_queue:
            ui_queue.put({
                "type": "protocolo_update",
                "descripcion": protocolo_seleccionado_actual['descripcion']
            })
    return protocolo_seleccionado_actual

def cambiar_estado(nuevo_estado, mensaje_gui=None):
    """Cambia el estado del sistema y actualiza la GUI a través de la cola"""
    global estado_actual_sistema, tiempo_inicio_estado_actual_s
    
    estado_actual_sistema = nuevo_estado
    tiempo_inicio_estado_actual_s = time.time()
    
    # Elige un mensaje por defecto si no se proporciona uno.
    if mensaje_gui is None:
        mensaje_gui = {
            EstadoSistema.REPOSO: "Sistema en reposo",
            EstadoSistema.ESPERANDO_VALIDACION_RFID: "Esperando tarjeta RFID...",
            EstadoSistema.ESPERANDO_VALIDACION_QR_REAL: "Prepare su código QR...",
            EstadoSistema.ESPERANDO_VALIDACION_FACIAL: "Mire a la cámara...",
            EstadoSistema.ABRIENDO_PUERTA: "Acceso concedido, abriendo...",
            EstadoSistema.PERSONA_CRUZANDO: "Persona cruzando...",
            EstadoSistema.ACCESO_DENEGADO_TEMPORAL: "Acceso denegado.",
            EstadoSistema.SISTEMA_BLOQUEADO_UID: "UID bloqueado temporalmente.",
            EstadoSistema.ALERTA_ERROR_CRUCE: "¡Alerta de cruce inválido!",
            EstadoSistema.CERRANDO_PUERTA: "Cerrando puerta...",
            EstadoSistema.EMERGENCIA_ACTIVA: "¡¡EMERGENCIA ACTIVADA!!",
        }.get(nuevo_estado, "Estado desconocido")

    # Envía el paquete de actualización a la cola de la GUI
    if ui_queue:
        ui_queue.put({
            "type": "estado_update",
            "nuevo_estado": nuevo_estado.value,
            "mensaje": mensaje_gui
        })

# ==============================================================================
# FUNCIÓN PRINCIPAL DE LA MÁQUINA DE ESTADOS
# ==============================================================================
def logica_maquina_estados():
    global puerta_logicamente_abierta, tiempo_puerta_abrio_s, tiempo_sp2_detecto_primera_vez_s 
    global estado_validacion_secuencial, cap_camara, frame_procesados_sin_deteccion_facial
    global estado_previo_a_emergencia, puerta_estaba_abierta_logicamente_antes_emergencia
    global video_writer_emergencia, grabando_video_emergencia, nombre_archivo_video_emergencia
    
    print("Hilo de Máquina de Estados iniciado.")
    db_manager.inicializar_bd() 
    reporting_logging.cargar_estado_diario() 
    facial_recognition_utils.cargar_encodings_faciales_al_inicio() 
    
    with arduino_comms.lock_datos_hardware: 
        s1_prev = arduino_comms.datos_hardware["s1_estado"]
        s2_prev = arduino_comms.datos_hardware["s2_estado"]
        determinar_protocolo_activo(s1_prev, s2_prev) 

    frame_procesados_sin_deteccion_facial = 0
    estado_previo_a_emergencia = None 
    puerta_estaba_abierta_logicamente_antes_emergencia = False
    video_writer_emergencia = None
    grabando_video_emergencia = False
    nombre_archivo_video_emergencia = ""

    while hilo_maquina_estados_activo: # Este flag debe ser importado o definido en este módulo
        # FIX: Añadir chequeo de la pausa
        if global_state.pausar_fsm_por_registro_rfid:
            time.sleep(0.1)
            continue

        if not arduino_comms.is_arduino_conectado(): 
            if estado_actual_sistema != EstadoSistema.REPOSO:
                cambiar_estado(EstadoSistema.REPOSO, "Arduino desconectado. Sistema en reposo.")
            if cap_camara and cap_camara.isOpened():
                cap_camara.release(); cap_camara = None; 
                if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
            time.sleep(0.5); continue 
        
        tiempo_actual_s = time.time()
        datos_hw_actuales = arduino_comms.get_datos_hardware_copia()
        dist_sp1 = datos_hw_actuales["sp1_distancia"]; dist_sp2 = datos_hw_actuales["sp2_distancia"]
        uid_actual_arduino = datos_hw_actuales["rfid_uid"]
        ultimo_rfid_procesado_acceso = datos_hw_actuales["ultimo_rfid_procesado_para_acceso"]
        s1_hw = datos_hw_actuales["s1_estado"]; s2_hw = datos_hw_actuales["s2_estado"]
        estado_emergencia_actual_hw = datos_hw_actuales["e_estado"]

        # --- MANEJO PRIORITARIO DE EMERGENCIA ---
        if estado_emergencia_actual_hw == 0 and estado_actual_sistema != EstadoSistema.EMERGENCIA_ACTIVA:
            print("¡MODO EMERGENCIA ACTIVADO POR SWITCH!")
            if cap_camara and cap_camara.isOpened(): 
                cap_camara.release(); cap_camara = None; 
                if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
            estado_previo_a_emergencia = estado_actual_sistema 
            puerta_estaba_abierta_logicamente_antes_emergencia = puerta_logicamente_abierta
            cambiar_estado(EstadoSistema.EMERGENCIA_ACTIVA, "¡¡MODO EMERGENCIA ACTIVADO!!")
            arduino_comms.enviar_comando_a_arduino("LED_ROJO_PARPADEAR_EMERGENCIA_INICIAR") 
            arduino_comms.enviar_comando_a_arduino("LED_VERDE_OFF") 
            if puerta_estaba_abierta_logicamente_antes_emergencia:
                print("Emergencia: Cerrando puerta."); arduino_comms.enviar_comando_a_arduino("CERRAR_PUERTA")
                puerta_logicamente_abierta = False 
            else:
                print("Emergencia: Abriendo puerta."); arduino_comms.enviar_comando_a_arduino("ABRIR_PUERTA")
                puerta_logicamente_abierta = True 
            try:
                if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None
                cap_camara = cv2.VideoCapture(constants.INDICE_CAMARA, cv2.CAP_DSHOW)
                time.sleep(0.5); 
                if cap_camara.isOpened():
                    fw = int(cap_camara.get(cv2.CAP_PROP_FRAME_WIDTH)); fh = int(cap_camara.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    fps_c = cap_camara.get(cv2.CAP_PROP_FPS); fps_g = int(fps_c) if fps_c and fps_c > 0 else 20 
                    ts_vid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    nombre_archivo_video_emergencia = os.path.join(constants.CARPETA_REPORTES, f"emergencia_{ts_vid}.avi") 
                    fourcc = cv2.VideoWriter_fourcc(*'XVID'); video_writer_emergencia = cv2.VideoWriter(nombre_archivo_video_emergencia, fourcc, fps_g, (fw, fh)) 
                    grabando_video_emergencia = True 
                    print(f"Iniciando grabación de emergencia en: {nombre_archivo_video_emergencia}")
                else: print("Error: No se pudo abrir cámara para grabación de emergencia."); grabando_video_emergencia = False
            except Exception as e_vid: print(f"Excepción al iniciar grabación de emergencia: {e_vid}"); grabando_video_emergencia = False
            continue 
        elif estado_emergencia_actual_hw == 1 and estado_actual_sistema == EstadoSistema.EMERGENCIA_ACTIVA:
            print("Modo Emergencia Desactivado. Restaurando...")
            if grabando_video_emergencia and video_writer_emergencia is not None:
                video_writer_emergencia.release(); print(f"Grabación de emergencia finalizada: {nombre_archivo_video_emergencia}")
            grabando_video_emergencia = False; video_writer_emergencia = None; nombre_archivo_video_emergencia = "" 
            if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None; 
            if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
            arduino_comms.enviar_comando_a_arduino("LED_ROJO_PARPADEAR_EMERGENCIA_DETENER") 
            cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Emergencia finalizada. Cerrando puerta..."); continue 
        
        if estado_actual_sistema == EstadoSistema.EMERGENCIA_ACTIVA:
            if grabando_video_emergencia and cap_camara and cap_camara.isOpened() and video_writer_emergencia is not None:
                ret, frame_e = cap_camara.read()
                if ret:
                    ts_e = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                    cv2.putText(frame_e, ts_e, (10, frame_e.shape[0] - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1, cv2.LINE_AA)
                    video_writer_emergencia.write(frame_e)
                    if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": frame_e})
                else: print("Error leyendo frame durante grabación de emergencia.")
            time.sleep(0.05); continue 
        
        if s1_hw != s1_prev or s2_hw != s2_prev: 
            determinar_protocolo_activo(s1_hw, s2_hw) 
            s1_prev, s2_prev = s1_hw, s2_hw
            if estado_actual_sistema not in [EstadoSistema.REPOSO, EstadoSistema.ABRIENDO_PUERTA, EstadoSistema.PERSONA_CRUZANDO, EstadoSistema.CERRANDO_PUERTA, EstadoSistema.ALERTA_ERROR_CRUCE]:
                 cambiar_estado(EstadoSistema.REPOSO, "Protocolo cambiado, reiniciando secuencia.")
                 estado_validacion_secuencial.clear()
        
        if estado_actual_sistema == EstadoSistema.REPOSO:
            if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None; 
            if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
            arduino_comms.enviar_comando_a_arduino("LED_VERDE_OFF"); arduino_comms.enviar_comando_a_arduino("LED_ROJO_OFF")
            if ultimo_rfid_procesado_acceso != "NADA": 
                with arduino_comms.lock_datos_hardware: arduino_comms.datos_hardware["ultimo_rfid_procesado_para_acceso"] = "NADA" 
            estado_validacion_secuencial.clear()
            if hasattr(app_gui_ref_fsm, 'lbl_mensaje_acceso') and app_gui_ref_fsm.lbl_mensaje_acceso.cget("text") != "" and not ("Concedido" in app_gui_ref_fsm.lbl_mensaje_acceso.cget("text")):
                 if time.time() - tiempo_inicio_estado_actual_s > 3: 
                     if ui_queue: ui_queue.put({"type": "mensaje_update", "mensaje": ""})
            if puerta_logicamente_abierta: cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Error: Puerta abierta, cerrando."); continue
            if 0 < dist_sp1 < constants.UMBRAL_DETECCION_SP1_CM:
                print(f"SP1 detectó. Protocolo: {protocolo_seleccionado_actual['descripcion']}")
                estado_validacion_secuencial.clear() 
                if protocolo_seleccionado_actual["rfid"]: arduino_comms.enviar_comando_a_arduino("SOLICITAR_LECTURA_RFID"); cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_RFID, "Presente su tarjeta RFID...")
                elif protocolo_seleccionado_actual["qr"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_QR_REAL, "Prepare su código QR...")
                elif protocolo_seleccionado_actual["facial"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_FACIAL, "Mire a la cámara...")
                else: cambiar_estado(EstadoSistema.ABRIENDO_PUERTA, "Acceso directo (prot. sin validación).") 
        
        elif estado_actual_sistema == EstadoSistema.ESPERANDO_VALIDACION_RFID:
            print(f"[FSM] ESPERANDO_VALIDACION_RFID | dist_sp1={dist_sp1} | uid_actual_arduino={uid_actual_arduino} | ultimo_rfid_procesado_acceso={ultimo_rfid_procesado_acceso} | tiempo={(tiempo_actual_s - tiempo_inicio_estado_actual_s):.2f}")
            if not (0 < dist_sp1 < constants.UMBRAL_DETECCION_SP1_CM): cambiar_estado(EstadoSistema.REPOSO, "Usuario se retiró."); estado_validacion_secuencial.clear(); continue
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > constants.TIMEOUT_PRESENTACION_RFID_S:
                uid_t = uid_actual_arduino if uid_actual_arduino!="NADA"and uid_actual_arduino!=ultimo_rfid_procesado_acceso else None
                reporting_logging.registrar_intento_fallido(uid_t, None, "Timeout Presentación RFID"); cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Tiempo agotado RFID."); estado_validacion_secuencial.clear(); continue
            if uid_actual_arduino != "NADA" and uid_actual_arduino != ultimo_rfid_procesado_acceso:
                print(f"RFID Recibido para validación: {uid_actual_arduino}"); 
                with arduino_comms.lock_datos_hardware: arduino_comms.datos_hardware["ultimo_rfid_procesado_para_acceso"] = uid_actual_arduino
                data_bloqueo = reporting_logging.intentos_fallidos_por_uid.get(uid_actual_arduino)
                if data_bloqueo and data_bloqueo.get("desbloqueo_hasta",0) > tiempo_actual_s:
                    t_r_b=int(data_bloqueo["desbloqueo_hasta"]-tiempo_actual_s)
                    minutos_restantes = max(0,t_r_b)//60
                    segundos_restantes = max(0,t_r_b)%60
                    msg_b = f"Acceso Denegado: Tarjeta bloqueada por intentos fallidos. Intente en {minutos_restantes}m {segundos_restantes}s."
                    print(msg_b)
                    reporting_logging.registrar_intento_fallido(uid_actual_arduino, None, "Intento con UID bloqueado", False)
                    cambiar_estado(EstadoSistema.SISTEMA_BLOQUEADO_UID, msg_b)
                    continue

                u_info = db_manager.obtener_usuario_por_rfid_bd(uid_actual_arduino)
                acc_val = False
                msg_den = "Acceso Denegado: Tarjeta no registrada en el sistema."
                mot_fallo = "Tarjeta no registrada"

                if u_info:
                    if u_info.get("nivel_usuario") == "Trabajador" and not validation_logic.verificar_horario_trabajador(u_info.get("hora_inicio"), u_info.get("hora_fin")):
                        msg_den = "Acceso Denegado: Fuera de horario laboral permitido."
                        mot_fallo = "Fuera de horario laboral"
                    else:
                        acc_val = True
                        msg_den = f"Bienvenido {u_info['nombre']}. Validando acceso..."
                        mot_fallo = None

                if not acc_val:
                    reporting_logging.registrar_intento_fallido(uid_actual_arduino, u_info, mot_fallo)
                    arduino_comms.enviar_comando_a_arduino("LED_ROJO_ON")
                    cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, msg_den)
                    continue

                if protocolo_seleccionado_actual["facial"]:
                    estado_validacion_secuencial["usuario_validado_info"] = u_info
                    cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_FACIAL, "Mire a la cámara para validación facial...")
                else:
                    cambiar_estado(EstadoSistema.ABRIENDO_PUERTA, f"Acceso Concedido: {u_info['nombre']}")
        
        
        elif estado_actual_sistema == EstadoSistema.ESPERANDO_VALIDACION_QR_REAL:
            if not (0 < dist_sp1 < constants.UMBRAL_DETECCION_SP1_CM):
                cambiar_estado(EstadoSistema.REPOSO, "Usuario se retiró (esperando QR).")
                estado_validacion_secuencial.clear()
                continue

            if cap_camara is None or not cap_camara.isOpened():
                try:
                    print("Iniciando cámara para escaneo QR...")
                    cap_camara = cv2.VideoCapture(constants.INDICE_CAMARA, cv2.CAP_DSHOW)
                    time.sleep(0.5)
                    if not cap_camara.isOpened():
                        raise IOError("No se pudo abrir la cámara para QR.")
                except Exception as e:
                    print(f"Error cámara QR: {e}")
                    cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Error al iniciar cámara.")
                    estado_validacion_secuencial.clear()
                    continue

            tiempo_actual_s = time.time()
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > constants.TIMEOUT_SIMULACION_QR_S:
                cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Tiempo agotado para QR.")
                estado_validacion_secuencial.clear()
                if cap_camara is not None and cap_camara.isOpened():
                    cap_camara.release()
                cap_camara = None
                if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
                continue

            ret, frame = cap_camara.read()
            if not ret:
                print("No se pudo leer frame QR.")
                time.sleep(0.1)
                continue

            # Mostrar frame en la GUI
            if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": frame})

            decoded_objects = decode_qr(frame)
            for obj in decoded_objects:
                data = obj.data.decode("utf-8")
                print(f"QR detectado: {data}")
                # Validar cualquier contenido de QR
                if data and len(data) > 0:  # Solo verificamos que haya contenido
                    u_actual = estado_validacion_secuencial.get("usuario_validado_info")
                    if protocolo_seleccionado_actual["facial"]:
                        cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_FACIAL, "QR OK. Mire a la cámara...")
                    else:
                        if not u_actual:
                            u_actual = {
                                "nombre": "Usuario QR",
                                "dni": "N/A_QR",
                                "nivel": "Visitante",
                                "area": "N/A",
                                "uid_rfid": "QR_VALIDO",
                                "facial_encoding_array": None
                            }
                        reporting_logging.registrar_evento_acceso_exitoso(u_actual)
                        arduino_comms.enviar_comando_a_arduino("LED_VERDE_ON")
                        cambiar_estado(EstadoSistema.ABRIENDO_PUERTA, f"Acceso Concedido: {u_actual['nombre']} (QR OK)")
                        if cap_camara is not None and cap_camara.isOpened():
                            cap_camara.release()
                        cap_camara = None
                        if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
                        cv2.destroyAllWindows()
                        estado_validacion_secuencial["qr_ok"] = True
                        break

        elif estado_actual_sistema == EstadoSistema.ESPERANDO_VALIDACION_FACIAL:
            # --- LÓGICA FACIAL REAL REFINADA ---
            if not (0 < dist_sp1 < constants.UMBRAL_DETECCION_SP1_CM): 
                if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None; 
                if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
                cambiar_estado(EstadoSistema.REPOSO, "Usuario se retiró (esperando Facial)."); estado_validacion_secuencial.clear(); continue
            
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > constants.TIMEOUT_RECONOCIMIENTO_FACIAL_S: 
                if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None; 
                if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
                u_prev = estado_validacion_secuencial.get("usuario_validado_info")
                reporting_logging.registrar_intento_fallido(u_prev.get("uid_rfid") if u_prev and u_prev.get("uid_rfid") else None, u_prev, "Timeout Reconocimiento Facial", False)
                cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Tiempo agotado para Facial."); estado_validacion_secuencial.clear(); continue

            if cap_camara is None or not cap_camara.isOpened(): 
                try:
                    print(f"Intentando abrir cámara con índice: {constants.INDICE_CAMARA}")
                    cap_camara = cv2.VideoCapture(constants.INDICE_CAMARA, cv2.CAP_DSHOW)
                    time.sleep(0.5); 
                    if not cap_camara.isOpened(): raise IOError(f"No se pudo abrir cámara {constants.INDICE_CAMARA}")
                    print("Cámara activada para reconocimiento facial.")
                    frame_procesados_sin_deteccion_facial = 0 
                except Exception as e_cam:
                    print(f"Error al iniciar cámara para facial: {e_cam}")
                    reporting_logging.registrar_intento_fallido(None, None, f"Error Cámara Facial: {e_cam}", False)
                    cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Error al iniciar cámara."); estado_validacion_secuencial.clear(); continue
            
            ret, frame = cap_camara.read()
            if not ret: print("Facial: Error al leer frame."); time.sleep(0.1); continue

            rgb_frame_pequeno = cv2.resize(frame, (0, 0), fx=constants.FACTOR_REDUCCION_FRAME_FACIAL, fy=constants.FACTOR_REDUCCION_FRAME_FACIAL)
            rgb_frame_pequeno_convertido = cv2.cvtColor(rgb_frame_pequeno, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame_pequeno_convertido, model="hog")
            
            # Inicializar variables para este frame
            rostro_finalmente_validado_ok = False
            info_usuario_para_acceso_final = None
            motivo_fallo_del_frame = "Rostro no reconocido"
            mensajes_cooldown_repetidos = 0

            # Dibujar información en el frame ANTES de procesar
            tiempo_restante = int(constants.TIMEOUT_RECONOCIMIENTO_FACIAL_S - (tiempo_actual_s - tiempo_inicio_estado_actual_s))
            cv2.putText(frame, f"Tiempo: {tiempo_restante}s", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            if not face_locations:
                frame_procesados_sin_deteccion_facial += 1
                if frame_procesados_sin_deteccion_facial % 30 == 0:
                    print("Facial: No se detectaron rostros...")
                    cv2.putText(frame, "No se detectan rostros", (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                frame_procesados_sin_deteccion_facial = 0
                usuario_identificado_paso_previo = estado_validacion_secuencial.get("usuario_validado_info")
                
                # FIX: Pre-validación CRÍTICA para protocolos secuenciales
                if usuario_identificado_paso_previo and protocolo_seleccionado_actual["facial"]:
                    if usuario_identificado_paso_previo.get("facial_encoding_array") is None:
                        # Si el protocolo requiere un rostro después de RFID/QR, el usuario DEBE tener uno.
                        msg_denial = f"Acceso Denegado: El usuario '{usuario_identificado_paso_previo['nombre']}' no tiene un rostro registrado."
                        print(msg_denial)
                        reporting_logging.registrar_intento_fallido(usuario_identificado_paso_previo.get("uid_rfid"), usuario_identificado_paso_previo, "Rostro no registrado", False)
                        
                        if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None; cv2.destroyAllWindows()
                        if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
                        cambiar_estado(EstadoSistema.ACCESO_DENEGADO_TEMPORAL, "Acceso Denegado: Rostro no registrado.")
                        estado_validacion_secuencial.clear()
                        continue # Salta el resto del procesamiento facial para este ciclo

                realizar_comparacion_1_a_1 = (
                    usuario_identificado_paso_previo is not None and
                    (protocolo_seleccionado_actual["rfid"] or protocolo_seleccionado_actual["qr"]) and
                    protocolo_seleccionado_actual["facial"] and 
                    usuario_identificado_paso_previo.get("facial_encoding_array") is not None 
                )

                current_face_encodings_in_frame = face_recognition.face_encodings(rgb_frame_pequeno_convertido, face_locations)
                
                for face_encoding_detectado in current_face_encodings_in_frame:
                    if realizar_comparacion_1_a_1:
                        distancia = face_recognition.face_distance([usuario_identificado_paso_previo["facial_encoding_array"]], face_encoding_detectado)[0]
                        if distancia <= constants.TOLERANCIA_FACIAL:
                            if usuario_identificado_paso_previo.get("nivel_usuario") == "Trabajador" and not validation_logic.verificar_horario_trabajador(usuario_identificado_paso_previo.get("hora_inicio"), usuario_identificado_paso_previo.get("hora_fin")):
                                motivo_fallo_del_frame = "Fuera de horario laboral permitido"
                            else:
                                rostro_finalmente_validado_ok = True
                                info_usuario_para_acceso_final = usuario_identificado_paso_previo
                                break
                        else:
                            motivo_fallo_del_frame = "Rostro no coincide con UID"
                    else: # Búsqueda 1 a N
                        if facial_recognition_utils.encodings_faciales_cargados_global:
                            distancias = face_recognition.face_distance(facial_recognition_utils.encodings_faciales_cargados_global, face_encoding_detectado)
                            best_match_index = np.argmin(distancias)
                            if distancias[best_match_index] <= constants.TOLERANCIA_FACIAL:
                                nombre_usuario_encontrado = facial_recognition_utils.nombres_usuarios_cargados_global[best_match_index]
                                el_usuario_info = db_manager.obtener_usuario_por_nombre_bd(nombre_usuario_encontrado)
                                if el_usuario_info:
                                    if el_usuario_info.get("nivel_usuario") == "Trabajador" and not validation_logic.verificar_horario_trabajador(el_usuario_info.get("hora_inicio"), el_usuario_info.get("hora_fin")):
                                        motivo_fallo_del_frame = "Fuera de horario laboral permitido"
                                    else:
                                        rostro_finalmente_validado_ok = True
                                        info_usuario_para_acceso_final = el_usuario_info
                                        break
                    if rostro_finalmente_validado_ok:
                        break

            # Decisión final después de procesar el frame
            if rostro_finalmente_validado_ok and info_usuario_para_acceso_final:
                if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None; cv2.destroyAllWindows()
                if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
                cambiar_estado(EstadoSistema.ABRIENDO_PUERTA, f"Acceso Concedido: {info_usuario_para_acceso_final['nombre']}")
                reporting_logging.registrar_evento_acceso_exitoso(info_usuario_para_acceso_final)
                estado_validacion_secuencial.clear()
            elif face_locations and not rostro_finalmente_validado_ok and estado_actual_sistema == EstadoSistema.ESPERANDO_VALIDACION_FACIAL:
                mensajes_cooldown_repetidos += 1
                if mensajes_cooldown_repetidos < 2:
                    u_prev = estado_validacion_secuencial.get("usuario_validado_info")
                    reporting_logging.registrar_intento_fallido(u_prev.get("uid_rfid") if u_prev else None, u_prev, motivo_fallo_del_frame, False)

            # Mostrar el frame con toda la información
            if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": frame})

            if cv2.waitKey(1) & 0xFF == ord('q'): continue

        elif estado_actual_sistema == EstadoSistema.SISTEMA_BLOQUEADO_UID:
            if not (0 < dist_sp1 < constants.UMBRAL_DETECCION_SP1_CM): cambiar_estado(EstadoSistema.REPOSO, "Usuario se retiró durante bloqueo."); 
            if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None; 
            if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > 60: cambiar_estado(EstadoSistema.REPOSO, "Timeout UID_BLOQUEADO."); 
            if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None; 
            if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
        
        elif estado_actual_sistema == EstadoSistema.ACCESO_DENEGADO_TEMPORAL:
            if cap_camara and cap_camara.isOpened(): cap_camara.release(); cap_camara = None; 
            if ui_queue: ui_queue.put({"type": "camera_feed_update", "frame": None, "text": "Cámara OFF"})
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > 2.5: 
                arduino_comms.enviar_comando_a_arduino("LED_ROJO_OFF")
                if 0 < dist_sp1 < constants.UMBRAL_DETECCION_SP1_CM: 
                     estado_validacion_secuencial.clear() 
                     if protocolo_seleccionado_actual["rfid"]: arduino_comms.enviar_comando_a_arduino("SOLICITAR_LECTURA_RFID"); cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_RFID, "Presente su tarjeta RFID...")
                     elif protocolo_seleccionado_actual["qr"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_QR_REAL, "Prepare su código QR...")
                     elif protocolo_seleccionado_actual["facial"]: cambiar_estado(EstadoSistema.ESPERANDO_VALIDACION_FACIAL, "Mire a la cámara...")
                     else: cambiar_estado(EstadoSistema.REPOSO)
                else: cambiar_estado(EstadoSistema.REPOSO, "Sistema en reposo.")
        
        elif estado_actual_sistema == EstadoSistema.ABRIENDO_PUERTA:
            if not puerta_logicamente_abierta: arduino_comms.enviar_comando_a_arduino("ABRIR_PUERTA"); puerta_logicamente_abierta = True; tiempo_puerta_abrio_s = tiempo_actual_s; tiempo_sp2_detecto_primera_vez_s = 0
            sp1_libre = not (0 < dist_sp1 < constants.UMBRAL_DETECCION_SP1_CM); sp2_detecta = (0 < dist_sp2 < constants.UMBRAL_DETECCION_SP2_CM)
            if sp1_libre and sp2_detecta: tiempo_sp2_detecto_primera_vez_s = tiempo_actual_s; cambiar_estado(EstadoSistema.PERSONA_CRUZANDO)
            elif tiempo_actual_s - tiempo_puerta_abrio_s > constants.TIEMPO_ESPERA_APERTURA_PUERTA_S:
                if not sp1_libre: cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "SP1 obstruido. Cerrando.")
                else: cambiar_estado(EstadoSistema.PERSONA_CRUZANDO) 
            if puerta_logicamente_abierta and (tiempo_actual_s - tiempo_puerta_abrio_s > constants.TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S): cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Timeout puerta abierta.")
        
        elif estado_actual_sistema == EstadoSistema.PERSONA_CRUZANDO:
            sp1_detecta_ahora = (0 < dist_sp1 < constants.UMBRAL_DETECCION_SP1_CM); sp2_detecta_ahora = (0 < dist_sp2 < constants.UMBRAL_DETECCION_SP2_CM)
            if sp1_detecta_ahora and sp2_detecta_ahora: arduino_comms.enviar_comando_a_arduino("LED_ROJO_PARPADEAR_ALERTA"); cambiar_estado(EstadoSistema.ALERTA_ERROR_CRUCE, "ALERTA: SP1 y SP2 activos!"); continue
            if sp2_detecta_ahora and tiempo_sp2_detecto_primera_vez_s == 0: tiempo_sp2_detecto_primera_vez_s = tiempo_actual_s
            if not sp2_detecta_ahora and tiempo_sp2_detecto_primera_vez_s != 0: cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Persona cruzó.")
            elif sp2_detecta_ahora and tiempo_sp2_detecto_primera_vez_s != 0 and (tiempo_actual_s - tiempo_sp2_detecto_primera_vez_s > constants.TIEMPO_MAX_SP2_ACTIVO_S): cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "SP2 activo mucho tiempo.")
            if puerta_logicamente_abierta and (tiempo_actual_s - tiempo_puerta_abrio_s > constants.TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S): cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Timeout puerta abierta.")
        
        elif estado_actual_sistema == EstadoSistema.ALERTA_ERROR_CRUCE:
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > 2.0: cambiar_estado(EstadoSistema.CERRANDO_PUERTA, "Alerta manejada.")
        
        elif estado_actual_sistema == EstadoSistema.CERRANDO_PUERTA:
            arduino_comms.enviar_comando_a_arduino("LED_VERDE_OFF") 
            if puerta_logicamente_abierta: arduino_comms.enviar_comando_a_arduino("CERRAR_PUERTA"); puerta_logicamente_abierta = False
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > constants.TIEMPO_CIERRE_PUERTA_S: cambiar_estado(EstadoSistema.REPOSO, "Sistema en reposo.")
        
        time.sleep(0.05) 
    print("Hilo de Máquina de Estados terminado.")
    if cap_camara and cap_camara.isOpened(): 
        print("Liberando cámara facial al finalizar programa...")
        cap_camara.release()