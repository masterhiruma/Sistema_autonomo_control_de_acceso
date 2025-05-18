# Sistema-de-Control-de-Acceso-Inteligente-con-M-ltiples-M-todos-de-Validaci-n-y-Auditor-a.
Desarrollar un sistema de control de acceso para una puerta, utilizando un Arduino para la interacción con hardware (sensores, actuadores) y una aplicación Python en una PC/Laptop para la lógica principal, gestión de usuarios, validación de credenciales (RFID, QR, Reconocimiento Facial), y generación de reportes. 
## Arquitectura General:

### Componente de Hardware (Arduino):
*   Responsable de la lectura directa de sensores:
    *   2x Sensores de proximidad ultrasónicos `HC-SR04` (SP1 exterior, SP2 interior) para detección de presencia y cruce.
    *   1x Lector RFID `MFRC522` para lectura de UIDs de tarjetas/tags.
    *   3x Interruptores físicos de dos estados:
        *   S1 y S2: Para selección manual del protocolo de validación.
        *   E: Para activación/desactivación del modo de emergencia.
    *   (Futuro) 2x Finales de carrera para detectar posición de puerta abierta/cerrada.
*   Responsable del accionamiento directo de actuadores bajo comando de Python:
    *   1x Servomotor `SG90` (simulando inicialmente, futuro motor DC/Pasos) para abrir/cerrar puerta.
    *   1x LED Verde: Indicador de acceso concedido / sistema listo (según estado).
    *   1x LED Rojo: Indicador de acceso denegado / error / emergencia.
*   **Comunicación:** Vía puerto serial con la aplicación Python, enviando un paquete de datos con el estado de todos los sensores/interruptores y recibiendo comandos para los actuadores.

### Componente de Software (Python en PC/Laptop):
*   **Cerebro del Sistema:** Contiene toda la lógica de negocio.
*   **Interfaz Gráfica de Usuario (GUI - Tkinter):**
    *   **Panel Principal:** Visualización de estado del sistema, modo de validación, datos de sensores en tiempo real, mensajes de acceso/error.
    *   **Panel de Gestión de Usuarios:** Formularios para registrar, listar, editar y borrar usuarios. Incluye captura de UID RFID y (futuro) registro facial.
    *   **Panel de Reportes Diarios:** Visualización del contador de accesos, logs de accesos exitosos e intentos fallidos del día. Botón para generar reportes manuales.
*   **Módulos Lógicos:**
    *   Máquina de Estados Principal.
    *   Gestión de Comunicación Serial con Arduino.
    *   Gestión de Base de Datos de Usuarios (SQLite).
    *   Validación de Credenciales (RFID, QR, Facial).
    *   Lógica de Control de Puerta (apertura, cierre, timeouts, detección de paso y alertas).
    *   Selección de Protocolo (basado en switches S1/S2).
    *   Manejo de Horarios (para trabajadores y visitantes).
    *   Mecanismos de Seguridad (cooldown anti-passback, bloqueo por insistencia).
    *   Conteo de Accesos y Generación de Reportes (JSON y CSV).
    *   Manejo de Modo de Emergencia.
    *   (Futuro) Interacción con Cámara para QR y Reconocimiento Facial (`OpenCV`, `pyzbar`, `face_recognition`).
*   **Persistencia de Datos:**
    *   `sistema_acceso.db`: Base de datos SQLite para usuarios.
    *   `estado_diario.json`: Para persistencia del contador y logs del día actual entre reinicios de la aplicación.
    *   Carpeta `reportes_acceso/`: Para almacenar los reportes JSON y CSV finales de cada día.
    *   (Futuro) `config.json`: Para configuraciones del sistema.

## Detalle de Fases del Proyecto:

### FASE 0: Configuración del Entorno y Arduino Base _(Implementada y Probada)_
*   **Arduino:** Lectura de SP1, SP2, S1, S2, E, RFID (bajo demanda). Control de LEDs (Rojo/Verde) y Servo (simulado, con comandos de abrir/cerrar a posiciones fijas). Comunicación serial robusta con Python (envío de `DATOS;...` y recepción de `COMANDO:...`).
*   **Python:** Script básico para conectar con Arduino, recibir y parsear datos, y mostrar en una GUI simple. Envío de comandos manuales a Arduino desde la GUI.

