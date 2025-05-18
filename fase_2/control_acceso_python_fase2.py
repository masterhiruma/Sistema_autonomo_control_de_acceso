import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time
import threading
from enum import Enum # Para definir los estados del sistema

# --- CONFIGURACIÓN ---
PUERTO_SERIAL_ARDUINO = '/dev/ttyUSB0' # <--- !!! VERIFICA Y MODIFICA ESTO SI ES NECESARIO !!!
VELOCIDAD_ARDUINO = 115200
TIMEOUT_SERIAL = 1

# --- CONSTANTES DEL SISTEMA (TIEMPOS EN SEGUNDOS) ---
UMBRAL_DETECCION_SP1_CM = 30.0
UMBRAL_DETECCION_SP2_CM = 30.0
TIEMPO_ESPERA_APERTURA_PUERTA_S = 2.0 # Tiempo para que SP1 se libere y SP2 detecte (simulado)
TIEMPO_MAX_SP2_ACTIVO_S = 5.0       # Tiempo máx con SP2 activo antes de cerrar
TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S = 10.0 # Tiempo máx total que la puerta puede estar abierta
TIEMPO_CIERRE_PUERTA_S = 1.0        # Simulación del tiempo que tarda la puerta en cerrarse físicamente

# --- ESTADOS DEL SISTEMA (usando Enum para claridad) ---
class EstadoSistema(Enum):
    REPOSO = "REPOSO"
    ESPERANDO_PERSONA_SP1 = "ESPERANDO_PERSONA_SP1" # Estado inicial o después de un ciclo
    # En futuras fases: ESPERANDO_VALIDACION
    ABRIENDO_PUERTA = "ABRIENDO_PUERTA"
    PERSONA_CRUZANDO = "PERSONA_CRUZANDO"
    CERRANDO_PUERTA = "CERRANDO_PUERTA"
    ALERTA_ERROR_CRUCE = "ALERTA_ERROR_CRUCE" # Estado temporal para manejar alerta SP1+SP2

# --- VARIABLES GLOBALES DEL ESTADO DEL HARDWARE ---
datos_hardware = {
    "sp1_distancia": 999.0,
    "sp2_distancia": 999.0,
    "s1_estado": 1,
    "s2_estado": 1,
    "e_estado": 1,
    "rfid_uid": "NADA"
}
lock_datos_hardware = threading.Lock()

# --- VARIABLES GLOBALES DE LA APLICACIÓN Y MÁQUINA DE ESTADOS ---
arduino_conectado = False
arduino_serial = None
hilo_listener_arduino_activo = True

estado_actual_sistema = EstadoSistema.ESPERANDO_PERSONA_SP1 # Estado inicial
puerta_logicamente_abierta = False

# Timers para la lógica de la puerta
tiempo_inicio_estado_actual_s = 0 # Cuándo se entró al estado actual
tiempo_sp1_detecto_s = 0          # Cuándo SP1 detectó por primera vez en un ciclo
tiempo_puerta_abrio_s = 0         # Cuándo se envió el comando de abrir puerta
tiempo_sp2_detecto_primera_vez_s = 0 # Cuándo SP2 detectó por primera vez tras abrir

