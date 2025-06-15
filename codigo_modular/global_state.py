import threading
from enum import Enum # Necesitaremos el Enum aquí si estado_actual_sistema vive aquí

# --- Módulos que podrían definir estructuras de datos o Enums ---
# Si EstadoSistema se define aquí, no necesitaría importarse de state_machine_logic
# Por ahora, asumamos que EstadoSistema se define en state_machine_logic.py
# from state_machine_logic import EstadoSistema # Esto crearía una dependencia circular si state_machine_logic también importa global_state

# --- Estado de la Conexión con Arduino ---
arduino_serial_object = None  # El objeto serial.Serial en sí mismo
arduino_esta_conectado = False # Flag del estado de la conexión

# --- Datos del Hardware y Lock ---
# Estos son los datos que actualiza el hilo listener de Arduino
# y que leen la GUI y la máquina de estados.
lock_datos_hardware = threading.Lock() 
datos_hardware_compartidos = {
    "sp1_distancia": 999.0,
    "sp2_distancia": 999.0,
    "s1_estado": 1,       
    "s2_estado": 1,       
    "e_estado": 1,        
    "rfid_uid": "NADA", # UID leído por Arduino en el último paquete de DATOS
    "ultimo_rfid_procesado_para_acceso": "NADA" # Para evitar doble procesamiento en FSM
}

# --- Estado Actual del Sistema (Máquina de Estados) ---
# Es crucial que solo la máquina de estados modifique esto, pero la GUI lo lee.
# Si EstadoSistema no está definido aquí, deberá ser importado por los módulos que lo usen.
# Por ahora, dejaremos que estado_actual_sistema se defina y gestione en state_machine_logic.py,
# ya que está íntimamente ligado a esa lógica. La GUI lo leerá desde allí.
# estado_actual_sistema = None # Se asignará una instancia de EstadoSistema

# --- Protocolo de Validación Seleccionado ---
# Gestionado y modificado por state_machine_logic.py, leído por la GUI.
protocolo_seleccionado_info = {
    "rfid": True, "qr": False, "facial": False,
    "descripcion": "Solo RFID (Predeterminado)"
}

# --- Información de Validación Secuencial ---
# Usado por la máquina de estados para rastrear pasos en protocolos multifactor.
estado_validacion_secuencial_actual = {} 
# Ej: {"rfid_ok": True, "usuario_validado_info": {datos_del_usuario_rfid_o_facial}}

# --- Encodings Faciales Cargados ---
# Cargados por facial_recognition_utils.py, leídos por state_machine_logic.py
encodings_faciales_globales = [] 

# --- Cámara Facial ---
# Objeto VideoCapture, gestionado principalmente por state_machine_logic.py
cap_camara_global = None 

# --- Estado de Reportes y Logs Diarios ---
# Gestionados por reporting_logging.py, leídos por la GUI y la FSM.
# Para evitar dependencias circulares fuertes, es mejor que reporting_logging.py
# mantenga sus propias variables de módulo para esto y ofrezca funciones para acceder/modificar.
# Sin embargo, si la GUI necesita accederlos directamente y con frecuencia, podrían estar aquí.
# Por ahora, asumimos que reporting_logging.py los gestiona.
# contador_accesos_diario_global = 0
# eventos_acceso_diarios_global = []
# intentos_fallidos_diarios_global = []
# fecha_actual_para_conteo_global = ""
# intentos_fallidos_por_uid_global = {}
# accesos_recientes_uid_global = {}

# --- Referencia a la Instancia de la GUI ---
# Esto permite que módulos sin importación directa de gui_manager puedan
# (con precaución) interactuar con la GUI, por ejemplo, para mostrar messageboxes.
app_gui_instancia = None

# --- Flags de Control de Hilos ---
# Estos flags son cruciales para la terminación ordenada.
# Serán modificados por main_app.py (al cerrar) y por la GUI (al desconectar).
# Serán leídos por los bucles de los hilos en arduino_comms.py y state_machine_logic.py.
hilo_listener_arduino_debe_correr = False
hilo_maquina_estados_debe_correr = False


# --- Funciones de utilidad para acceder/modificar algunas globales si es necesario ---
# (Generalmente es mejor que los módulos gestionen su propio estado interno
# y expongan funciones para interactuar con él, en lugar de modificar directamente
# las variables de global_state desde fuera).

# Ejemplo de cómo main_app.py o gui_manager.py podrían asignar la instancia de la GUI:
def set_app_gui_instance(gui_instance):
    global app_gui_instancia
    app_gui_instancia = gui_instance

def get_app_gui_instance():
    return app_gui_instancia

print("Módulo global_state.py cargado.")