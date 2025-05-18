## Fase 3 (Combinada 3.1 + 4): Validación RFID, Gestión de Usuarios, Contador, Logs, Reportes, Bloqueos y Cooldown

**Objetivo Principal:** Implementar un sistema robusto de validación de acceso mediante tarjetas RFID, gestionando usuarios con diferentes niveles y restricciones horarias. Incorporar mecanismos de seguridad (cooldown anti-passback, bloqueo por insistencia). Establecer un sistema completo de conteo de accesos, logging detallado de eventos (exitosos y fallidos), persistencia de datos diarios y generación de reportes en formatos JSON y CSV.

**Componentes y Funcionalidad (Principalmente Python):**

1.  **Base de Datos SQLite (`sistema_acceso.db`):**
    *   **Tabla `usuarios`:**
        *   Campos: `id_usuario` (PK, autoincremental), `nombre_completo` (NOT NULL), `dni` (UNIQUE, NOT NULL), `nivel_usuario` (NOT NULL, CHECK 'Admin'/'Trabajador'/'Visitante'), `area_trabajo` (TEXT), `uid_rfid` (UNIQUE, NOT NULL), `horario_trabajo_inicio` (TEXT, HH:MM), `horario_trabajo_fin` (TEXT, HH:MM).
        *   Constraint `CHECK` para asegurar que los horarios solo se apliquen a 'Trabajador'.
    *   **Funciones de Acceso a BD (Python):**
        *   `inicializar_bd()`: Crea la tabla si no existe y la carpeta de reportes.
        *   `agregar_usuario_bd()`: Inserta nuevos usuarios, manejando errores de unicidad para DNI/UID.
        *   `obtener_usuario_por_rfid_bd()`: Recupera datos de usuario por UID RFID.
        *   `obtener_usuario_por_id_bd()`: Recupera datos de usuario por `id_usuario`.
        *   `verificar_uid_existente_bd()`: Chequea si un UID ya existe (opcionalmente excluyendo un ID de usuario).
        *   `verificar_dni_existente_bd()`: Chequea si un DNI ya existe (opcionalmente excluyendo un ID de usuario).
        *   `obtener_todos_los_usuarios_bd()`: Para listar usuarios en la GUI.
        *   `actualizar_usuario_bd()`: Modifica los datos de un usuario existente.
        *   `borrar_usuario_bd()`: Elimina un usuario de la BD.

2.  **Interfaz Gráfica de Usuario (GUI - Tkinter, clase `InterfazGrafica`):**
    *   **Pestañas (`ttk.Notebook`):** "Panel Principal", "Gestión de Usuarios", "Reportes Diarios".
    *   **Pestaña "Panel Principal":**
        *   Muestra `estado_actual_sistema` y `protocolo_seleccionado_actual` (preparando para Fase 7).
        *   Label `lbl_mensaje_acceso` para feedback de validación (Concedido/Denegado, motivos).
        *   Visualización en tiempo real de datos de `datos_hardware` (sensores, interruptores).
    *   **Pestaña "Gestión de Usuarios":**
        *   **Formulario Unificado (Registrar/Editar):**
            *   Campos para: Nombre, DNI, Nivel (Combobox), Área, UID RFID (Entry con `textvariable`), Horarios (Entry, condicionales para "Trabajador").
            *   Botón **"Escanear UID"**: Activa `modo_escaneo_rfid_para_registro`, envía comando a Arduino. El UID recibido se muestra en el campo del formulario. Lógica para verificar si el UID escaneado ya existe y preguntar al usuario. Campo UID editable.
            *   Botón **"Guardar Nuevo Usuario" / "Guardar Cambios"**: Valida todos los campos (obligatorios, formato UID/DNI/Horario, unicidad de DNI/UID) y llama a `agregar_usuario_bd` o `actualizar_usuario_bd`.
            *   Botón "Limpiar Formulario" / "Cancelar Edición".
        *   **Lista de Usuarios Registrados:**
            *   `ttk.Treeview` para mostrar `id`, Nombre, DNI, Nivel, UID.
            *   Botones: "Cargar/Actualizar Lista", "Editar Seleccionado", "Borrar Seleccionado".
            *   Lógica para cargar datos del usuario seleccionado en el formulario para edición.
            *   Lógica para borrar usuario seleccionado (con confirmación).
    *   **Pestaña "Reportes Diarios":**
        *   Label para `contador_accesos_hoy`.
        *   Botón "Generar Reporte CSV/JSON del Día Actual".
        *   Dos `ttk.Treeview` para mostrar en tiempo real:
            *   "Accesos Exitosos Hoy" (Columnas: Timestamp, Nombre, DNI, Nivel, Área, UID Usado).
            *   "Intentos Fallidos Hoy" (Columnas: Timestamp, UID Presentado, Nombre Detectado, DNI Detectado, Motivo del Fallo).
        *   Método `actualizar_reportes_en_gui()` para refrescar estos Treeviews y el contador.

