## Fases 0 y 1: Configuración del Entorno, Arduino Base, GUI Inicial y Comunicación Estable

**Objetivo Principal Combinado:** Establecer la infraestructura fundamental del proyecto. Esto incluye la preparación del hardware Arduino para leer sensores y controlar actuadores básicos, y el desarrollo de una aplicación Python inicial con una Interfaz Gráfica de Usuario (GUI) capaz de conectarse al Arduino, recibir datos de sus sensores en tiempo real, mostrar esta información, y enviar comandos manuales simples al Arduino.

### Componente de Hardware (Arduino) - (`control_acceso_arduino_fase0_modificado.ino`)

**Hardware Utilizado:**

*   **Microcontrolador:** Arduino Uno.
*   **Sensores de Proximidad:** 2 x HC-SR04 (SP1 exterior, SP2 interior).
*   **Interruptores Físicos:** 3 x Interruptores de dos estados (para S1, S2, E), configurados con `INPUT_PULLUP` (activos en `LOW`).
*   **Lector RFID:** 1 x MFRC522, conectado vía interfaz SPI.
*   **Actuadores (Simulación/Indicadores):**
    *   1 x LED Verde (indicador general).
    *   1 x LED Rojo (indicador general).
    *   *(Nota: El servomotor SG90 para la puerta está considerado en el diseño de pines pero su funcionalidad de movimiento está comentada en esta fase inicial del código Arduino).*

**Lógica del Firmware Arduino:**

1.  **`setup()` - Inicialización:**
    *   Establece la comunicación serial con Python a 115200 baudios.
    *   Configura los pines de los sensores HC-SR04 (TRIG como `OUTPUT`, ECHO como `INPUT`).
    *   Configura los pines de los interruptores S1, S2, y E como `INPUT_PULLUP`.
    *   Configura los pines de los LEDs Verde y Rojo como `OUTPUT` y los inicializa en estado `LOW` (apagados).
    *   Inicializa la interfaz SPI y el lector MFRC522.
    *   Realiza una lectura inicial del estado de los interruptores (con debouncing).
    *   Envía el mensaje `ARDUINO_LISTO` por el puerto serial para notificar a Python que está operativo y listo para la comunicación.

2.  **`loop()` - Bucle Principal:**
    *   **Lectura de Interruptores:** Llama continuamente a `leerInterruptores()` para obtener el estado actual de S1, S2 y E, aplicando una lógica de debouncing para evitar lecturas erráticas.
    *   **Manejo de Comandos:** Llama a `manejarComandosPython()` para procesar cualquier comando entrante desde la aplicación Python.
    *   **Envío de Datos Periódico:** Cada `INTERVALO_ENVIO_DATOS_MS` (ej: 100ms), llama a `enviarDatosAPython()` para transmitir el estado actual de los sensores y el hardware a Python.
    *   **Control de Parpadeo LED:** Si se ha activado el parpadeo del LED rojo mediante un comando de Python, la función `parpadearLedRojoComandado()` gestiona este parpadeo.

3.  **Funciones de Soporte:**
    *   **`leerUltrasonico(pinTrig, pinEcho)`:** Mide y devuelve la distancia en centímetros para un sensor HC-SR04.
    *   **`leerInterruptores()`:** Implementa el debouncing para los interruptores S1, S2 y E, actualizando las variables globales que almacenan su estado (0 para `LOW`/activo, 1 para `HIGH`/inactivo).
    *   **`leerUidRfid()`:** (Se llama bajo demanda) Intenta leer una tarjeta RFID. Si tiene éxito, formatea el UID como una cadena hexadecimal, ejecuta `rfid.PICC_HaltA()` y `rfid.PCD_StopCrypto1()` para preparar el lector para la siguiente lectura, y devuelve el UID. Si no hay tarjeta, devuelve "NADA".
    *   **`enviarDatosAPython()`:**
        *   Recolecta las distancias de SP1 y SP2.
        *   Si `solicitarLecturaRfidActiva` es `true` (activado por Python) y no se ha enviado un UID para esa solicitud, llama a `leerUidRfid()`.
        *   Construye y envía el paquete de datos a Python en el formato: `DATOS;SP1:[val];SP2:[val];S1:[0/1];S2:[0/1];E:[0/1];RFID:[UID/NADA]\n`.
    *   **`manejarComandosPython()`:**
        *   Interpreta comandos entrantes desde Python que comienzan con `COMANDO:`.
        *   Ejecuta acciones como encender/apagar LEDs, activar/detener parpadeo del LED rojo, y activar el flag `solicitarLecturaRfidActiva`.
        *   Los comandos para el servo (`ABRIR_PUERTA`/`CERRAR_PUERTA`) son reconocidos pero su acción está comentada (solo imprimen un mensaje informativo en el serial de Arduino).
    *   **`parpadearLedRojoComandado()`:** Gestiona el parpadeo del LED rojo (ya sea un número fijo de veces para una alerta, o continuamente para emergencia) cuando es activado por un comando.