### FASE 1: Estructura Python, GUI Inicial, Comunicación Estable _(Subsumida en Fase 0 funcionalmente)_
*   _(Ya cubierto por la implementación funcional de la Fase 0)._

### FASE 2: Lógica de Puerta (Servo Simulado) y Máquina de Estados Básica _(Implementada y Probada)_
*   **Python:**
    *   Máquina de estados implementada (`REPOSO`, `ESPERANDO_PERSONA_SP1` (ahora es `REPOSO`), `ABRIENDO_PUERTA`, `PERSONA_CRUZANDO`, `CERRANDO_PUERTA`, `ALERTA_ERROR_CRUCE`).
    *   Control de puerta simulado (envío de comandos al servo) basado en detección de SP1 (trigger inicial).
    *   Lógica de timeouts para apertura, cruce (SP2 activo), y puerta abierta total.
    *   Detección de cruce (SP1 libre -> SP2 activo -> SP2 libre).
    *   Alerta (parpadeo LED rojo comandado a Arduino) si SP1 y SP2 se activan simultáneamente durante `PERSONA_CRUZANDO`.
    *   GUI muestra el estado actual del sistema.

### FASE 3.1 + FASE 4 (Gran Fase): Validación RFID, Gestión de Usuarios, Contador, Logs, Reportes, Bloqueos, Cooldown _(Implementada y Probada en su Lógica Central)_
*   **Python:**
    *   **Base de Datos SQLite (usuarios):** Creada y funcional para almacenar nombre, DNI, nivel (Admin, Trabajador, Visitante), área, UID RFID, horarios para trabajador.
    *   **GUI - Gestión de Usuarios:**
        *   Pestaña dedicada.
        *   Formulario para registrar nuevos usuarios con todos los campos, incluyendo escaneo de UID RFID (campo editable). Validaciones de formato y unicidad.
        *   Funcionalidad para listar usuarios en un Treeview.
        *   Funcionalidad para editar usuarios existentes (cargando datos en el formulario, permitiendo re-escanear/editar UID, validaciones).
        *   Funcionalidad para borrar usuarios (con confirmación).
    *   **Máquina de Estados (Actualizada):**
        *   Nuevo estado `ESPERANDO_VALIDACION_RFID` y `ACCESO_DENEGADO_TEMPORAL`, `SISTEMA_BLOQUEADO_UID`.
        *   Al detectar SP1, transita a `ESPERANDO_VALIDACION_RFID`.
        *   Lógica de validación: consulta a BD por UID, verifica nivel y horario (Admin: siempre; Trabajador: L-V + horario laboral; Visitante: Miércoles 9-10 AM).
    *   **Seguridad:**
        *   **Cooldown Anti-Passback:** Un UID válido no puede reingresar por 5 minutos. Registra el intento con motivo "Cooldown" y NO cuenta para bloqueo por insistencia.
        *   **Bloqueo por Insistencia de UID:** Tras 3 intentos fallidos (que sí cuentan), el UID específico se bloquea progresivamente (5min, 10min, 1 día). Los intentos con UID bloqueado se registran sin re-contar para el bloqueo.
    *   **Contador y Logs:**
        *   `contador_accesos_hoy`, `eventos_acceso_hoy` (para éxitos), `intentos_fallidos_hoy`.
        *   Registro de acceso exitoso: timestamp, nombre, DNI, nivel, área, UID usado.
        *   Registro de intento fallido: timestamp, UID presentado, nombre (si reconocido), motivo (tarjeta no reconocida, fuera de horario, timeout, cooldown, UID bloqueado).
    *   **Persistencia (`estado_diario.json`):**
        *   Guarda y carga al inicio: fecha, contador, listas de eventos, y los diccionarios `intentos_fallidos_por_uid` y `accesos_recientes_uid`.
        *   Filtra bloqueos/cooldowns expirados al cargar.
    *   **Reportes (JSON y CSV):**
        *   Generación automática de reporte del día anterior al detectar cambio de día.
        *   Botón en GUI para generar reporte manual del día actual.
        *   Archivos guardados en `reportes_acceso/`.
    *   **GUI - Reportes Diarios:**
        *   Pestaña dedicada.
        *   Muestra contador y logs del día actual en Treeviews.

