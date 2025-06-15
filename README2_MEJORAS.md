# Ideas Posiblemente Implementables

Este documento sirve como una hoja de ruta para futuras mejoras y funcionalidades que pueden llevar el proyecto de un prototipo avanzado a un producto robusto y comercializable. Las ideas están organizadas por prioridad y esfuerzo estimado.

---

## Fase 1: Mejoras Inmediatas y Refinamientos (Bajo Esfuerzo, Alto Impacto)

Estas mejoras pulirán la experiencia actual y robustecerán el sistema con cambios relativamente sencillos.

### 1. Centralizar la Configuración en un Archivo `config.json`
*   **Por qué:** Desacopla la configuración (puertos, timers, rutas) del código fuente. Facilita la configuración del sistema en diferentes entornos sin modificar el código.
*   **Implementación:**
    1.  Crear un archivo `config.json` con parámetros como:
        ```json
        {
          "serial_port": "COM3",
          "baud_rate": 9600,
          "camera_index": 0,
          "database_path": "data/sistema_acceso.db",
          "cooldown_seconds": 300,
          "lockout_attempts": 3,
          "lockout_durations_minutes": [5, 10, 1440],
          "paths": {
            "reports": "reportes/",
            "known_faces": "rostros_conocidos/"
          }
        }
        ```
    2.  Crear un módulo `config_manager.py` que cargue este archivo al inicio.
    3.  Utilizar **inyección de dependencias**: pasar el objeto de configuración a las clases que lo necesiten.
*   **Módulos Afectados:** `main_app.py`, `arduino_comms.py`, `db_manager.py`, y otros que usen valores fijos.

### 2. Integrar la Vista de la Cámara en la GUI de Tkinter
*   **Por qué:** Evita abrir ventanas separadas de OpenCV, ofreciendo una experiencia de usuario unificada y profesional.
*   **Implementación:**
    1.  Usar la librería `Pillow` (`pip install Pillow`).
    2.  En el bucle de la cámara, convertir el frame de OpenCV a una `PhotoImage` de Tkinter y mostrarlo en un widget `Label`.
        ```python
        # Ejemplo conceptual
        from PIL import Image, ImageTk
        import cv2

        cv2image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(cv2image)
        imgtk = ImageTk.PhotoImage(image=img)
        video_label.configure(image=imgtk)
        video_label.image = imgtk # Guardar referencia
        ```
*   **Módulos Afectados:** `gui_manager.py`, lógica de validación facial/QR.

### 3. Mejorar el Feedback Visual al Usuario en la GUI
*   **Por qué:** Proporciona información clara e instantánea sobre el resultado de una acción, reduciendo la confusión.
*   **Implementación:**
    1.  Usar un `Label` principal en la GUI para mostrar mensajes de estado.
    2.  Cambiar el color del texto/fondo del label según el resultado:
        *   **Verde:** "Acceso Concedido: Bienvenido, [Nombre]".
        *   **Rojo:** "Acceso Denegado: UID no reconocido".
        *   **Naranja/Amarillo:** "Acceso Denegado: Fuera de horario permitido", "Por favor, espere 5 minutos (Anti-Passback)".
*   **Módulos Afectados:** `gui_manager.py`, `state_machine_logic.py`.

---

## Fase 2: Funcionalidades Clave para un Prototipo Robusto

Pasos lógicos que añaden valor significativo y completan las funcionalidades principales.

### 1. Enrollment Facial Completo desde la GUI
*   **Por qué:** Elimina la necesidad de procesos manuales (añadir fotos, ejecutar scripts) para registrar nuevos usuarios, haciendo el sistema autónomo.
*   **Implementación:**
    1.  En el formulario de "Gestión de Usuarios", añadir un botón "Capturar Rostro".
    2.  Este botón activa la cámara, detecta un rostro y captura 3-5 imágenes de buena calidad.
    3.  Genera el `encoding` facial a partir de las capturas.
    4.  Guarda el `encoding` directamente como un `BLOB` en la base de datos, asociado al usuario.
    5.  **Crucial:** Modificar el sistema para que al iniciar, cargue todos los `encodings` y nombres/IDs desde la base de datos en lugar de un archivo `.pkl`.
*   **Módulos Afectados:** `gui_manager.py`, `db_manager.py`, `facial_recognition_utils.py`.

### 2. Implementar QR Dinámicos (One-Time Use) para Visitantes
*   **Por qué:** Un QR estático es una gran vulnerabilidad de seguridad. Los QR de un solo uso son el estándar para accesos temporales.
*   **Implementación (Enfoque de Token):**
    1.  Al registrar un visitante, generar un token único y seguro (ej. `uuid.uuid4().hex`).
    2.  Guardar el token en la base de datos junto al ID del visitante, una fecha de expiración y un campo `usado` (booleano, `False` por defecto).
    3.  Generar una imagen QR a partir de este token para ser enviada al visitante.
    4.  En la validación, buscar el token del QR en la BD. Si se encuentra, no ha expirado y `usado == False`, se concede el acceso y se actualiza `usado = True`.