---

### Componente de Software (Python) - (`control_acceso_python_fase1.py` o versión inicial)

**Bibliotecas Utilizadas:** `tkinter`, `serial`, `threading`.

**Lógica de la Aplicación Python:**

1.  **Configuración Inicial:**
    *   Define constantes para `PUERTO_SERIAL_ARDUINO` y `VELOCIDAD_ARDUINO`.

2.  **Conexión Serial (`conectar_a_arduino()`):**
    *   Establece la conexión con el Arduino en el puerto y velocidad especificados.
    *   Espera la señal `ARDUINO_LISTO` para confirmar la sincronización.
    *   Maneja errores si la conexión no se puede establecer.

3.  **Recepción de Datos Asíncrona (`escuchar_datos_arduino()` en un Hilo):**
    *   Un hilo dedicado lee continuamente el puerto serial para no bloquear la GUI.
    *   **Parseo de Paquetes `DATOS;`:**
        *   Cuando recibe una línea que comienza con `DATOS;`, la divide y extrae los valores para:
            *   `sp1_distancia` (float)
            *   `sp2_distancia` (float)
            *   `s1_estado` (int 0 o 1)
            *   `s2_estado` (int 0 o 1)
            *   `e_estado` (int 0 o 1)
            *   `rfid_uid` (string)
        *   Estos valores se almacenan en un diccionario global `datos_hardware`.
        *   Se utiliza un `threading.Lock` (`lock_datos_hardware`) para proteger el acceso concurrente a `datos_hardware` desde el hilo de escucha y el hilo de la GUI.
    *   Incluye una lógica básica de intento de reconexión si la comunicación serial falla.

4.  **Envío de Comandos (`enviar_comando_a_arduino()`):**
    *   Función que toma una cadena de texto como comando.
    *   Añade el prefijo `COMANDO:` y un terminador `\n`.
    *   Envía el comando formateado al Arduino.

5.  **Interfaz Gráfica de Usuario (GUI - Clase `InterfazGrafica` con Tkinter):**
    *   **Estructura:**
        *   Ventana principal con título.
        *   `ttk.LabelFrame` para "Estado de Sensores e Interruptores".
        *   `ttk.LabelFrame` para "Control Manual (Test)".
    *   **Visualización de Datos:**
        *   Labels de texto fijos para describir cada dato (ej: "SP1 (cm):").
        *   Labels de valor (`ttk.Label`) que se actualizan dinámicamente para mostrar los datos leídos de `datos_hardware`.
    *   **Controles Manuales:**
        *   Botones (`ttk.Button`) que, al ser presionados, llaman a `enviar_comando_a_arduino()` con el comando apropiado:
            *   "Abrir Puerta" / "Cerrar Puerta" (simulados).
            *   "LED Verde ON" / "LED Verde OFF".
            *   "LED Rojo ON" / "LED Rojo OFF".
            *   "Solicitar RFID".
    *   **Actualización Dinámica de la GUI (`actualizar_gui_periodicamente()`):**
        *   Un método que se auto-reprograma usando `self.after(200, ...)` para ejecutarse cada 200ms.
        *   Lee (con `lock`) los valores de `datos_hardware`.
        *   Actualiza el texto de los labels de valor en la GUI.
    *   **Cierre Limpio (`al_cerrar_ventana()`):**
        *   Detiene los hilos secundarios.
        *   Cierra el puerto serial.
        *   Destruye la ventana.

6.  **Ejecución Principal (`if __name__ == "__main__":`)**
    *   Intenta conectar al Arduino.
    *   Si tiene éxito, inicia el hilo `escuchar_datos_arduino`.
    *   Crea y lanza la `InterfazGrafica`.
    *   Gestiona la finalización limpia de los hilos al cerrar la GUI.

**Estado al Finalizar Fase 0 y 1 Combinadas:**
El sistema cuenta con una comunicación bidireccional funcional entre Arduino y Python. La aplicación Python puede mostrar el estado del hardware en tiempo real en una GUI y enviar comandos básicos. Esta es la base esencial sobre la cual se construirán todas las lógicas más complejas de control, validación y gestión.
