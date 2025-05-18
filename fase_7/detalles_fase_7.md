## Fase 7: Selección de Protocolo por Switches S1, S2 (con Simulación de QR/Facial)

**Objetivo Principal:** Implementar la capacidad de seleccionar diferentes protocolos de validación de acceso (combinaciones de RFID, QR y Reconocimiento Facial) mediante el uso de dos interruptores físicos (S1 y S2) conectados al Arduino. La lógica de QR y Reconocimiento Facial se simulará en esta fase para probar el flujo de la máquina de estados.

**Componentes y Funcionalidad:**

1.  **Definición de Protocolos de Validación:**
    *   Se establecen cuatro combinaciones de protocolos basadas en el estado de los interruptores S1 y S2 (donde 0=LOW/activo, 1=HIGH/inactivo):
        *   **S1=0, S2=0:** RFID + QR Dinámico (Simulado)
        *   **S1=0, S2=1:** RFID + Reconocimiento Facial (Simulado)
        *   **S1=1, S2=0:** QR Dinámico (Simulado) + Reconocimiento Facial (Simulado)
        *   **S1=1, S2=1:** Solo RFID (Protocolo predeterminado)

2.  **Nuevos Estados del Sistema (`EstadoSistema` Enum en Python):**
    *   Se añaden estados para manejar los nuevos métodos de validación (aunque su lógica interna sea simulada en esta fase):
        *   `ESPERANDO_VALIDACION_QR`
        *   `ESPERANDO_VALIDACION_FACIAL`

3.  **Determinación del Protocolo Activo (Función `determinar_protocolo_activo()` en Python):**
    *   Esta función lee los estados actuales de `s1_estado` y `s2_estado` (recibidos de Arduino y almacenados en `datos_hardware`).
    *   Devuelve un diccionario que especifica qué métodos de validación son requeridos y una descripción textual del protocolo. Ejemplo:
        ```python
        protocolo = {
            "rfid": True, 
            "qr": True, 
            "facial": False, 
            "descripcion": "RFID + QR"
        }
        ```
    *   La variable global `protocolo_seleccionado_actual` almacena este diccionario.

