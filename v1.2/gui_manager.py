import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import serial.tools.list_ports 
import threading # Para manejar referencias a hilos
import time # Para delays si es necesario
import re  # Agregando importación del módulo re
import cv2 # Importar OpenCV
import buscar_camaras # Importar el módulo para buscar cámaras
import datetime # Mover datetime a las importaciones superiores
from PIL import Image, ImageTk # Importar para manejar imágenes de OpenCV en Tkinter
from enum import Enum
import face_recognition # Para el reconocimiento facial
import numpy as np # Para promediar encodings
import facial_recognition_utils # <-- Agregado aquí para evitar NameError

# --- Importar nuestros módulos y constantes ---
try:
    import constants
    import arduino_comms 
    import state_machine_logic 
    import db_manager    
    import reporting_logging 
    import global_state # FIX: Importar el estado global
    # facial_recognition_utils no se importa directamente aquí, 
    # ya que la GUI no interactúa con sus funciones directamente en esta fase
except ImportError as e:
    print(f"Error CRÍTICO al importar módulos en gui_manager.py: {e}")
    # Definir stubs si es necesario para que el script al menos se analice
    # class constants: INDICE_CAMARA=0 # Placeholder - ELIMINADO
    class arduino_comms: 
        datos_hardware={"sp1_distancia":0,"sp2_distancia":0,"s1_estado":1,"s2_estado":1,"e_estado":1,"rfid_uid":"N/A"}
        lock_datos_hardware=threading.Lock(); arduino_conectado = False; hilo_listener_arduino=None; hilo_listener_arduino_activo=False
        enviar_comando_a_arduino=print; conectar_a_arduino=lambda p:False; escuchar_datos_arduino=print; get_datos_hardware_copia=lambda:arduino_comms.datos_hardware; is_arduino_conectado=lambda:False
    class state_machine_logic: 
        class EstadoSistema: REPOSO="S_REPOSO_STUB"
        estado_actual_sistema=EstadoSistema.REPOSO; protocolo_seleccionado_actual={"descripcion":"--"}; logica_maquina_estados=print; hilo_maquina_estados=None; hilo_maquina_estados_activo=False
    class db_manager: obtener_usuario_por_id_bd=lambda x:None;verificar_uid_existente_bd=lambda x,y=None:None;verificar_dni_existente_bd=lambda x,y=None:None;agregar_usuario_bd=lambda d:(False,"");actualizar_usuario_bd=lambda x,d:(False,"");obtener_todos_los_usuarios_bd=lambda:[];borrar_usuario_bd=lambda x:(False,"")
    class reporting_logging: contador_accesos_hoy=0;eventos_acceso_hoy=[];intentos_fallidos_hoy=[];fecha_actual_para_conteo="";verificar_y_resetear_por_cambio_de_dia=print;generar_reporte_final_dia=print
    print("ADVERTENCIA: GUI con funcionalidad limitada debido a errores de importación.")