3.  **Máquina de Estados (`logica_maquina_estados()` en Python):**
    *   **Nuevos Estados:**
        *   `ESPERANDO_VALIDACION_RFID`: Se entra desde `REPOSO` si SP1 detecta y el protocolo requiere RFID.
        *   `ACCESO_DENEGADO_TEMPORAL`: Estado breve para mostrar mensaje/LED de denegación antes de reintentar o volver a `REPOSO`.
        *   `SISTEMA_BLOQUEADO_UID`: Estado para cuando un UID es bloqueado por insistencia.
    *   **En `ESPERANDO_VALIDACION_RFID`:**
        1.  Se envía `SOLICITAR_LECTURA_RFID` a Arduino.
        2.  Se maneja un `TIMEOUT_PRESENTACION_RFID_S`.
        3.  Si se recibe un UID válido (y no es el `ultimo_rfid_procesado_para_acceso`):
            *   **Chequeo de Bloqueo por Insistencia:** Verifica si el UID está en `intentos_fallidos_por_uid` y si `desbloqueo_hasta` es futuro. Si está bloqueado, va a `SISTEMA_BLOQUEADO_UID`, registra el intento (sin contar para nuevo bloqueo).
            *   **Obtención de Usuario:** Llama a `obtener_usuario_por_rfid_bd()`.
            *   **Si Usuario Existe:**
                *   **Chequeo de Cooldown Anti-Passback:** Verifica `accesos_recientes_uid` y `TIEMPO_COOLDOWN_ACCESO_S`. Si está en cooldown, va a `ACCESO_DENEGADO_TEMPORAL`, registra el intento (sin contar para bloqueo por insistencia, motivo "Cooldown").
                *   **Validación de Nivel y Horario:**
                    *   Admin: Siempre acceso.
                    *   Trabajador: Llama a `verificar_horario_trabajador()` (L-V, horario laboral).
                    *   Visitante: Llama a `verificar_horario_visitante()` (Miércoles, 9-10 AM).
                *   Si la validación de nivel/horario es exitosa: Se considera `acceso_valido_este_paso = True`.
            *   **Resultado de Validación RFID:**
                *   Si `acceso_valido_este_paso` es `True`:
                    *   Se actualiza `estado_validacion_secuencial` (para Fase 7).
                    *   Se decide si pasar al siguiente paso de validación (QR/Facial - simulado en Fase 7) o conceder acceso.
                    *   Si es el paso final y exitoso: `registrar_evento_acceso_exitoso()`, LED Verde ON, transita a `ABRIENDO_PUERTA`.
                *   Si `acceso_valido_este_paso` es `False` (o usuario no existe):
                    *   Se llama a `registrar_intento_fallido()` con `contar_para_bloqueo_insistencia=True`.
                    *   Si `registrar_intento_fallido()` devuelve `True` (se aplicó un bloqueo): Transita a `SISTEMA_BLOQUEADO_UID`.
                    *   Si no se aplicó bloqueo: LED Rojo ON, transita a `ACCESO_DENEGADO_TEMPORAL`.
    *   **En `ACCESO_DENEGADO_TEMPORAL`:**
        *   Mantiene mensaje/LED por ~3 segundos.
        *   Si SP1 sigue activo, vuelve al inicio de la secuencia de validación del protocolo actual (ej: `ESPERANDO_VALIDACION_RFID` o `ESPERANDO_VALIDACION_QR` según el protocolo). Si no, a `REPOSO`.
    *   **En `SISTEMA_BLOQUEADO_UID`:**
        *   Muestra mensaje de UID bloqueado con tiempo restante.
        *   Si SP1 se libera o pasa un timeout largo (ej: 60s), vuelve a `REPOSO`.

