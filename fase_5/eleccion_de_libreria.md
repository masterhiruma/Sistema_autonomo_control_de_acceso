## Fase 5: Integración de Reconocimiento Facial

**Objetivo Principal:** Implementar la capacidad de validar usuarios mediante el reconocimiento de sus rostros, utilizando una cámara conectada al sistema Python. Este método de validación se integrará en los protocolos de acceso definidos por la Fase 7.

**Decisión Tecnológica: OpenCV + `face-recognition` vs. Google MediaPipe**

Para la implementación del reconocimiento facial, se consideraron dos enfoques principales basados en bibliotecas populares de Python:

1.  **OpenCV + `face-recognition`:**
    *   **OpenCV (`opencv-python`):** Una biblioteca extremadamente completa y madura para visión por computadora en general. Proporciona las herramientas fundamentales para la captura de vídeo desde cámaras, preprocesamiento de imágenes (redimensionar, convertir a escala de grises/RGB), y dibujo de elementos sobre los frames (rectángulos, texto).
    *   **`face-recognition`:** Una biblioteca de alto nivel construida sobre `dlib`. Simplifica enormemente tareas complejas como:
        *   **Detección de Rostros:** Encontrar las ubicaciones de los rostros en una imagen (`face_locations`).
        *   **Extracción de "Encodings" Faciales:** Convertir un rostro detectado en una representación numérica vectorial de 128 dimensiones que es única para ese rostro (`face_encodings`). Este encoding es la "firma" del rostro.
        *   **Comparación de Rostros:** Comparar un encoding facial desconocido con una lista de encodings conocidos para determinar si hay coincidencias (`compare_faces`), calculando la distancia entre los vectores.
    *   **Ventajas:**
        *   `face-recognition` es relativamente fácil de usar para las tareas específicas de reconocimiento facial.
        *   Amplia comunidad y muchos tutoriales disponibles.
        *   Buen rendimiento para un número moderado de rostros conocidos si se optimiza la carga de encodings.
    *   **Desventajas:**
        *   `dlib` (la dependencia subyacente) puede ser a veces complicada de instalar en ciertos sistemas debido a sus requisitos de compilación (necesita `cmake`).
        *   El rendimiento de la comparación 1-a-N puede degradarse si la base de datos de rostros conocidos es muy grande (miles) sin técnicas de indexación avanzadas.

2.  **Google MediaPipe:**
    *   **MediaPipe:** Un framework de Google para construir pipelines de percepción multimodal (rostro, manos, pose, etc.) multiplataforma y de alto rendimiento. Ofrece soluciones pre-entrenadas para diversas tareas.
    *   **Ventajas:**
        *   Suele ser muy optimizado para rendimiento, incluso en dispositivos con menos recursos.
        *   Proporciona modelos robustos para detección de rostros, detección de puntos faciales clave (landmarks), etc.
        *   Google lo mantiene activamente.
    *   **Desventajas para Reconocimiento de Identidad Específico:**
        *   Si bien MediaPipe es excelente para la *detección* de rostros y sus características, su solución "Face Mesh" o "Face Detection" no proporciona directamente un "encoding" facial de 128-d como `face-recognition` para la *identificación* de individuos específicos.
        *   Para realizar reconocimiento de identidad (quién es esta persona), se necesitaría tomar la salida de MediaPipe (ej: el rostro recortado o los landmarks) y pasarla a otro modelo o algoritmo de extracción de características/clasificación que el desarrollador tendría que implementar o integrar (ej: usando un modelo siamés, FaceNet, ArcFace, o entrenando un clasificador sobre características extraídas). Esto añade una capa de complejidad significativa en comparación con la solución "todo en uno" de `face-recognition` para la identificación.
        *   La curva de aprendizaje para construir pipelines personalizados en MediaPipe puede ser más pronunciada.

**Decisión Adoptada para el Proyecto:**

Tras una breve investigación y considerando los objetivos del proyecto (principalmente la identificación de un conjunto conocido de usuarios), se ha decidido proceder con el enfoque de **OpenCV + `face-recognition`**.