# --- CLASE PARA LA INTERFAZ GRÁFICA (Modificada para mostrar estado) ---
class InterfazGrafica(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Control de Acceso - Fase 2")
        self.geometry("650x450") # Un poco más ancho para el estado

        self.protocol("WM_DELETE_WINDOW", self.al_cerrar_ventana)

        # --- Frame para el ESTADO DEL SISTEMA ---
        frame_estado_sistema = ttk.LabelFrame(self, text="Estado del Sistema")
        frame_estado_sistema.pack(padx=10, pady=5, fill="x")
        self.lbl_estado_sistema_valor = ttk.Label(frame_estado_sistema, text=estado_actual_sistema.value, font=("Arial", 12, "bold"))
        self.lbl_estado_sistema_valor.pack(pady=5)

        # --- Frames Principales (como antes) ---
        frame_estado_sensores = ttk.LabelFrame(self, text="Estado de Sensores e Interruptores")
        frame_estado_sensores.pack(padx=10, pady=5, fill="x")

        frame_control_manual = ttk.LabelFrame(self, text="Control Manual (Test)")
        frame_control_manual.pack(padx=10, pady=5, fill="x")
        
        self.labels_estado = {}
        nombres_labels = {
            "SP1 (cm):": "sp1_distancia",
            "SP2 (cm):": "sp2_distancia",
            "Interruptor S1 (0=LOW):": "s1_estado",
            "Interruptor S2 (0=LOW):": "s2_estado",
            "Interruptor Emergencia (0=ACTIVA):": "e_estado",
            "Último UID RFID:": "rfid_uid"
        }
        for i, (texto_label, clave_dato) in enumerate(nombres_labels.items()):
            lbl_texto = ttk.Label(frame_estado_sensores, text=texto_label)
            lbl_texto.grid(row=i, column=0, padx=5, pady=2, sticky="w")
            lbl_valor = ttk.Label(frame_estado_sensores, text="---", width=20)
            lbl_valor.grid(row=i, column=1, padx=5, pady=2, sticky="w")
            self.labels_estado[clave_dato] = lbl_valor
        
        ttk.Button(frame_control_manual, text="Abrir Puerta", command=lambda: enviar_comando_a_arduino("ABRIR_PUERTA")).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_control_manual, text="Cerrar Puerta", command=lambda: enviar_comando_a_arduino("CERRAR_PUERTA")).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_control_manual, text="LED Verde ON", command=lambda: enviar_comando_a_arduino("LED_VERDE_ON")).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_control_manual, text="LED Verde OFF", command=lambda: enviar_comando_a_arduino("LED_VERDE_OFF")).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_control_manual, text="LED Rojo ON", command=lambda: enviar_comando_a_arduino("LED_ROJO_ON")).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_control_manual, text="LED Rojo OFF", command=lambda: enviar_comando_a_arduino("LED_ROJO_OFF")).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_control_manual, text="Solicitar RFID", command=lambda: enviar_comando_a_arduino("SOLICITAR_LECTURA_RFID")).pack(side=tk.LEFT, padx=5)

        self.actualizar_gui_periodicamente()

    def actualizar_gui_periodicamente(self):
        with lock_datos_hardware:
            for clave_dato, label_widget in self.labels_estado.items():
                valor = datos_hardware.get(clave_dato, "Error")
                if isinstance(valor, float):
                    label_widget.config(text=f"{valor:.1f}")
                else:
                    label_widget.config(text=str(valor))
        
        self.lbl_estado_sistema_valor.config(text=estado_actual_sistema.value) # Actualizar estado del sistema
        self.after(200, self.actualizar_gui_periodicamente)

    def al_cerrar_ventana(self):
        print("Cerrando aplicación...")
        global hilo_listener_arduino_activo, hilo_maquina_estados_activo
        hilo_listener_arduino_activo = False
        hilo_maquina_estados_activo = False
        
        if arduino_serial and arduino_serial.is_open:
            arduino_serial.close()
            print("Puerto serial cerrado.")
        self.destroy()

# --- FUNCIONES DE COMUNICACIÓN CON ARDUINO (Sin cambios respecto a Fase 1) ---
def conectar_a_arduino():
    global arduino_serial, arduino_conectado
    try:
        arduino_serial = serial.Serial(PUERTO_SERIAL_ARDUINO, VELOCIDAD_ARDUINO, timeout=TIMEOUT_SERIAL)
        time.sleep(2)
        timeout_inicio = time.time()
        while time.time() - timeout_inicio < 10:
            if arduino_serial.in_waiting > 0:
                linea = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
                if linea == "ARDUINO_LISTO":
                    arduino_conectado = True
                    print("Arduino conectado y listo.")
                    return True
            time.sleep(0.1)
        print("Error: No se recibió ARDUINO_LISTO de Arduino.")
        arduino_serial.close()
        return False
    except serial.SerialException as e:
        print(f"Error al conectar con Arduino en {PUERTO_SERIAL_ARDUINO}: {e}")
        messagebox.showerror("Error de Conexión", f"No se pudo conectar a Arduino en {PUERTO_SERIAL_ARDUINO}.\nError: {e}")
        return False