4.  **Lógica de Seguridad Adicional:**
    *   **`intentos_fallidos_por_uid` (Diccionario):** Almacena `{"UID": {"contador": X, "nivel_bloqueo": Y, "desbloqueo_hasta": timestamp}}`.
        *   El contador se incrementa con cada fallo contado.
        *   Al alcanzar `MAX_INTENTOS_FALLIDOS_UID`, se aplica el bloqueo según `TIEMPO_BLOQUEO_UID_NIVEL` (progresivo), se actualiza `desbloqueo_hasta` y `nivel_bloqueo`, y se resetea el `contador` para ese nivel.
    *   **`accesos_recientes_uid` (Diccionario):** Almacena `{"UID": timestamp_ultimo_acceso_exitoso}`.

5.  **Manejo de Estado Diario y Reportes (`cargar_estado_diario`, `guardar_estado_diario`, etc.):**
    *   Al inicio (`cargar_estado_diario`):
        *   Lee `ARCHIVO_ESTADO_DIARIO` (JSON).
        *   Si es de hoy, carga `contador_accesos_hoy`, `eventos_acceso_hoy`, `intentos_fallidos_hoy`, `intentos_fallidos_por_uid`, `accesos_recientes_uid`. Filtra bloqueos/cooldowns expirados.
        *   Si es de un día anterior (o no existe), genera el reporte final para el día anterior (si había datos) y resetea todas las variables para el nuevo día.
        *   Establece `fecha_actual_para_conteo`.
    *   `guardar_estado_diario()`: Escribe el estado actual de todas estas variables en `ARCHIVO_ESTADO_DIARIO`. Se llama después de cada acceso/intento.
    *   `verificar_y_resetear_por_cambio_de_dia()`: Función auxiliar llamada al inicio de los registros de eventos para asegurar que se maneje el cambio de día si la app corre continuamente.
    *   `registrar_evento_acceso_exitoso()`: Incrementa contador, crea y añade evento a `eventos_acceso_hoy`, actualiza `accesos_recientes_uid`, resetea `intentos_fallidos_por_uid` para ese UID, guarda estado diario, actualiza GUI.
    *   `registrar_intento_fallido()`: Añade evento a `intentos_fallidos_hoy`, maneja la lógica de `intentos_fallidos_por_uid` (conteo y bloqueo), guarda estado diario, actualiza GUI.
    *   `generar_reporte_final_dia()`: Crea archivos `reporte_FECHA.json`, `reporte_accesos_exitosos_FECHA.csv`, y `reporte_intentos_fallidos_FECHA.csv` en la carpeta `reportes_acceso/`.
    *   **Al Cerrar Ventana:** Se llama a `verificar_y_resetear_por_cambio_de_dia()` y luego a `generar_reporte_final_dia()` para el día actual, asegurando que los últimos datos se guarden.

**Estado al Finalizar Fase 3.1 + 4:**
El sistema cuenta con una robusta validación RFID basada en una base de datos de usuarios con niveles y horarios. La gestión de usuarios (CRUD básico) es posible desde la GUI. Se implementan mecanismos de seguridad como cooldown y bloqueo por insistencia. El sistema registra detalladamente todos los accesos exitosos e intentos fallidos, persiste esta información diariamente, y es capaz de generar reportes completos en formatos JSON y CSV, tanto automáticamente al cambiar de día como bajo demanda. La GUI refleja el estado del sistema y los logs diarios.
