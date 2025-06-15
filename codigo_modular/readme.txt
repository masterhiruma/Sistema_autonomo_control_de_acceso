Componentes y Funcionalidades Implementadas y Probadas Exitosamente:
Hardware y Comunicación (Arduino + Python con pyserial):
Lectura de 2 sensores de proximidad HC-SR04 (SP1 exterior, SP2 interior).
Lectura de un lector RFID MFRC522 (UIDs de tarjetas).
Lectura de 3 interruptores físicos de 2 posiciones (S1, S2 para selección de protocolo; E para emergencia).
Control de LEDs indicadores (Rojo, Verde) y un servomotor SG90 (simulando puerta).
Comunicación serial estable entre Arduino y Python (envío de datos de sensores formateados, recepción de comandos).
Interfaz Gráfica de Usuario (GUI - Tkinter en Python):
Panel principal para visualización en tiempo real del estado del sistema, datos de sensores/interruptores, y modo de validación activo.
Funcionalidad para seleccionar el puerto serial y conectar/desconectar con Arduino.
Pestaña de "Gestión de Usuarios" con formularios y lógica para:
Registrar nuevos usuarios (Admin, Trabajador, Visitante) con nombre, DNI, área, UID RFID (escaneado y editable), y horarios específicos para Trabajadores/Visitantes.
Listar usuarios existentes en un Treeview.
Editar la información de usuarios existentes.
Borrar usuarios (con confirmación).
Pestaña de "Reportes Diarios" para:
Visualizar el contador de accesos exitosos del día.
Mostrar logs en tiempo real de accesos exitosos e intentos fallidos en Treeviews.
Botón para generar manualmente reportes del día actual.
Lógica Central y Máquina de Estados (Python):
Máquina de Estados Finita (FSM) robusta que gestiona los estados: REPOSO, ESPERANDO_VALIDACION_RFID, ESPERANDO_VALIDACION_QR_REAL (actualmente QR real estático), ESPERANDO_VALIDACION_FACIAL (actualmente con encodings pre-cargados), ABRIENDO_PUERTA, PERSONA_CRUZANDO, CERRANDO_PUERTA, ALERTA_ERROR_CRUCE, ACCESO_DENEGADO_TEMPORAL, SISTEMA_BLOQUEADO_UID, EMERGENCIA_ACTIVA.
Selección de Protocolo (Switches S1/S2): Funciona correctamente, permitiendo cambiar entre:
Solo Reconocimiento Facial
RFID + QR (Estático Real)
RFID + Reconocimiento Facial
QR (Estático Real) + Reconocimiento Facial
La FSM sigue correctamente las secuencias de validación según el protocolo activo.
Validación de Credenciales y Políticas de Acceso (Python + SQLite):
Base de datos SQLite (sistema_acceso.db) para almacenar usuarios, incluyendo un campo facial_encoding BLOB.
Validación RFID: Funciona correctamente, incluyendo consulta a BD y verificación de niveles y horarios (Admin: siempre; Trabajador: L-V + horario; Visitante: Mié 9-10 AM).
Validación QR (Estático Real): Implementada con pyzbar y la cámara (DroidCam). Lee un QR estático y lo compara contra una cadena predefinida (CADENA_QR_ESPERADA). Se muestra ventana de OpenCV con el feed de la cámara y recuadro alrededor del QR.
Reconocimiento Facial (Básico Real): Implementado con face_recognition y OpenCV (DroidCam). Carga encodings desde encodings_faciales.pkl (generado por un script separado a partir de imágenes en rostros_conocidos/). Realiza comparación 1-a-N ("Solo Facial", "QR+Facial") y 1-a-1 ("RFID+Facial" si el usuario RFID tiene encoding asociado). Se muestra ventana de OpenCV con el feed y recuadros/nombres. La lógica 1-a-1 vs 1-a-N ha sido refinada y parece funcionar correctamente.
Mecanismos de Seguridad (Python):
Cooldown Anti-Passback (5 min): Funciona para RFID y para rostros reconocidos, previniendo reingresos inmediatos y registrando el intento con el motivo correcto sin contar para bloqueo.
Bloqueo por Insistencia de UID/Identificador (3 intentos): Funciona con bloqueo progresivo (5min, 10min, 1 día) para el identificador que falla (UID RFID, o DNI/Nombre si es solo facial).
Auditoría y Reportes (Python):
Registro detallado de accesos exitosos (timestamp, nombre, DNI, nivel, área, UID/método) e intentos fallidos (timestamp, UID/identificador presentado, nombre detectado, motivo del fallo).
Persistencia diaria del estado (contador, logs, estados de bloqueo/cooldown) en estado_diario.json.
Generación automática de reportes finales del día anterior (JSON y CSV) al detectar cambio de día.
Generación manual de reportes del día actual desde la GUI.
Manejo de Emergencia (Python + Arduino):
Activación/Desactivación mediante switch físico (E).
Lógica de inversión de estado de puerta y LED rojo parpadeante (comandado a Arduino).
Grabación de vídeo funcional durante la emergencia a un archivo .avi con timestamp.
Estado del Desarrollo Modular:
El proyecto ha sido refactorizado en los siguientes módulos Python: main_app.py, gui_manager.py, arduino_comms.py, state_machine_logic.py, db_manager.py, validation_logic.py, reporting_logging.py, facial_recognition_utils.py, y constants.py. La interconexión y el flujo de datos entre módulos parecen estar funcionando.
se logro hacer un ejecutable .exe utilizando pyinstaller.