def enviar_comando_a_arduino(comando_str):
    if arduino_conectado and arduino_serial and arduino_serial.is_open:
        try:
            mensaje_completo = f"COMANDO:{comando_str}\n"
            arduino_serial.write(mensaje_completo.encode('utf-8'))
            # print(f"PY->ARD: {mensaje_completo.strip()}") # Descomentar para depurar envíos
        except Exception as e:
            print(f"Error al enviar comando a Arduino: {e}")
    else:
        print("Error: Arduino no conectado. No se puede enviar comando.")

def escuchar_datos_arduino():
    global arduino_conectado, hilo_listener_arduino_activo
    print("Hilo listener de Arduino iniciado.")
    while hilo_listener_arduino_activo:
        if not arduino_conectado or not arduino_serial or not arduino_serial.is_open:
            print("Listener: Arduino no conectado. Intentando reconectar en 5s...")
            time.sleep(5)
            if hilo_listener_arduino_activo:
                 conectar_a_arduino()
            continue
        try:
            if arduino_serial.in_waiting > 0:
                linea_bytes = arduino_serial.readline()
                linea_str = linea_bytes.decode('utf-8', errors='ignore').strip()
                if linea_str and linea_str.startswith("DATOS;"):
                    partes = linea_str.split(';')
                    if len(partes) == 7:
                        with lock_datos_hardware:
                            try:
                                datos_hardware["sp1_distancia"] = float(partes[1].split(':')[1])
                                datos_hardware["sp2_distancia"] = float(partes[2].split(':')[1])
                                datos_hardware["s1_estado"] = int(partes[3].split(':')[1])
                                datos_hardware["s2_estado"] = int(partes[4].split(':')[1])
                                datos_hardware["e_estado"] = int(partes[5].split(':')[1])
                                rfid_leido = partes[6].split(':')[1]
                                if rfid_leido != "NADA":
                                    datos_hardware["rfid_uid"] = rfid_leido
                            except (ValueError, IndexError) as e:
                                print(f"Error de parseo: {e} -> Línea: {linea_str}")
        except serial.SerialException as se:
            print(f"Error Serial en listener: {se}")
            arduino_conectado = False
            if arduino_serial and arduino_serial.is_open:
                arduino_serial.close()
        except Exception as e:
            print(f"Error inesperado en listener_arduino: {e}")
            time.sleep(1)
        time.sleep(0.01)
    print("Hilo listener de Arduino terminado.")

# --- LÓGICA DE LA MÁQUINA DE ESTADOS ---
hilo_maquina_estados_activo = True

def cambiar_estado(nuevo_estado):
    global estado_actual_sistema, tiempo_inicio_estado_actual_s
    if estado_actual_sistema != nuevo_estado:
        print(f"Cambiando estado de {estado_actual_sistema.value} a {nuevo_estado.value}")
        estado_actual_sistema = nuevo_estado
        tiempo_inicio_estado_actual_s = time.time() # Registrar cuándo se entró al nuevo estado