*   **Módulos Afectados:** `gui_manager.py`, `db_manager.py`, `validation_logic.py`.

### 3. Control de Motor Realista (Motor DC + Finales de Carrera)
*   **Por qué:** Reemplaza la simulación del servo por un mecanismo más potente y fiable, que reporta el estado real de la puerta.
*   **Implementación:**
    1.  **Hardware:** Usar un motor DC con un controlador (ej. H-Bridge L298N) y dos finales de carrera (microswitches) para detectar las posiciones "totalmente abierta" y "totalmente cerrada".
    2.  **Arduino:** Leer los finales de carrera. Activar el motor hasta que el final de carrera correspondiente se active, luego detenerlo. Enviar el estado de los finales de carrera a Python.
    3.  **Python (FSM):** Modificar la máquina de estados para que sea controlada por eventos.
        *   `ABRIENDO_PUERTA` espera a recibir la señal `final_carrera_abierto:1`.
        *   `CERRANDO_PUERTA` espera a recibir la señal `final_carrera_cerrado:1`.
        *   Añadir estados de error con timeout si no se reciben las señales en un tiempo prudencial.
*   **Módulos Afectados:** `arduino_comms.py`, `state_machine_logic.py`.

---

## Fase 3: Evolución Hacia un Producto Comercial

Cambios significativos que elevan el proyecto a un nivel profesional y lo preparan para un entorno de producción.

### 1. Robustez del Hardware y Diseño de Carcasa
*   **Sensor de Paso:** Reemplazar el sensor de ultrasonido interior (SP2) por una **barrera de infrarrojos (emisor-receptor)**. Es mucho más fiable para detectar el cruce de una persona.
*   **Microcontrolador Inalámbrico:** Migrar de Arduino a un **ESP32**. Esto permite la comunicación vía **WiFi (usando el protocolo MQTT)**, desacoplando el punto de acceso del PC de control y permitiendo una red de múltiples dispositivos.
*   **Carcasa:** Diseñar y construir una carcasa robusta, preferiblemente de **acero inoxidable**. Debe proteger los componentes y ofrecer un acceso fácil para el mantenimiento.

### 2. GUI Avanzada 
*   **Librería Gráfica:** Migrar de Tkinter a una opción más moderna.
    *   **CustomTkinter:** Ofrece un look moderno con bajo esfuerzo de migración.
    *   **PyQt6 / PySide6:** Mucho más potente y personalizable. Es el estándar para aplicaciones de escritorio profesionales.

### 3. Mejorar la Librería de Reconocimiento Facial
*   **Por qué:** `face_recognition` (dlib) es bueno, pero hay modelos más precisos y robustos.
*   **Implementación:** Investigar y migrar a la librería `deepface`. Permite usar modelos de vanguardia como **FaceNet**, **VGG-Face** o **ArcFace** (muy recomendado) para una mayor precisión ante variaciones de ángulo, iluminación y uso de mascarillas.

### 4. Base de Datos Escalable (Cliente-Servidor)
*   **Por qué:** SQLite no maneja bien la escritura concurrente, lo que limita la escalabilidad a múltiples puntos de acceso o a una interfaz de administración web.
*   **Implementación:** Migrar la base de datos a un sistema cliente-servidor como **PostgreSQL** (opción más robusta y profesional) o **MariaDB/MySQL**. Ambas son opciones open-source potentes.

---

## Fase 4: Arquitectura y Calidad del Código

Prácticas que mejorarán la mantenibilidad y escalabilidad a largo plazo del proyecto.

### 1. Aplicar Patrones de Diseño (Inyección de Dependencias)
*   **Por qué:** Mejora el desacoplamiento entre módulos, simplifica las pruebas y facilita la modificación o sustitución de componentes.
*   **Implementación:** En `main_app.py`, crear las instancias de los managers (`DBManager`, `ArduinoComms`, etc.) y pasarlas como argumentos al constructor de las clases que las necesiten.
    ```python
    # Ejemplo en main_app.py
    db_manager = DBManager(config)
    comms_manager = ArduinoComms(config)
    validation_logic = ValidationLogic(db_manager)
    state_machine = StateMachine(comms_manager, validation_logic)
    ```

### 2. Implementar una Estrategia de Pruebas Formal
*   **Por qué:** Asegura que las nuevas funcionalidades no rompan el código existente y garantiza la robustez del sistema.
*   **Implementación:**
    *   **Pruebas Unitarias (`pytest`):** Para funciones puras en `validation_logic.py`, `reporting_logging.py`, etc.
    *   **Pruebas de Integración:** Scripts que prueban flujos completos (ej. simular un evento RFID y verificar que la FSM transita correctamente y se escribe el log).
    *   **Pruebas de Estrés:** Simular altas cargas de eventos (múltiples lecturas de sensor, intentos de acceso rápidos) para encontrar cuellos de botella.
    *   **Pruebas de Usuario (Caja Negra):** Pedir a alguien externo que use el sistema para identificar problemas de usabilidad.