4.  **Máquina de Estados (`logica_maquina_estados()` en Python - Modificaciones Clave):**
    *   **Detección de Cambio de Protocolo:**
        *   Al inicio del bucle de la máquina de estados y cada vez que se detecta un cambio en los pines S1 o S2, se llama a `determinar_protocolo_activo()` para actualizar `protocolo_seleccionado_actual`.
        *   Si el protocolo cambia mientras una secuencia de validación está en curso (y no está en `REPOSO` o en un estado de movimiento de puerta), el sistema vuelve a `REPOSO` para reiniciar con el nuevo protocolo.
    *   **Inicio de Secuencia de Validación (desde `REPOSO`):**
        *   Cuando SP1 detecta una persona:
            1.  Se determina el `protocolo_seleccionado_actual`.
            2.  Se limpia `estado_validacion_secuencial` (diccionario para rastrear resultados parciales de validación).
            3.  Se transita al *primer* estado de validación requerido por el protocolo:
                *   Si `protocolo_seleccionado_actual["rfid"]` es `True` -> `ESPERANDO_VALIDACION_RFID`.
                *   Else if `protocolo_seleccionado_actual["qr"]` es `True` -> `ESPERANDO_VALIDACION_QR`.
                *   Else if `protocolo_seleccionado_actual["facial"]` es `True` -> `ESPERANDO_VALIDACION_FACIAL`.
    *   **Transiciones Secuenciales entre Estados de Validación:**
        *   **Desde `ESPERANDO_VALIDACION_RFID`:**
            *   Si la validación RFID es exitosa:
                *   `estado_validacion_secuencial["rfid_ok"] = True`.
                *   `estado_validacion_secuencial["usuario_validado_rfid"]` almacena la información del usuario.
                *   Si `protocolo_seleccionado_actual["qr"]` es `True` (y es el siguiente paso), transita a `ESPERANDO_VALIDACION_QR`.
                *   Else if `protocolo_seleccionado_actual["facial"]` es `True` (y es el siguiente paso), transita a `ESPERANDO_VALIDACION_FACIAL`.
                *   Else (solo RFID era requerido), se concede el acceso y transita a `ABRIENDO_PUERTA`.
            *   Si RFID falla, transita a `ACCESO_DENEGADO_TEMPORAL`.
        *   **Desde `ESPERANDO_VALIDACION_QR` (Simulado):**
            *   Se maneja un timeout (`TIMEOUT_SIMULACION_QR_S`).
            *   Se simula el resultado (éxito/fallo) basado en un booleano (`qr_ok_simulado`) tras un breve delay.
            *   Si la simulación es exitosa:
                *   `estado_validacion_secuencial["qr_ok"] = True`.
                *   Si `protocolo_seleccionado_actual["facial"]` es `True` (y es el siguiente paso), transita a `ESPERANDO_VALIDACION_FACIAL`.
                *   Else (QR era el último o único paso requerido), se concede el acceso y transita a `ABRIENDO_PUERTA`. (Se usa información de `usuario_validado_rfid` si existe, o un placeholder "Usuario QR").
            *   Si la simulación de QR falla, transita a `ACCESO_DENEGADO_TEMPORAL`.
        *   **Desde `ESPERANDO_VALIDACION_FACIAL` (Simulado):**
            *   Se maneja un timeout (`TIMEOUT_SIMULACION_FACIAL_S`).
            *   Se simula el resultado (éxito/fallo) basado en un booleano (`facial_ok_simulado`) tras un breve delay.
            *   Si la simulación es exitosa:
                *   `estado_validacion_secuencial["facial_ok"] = True`.
                *   Se concede el acceso y transita a `ABRIENDO_PUERTA`. (Se usa información de `usuario_validado_rfid` si existe, o un placeholder "Usuario Facial/QR" o "Usuario Facial").
            *   Si la simulación de Facial falla, transita a `ACCESO_DENEGADO_TEMPORAL`.
    *   **Cancelación de Secuencia:** Si SP1 se libera durante *cualquier* estado de validación (`ESPERANDO_...`), se cancela la secuencia, se limpia `estado_validacion_secuencial`, y se transita a `REPOSO`.
    *   **Reintento tras Fallo Temporal:** Desde `ACCESO_DENEGADO_TEMPORAL`, si SP1 sigue activo, el sistema vuelve al *inicio* de la secuencia de validación del protocolo actualmente seleccionado (limpiando `estado_validacion_secuencial`).

5.  **Interfaz Gráfica de Usuario (GUI - Tkinter):**
    *   **Panel Principal:**
        *   Se añade un nuevo `Label` (`self.lbl_modo_validacion_actual`) para mostrar la descripción del protocolo de validación activo (ej: "Modo Validación: RFID + QR").
        *   Este label se actualiza cada vez que los interruptores S1/S2 cambian y se determina un nuevo protocolo.
    *   Los mensajes en `self.lbl_mensaje_acceso` se actualizan para guiar al usuario a través de los pasos de validación del protocolo actual (ej: "RFID OK. Prepare QR...", "Presente su tarjeta RFID...", "Mire a la cámara...").

6.  **Lógica de Cooldown y Bloqueo por Insistencia:**
    *   Estas lógicas, implementadas en la Fase 3/4, continúan funcionando.
    *   El cooldown se aplica al UID RFID si intenta un reingreso rápido, independientemente del protocolo.
    *   El bloqueo por insistencia se aplica a los intentos fallidos de RFID que sí cuentan para ello.
    *   Los fallos simulados de QR y Facial se registran pero **no** cuentan para el bloqueo por insistencia de UID RFID.

**Estado al Finalizar Fase 7:**
*   El sistema puede cambiar dinámicamente entre cuatro protocolos de validación diferentes basados en interruptores físicos.
*   La máquina de estados está preparada para manejar secuencias de múltiples pasos de validación.
*   Los métodos de validación QR y Facial están presentes como estados y flujos lógicos, pero su resultado (éxito/fallo) es simulado mediante un delay y un booleano configurable en el código, permitiendo probar todas las rutas lógicas.
*   La GUI informa al usuario sobre el modo de validación activo y lo guía a través de los pasos de la secuencia.
*   El sistema está listo para que las simulaciones de QR y Facial sean reemplazadas por la lógica de cámara real en fases posteriores.
