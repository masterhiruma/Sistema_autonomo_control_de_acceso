# ==============================================================================
# CONSTANTES GENERALES DEL SISTEMA Y CONFIGURACIÓN
# ==============================================================================

# --- Configuración de Comunicación Serial ---
VELOCIDAD_ARDUINO = 115200
TIMEOUT_SERIAL = 1  # Segundos para timeout en lecturas seriales

# --- Nombres de Archivos y Carpetas ---
NOMBRE_BD = "sistema_acceso.db"
ARCHIVO_ESTADO_DIARIO = "estado_diario.json"
CARPETA_REPORTES = "reportes_acceso" 
ARCHIVO_ENCODINGS_FACIALES_PKL = "encodings_faciales.pkl"
ROSTROS_CONOCIDOS_DIR = "rostros_conocidos" # Usado por facial_recognition_utils.py

# --- Parámetros de Sensores y Puerta ---
UMBRAL_DETECCION_SP1_CM = 30.0
UMBRAL_DETECCION_SP2_CM = 30.0
TIEMPO_ESPERA_APERTURA_PUERTA_S = 5.0       # Tiempo para que SP1 se libere y SP2 detecte (lógica de puerta)
TIEMPO_MAX_SP2_ACTIVO_S = 5.0              # Tiempo máx con SP2 activo antes de cerrar
TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S = 10.0   # Tiempo máx total que la puerta puede estar abierta
TIEMPO_CIERRE_PUERTA_S = 1.0               # Simulación del tiempo que tarda la puerta en cerrarse físicamente

# --- Timeouts de Validación ---
TIMEOUT_PRESENTACION_RFID_S = 10.0         # Tiempo para que el usuario presente la tarjeta RFID
TIMEOUT_SIMULACION_QR_S = 10.0              # Tiempo para la simulación de QR (se ajustará para QR real)
TIMEOUT_RECONOCIMIENTO_FACIAL_S = 15.0     # Timeout para el proceso de reconocimiento facial real

# --- Parámetros de Seguridad ---
MAX_INTENTOS_FALLIDOS_UID = 3              # Intentos antes de bloquear un UID/identificador
TIEMPO_BLOQUEO_UID_NIVEL = {               # Duración del bloqueo en segundos según el nivel
    1: 5 * 60,  # 5 minutos para el primer bloqueo
    2: 10 * 60, # 10 minutos para el segundo bloqueo
    3: 24 * 60 * 60 # 1 día para el tercer bloqueo y subsiguientes
}
TIEMPO_COOLDOWN_ACCESO_S = 30

# --- Parámetros de Cámara y Reconocimiento Facial ---
INDICE_CAMARA = 1                          # Índice de la cámara a usar (0 suele ser la integrada, 1 podría ser DroidCam)
FACTOR_REDUCCION_FRAME_FACIAL = 0.5        # Factor para redimensionar frames al procesar rostros (0.25 - 1.0)
TOLERANCIA_FACIAL = 0.6                    # Tolerancia para la comparación de rostros (más bajo = más estricto)

# --- (Opcional) Cadenas de Texto Específicas ---
CADENA_QR_ESPERADA_ESTATICO = "12 34 21 32 A2 6F 8B" # Cadena para el QR estático de prueba

# --- Textos para la GUI (opcional, para facilitar internacionalización futura) ---
# Por ahora, los mantenemos directamente en gui_manager.py

# --- Definiciones de Pines Arduino (SOLO COMO REFERENCIA, NO USADAS EN PYTHON DIRECTAMENTE) ---
# Estos pines se configuran en el sketch de Arduino.
# PIN_RST_RFID = 9
# PIN_SS_RFID  = 10
# PIN_TRIG_SP1 = 2
# PIN_ECHO_SP1 = 3
# ... etc.