# ==============================================================================
# CLASE INTERFAZ GRÁFICA 
# ==============================================================================
class InterfazGrafica(tk.Tk):
    def __init__(self):
        super().__init__()
        self.hilo_listener_ref = None # Referencia al objeto Thread
        self.hilo_estados_ref = None  # Referencia al objeto Thread

        self.uid_escaneado_para_formulario = tk.StringVar()
        self.modo_escaneo_rfid_para_registro = False 
        self.usuario_a_editar_id = None 
        self.title("Sistema de Control de Acceso Modularizado") 
        self.geometry("950x820") 
        self.protocol("WM_DELETE_WINDOW", self.al_cerrar_ventana)

        self.facial_encoding_para_guardar = None # Almacena el encoding capturado

        # Inicializar la base de datos al inicio
        try:
            db_manager.inicializar_bd()
            print("Base de datos inicializada correctamente.")
        except Exception as e:
            print(f"Error al inicializar base de datos: {e}")

        frame_conexion_principal = ttk.LabelFrame(self, text="Conexión Arduino")
        frame_conexion_principal.pack(padx=10, pady=5, fill="x")
        self.crear_widgets_conexion(frame_conexion_principal)

        self.notebook = ttk.Notebook(self)
        self.tab_principal = ttk.Frame(self.notebook)
        self.tab_gestion_usuarios = ttk.Frame(self.notebook)
        self.tab_reportes_diarios = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_principal, text='Panel Principal')
        self.notebook.add(self.tab_gestion_usuarios, text='Gestión de Usuarios')
        self.notebook.add(self.tab_reportes_diarios, text='Reportes Diarios')
        self.notebook.pack(expand=True, fill='both', padx=10, pady=(0,10))
        
        self.crear_widgets_tab_principal()
        self.crear_widgets_tab_gestion_usuarios()
        self.crear_widgets_tab_reportes_diarios()
        
        self.actualizar_gui_periodicamente()
        self.habilitar_deshabilitar_gui_por_conexion(False) 

    def crear_widgets_conexion(self, master_frame):
        ttk.Button(master_frame, text="Refrescar Puertos", command=self.refrescar_lista_puertos_action).grid(row=0, column=0, padx=5, pady=5)
        self.combo_puertos = ttk.Combobox(master_frame, state="readonly", width=20); self.combo_puertos.grid(row=0, column=1, padx=5, pady=5)
        self.btn_conectar = ttk.Button(master_frame, text="Conectar", width=15, command=self.accion_conectar_desconectar); self.btn_conectar.grid(row=0, column=2, padx=5, pady=5)
        self.lbl_estado_conexion = ttk.Label(master_frame, text="Estado: Desconectado", font=("Arial", 10, "bold")); self.lbl_estado_conexion.grid(row=0, column=3, padx=10, pady=5, sticky="w")
        master_frame.columnconfigure(3, weight=1); self.refrescar_lista_puertos_action() 

        # Controles para la cámara
        ttk.Label(master_frame, text="Índice de Cámara:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.combo_camaras = ttk.Combobox(master_frame, state="readonly", width=20)
        self.combo_camaras.grid(row=1, column=1, padx=5, pady=5)
        ttk.Button(master_frame, text="Detectar Cámaras", command=self.refrescar_lista_camaras_action).grid(row=1, column=2, padx=5, pady=5)
        ttk.Button(master_frame, text="Seleccionar Cámara", command=self.seleccionar_camara_action).grid(row=1, column=3, padx=5, pady=5)
        self.refrescar_lista_camaras_action()

    def crear_widgets_tab_principal(self):
        # Frame principal
        frame_principal = ttk.Frame(self.tab_principal)
        frame_principal.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Estado del sistema
        frame_estado = ttk.LabelFrame(frame_principal, text="Estado del Sistema", padding=10)
        frame_estado.pack(fill=tk.X, pady=5)

        # Grid para estados
        self.labels_estado_principal = {}
        estados = [
            ("Estado Actual:", "lbl_estado_sistema_valor"),
            ("Modo Validación:", "lbl_modo_validacion_actual"),
            ("Accesos Hoy:", "lbl_contador_accesos_hoy")
        ]

        for i, (texto, key) in enumerate(estados):
            ttk.Label(frame_estado, text=texto, font=("Arial", 10, "bold")).grid(row=i, column=0, sticky=tk.W, pady=2)
            self.labels_estado_principal[key] = ttk.Label(frame_estado, text="---", font=("Arial", 10))
            self.labels_estado_principal[key].grid(row=i, column=1, sticky=tk.W, pady=2)

        # Frame para mensajes de estado
        frame_mensajes = ttk.LabelFrame(frame_principal, text="Mensajes del Sistema", padding=10)
        frame_mensajes.pack(fill=tk.X, pady=5)

        # Label para mensajes de acceso con estilo mejorado
        self.lbl_mensaje_acceso = ttk.Label(
            frame_mensajes,
            text="",
            font=("Arial", 12, "bold"),
            wraplength=400,  # Ajustar según el ancho de la ventana
            justify=tk.CENTER
        )
        self.lbl_mensaje_acceso.pack(fill=tk.X, pady=5)

        # Frame para visualización de cámara
        frame_camara = ttk.LabelFrame(frame_principal, text="Visualización de Cámara", padding=10)
        frame_camara.pack(fill=tk.BOTH, expand=True, pady=5)

        self.lbl_camera_feed = ttk.Label(frame_camara, text="Cámara OFF")
        self.lbl_camera_feed.pack(fill=tk.BOTH, expand=True)

    def crear_widgets_tab_gestion_usuarios(self):
        self.frame_formulario_usuario = ttk.LabelFrame(self.tab_gestion_usuarios, text="Registrar/Editar Usuario"); self.frame_formulario_usuario.pack(padx=10, pady=10, fill="x")
        ttk.Label(self.frame_formulario_usuario, text="Nombre Completo:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.entry_nombre = ttk.Entry(self.frame_formulario_usuario, width=40); self.entry_nombre.grid(row=0, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_formulario_usuario, text="DNI:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.entry_dni = ttk.Entry(self.frame_formulario_usuario, width=40); self.entry_dni.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_formulario_usuario, text="Nivel de Usuario:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.combo_nivel = ttk.Combobox(self.frame_formulario_usuario, values=["Admin", "Trabajador", "Visitante"], state="readonly", width=38); self.combo_nivel.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew"); self.combo_nivel.current(0) 
        self.combo_nivel.bind("<<ComboboxSelected>>", self.actualizar_campos_horario_form)
        ttk.Label(self.frame_formulario_usuario, text="Área de Trabajo:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.entry_area = ttk.Entry(self.frame_formulario_usuario, width=40); self.entry_area.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        ttk.Label(self.frame_formulario_usuario, text="UID RFID:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.entry_uid_rfid_registro = ttk.Entry(self.frame_formulario_usuario, textvariable=self.uid_escaneado_para_formulario, width=30); self.entry_uid_rfid_registro.grid(row=4, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(self.frame_formulario_usuario, text="Escanear UID", command=self.iniciar_escaneo_rfid_para_formulario).grid(row=4, column=2, padx=5, pady=5, sticky="w")
        self.lbl_h_inicio = ttk.Label(self.frame_formulario_usuario, text="Horario Inicio (HH:MM):"); self.entry_h_inicio = ttk.Entry(self.frame_formulario_usuario, width=10)
        self.lbl_h_fin = ttk.Label(self.frame_formulario_usuario, text="Horario Fin (HH:MM):"); self.entry_h_fin = ttk.Entry(self.frame_formulario_usuario, width=10)
        self.lbl_h_inicio.grid(row=5, column=0, padx=5, pady=5, sticky="w"); self.entry_h_inicio.grid(row=5, column=1, padx=5, pady=5, sticky="w")
        self.lbl_h_fin.grid(row=6, column=0, padx=5, pady=5, sticky="w"); self.entry_h_fin.grid(row=6, column=1, padx=5, pady=5, sticky="w") 
        self.actualizar_campos_horario_form() 
        self.btn_guardar_usuario_form = ttk.Button(self.frame_formulario_usuario, text="Guardar Nuevo Usuario", command=self.accion_guardar_usuario_formulario); self.btn_guardar_usuario_form.grid(row=7, column=0, padx=5, pady=15, sticky="ew")
        self.btn_limpiar_form = ttk.Button(self.frame_formulario_usuario, text="Limpiar Formulario", command=self.limpiar_formulario_usuario); self.btn_limpiar_form.grid(row=7, column=1, padx=5, pady=15, sticky="ew")
        self.btn_cancelar_edicion = ttk.Button(self.frame_formulario_usuario, text="Cancelar Edición", command=self.cancelar_edicion_usuario, state=tk.DISABLED); self.btn_cancelar_edicion.grid(row=7, column=2, padx=5, pady=15, sticky="ew")
        
        # Nuevos widgets para captura facial
        ttk.Label(self.frame_formulario_usuario, text="Captura Facial:").grid(row=8, column=0, padx=5, pady=5, sticky="w")
        self.btn_capturar_rostro = ttk.Button(self.frame_formulario_usuario, text="Capturar Rostro", command=self.capturar_rostro_action)
        self.btn_capturar_rostro.grid(row=8, column=1, padx=5, pady=5, sticky="ew")
        self.lbl_estado_facial = ttk.Label(self.frame_formulario_usuario, text="No capturado", foreground="gray")
        self.lbl_estado_facial.grid(row=8, column=2, padx=5, pady=5, sticky="w")

        frame_lista_usuarios = ttk.LabelFrame(self.tab_gestion_usuarios, text="Lista de Usuarios Registrados"); frame_lista_usuarios.pack(padx=10, pady=10, fill="both", expand=True)
        cols_usuarios = ("id", "nombre", "dni", "nivel", "uid_rfid")
        self.tree_usuarios = ttk.Treeview(frame_lista_usuarios, columns=cols_usuarios, show="headings", selectmode="browse")
        for col in cols_usuarios:
            ancho = 100; 
            if col == "id": ancho = 40
            elif col == "nombre": ancho = 200
            elif col == "uid_rfid": ancho = 120
            self.tree_usuarios.heading(col, text=col.replace("_", " ").title()); self.tree_usuarios.column(col, width=ancho, anchor="w")
        scrollbar_tree = ttk.Scrollbar(frame_lista_usuarios, orient="vertical", command=self.tree_usuarios.yview); self.tree_usuarios.configure(yscrollcommand=scrollbar_tree.set)
        self.tree_usuarios.pack(side="left", fill="both", expand=True); scrollbar_tree.pack(side="right", fill="y")
        self.tree_usuarios.bind("<<TreeviewSelect>>", self.al_seleccionar_usuario_lista)
        frame_botones_lista = ttk.Frame(self.tab_gestion_usuarios); frame_botones_lista.pack(padx=10, pady=5, fill="x")
        ttk.Button(frame_botones_lista, text="Cargar/Actualizar Lista", command=self.cargar_usuarios_al_treeview).pack(side=tk.LEFT, padx=5)
        self.btn_editar_usuario_lista = ttk.Button(frame_botones_lista, text="Editar Seleccionado", command=self.accion_editar_usuario_lista, state=tk.DISABLED); self.btn_editar_usuario_lista.pack(side=tk.LEFT, padx=5)
        self.btn_borrar_usuario_lista = ttk.Button(frame_botones_lista, text="Borrar Seleccionado", command=self.accion_borrar_usuario_lista, state=tk.DISABLED); self.btn_borrar_usuario_lista.pack(side=tk.LEFT, padx=5)
        self.cargar_usuarios_al_treeview()

    def crear_widgets_tab_reportes_diarios(self):
        frame_contador_reporte = ttk.LabelFrame(self.tab_reportes_diarios, text="Resumen y Generación"); frame_contador_reporte.pack(padx=10, pady=10, fill="x")
        ttk.Label(frame_contador_reporte, text="Accesos Exitosos Hoy:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.lbl_contador_accesos_hoy = ttk.Label(frame_contador_reporte, text="0", font=("Arial", 12, "bold")); self.lbl_contador_accesos_hoy.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        ttk.Button(frame_contador_reporte, text="Generar Reporte CSV/JSON del Día Actual", command=self.generar_reporte_dia_actual_manual).grid(row=0, column=2, padx=20, pady=5)
        frame_visualizacion_logs = ttk.LabelFrame(self.tab_reportes_diarios, text="Logs del Día Actual"); frame_visualizacion_logs.pack(padx=10, pady=10, fill="both", expand=True)
        notebook_logs = ttk.Notebook(frame_visualizacion_logs)
        tab_exitosos = ttk.Frame(notebook_logs); cols_exitosos = ("timestamp_acceso", "nombre_usuario", "dni_usuario", "nivel_usuario", "area_trabajo", "uid_rfid_usado")
        self.tree_accesos_exitosos = ttk.Treeview(tab_exitosos, columns=cols_exitosos, show="headings")
        for col in cols_exitosos: 
            ancho = 120; 
            if col == "timestamp_acceso": ancho = 160
            elif col == "nombre_usuario": ancho = 150
            self.tree_accesos_exitosos.heading(col, text=col.replace("_", " ").title()); self.tree_accesos_exitosos.column(col, width=ancho, anchor="w")
        self.tree_accesos_exitosos.pack(fill="both", expand=True); notebook_logs.add(tab_exitosos, text="Accesos Exitosos")
        tab_fallidos = ttk.Frame(notebook_logs); cols_fallidos = ("timestamp_intento", "uid_rfid_presentado", "nombre_usuario_detectado", "dni_usuario_detectado", "motivo_fallo")
        self.tree_intentos_fallidos = ttk.Treeview(tab_fallidos, columns=cols_fallidos, show="headings")
        for col in cols_fallidos: 
            ancho = 150; 
            if col == "motivo_fallo": ancho = 250
            self.tree_intentos_fallidos.heading(col, text=col.replace("_", " ").title()); self.tree_intentos_fallidos.column(col, width=ancho, anchor="w")
        self.tree_intentos_fallidos.pack(fill="both", expand=True); notebook_logs.add(tab_fallidos, text="Intentos Fallidos")
        notebook_logs.pack(expand=True, fill='both', padx=5, pady=5)

    def actualizar_campos_horario_form(self, event=None):
        nivel_seleccionado = self.combo_nivel.get(); estado_horario = tk.NORMAL if nivel_seleccionado == "Trabajador" else tk.DISABLED
        self.entry_h_inicio.config(state=estado_horario); self.entry_h_fin.config(state=estado_horario)
        if estado_horario == tk.DISABLED: self.entry_h_inicio.delete(0, tk.END); self.entry_h_fin.delete(0, tk.END)

    def iniciar_escaneo_rfid_para_formulario(self):
        if not arduino_comms.arduino_conectado: 
            messagebox.showwarning("Desconectado", "Arduino no está conectado. Conéctese primero."); return
        
        self.uid_escaneado_para_formulario.set(""); self.modo_escaneo_rfid_para_registro = True 
        arduino_comms.enviar_comando_a_arduino("SOLICITAR_LECTURA_RFID")
        if hasattr(self, 'lbl_mensaje_acceso'): self.lbl_mensaje_acceso.config(text="Acerque la tarjeta RFID al lector para formulario...")
        messagebox.showinfo("Escanear RFID", "Acerque la tarjeta RFID al lector.\nEl UID aparecerá en el campo UID del formulario.")

    def _procesar_rfid_llegado_para_formulario(self, uid_recibido): # Este método usa variables de instancia y db_manager
        if not self.modo_escaneo_rfid_para_registro or uid_recibido == "NADA" or uid_recibido == self.uid_escaneado_para_formulario.get(): return
        excluir_id = self.usuario_a_editar_id if self.usuario_a_editar_id else None
        usuario_existente_con_uid = db_manager.verificar_uid_existente_bd(uid_recibido, excluir_id_usuario=excluir_id)
        decision_tomada_sobre_uid = False
        if usuario_existente_con_uid:
            respuesta = messagebox.askyesno("UID Existente",f"UID '{uid_recibido}' ya registrado para '{usuario_existente_con_uid}'.\n¿Usar este UID o escanear otro?")
            if respuesta: self.uid_escaneado_para_formulario.set(uid_recibido); messagebox.showinfo("UID Asignado", f"UID '{uid_recibido}' asignado."); decision_tomada_sobre_uid = True
            else: self.uid_escaneado_para_formulario.set(""); messagebox.showinfo("Escaneo Cancelado", "Campo UID limpiado."); decision_tomada_sobre_uid = True 
        else: self.uid_escaneado_para_formulario.set(uid_recibido); messagebox.showinfo("UID Capturado", f"UID '{uid_recibido}' capturado."); decision_tomada_sobre_uid = True
        if decision_tomada_sobre_uid: 
            self.modo_escaneo_rfid_para_registro = False 
            if hasattr(self, 'lbl_mensaje_acceso'): self.lbl_mensaje_acceso.config(text="") 

    def validar_formulario_usuario(self, datos, es_edicion=False): # Este método usa db_manager
        print(f"DEBUG: Validando formulario. Datos: {datos}")
        if not datos["nombre"] or not datos["dni"] or not datos["uid_rfid"]: 
            print("DEBUG: Error de validación: Campos obligatorios vacíos.")
            messagebox.showerror("Error Validación", "Nombre, DNI y UID RFID obligatorios."); return False
        
        valido_uid, msg_uid = self.validar_formato_uid(datos["uid_rfid"]); 
        if not valido_uid: 
            print(f"DEBUG: Error de validación: Formato UID inválido: {msg_uid}")
            messagebox.showerror("Error Validación", msg_uid); return False
        
        if not datos["dni"].isalnum() or len(datos["dni"]) < 5: 
            print("DEBUG: Error de validación: DNI inválido (no alfanumérico o muy corto).")
            messagebox.showerror("Error Validación", "DNI inválido."); return False
        
        if datos["nivel"] == "Trabajador":
            h_i, h_f = datos.get('h_inicio', ""), datos.get('h_fin', "")
            if not h_i or not h_f: 
                print("DEBUG: Error de validación: Horarios obligatorios para Trabajador vacíos.")
                messagebox.showerror("Error Validación", "Horarios obligatorios para Trabajador."); return False
            try: 
                datetime.datetime.strptime(h_i, "%H:%M"); datetime.datetime.strptime(h_f, "%H:%M")
            except ValueError: 
                print("DEBUG: Error de validación: Formato horario HH:MM incorrecto para Trabajador.")
                messagebox.showerror("Error Validación", "Formato horario HH:MM para Trabajador."); return False
        
        excluir_id = self.usuario_a_editar_id if es_edicion else None
        
        dni_owner = db_manager.verificar_dni_existente_bd(datos["dni"], excluir_id_usuario=excluir_id)
        if dni_owner: 
            print(f"DEBUG: Error de validación: DNI ya existe para '{dni_owner}'.")
            messagebox.showerror("Error Validación", f"DNI '{datos['dni']}' ya existe para '{dni_owner}'."); return False
        
        uid_owner = db_manager.verificar_uid_existente_bd(datos["uid_rfid"], excluir_id_usuario=excluir_id)
        if uid_owner: 
            print(f"DEBUG: Error de validación: UID ya existe para '{uid_owner}'.")
            messagebox.showerror("Error Validación", f"UID '{datos['uid_rfid']}' ya existe para '{uid_owner}'."); return False
        
        print("DEBUG: Formulario validado correctamente.")
        return True

    def accion_guardar_usuario_formulario(self): # Usa arduino_comms y db_manager
        print("DEBUG: Botón 'Guardar Nuevo Usuario' presionado.")
        if not arduino_comms.arduino_conectado: 
            print("DEBUG: Arduino no conectado. Mostrando advertencia.")
            messagebox.showwarning("Desconectado", "Arduino no está conectado."); return
        
        # Determinar qué encoding facial se debe guardar
        encoding_a_guardar = None
        if self.facial_encoding_para_guardar is not None:
            # Prioridad 1: Usar el nuevo rostro recién capturado.
            encoding_a_guardar = self.facial_encoding_para_guardar
            print("DEBUG: Usando nuevo encoding facial capturado.")
        elif self.usuario_a_editar_id:
            # Prioridad 2: Si no hay rostro nuevo y estamos editando, mantener el que ya existía.
            usuario_existente_data = db_manager.obtener_usuario_por_id_bd(self.usuario_a_editar_id)
            if usuario_existente_data and usuario_existente_data.get('facial_encoding_array') is not None:
                encoding_a_guardar = usuario_existente_data.get('facial_encoding_array')
                print("DEBUG: Manteniendo encoding facial existente del usuario.")

        datos_f = {
            "nombre": self.entry_nombre.get().strip(), 
            "dni": self.entry_dni.get().strip(), 
            "nivel": self.combo_nivel.get(), 
            "area": self.entry_area.get().strip(), 
            "uid_rfid": self.uid_escaneado_para_formulario.get().strip().upper(), 
            "h_inicio": self.entry_h_inicio.get().strip() if self.combo_nivel.get() == "Trabajador" else None, 
            "h_fin": self.entry_h_fin.get().strip() if self.combo_nivel.get() == "Trabajador" else None,
            "facial_encoding_array": encoding_a_guardar
        }
        
        if self.usuario_a_editar_id: 
            print(f"DEBUG: Modo Edición. ID de usuario: {self.usuario_a_editar_id}")
            
            if not self.validar_formulario_usuario(datos_f, es_edicion=True): 
                print("DEBUG: Fallo la validación del formulario en modo edición.")
                return
            
            exito, msg = db_manager.actualizar_usuario_bd(self.usuario_a_editar_id, datos_f)
            print(f"DEBUG: Resultado de actualizar usuario: Exito={exito}, Mensaje='{msg}'")
        else: 
            print("DEBUG: Modo Nuevo Usuario.")
            if not self.validar_formulario_usuario(datos_f, es_edicion=False): 
                print("DEBUG: Fallo la validación del formulario en modo nuevo usuario.")
                return
            
            exito, msg = db_manager.agregar_usuario_bd(datos_f)
            print(f"DEBUG: Resultado de agregar usuario: Exito={exito}, Mensaje='{msg}'")
        
        if exito: 
            print("DEBUG: Operación de guardado exitosa. Mostrando info y limpiando formulario.")
            messagebox.showinfo("Éxito", msg)
            self.limpiar_formulario_usuario()
            self.cargar_usuarios_al_treeview()
            # FIX: Recargar los encodings en memoria para que el reconocimiento facial funcione inmediatamente.
            print("Refrescando encodings faciales en memoria tras guardado...")
            if hasattr(facial_recognition_utils, 'cargar_encodings_faciales_al_inicio'):
                facial_recognition_utils.cargar_encodings_faciales_al_inicio()
        else: 
            print("DEBUG: Operación de guardado fallida. Mostrando error.")
            messagebox.showerror("Error al Guardar", msg)

    def limpiar_formulario_usuario(self):
        self.usuario_a_editar_id = None; self.frame_formulario_usuario.config(text="Registrar Nuevo Usuario"); self.btn_guardar_usuario_form.config(text="Guardar Nuevo Usuario"); self.btn_cancelar_edicion.config(state=tk.DISABLED)
        self.entry_nombre.delete(0, tk.END); self.entry_dni.delete(0, tk.END); self.entry_area.delete(0, tk.END); self.uid_escaneado_para_formulario.set("")
        self.combo_nivel.current(0); self.actualizar_campos_horario_form(); self.entry_nombre.focus()
        # Limpiar también el estado del rostro capturado
        self.facial_encoding_para_guardar = None
        if hasattr(self, 'lbl_estado_facial'):
            self.lbl_estado_facial.config(text="No capturado", foreground="gray")

    def cancelar_edicion_usuario(self): self.limpiar_formulario_usuario()

    def cargar_usuarios_al_treeview(self): # Usa db_manager
        for i in self.tree_usuarios.get_children(): self.tree_usuarios.delete(i)
        try:
            # Asegurar que la base de datos esté inicializada
            db_manager.inicializar_bd()
            for u in db_manager.obtener_todos_los_usuarios_bd(): self.tree_usuarios.insert("", "end", values=u)
        except Exception as e:
            print(f"Error al cargar usuarios: {e}")
            # Si hay error, mostrar mensaje en la GUI
            if hasattr(self, 'lbl_mensaje_acceso'):
                self.lbl_mensaje_acceso.config(text=f"Error al cargar usuarios: {e}", foreground="red")
        self.btn_editar_usuario_lista.config(state=tk.DISABLED); self.btn_borrar_usuario_lista.config(state=tk.DISABLED)

    def al_seleccionar_usuario_lista(self, event=None):
        st = tk.NORMAL if self.tree_usuarios.focus() else tk.DISABLED; self.btn_editar_usuario_lista.config(state=st); self.btn_borrar_usuario_lista.config(state=st)

    def accion_editar_usuario_lista(self): # Usa db_manager
        sel = self.tree_usuarios.focus();
        if not sel: messagebox.showwarning("Sin Selección", "Seleccione usuario a editar."); return
        id_u = self.tree_usuarios.item(sel)['values'][0]; datos_u = db_manager.obtener_usuario_por_id_bd(id_u) 
        if not datos_u: messagebox.showerror("Error", "No se cargaron datos para edición."); return
        self.limpiar_formulario_usuario(); self.usuario_a_editar_id = id_u; self.frame_formulario_usuario.config(text=f"Editando Usuario ID: {id_u}"); self.btn_guardar_usuario_form.config(text="Guardar Cambios"); self.btn_cancelar_edicion.config(state=tk.NORMAL)
        self.entry_nombre.insert(0, datos_u.get("nombre", "")); self.entry_dni.insert(0, datos_u.get("dni", "")); self.combo_nivel.set(datos_u.get("nivel", "Admin")); self.entry_area.insert(0, datos_u.get("area", ""))
        self.uid_escaneado_para_formulario.set(datos_u.get("uid_rfid", "")); self.actualizar_campos_horario_form()
        if datos_u.get("nivel") == "Trabajador": self.entry_h_inicio.insert(0, datos_u.get("h_inicio", "")); self.entry_h_fin.insert(0, datos_u.get("h_fin", ""))
        self.notebook.select(self.tab_gestion_usuarios); self.entry_nombre.focus()

    def accion_borrar_usuario_lista(self): # Usa db_manager
        sel = self.tree_usuarios.focus();
        if not sel: messagebox.showwarning("Sin Selección", "Seleccione usuario a borrar."); return
        item = self.tree_usuarios.item(sel); id_u, nom_u = item['values'][0], item['values'][1]
        if messagebox.askyesno("Confirmar Borrado", f"¿Borrar usuario:\nID: {id_u}\nNombre: {nom_u}?"):
            ex, msg = db_manager.borrar_usuario_bd(id_u); messagebox.showinfo("Resultado", msg) if ex else messagebox.showerror("Error", msg)
            if ex: self.cargar_usuarios_al_treeview()
    
    def actualizar_reportes_en_gui(self): # Usa reporting_logging
        if hasattr(self, 'lbl_contador_accesos_hoy'): self.lbl_contador_accesos_hoy.config(text=str(reporting_logging.contador_accesos_hoy))
        if hasattr(self, 'tree_accesos_exitosos'):
            for i in self.tree_accesos_exitosos.get_children(): self.tree_accesos_exitosos.delete(i)
            for ev in reporting_logging.eventos_acceso_hoy: vals = tuple(ev.get(c, "N/A") for c in self.tree_accesos_exitosos["columns"]); self.tree_accesos_exitosos.insert("", "end", values=vals)
        if hasattr(self, 'tree_intentos_fallidos'):
            for i in self.tree_intentos_fallidos.get_children(): self.tree_intentos_fallidos.delete(i)
            for ev in reporting_logging.intentos_fallidos_hoy: vals = tuple(ev.get(c, "N/A") for c in self.tree_intentos_fallidos["columns"]); self.tree_intentos_fallidos.insert("", "end", values=vals)

    def generar_reporte_dia_actual_manual(self): # Usa arduino_comms y reporting_logging
        if not arduino_comms.arduino_conectado: messagebox.showwarning("Desconectado", "Arduino no está conectado."); return
        reporting_logging.verificar_y_resetear_por_cambio_de_dia(); 
        reporting_logging.generar_reporte_final_dia(reporting_logging.fecha_actual_para_conteo, 
                                                    reporting_logging.contador_accesos_hoy, 
                                                    reporting_logging.eventos_acceso_hoy, 
                                                    reporting_logging.intentos_fallidos_hoy, bajo_demanda=True)

    def validar_formato_uid(self, uid_str): # Lógica local
        if len(uid_str) != 8: return False, "UID debe tener 8 caracteres."
        if not re.match(r"^[0-9a-fA-F]+$", uid_str): return False, "UID solo hexadecimales."
        return True, ""

    def refrescar_lista_puertos_action(self):
        puertos = [port.device for port in serial.tools.list_ports.comports()]
        self.combo_puertos['values'] = puertos
        if puertos:
            self.combo_puertos.current(0)
            if hasattr(self, 'btn_conectar'): self.btn_conectar.config(state=tk.NORMAL) 
        else:
            self.combo_puertos.set("No hay puertos")
            self.combo_puertos['values'] = []
            if hasattr(self, 'btn_conectar'): self.btn_conectar.config(state=tk.DISABLED)

    def accion_conectar_desconectar(self): # Usa arduino_comms y state_machine_logic
        if not arduino_comms.arduino_conectado:
            puerto_seleccionado = self.combo_puertos.get()
            if not puerto_seleccionado or puerto_seleccionado == "No hay puertos" or puerto_seleccionado == "":
                messagebox.showerror("Error", "No se ha seleccionado un puerto válido."); return
            self.lbl_estado_conexion.config(text=f"Conectando a {puerto_seleccionado}...", foreground="orange")
            self.update_idletasks()
            
            if arduino_comms.conectar_a_arduino(puerto_seleccionado): 
                self.lbl_estado_conexion.config(text=f"Conectado a {puerto_seleccionado}", foreground="green")
                self.btn_conectar.config(text="Desconectar")
                
                arduino_comms.hilo_listener_arduino_activo = True # Flag del módulo arduino_comms
                if arduino_comms.hilo_listener_arduino is None or not arduino_comms.hilo_listener_arduino.is_alive():
                    arduino_comms.hilo_listener_arduino = threading.Thread(target=arduino_comms.escuchar_datos_arduino, daemon=True)
                    self.hilo_listener_ref = arduino_comms.hilo_listener_arduino 
                    self.hilo_listener_ref.start()
                
                state_machine_logic.hilo_maquina_estados_activo = True # Flag del módulo state_machine_logic
                if state_machine_logic.hilo_maquina_estados is None or not state_machine_logic.hilo_maquina_estados.is_alive():
                    state_machine_logic.hilo_maquina_estados = threading.Thread(target=state_machine_logic.logica_maquina_estados, daemon=True)
                    self.hilo_estados_ref = state_machine_logic.hilo_maquina_estados 
                    self.hilo_estados_ref.start()
                
                self.habilitar_deshabilitar_gui_por_conexion(True)
            else:
                self.lbl_estado_conexion.config(text=f"Error al conectar", foreground="red")
        else: 
            print("Señalando a hilos para terminar por desconexión manual...")
            arduino_comms.hilo_listener_arduino_activo = False
            state_machine_logic.hilo_maquina_estados_activo = False
            
            if self.hilo_listener_ref and self.hilo_listener_ref.is_alive(): self.hilo_listener_ref.join(timeout=0.5)
            if self.hilo_estados_ref and self.hilo_estados_ref.is_alive(): self.hilo_estados_ref.join(timeout=0.5)
            
            if arduino_comms.arduino_serial and arduino_comms.arduino_serial.is_open: 
                arduino_comms.arduino_serial.close(); print("Puerto serial cerrado manualmente.")
            
            arduino_comms.arduino_conectado = False # Actualizar el estado en el módulo

            self.lbl_estado_conexion.config(text="Estado: Desconectado", foreground="black")
            self.btn_conectar.config(text="Conectar")
            self.habilitar_deshabilitar_gui_por_conexion(False)

    def habilitar_deshabilitar_gui_por_conexion(self, conectar):
        estado_widgets = tk.NORMAL if conectar else tk.DISABLED

        # FIX: Manejar estado de los controles de la cámara correctamente
        estado_camara_combo = "readonly" if conectar else tk.DISABLED
        if hasattr(self, 'combo_camaras'):
            self.combo_camaras.config(state=estado_camara_combo)
            if not conectar:
                self.combo_camaras.set("No hay cámaras")
        
        # Habilitar/deshabilitar los botones de la cámara
        if hasattr(self, 'combo_puertos'): # Usar un widget existente para encontrar el frame padre
            parent_frame = self.combo_puertos.master
            for widget in parent_frame.winfo_children():
                if isinstance(widget, ttk.Button):
                    if widget.cget("text") in ["Detectar Cámaras", "Seleccionar Cámara"]:
                        widget.config(state=estado_widgets)

        if hasattr(self, 'frame_formulario_usuario'):
            for child in self.frame_formulario_usuario.winfo_children():
                if isinstance(child, (ttk.Entry, ttk.Button, ttk.Combobox)):
                    if child == self.btn_cancelar_edicion: child.config(state=tk.NORMAL if conectar and self.usuario_a_editar_id else tk.DISABLED)
                    else: child.config(state=estado_widgets)
        if hasattr(self, 'tab_gestion_usuarios'):
            # Botones de la lista de usuarios
            frame_botones_lista = None
            for child in self.tab_gestion_usuarios.winfo_children():
                if isinstance(child, ttk.Frame) and child != self.frame_formulario_usuario:
                    frame_botones_lista = child; break
            if frame_botones_lista:
                for btn in frame_botones_lista.winfo_children():
                    if isinstance(btn, ttk.Button): btn.config(state=estado_widgets)

        if not conectar: 
             if hasattr(self, 'btn_editar_usuario_lista'): self.btn_editar_usuario_lista.config(state=tk.DISABLED)
             if hasattr(self, 'btn_borrar_usuario_lista'): self.btn_borrar_usuario_lista.config(state=tk.DISABLED)
        
        if hasattr(self, 'tab_reportes_diarios'): 
            frame_contador_reporte = None
            for child in self.tab_reportes_diarios.winfo_children():
                if isinstance(child, ttk.LabelFrame) and "Resumen y Generación" in child.cget("text"):
                    frame_contador_reporte = child; break
            if frame_contador_reporte:
                for sub_child in frame_contador_reporte.winfo_children():
                    if isinstance(sub_child, ttk.Button): 
                            sub_child.config(state=estado_widgets)
        
        if not conectar: 
            if hasattr(self, 'labels_estado_principal'):
                for label_widget in self.labels_estado_principal.values(): label_widget.config(text="---")
            if hasattr(self, 'lbl_estado_sistema_valor'): self.lbl_estado_sistema_valor.config(text="DESCONECTADO")
            if hasattr(self, 'lbl_modo_validacion_actual'): self.lbl_modo_validacion_actual.config(text="Modo Validación: ---")
            if hasattr(self, 'lbl_mensaje_acceso'): self.lbl_mensaje_acceso.config(text="")
            if hasattr(self, 'lbl_contador_accesos_hoy'): self.lbl_contador_accesos_hoy.config(text="---")
            if hasattr(self, 'tree_accesos_exitosos'):
                for i in self.tree_accesos_exitosos.get_children(): self.tree_accesos_exitosos.delete(i)
            if hasattr(self, 'tree_intentos_fallidos'):
                for i in self.tree_intentos_fallidos.get_children(): self.tree_intentos_fallidos.delete(i)
            
            # --- SE ELIMINA EL BLOQUE ANTIGUO Y REDUNDANTE DE LA CÁMARA DE AQUÍ ---
            # Ya se maneja correctamente al inicio de la función

    def actualizar_gui_periodicamente(self):
        # Actualizar con variables de arduino_comms y state_machine_logic
        if arduino_comms.arduino_conectado: 
            datos_hw_copia = arduino_comms.get_datos_hardware_copia()
            for clave_dato, label_widget in self.labels_estado_principal.items():
                valor = datos_hw_copia.get(clave_dato, "---")
                if clave_dato == "rfid_uid" and self.modo_escaneo_rfid_para_registro: 
                    if valor != "NADA" and valor != self.uid_escaneado_para_formulario.get(): 
                         self._procesar_rfid_llegado_para_formulario(valor) 
                elif isinstance(valor, float): label_widget.config(text=f"{valor:.1f}")
                else: label_widget.config(text=str(valor))
            
            if hasattr(self, 'lbl_estado_sistema_valor'): self.lbl_estado_sistema_valor.config(text=state_machine_logic.estado_actual_sistema.value)
            if hasattr(self, 'lbl_modo_validacion_actual'): self.lbl_modo_validacion_actual.config(text=f"Modo Validación: {state_machine_logic.protocolo_seleccionado_actual['descripcion']}")
        
        # Actualizar reportes siempre que la GUI esté visible y el módulo esté cargado
        if hasattr(reporting_logging, 'contador_accesos_hoy') and hasattr(self, 'actualizar_reportes_en_gui'):
             self.actualizar_reportes_en_gui()

        self.after(200, self.actualizar_gui_periodicamente)

    def al_cerrar_ventana(self):
        print("Cerrando aplicación..."); 
        if arduino_comms.arduino_conectado: self.accion_conectar_desconectar() 
        else: 
            if hasattr(arduino_comms, 'hilo_listener_arduino_activo'):
                arduino_comms.hilo_listener_arduino_activo = False
            if hasattr(state_machine_logic, 'hilo_maquina_estados_activo'):
                state_machine_logic.hilo_maquina_estados_activo = False

        if reporting_logging.fecha_actual_para_conteo: 
             print("Generando reporte final antes de salir...")
             reporting_logging.verificar_y_resetear_por_cambio_de_dia() 
             reporting_logging.generar_reporte_final_dia(reporting_logging.fecha_actual_para_conteo, 
                                       reporting_logging.contador_accesos_hoy, 
                                       reporting_logging.eventos_acceso_hoy, 
                                       reporting_logging.intentos_fallidos_hoy, bajo_demanda=False)
        self.destroy()

    def refrescar_lista_camaras_action(self):
        camaras_disponibles = buscar_camaras.listar_y_probar_camaras_sin_gui()
        if camaras_disponibles:
            self.combo_camaras['values'] = camaras_disponibles
            self.combo_camaras.set(camaras_disponibles[0]) # Seleccionar la primera por defecto
            messagebox.showinfo("Cámaras Detectadas", f"Se encontraron las siguientes cámaras: {camaras_disponibles}")
        else:
            self.combo_camaras.set("No hay cámaras")
            self.combo_camaras['values'] = []
            messagebox.showwarning("Cámaras", "No se encontraron cámaras activas.")

    def seleccionar_camara_action(self):
        indice_seleccionado = self.combo_camaras.get()
        if indice_seleccionado and indice_seleccionado.isdigit():
            try:
                indice = int(indice_seleccionado)
                constants.guardar_configuracion({"INDICE_CAMARA": indice})
                constants.INDICE_CAMARA = indice # Actualizar la constante en memoria para efecto inmediato
                messagebox.showinfo("Configuración de Cámara", f"Índice de cámara configurado a: {indice}")
            except ValueError:
                messagebox.showerror("Error", "Índice de cámara inválido.")
        else:
            messagebox.showwarning("Selección de Cámara", "Por favor, selecciona un índice de cámara válido.")

    def mostrar_frame_camara(self, frame_np):
        # Redimensionar el frame para que encaje en el Label si es necesario
        # Obtener el tamaño actual del label para escalado dinámico
        lbl_width = self.lbl_camera_feed.winfo_width()
        lbl_height = self.lbl_camera_feed.winfo_height()

        if lbl_width == 1 and lbl_height == 1: # Valor por defecto antes de que el widget tenga tamaño real
            lbl_width = 640 # Tamaño por defecto
            lbl_height = 480

        # Mantener la relación de aspecto
        (h, w) = frame_np.shape[:2]
        if lbl_width / w < lbl_height / h:
            scale = lbl_width / w
        else:
            scale = lbl_height / h
        
        new_width, new_height = int(w * scale), int(h * scale)
        resized_frame = cv2.resize(frame_np, (new_width, new_height), interpolation=cv2.INTER_AREA)

        # Convertir el frame de OpenCV a un formato compatible con Tkinter
        img = Image.fromarray(resized_frame)
        imgtk = ImageTk.PhotoImage(image=img)
        self.lbl_camera_feed.imgtk = imgtk  # Mantener una referencia para evitar que sea recolectada por el GC
        self.lbl_camera_feed.config(image=imgtk)

    def actualizar_mensaje(self, mensaje, color=None):
        """Actualiza el mensaje en la GUI con el color especificado"""
        if not hasattr(self, 'lbl_mensaje_acceso'):
            return

        # Colores predefinidos
        colores = {
            'error': '#FF0000',      # Rojo para errores
            'exito': '#00AA00',      # Verde para éxito
            'advertencia': '#FFA500', # Naranja para advertencias
            'info': '#0000FF',       # Azul para información
            'espera': '#FFD700'      # Amarillo para espera
        }

        # Determinar el color basado en el mensaje si no se especifica
        if color is None:
            mensaje_lower = mensaje.lower()
            if any(palabra in mensaje_lower for palabra in ['error', 'denegado', 'bloqueado', 'fallido']):
                color = colores['error']
            elif any(palabra in mensaje_lower for palabra in ['concedido', 'exitoso', 'bienvenido']):
                color = colores['exito']
            elif any(palabra in mensaje_lower for palabra in ['esperando', 'procesando', 'validando']):
                color = colores['espera']
            elif any(palabra in mensaje_lower for palabra in ['advertencia', 'atención']):
                color = colores['advertencia']
            else:
                color = colores['info']

        # Actualizar el mensaje y el color
        self.lbl_mensaje_acceso.configure(text=mensaje, foreground=color)

        # Programar la limpieza del mensaje después de 5 segundos si es un mensaje de éxito
        if color == colores['exito']:
            self.after(5000, lambda: self.lbl_mensaje_acceso.configure(text="", foreground=colores['info']))

    def capturar_rostro_action(self):
        """Acción para el botón Capturar Rostro. Abre una ventana para la captura y procesamiento."""
        if not arduino_comms.arduino_conectado:
            messagebox.showwarning("Cámara Desconectada", "El sistema de Arduino debe estar conectado para utilizar la cámara.")
            return
        
        self.captura_facial_activa = True
        self.encodings_capturados_temp = []
        self.capturas_exitosas_count = 0
        self.ventana_captura = tk.Toplevel(self)
        self.ventana_captura.title("Captura de Rostro")
        self.ventana_captura.geometry("600x550")
        self.ventana_captura.protocol("WM_DELETE_WINDOW", self._cerrar_ventana_captura_facial)
        
        lbl_instruccion = ttk.Label(self.ventana_captura, text="Por favor, mire directamente a la cámara. Se tomarán 3 capturas.", font=("Arial", 10, "bold"))
        lbl_instruccion.pack(pady=10)

        self.lbl_video_captura = ttk.Label(self.ventana_captura)
        self.lbl_video_captura.pack(expand=True, fill="both")
        
        self.lbl_estado_captura = ttk.Label(self.ventana_captura, text="Inicializando cámara...", font=("Arial", 11, "italic"), foreground="blue")
        self.lbl_estado_captura.pack(pady=5)
        
        btn_cancelar = ttk.Button(self.ventana_captura, text="Cancelar Captura", command=self._cerrar_ventana_captura_facial)
        btn_cancelar.pack(pady=10)

        self.cap_facial_temp = cv2.VideoCapture(constants.INDICE_CAMARA, cv2.CAP_DSHOW)
        if not self.cap_facial_temp.isOpened():
            messagebox.showerror("Error de Cámara", f"No se pudo abrir la cámara con índice {constants.INDICE_CAMARA}. Verifique la conexión o el índice en configuración.")
            self._cerrar_ventana_captura_facial()
            return
        
        self.lbl_estado_captura.config(text="Cámara lista. Buscando rostro...", foreground="orange")
        self._actualizar_captura_facial()

    def _actualizar_captura_facial(self):
        if not self.captura_facial_activa or not self.cap_facial_temp.isOpened():
            return

        ret, frame = self.cap_facial_temp.read()
        if not ret:
            self.lbl_estado_captura.config(text="Error al leer de la cámara.", foreground="red")
            self.after(50, self._actualizar_captura_facial) # Intentar de nuevo
            return
        
        # Convertir a RGB (face_recognition usa RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        # Reducir tamaño para un procesamiento más rápido
        small_frame = cv2.resize(rgb_frame, (0, 0), fx=constants.FACTOR_REDUCCION_FRAME_FACIAL, fy=constants.FACTOR_REDUCCION_FRAME_FACIAL)
        
        face_locations = face_recognition.face_locations(small_frame, model="hog") # O "cnn" para más precisión
        face_encodings = face_recognition.face_encodings(small_frame, face_locations)

        if face_locations and face_encodings:
            if self.capturas_exitosas_count < 3: # Número de capturas a tomar
                # Dibujar un recuadro verde en el rostro detectado
                for (top, right, bottom, left) in face_locations:
                    top *= int(1/constants.FACTOR_REDUCCION_FRAME_FACIAL)
                    right *= int(1/constants.FACTOR_REDUCCION_FRAME_FACIAL)
                    bottom *= int(1/constants.FACTOR_REDUCCION_FRAME_FACIAL)
                    left *= int(1/constants.FACTOR_REDUCCION_FRAME_FACIAL)
                    cv2.rectangle(frame, (left, top), (right, bottom), (0, 255, 0), 2)
                
                self.encodings_capturados_temp.append(face_encodings[0]) # Tomar el primer encoding
                self.capturas_exitosas_count += 1
                self.lbl_estado_captura.config(text=f"Rostro detectado! Captura {self.capturas_exitosas_count}/3...", foreground="green")
                print(f"Captura facial: {self.capturas_exitosas_count}/3")
                time.sleep(0.5) # Pequeña pausa para evitar capturas muy seguidas
            
            if self.capturas_exitosas_count >= 3:
                # Ya se tomaron suficientes capturas, procesar y cerrar
                self.lbl_estado_captura.config(text="Procesando encodings...", foreground="blue")
                print("Capturas completas. Procesando encodings.")
                self._finalizar_captura_facial()
                return
        else:
            self.lbl_estado_captura.config(text="No se detecta rostro. Asegúrese de estar centrado y bien iluminado.", foreground="orange")
        
        # Mostrar el frame en la ventana de captura
        img_tk = ImageTk.PhotoImage(image=Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        self.lbl_video_captura.imgtk = img_tk
        self.lbl_video_captura.config(image=img_tk)

        self.after(20, self._actualizar_captura_facial) # Continuar el bucle de la cámara

    def _finalizar_captura_facial(self):
        if self.encodings_capturados_temp:
            # Calcular el encoding promedio para mayor robustez
            self.facial_encoding_para_guardar = np.mean(self.encodings_capturados_temp, axis=0)
            self.lbl_estado_facial.config(text="Rostro Capturado (Listo para Guardar)", foreground="green")
            messagebox.showinfo("Captura Facial", "Rostro capturado y encoding generado con éxito.")
        else:
            self.facial_encoding_para_guardar = None
            self.lbl_estado_facial.config(text="Fallo la captura de rostro.", foreground="red")
            messagebox.showwarning("Captura Facial", "No se pudo capturar un rostro válido.")
        
        self._cerrar_ventana_captura_facial()
        
    def _cerrar_ventana_captura_facial(self):
        self.captura_facial_activa = False
        if self.cap_facial_temp and self.cap_facial_temp.isOpened():
            self.cap_facial_temp.release()
        if hasattr(self, 'ventana_captura') and self.ventana_captura.winfo_exists():
            self.ventana_captura.destroy()
        print("Ventana de captura facial cerrada.")