### FASE 7: Selección de Protocolo por Switches S1, S2 _(Implementada con Simulación para QR/Facial, Probada)_
*   **Python:**
    *   Nuevos estados `ESPERANDO_VALIDACION_QR`, `ESPERANDO_VALIDACION_FACIAL`.
    *   Función `determinar_protocolo_activo(s1, s2)` basada en `datos_hardware["s1_estado"]` y `datos_hardware["s2_estado"]`. Combinaciones:
        *   S1=0,S2=0: RFID + QR
        *   S1=0,S2=1: RFID + Facial
        *   S1=1,S2=0: QR + Facial
        *   S1=1,S2=1: Solo RFID
    *   **Máquina de Estados (Actualizada):**
        *   Al detectar SP1, determina el protocolo y luego inicia la secuencia de validación apropiada.
        *   Maneja transiciones entre `ESPERANDO_VALIDACION_RFID`, `ESPERANDO_VALIDACION_QR`, `ESPERANDO_VALIDACION_FACIAL` según el protocolo.
        *   `estado_validacion_secuencial` rastrea el progreso.
        *   Simulación para QR y Facial: Usa un delay y un booleano configurable en el código (`qr_ok_simulado`, `facial_ok_simulado`) para simular éxito/fallo, en lugar de un messagebox interactivo (para no bloquear el hilo de la máquina de estados). El fallo simulado lleva a `ACCESO_DENEGADO_TEMPORAL` y registra el intento sin contar para bloqueo de UID.
        *   Cancelación de secuencia si SP1 se libera.
    *   **GUI:** Label en "Panel Principal" muestra el "Modo de Validación Activo".

## Fases Pendientes de Implementación (Lógica Principal):

### FASE 5: Integración de Reconocimiento Facial (Real)
*   **Objetivo:** Reemplazar la simulación de `ESPERANDO_VALIDACION_FACIAL` con lógica real.
*   **Python:**
    *   **Integración de Bibliotecas:** `opencv-python`, `face_recognition`, `Pillow`.
    *   **BD:** Campo `facial_encoding` BLOB en tabla `usuarios`.
    *   **GUI - Gestión de Usuarios (Extensión):**
        *   Botón "Capturar/Registrar Rostro".
        *   Lógica para activar cámara, detectar un rostro, extraer encoding (NumPy array), serializar con `pickle`, y permitir asociarlo al usuario en el formulario.
        *   Al guardar/actualizar usuario, almacenar el encoding serializado en la BD.
    *   **Máquina de Estados - `ESPERANDO_VALIDACION_FACIAL` (Lógica Real):**
        *   Activar cámara.
        *   Bucle de detección: leer frame, encontrar `face_locations`, extraer `face_encodings`.
        *   Si el protocolo es "Solo Facial" o "QR + Facial" (y QR fue OK):
            *   Cargar todos los encodings conocidos (deserializados) y `id_usuario` de la BD.
            *   Para cada rostro detectado en el frame, compararlo (1 a N) con los encodings de la BD usando `face_recognition.compare_faces`.
            *   Si hay una (y solo una) coincidencia clara: obtener `info_usuario` de la BD. Validar horario/nivel/cooldown para ese usuario. Si OK -> Conceder Acceso.
            *   Si múltiples rostros o ninguna coincidencia -> Continuar/Timeout/Denegar.
        *   Si el protocolo es "RFID + Facial" (y RFID del usuario U1 fue OK):
            *   Cargar el encoding facial específico del usuario U1 de la BD.
            *   Para cada rostro detectado, compararlo (1 a 1) con el encoding de U1.
            *   Si coincide: Validar cooldown para U1. Si OK -> Conceder Acceso.
        *   Manejar timeouts, si usuario se va (SP1 libre).
        *   Registrar accesos exitosos e intentos fallidos (motivo: "Facial - Rostro no reconocido", "Facial - Fuera de Horario", etc.).
    *   **GUI:** Mostrar feed de cámara durante registro y acceso.