def logica_maquina_estados():
    global puerta_logicamente_abierta, tiempo_sp1_detecto_s, tiempo_puerta_abrio_s, tiempo_sp2_detecto_primera_vez_s
    print("Hilo de Máquina de Estados iniciado.")

    while hilo_maquina_estados_activo:
        tiempo_actual_s = time.time()
        dist_sp1 = datos_hardware["sp1_distancia"] # Acceso seguro no es estrictamente necesario si solo leemos aquí
        dist_sp2 = datos_hardware["sp2_distancia"] # y el listener solo escribe. Pero con lock es más robusto.
                                                 # Por simplicidad en esta fase, accedemos directamente.
                                                 # En fases más complejas, usaríamos el lock.
        
        # --- LÓGICA PARA CADA ESTADO ---
        if estado_actual_sistema == EstadoSistema.ESPERANDO_PERSONA_SP1:
            enviar_comando_a_arduino("LED_VERDE_ON") # Indicar sistema listo
            enviar_comando_a_arduino("LED_ROJO_OFF")
            if puerta_logicamente_abierta: # Si por alguna razón quedó abierta
                print("Detectada puerta abierta en ESPERANDO_PERSONA_SP1, intentando cerrar.")
                cambiar_estado(EstadoSistema.CERRANDO_PUERTA)
                continue

            if 0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM:
                print(f"SP1 detectó persona ({dist_sp1:.1f} cm).")
                tiempo_sp1_detecto_s = tiempo_actual_s
                # Aquí, en el futuro, iría a un estado de VALIDACIÓN (RFID, QR, Facial)
                # Por ahora, asumimos validación exitosa y procedemos a abrir.
                cambiar_estado(EstadoSistema.ABRIENDO_PUERTA)

        elif estado_actual_sistema == EstadoSistema.ABRIENDO_PUERTA:
            enviar_comando_a_arduino("LED_VERDE_OFF") # Ocupado
            if not puerta_logicamente_abierta:
                print("Comando: Abrir Puerta")
                enviar_comando_a_arduino("ABRIR_PUERTA")
                puerta_logicamente_abierta = True
                tiempo_puerta_abrio_s = tiempo_actual_s
                tiempo_sp2_detecto_primera_vez_s = 0 # Resetear para este ciclo de apertura

            # Transición a PERSONA_CRUZANDO:
            # Condición 1: Si SP1 se libera Y SP2 detecta persona
            sp1_libre = not (0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM)
            sp2_detecta = (0 < dist_sp2 < UMBRAL_DETECCION_SP2_CM)

            if sp1_libre and sp2_detecta:
                print("SP1 libre y SP2 detectó. Persona cruzando.")
                tiempo_sp2_detecto_primera_vez_s = tiempo_actual_s
                cambiar_estado(EstadoSistema.PERSONA_CRUZANDO)
            # Condición 2: Si ha pasado un tiempo inicial de apertura y SP1 sigue activo (persona no se movió)
            # O si SP1 se liberó pero SP2 no detecta nada tras un tiempo.
            elif tiempo_actual_s - tiempo_puerta_abrio_s > TIEMPO_ESPERA_APERTURA_PUERTA_S:
                if not sp1_libre: # SP1 sigue obstruido
                     print(f"SP1 sigue obstruido tras {TIEMPO_ESPERA_APERTURA_PUERTA_S}s. Cerrando por seguridad.")
                     cambiar_estado(EstadoSistema.CERRANDO_PUERTA)
                else: # SP1 libre, pero SP2 no detectó
                    print(f"SP1 libre, SP2 no detectó tras {TIEMPO_ESPERA_APERTURA_PUERTA_S}s. Asumiendo cruce o error.")
                    # Aquí podríamos ir a CERRANDO_PUERTA o a PERSONA_CRUZANDO para el timeout general
                    cambiar_estado(EstadoSistema.PERSONA_CRUZANDO) # Dejamos que PERSONA_CRUZANDO maneje el timeout

            # Timeout general de puerta abierta
            if puerta_logicamente_abierta and (tiempo_actual_s - tiempo_puerta_abrio_s > TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S):
                print("Timeout máximo de puerta abierta alcanzado. Cerrando.")
                cambiar_estado(EstadoSistema.CERRANDO_PUERTA)


        elif estado_actual_sistema == EstadoSistema.PERSONA_CRUZANDO:
            sp1_detecta_ahora = (0 < dist_sp1 < UMBRAL_DETECCION_SP1_CM)
            sp2_detecta_ahora = (0 < dist_sp2 < UMBRAL_DETECCION_SP2_CM)

            # ALERTA: Intento de "tailgating" o error de sensor
            if sp1_detecta_ahora and sp2_detecta_ahora:
                print("ALERTA: SP1 y SP2 activos simultáneamente durante cruce!")
                enviar_comando_a_arduino("LED_ROJO_PARPADEAR_ALERTA") # Arduino parpadea 3 veces
                cambiar_estado(EstadoSistema.ALERTA_ERROR_CRUCE) # Estado para manejar la alerta
                continue

            if sp2_detecta_ahora and tiempo_sp2_detecto_primera_vez_s == 0:
                # Si SP2 se activa por primera vez en este estado (ej. vino de ABRIENDO_PUERTA sin que SP2 detectara)
                print("SP2 detectó durante PERSONA_CRUZANDO.")
                tiempo_sp2_detecto_primera_vez_s = tiempo_actual_s

            # Persona terminó de cruzar (SP2 se liberó)
            if not sp2_detecta_ahora and tiempo_sp2_detecto_primera_vez_s != 0:
                print("SP2 liberado. Persona ha cruzado. Cerrando puerta.")
                cambiar_estado(EstadoSistema.CERRANDO_PUERTA)
            
            # Timeout si SP2 permanece activo demasiado tiempo
            elif sp2_detecta_ahora and tiempo_sp2_detecto_primera_vez_s != 0 and \
                 (tiempo_actual_s - tiempo_sp2_detecto_primera_vez_s > TIEMPO_MAX_SP2_ACTIVO_S):
                print(f"SP2 activo por más de {TIEMPO_MAX_SP2_ACTIVO_S}s. Cerrando puerta.")
                cambiar_estado(EstadoSistema.CERRANDO_PUERTA)

            # Timeout general de puerta abierta
            if puerta_logicamente_abierta and (tiempo_actual_s - tiempo_puerta_abrio_s > TIEMPO_MAX_PUERTA_ABIERTA_TOTAL_S):
                print("Timeout máximo de puerta abierta (en PERSONA_CRUZANDO). Cerrando.")
                cambiar_estado(EstadoSistema.CERRANDO_PUERTA)
            
            # Si SP1 se vuelve a activar y SP2 está libre (persona regresa o nuevo intento)
            # Esto es más complejo, por ahora lo simplificamos. El tailgating ya se maneja.

        elif estado_actual_sistema == EstadoSistema.ALERTA_ERROR_CRUCE:
            # Este estado es para permitir que el parpadeo del LED termine.
            # Arduino maneja el parpadeo por 3 veces (aprox 1.5 segundos con intervalo de 250ms)
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > (TIEMPO_CIERRE_PUERTA_S + 1.5): # Dar tiempo al parpadeo
                print("Alerta SP1+SP2 manejada. Procediendo a cerrar puerta.")
                cambiar_estado(EstadoSistema.CERRANDO_PUERTA)


        elif estado_actual_sistema == EstadoSistema.CERRANDO_PUERTA:
            if puerta_logicamente_abierta:
                print("Comando: Cerrar Puerta")
                enviar_comando_a_arduino("CERRAR_PUERTA")
                puerta_logicamente_abierta = False
                # Aquí no encendemos LED verde, esperamos a que se cierre y vaya a ESPERANDO_PERSONA_SP1
            
            # Simular tiempo de cierre físico
            if tiempo_actual_s - tiempo_inicio_estado_actual_s > TIEMPO_CIERRE_PUERTA_S:
                print("Puerta cerrada (simulado). Volviendo a esperar persona.")
                cambiar_estado(EstadoSistema.ESPERANDO_PERSONA_SP1)
        
        # Aquí iría la lógica para el estado de EMERGENCIA en futuras fases

        time.sleep(0.1) # Ciclo de la máquina de estados cada 100ms

    print("Hilo de Máquina de Estados terminado.")


# --- FUNCIÓN PRINCIPAL ---
if __name__ == "__main__":
    if conectar_a_arduino():
        hilo_escucha = threading.Thread(target=escuchar_datos_arduino, daemon=True)
        hilo_escucha.start()

        # Iniciar el hilo de la máquina de estados
        hilo_estados = threading.Thread(target=logica_maquina_estados, daemon=True)
        hilo_estados.start()

        app = InterfazGrafica()
        app.mainloop()
        
        if hilo_escucha.is_alive():
             hilo_escucha.join(timeout=1)
        if hilo_estados.is_alive():
             hilo_estados.join(timeout=1)
    else:
        print("No se pudo iniciar la aplicación porque Arduino no está conectado.")