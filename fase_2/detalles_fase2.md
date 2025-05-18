## Fase 2: Lógica de Puerta (Servo Simulado) y Máquina de Estados Básica

**Objetivo Principal:** Implementar en Python la lógica de control para la apertura y cierre de la puerta (simulada por el servo) basada en la detección de los sensores de proximidad SP1 y SP2. Introducir una máquina de estados para gestionar el flujo del sistema.

**Componentes y Funcionalidad (Principalmente Python):**

1.  **Constantes del Sistema (Python):**
    *   `UMBRAL_DETECCION_SP1_CM`, `UMBRAL_DETECCION_SP2_CM`: Distancias umbral para considerar que los sensores detectan un objeto.
    *   `TIEMPO_ESPERA_APERTURA_PUERTA_S`: Tiempo inicial para que SP1 se libere después de que la puerta comience a abrir, o para que SP2 detecte.
    *   `TIEMPO_MAX_SP2_ACTIVO_S`: Máximo tiempo que SP2 puede estar activo continuamente antes de forzar el cierre de la puerta (evita que la puerta quede abierta si alguien se detiene en SP2).
    *   `TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S`: Tiempo máximo total que la puerta puede permanecer abierta en un ciclo.
    *   `TIEMPO_CIERRE_PUERTA_S`: Simulación del tiempo que tarda la puerta en cerrarse físicamente.

2.  **Máquina de Estados (`EstadoSistema` Enum en Python):**
    *   Se introduce una enumeración para definir los estados del sistema de forma clara:
        *   `REPOSO` (anteriormente `ESPERANDO_PERSONA_SP1`): Estado inicial o después de un ciclo completo.
        *   `ABRIENDO_PUERTA`: La puerta está en proceso de apertura.
        *   `PERSONA_CRUZANDO`: Se detecta que una persona está pasando por la puerta (SP1 libre, SP2 activo).
        *   `CERRANDO_PUERTA`: La puerta está en proceso de cierre.
        *   `ALERTA_ERROR_CRUCE`: Estado temporal si se detecta una anomalía (SP1 y SP2 activos simultáneamente durante el cruce).
    *   Una variable global `estado_actual_sistema` rastrea el estado actual.
    *   Una función `cambiar_estado(nuevo_estado, mensaje_gui)` gestiona las transiciones, registra el tiempo de entrada al nuevo estado y actualiza mensajes en la GUI.

3.  **Variables Globales de Estado y Temporizadores (Python):**
    *   `puerta_logicamente_abierta`: Booleano que indica si Python cree que la puerta está abierta.
    *   `tiempo_inicio_estado_actual_s`: Timestamp de cuándo se entró al estado actual.
    *   `tiempo_puerta_abrio_s`: Timestamp de cuándo se envió el comando de abrir puerta.
    *   `tiempo_sp2_detecto_primera_vez_s`: Timestamp de cuándo SP2 detectó por primera vez después de que la puerta se abrió.

4.  **Hilo de Lógica de Máquina de Estados (`logica_maquina_estados()` en Python):**
    *   Se ejecuta en un hilo separado para no bloquear la GUI ni la recepción de datos de Arduino.
    *   **Bucle Principal:**
        *   Obtiene el tiempo actual y los datos de los sensores (`dist_sp1`, `dist_sp2`) del diccionario `datos_hardware`.
        *   **Lógica específica para cada estado:**
            *   **`REPOSO`:**
                *   Acciones: LED Verde ON (o OFF según la lógica final), LED Rojo OFF. Si `puerta_logicamente_abierta` es `True`, transita a `CERRANDO_PUERTA`.
                *   Transición: Si SP1 detecta (`0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM`), transita a `ABRIENDO_PUERTA` (asumiendo validación exitosa por ahora).
            *   **`ABRIENDO_PUERTA`:**
                *   Acciones: LED Verde OFF. Si la puerta no está lógicamente abierta, envía comando `ABRIR_PUERTA` a Arduino, actualiza `puerta_logicamente_abierta`, registra `tiempo_puerta_abrio_s`.
                *   Transiciones:
                    *   A `PERSONA_CRUZANDO`: Si SP1 se libera Y SP2 detecta.
                    *   A `CERRANDO_PUERTA`: Si SP1 sigue obstruido después de `TIEMPO_ESPERA_APERTURA_PUERTA_S`.
                    *   A `PERSONA_CRUZANDO` (para timeout): Si SP1 se libera pero SP2 no detecta después de `TIEMPO_ESPERA_APERTURA_PUERTA_S`.
                    *   A `CERRANDO_PUERTA`: Si se excede `TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S`.
            *   **`PERSONA_CRUZANDO`:**
                *   Alerta: Si SP1 y SP2 están activos simultáneamente, envía comando `LED_ROJO_PARPADEAR_ALERTA` y transita a `ALERTA_ERROR_CRUCE`.
                *   Transiciones:
                    *   A `CERRANDO_PUERTA`: Si SP2 se libera (y había detectado antes).
                    *   A `CERRANDO_PUERTA`: Si SP2 permanece activo más de `TIEMPO_MAX_SP2_ACTIVO_S`.
                    *   A `CERRANDO_PUERTA`: Si se excede `TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S`.
            *   **`ALERTA_ERROR_CRUCE`:**
                *   Acción: Espera un tiempo para que el LED parpadee.
                *   Transición: A `CERRANDO_PUERTA`.
            *   **`CERRANDO_PUERTA`:**
                *   Acciones: Si la puerta está lógicamente abierta, envía comando `CERRAR_PUERTA`, actualiza `puerta_logicamente_abierta`.
                *   Transición: A `REPOSO` después de `TIEMPO_CIERRE_PUERTA_S` (simulación).
        *   Pequeño `time.sleep(0.1)` para el ciclo de la máquina de estados.

5.  **Interfaz Gráfica de Usuario (GUI - Tkinter, clase `InterfazGrafica` en Python):**
    *   Se añade un `Label` en el "Panel Principal" (`self.lbl_estado_sistema_valor`) para mostrar el valor del `estado_actual_sistema` en tiempo real.
    *   La función `actualizar_gui_periodicamente()` ahora también actualiza este nuevo label.
    *   En `al_cerrar_ventana()`, se añade la señal para detener el `hilo_maquina_estados_activo`.

6.  **Bloque Principal (`if __name__ == "__main__":` en Python):**
    *   Ahora también crea e inicia el `hilo_estados` para la `logica_maquina_estados`.
    *   Al cerrar, intenta hacer `join()` en ambos hilos (escucha y estados).

**Modificaciones en Arduino (para esta fase):**
*   Se espera que Arduino tenga un comando `LED_ROJO_PARPADEAR_ALERTA` que haga parpadear el LED rojo un número fijo de veces (ej: 3 veces) y luego se detenga automáticamente. El código de Fase 0 (`control_acceso_arduino_fase0_modificado.ino`) ya incluía esta lógica.

**Estado al Finalizar Fase 2:**
*   La aplicación Python tiene una máquina de estados funcional que controla un ciclo básico de apertura y cierre de puerta basado en la detección de los sensores SP1 y SP2.
*   Se manejan timeouts básicos y una condición de alerta (SP1+SP2 activos).
*   La GUI refleja el estado actual del sistema.
*   La validación de identidad aún no está implementada; la detección en SP1 es el único disparador para abrir la puerta.
*   El control de la puerta sigue siendo simulado mediante comandos al servo (cuya funcionalidad de movimiento real está comentada en el Arduino).