### FASE 6: Integración de QR (Real - Estático Inicialmente)
*   **Objetivo:** Reemplazar la simulación de `ESPERANDO_VALIDACION_QR` con lógica real.
*   **Python:**
    *   **Integración de Bibliotecas:** `pyzbar` (además de `opencv-python`).
    *   (Opcional) `config.json` o GUI: Campo para que el admin defina la cadena de texto esperada del QR estático "llave".
    *   **Máquina de Estados - `ESPERANDO_VALIDACION_QR` (Lógica Real):**
        *   Activar cámara.
        *   Bucle de detección: leer frame, usar `pyzbar.decode` para encontrar y decodificar QRs.
        *   Si se decodifica un QR:
            *   Obtener su contenido (string).
            *   Compararlo con la cadena "llave" esperada.
            *   Si coincide: `qr_ok = True`.
            *   Si no coincide: `qr_ok = False`.
        *   Si `qr_ok` es `True`, proceder al siguiente paso de validación (si hay) o conceder acceso.
        *   Si `qr_ok` es `False` o timeout -> `ACCESO_DENEGADO_TEMPORAL`.
        *   Manejar si usuario se va (SP1 libre).
        *   Registrar intentos.
    *   **GUI:** Mostrar feed de cámara durante escaneo QR.
    *   (Futuro - QR Dinámico): Requeriría definir el protocolo de generación/validación de tokens.

### FASE 8: Manejo Avanzado de Emergencia (Completo)
*   **Objetivo:** Implementar toda la lógica de emergencia.
*   **Python:**
    *   **Máquina de Estados - Nuevo estado `EMERGENCIA_ACTIVA`.**
    *   **Al Activar (E=LOW):**
        *   Prioridad sobre otros estados.
        *   Guardar estado previo de puerta.
        *   Invertir estado de puerta (Comando a Arduino).
        *   Comandar `LED_ROJO_PARPADEAR_EMERGENCIA_INICIAR` a Arduino.
        *   Iniciar grabación de vídeo con OpenCV (`cv2.VideoWriter`) a un archivo (ej: `emergencia_YYYYMMDD_HHMMSS.avi` en `CARPETA_REPORTES`).
    *   **Durante `EMERGENCIA_ACTIVA`:**
        *   Continuar grabación.
        *   (Conteo de personas fue descartado en favor de solo grabar).
    *   **Al Desactivar (E=HIGH):**
        *   Comandar `LED_ROJO_PARPADEAR_EMERGENCIA_DETENER`.
        *   Detener y guardar grabación de vídeo.
        *   Transitar a `CERRANDO_PUERTA` (para asegurar puerta) y luego a `REPOSO`.
    *   **GUI:** Indicador visual grande de "MODO EMERGENCIA ACTIVO".

### FASE 9: (Opcional) Finales de Carrera y Control de Motor DC/Pasos
*   **Objetivo:** Usar hardware de puerta más robusto.
*   **Arduino:**
    *   Leer finales de carrera. Enviar estado a Python.
    *   Controlar motor DC (con H-Bridge) o Motor de Pasos (con driver `A4988`). Lógica para mover hasta activar final de carrera o N pasos, con timeouts de seguridad.
*   **Python:**
    *   Leer estado de finales de carrera.
    *   Adaptar comandos y timeouts en `ABRIENDO_PUERTA` y `CERRANDO_PUERTA` para considerar los finales de carrera o el movimiento por pasos.

### FASE 10: (Opcional) Archivo de Configuración `config.json`
*   **Python:**
    *   Mover constantes (puerto serial, umbrales, timeouts, cadena QR) a `config.json`.
    *   Función para cargar configuración al inicio.
    *   (Opcional GUI) Interfaz para editar algunas configuraciones.

### FASE 11: Empaquetado (.exe) y Pruebas Finales
*   **Python:**
    *   Usar `PyInstaller`.
    *   Asegurar empaquetado de dependencias (`OpenCV`, `face_recognition`, etc.) y recursos (BD, archivos de estado/reportes iniciales si se desea).
    *   Pruebas exhaustivas del ejecutable.