*   **Razón Principal:** La biblioteca `face-recognition` ofrece una API de alto nivel que simplifica directamente las tres tareas cruciales: detección de rostros, generación de encodings faciales únicos, y comparación de estos encodings para la identificación. Esto reduce la complejidad de implementación inicial para la funcionalidad de reconocimiento de identidad.
*   Si bien la instalación de `dlib` puede presentar un desafío, una vez superado, el desarrollo de la lógica de reconocimiento es más directo para este caso de uso.
*   La gestión de un número moderado de usuarios (decenas, quizás cientos) es manejable con `face-recognition` sin recurrir a optimizaciones de indexación de vectores faciales muy complejas.

**Pasos Conceptuales de Implementación para la Fase 5 (usando OpenCV + `face-recognition`):**

1.  **Preparación del Entorno:**
    *   Instalar las bibliotecas necesarias: `opencv-python`, `face-recognition`, `Pillow`, `cmake`, `dlib`.

2.  **Modificación de la Base de Datos:**
    *   Añadir un campo `facial_encoding BLOB` a la tabla `usuarios` para almacenar el encoding serializado (ej: con `pickle`) del rostro de cada usuario.

3.  **Enrollment (Registro) de Rostros:**
    *   **Funcionalidad en la GUI ("Gestión de Usuarios"):**
        *   Botón "Capturar/Registrar Rostro" para el usuario que se está agregando o editando.
        *   Al activarse, se abre la cámara.
        *   Se detecta un rostro en el feed (idealmente solo uno para un buen enrollment).
        *   Se extrae el `face_encoding` (array NumPy de 128 dimensiones).
        *   Este encoding se serializa y se guarda en la base de datos junto con los demás datos del usuario.
    *   *(Implementación inicial simplificada: se pueden pre-generar encodings de archivos de imagen y cargarlos desde un archivo `.pkl` para las primeras pruebas de verificación, antes de implementar la GUI de enrollment completa).*

4.  **Verificación (Reconocimiento) Facial Durante el Acceso:**
    *   **Activación:** Cuando la máquina de estados entre en `ESPERANDO_VALIDACION_FACIAL` (según el protocolo seleccionado por S1/S2).
    *   **Proceso:**
        1.  Activar la cámara.
        2.  En un bucle:
            *   Capturar un frame.
            *   Convertir a RGB.
            *   Detectar todas las `face_locations` en el frame.
            *   Si se detectan rostros:
                *   Si el protocolo es **"Solo Facial"** o **"QR + Facial" (y QR fue OK)**:
                    *   Extraer el `face_encoding` de cada rostro detectado.
                    *   Comparar cada encoding detectado con la lista de `encodings_faciales_conocidos` (cargados desde la BD o el archivo `.pkl`). Se usa `face_recognition.compare_faces()`.
                    *   Si se encuentra una única coincidencia clara (y no hay múltiples rostros detectados, según la política definida), se identifica al usuario.
                *   Si el protocolo es **"RFID + Facial" (y RFID del usuario U1 fue OK)**:
                    *   Extraer el `face_encoding` del rostro detectado (idealmente solo uno).
                    *   Compararlo únicamente con el `facial_encoding` almacenado para el usuario U1.
                *   Si se identifica un usuario y el rostro coincide:
                    *   Verificar el nivel del usuario, restricciones horarias y cooldown anti-passback.
                    *   Si todo es válido: Conceder acceso (transitar a `ABRIENDO_PUERTA`).
                    *   Si no: Denegar acceso (transitar a `ACCESO_DENEGADO_TEMPORAL`), registrar intento fallido (motivo: "Facial - Fuera de Horario", "Facial - Cooldown", etc.).
                *   Si no hay coincidencia (rostro no reconocido): Continuar procesando frames hasta timeout o registrar intento fallido (motivo: "Facial - Rostro no reconocido").
        3.  Manejar timeouts y si el usuario se va (SP1 libre), liberando la cámara.

5.  **GUI durante Verificación:**
    *   Mostrar el feed de la cámara.
    *   Mensajes de estado ("Mire a la cámara", "Procesando...", "Rostro reconocido: [Nombre]", "Rostro no reconocido").

**Estado al Finalizar Fase 5:**
El sistema será capaz de utilizar el reconocimiento facial como un método de validación. Los usuarios podrán ser registrados con sus características faciales (aunque el enrollment completo en GUI vendrá después), y el sistema podrá identificarlos para conceder o denegar el acceso según los protocolos y reglas establecidas.





