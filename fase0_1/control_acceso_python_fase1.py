import tkinter as tk
from tkinter import ttk, messagebox
import serial
import time
import threading

# --- CONFIGURACIÓN ---
# !!! CAMBIA 'COMX' por tu puerto serial correcto !!!
# Ejemplos: 'COM3' en Windows, '/dev/ttyUSB0' o '/dev/ttyACM0' en Linux/Mac
PUERTO_SERIAL_ARDUINO = '/dev/ttyUSB0' # <--- !!! MODIFICA ESTO !!!
VELOCIDAD_ARDUINO = 115200
TIMEOUT_SERIAL = 1

# Archivo de configuración (lo usaremos más adelante)
# ARCHIVO_CONFIG = "config_sistema.json"

# --- VARIABLES GLOBALES DEL ESTADO DEL HARDWARE (recibidas de Arduino) ---
datos_hardware = {
    "sp1_distancia": 999.0,
    "sp2_distancia": 999.0,
    "s1_estado": 1,  # 1 = HIGH (no presionado), 0 = LOW (presionado)
    "s2_estado": 1,  # 1 = HIGH (no presionado), 0 = LOW (presionado)
    "e_estado": 1,   # 1 = HIGH (no emergencia), 0 = LOW (emergencia)
    "rfid_uid": "NADA"
}
lock_datos_hardware = threading.Lock() # Para acceso seguro desde múltiples hilos

# --- VARIABLES GLOBALES DE LA APLICACIÓN ---
arduino_conectado = False
arduino_serial = None # Objeto Serial

# --- CLASE PARA LA INTERFAZ GRÁFICA ---
class InterfazGrafica(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Sistema de Control de Acceso - Fase 1")
        self.geometry("600x400")

        self.protocol("WM_DELETE_WINDOW", self.al_cerrar_ventana)

        # --- Frames Principales ---
        frame_estado_sensores = ttk.LabelFrame(self, text="Estado de Sensores e Interruptores")
        frame_estado_sensores.pack(padx=10, pady=10, fill="x")

        frame_control_manual = ttk.LabelFrame(self, text="Control Manual (Test)")
        frame_control_manual.pack(padx=10, pady=10, fill="x")

        # --- Labels para mostrar datos de Arduino (en frame_estado_sensores) ---
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
        
        # --- Botones de Control Manual (en frame_control_manual) ---
        ttk.Button(frame_control_manual, text="Abrir Puerta", command=lambda: enviar_comando_a_arduino("ABRIR_PUERTA")).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_control_manual, text="Cerrar Puerta", command=lambda: enviar_comando_a_arduino("CERRAR_PUERTA")).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(frame_control_manual, text="LED Verde ON", command=lambda: enviar_comando_a_arduino("LED_VERDE_ON")).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_control_manual, text="LED Verde OFF", command=lambda: enviar_comando_a_arduino("LED_VERDE_OFF")).pack(side=tk.LEFT, padx=5)

        ttk.Button(frame_control_manual, text="LED Rojo ON", command=lambda: enviar_comando_a_arduino("LED_ROJO_ON")).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_control_manual, text="LED Rojo OFF", command=lambda: enviar_comando_a_arduino("LED_ROJO_OFF")).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(frame_control_manual, text="Solicitar RFID", command=lambda: enviar_comando_a_arduino("SOLICITAR_LECTURA_RFID")).pack(side=tk.LEFT, padx=5)


        # Iniciar actualización periódica de la GUI
        self.actualizar_gui_periodicamente()

    def actualizar_gui_periodicamente(self):
        with lock_datos_hardware:
            for clave_dato, label_widget in self.labels_estado.items():
                valor = datos_hardware.get(clave_dato, "Error")
                if isinstance(valor, float):
                    label_widget.config(text=f"{valor:.1f}")
                else:
                    label_widget.config(text=str(valor))
        
        # Reprogramar esta función
        self.after(200, self.actualizar_gui_periodicamente) # Actualizar cada 200 ms

    def al_cerrar_ventana(self):
        print("Cerrando aplicación...")
        global hilo_listener_arduino_activo
        hilo_listener_arduino_activo = False # Señal para que el hilo termine
        
        if arduino_serial and arduino_serial.is_open:
            # Opcional: Enviar comandos de apagado a Arduino si es necesario
            # enviar_comando_a_arduino("LED_ROJO_OFF")
            # enviar_comando_a_arduino("LED_VERDE_OFF")
            arduino_serial.close()
            print("Puerto serial cerrado.")
        self.destroy()

# --- FUNCIONES DE COMUNICACIÓN CON ARDUINO ---
def conectar_a_arduino():
    global arduino_serial, arduino_conectado
    try:
        arduino_serial = serial.Serial(PUERTO_SERIAL_ARDUINO, VELOCIDAD_ARDUINO, timeout=TIMEOUT_SERIAL)
        time.sleep(2) # Esperar a que Arduino se reinicie tras la conexión

        # Esperar la señal ARDUINO_LISTO
        timeout_inicio = time.time()
        while time.time() - timeout_inicio < 10: # Esperar max 10s
            if arduino_serial.in_waiting > 0:
                linea = arduino_serial.readline().decode('utf-8', errors='ignore').strip()
                if linea == "ARDUINO_LISTO":
                    arduino_conectado = True
                    print("Arduino conectado y listo.")
                    return True
                # else: # Útil para depuración inicial
                    # print(f"Arduino dice (pre-listo): {linea}")
            time.sleep(0.1)
        
        print("Error: No se recibió ARDUINO_LISTO de Arduino en el tiempo esperado.")
        arduino_serial.close()
        return False

    except serial.SerialException as e:
        print(f"Error al conectar con Arduino en {PUERTO_SERIAL_ARDUINO}: {e}")
        messagebox.showerror("Error de Conexión", f"No se pudo conectar a Arduino en {PUERTO_SERIAL_ARDUINO}.\nVerifica el puerto y que Arduino esté conectado.\nError: {e}")
        return False

def enviar_comando_a_arduino(comando_str):
    if arduino_conectado and arduino_serial and arduino_serial.is_open:
        try:
            mensaje_completo = f"COMANDO:{comando_str}\n"
            arduino_serial.write(mensaje_completo.encode('utf-8'))
            print(f"PY->ARD: {mensaje_completo.strip()}")
        except Exception as e:
            print(f"Error al enviar comando a Arduino: {e}")
            # Considerar manejar la desconexión aquí
    else:
        print("Error: Arduino no conectado. No se puede enviar comando.")
        # messagebox.showwarning("Arduino Desconectado", "No se puede enviar el comando. Arduino no está conectado.")


hilo_listener_arduino_activo = True # Flag para controlar el bucle del hilo

def escuchar_datos_arduino():
    global arduino_conectado, hilo_listener_arduino_activo
    print("Hilo listener de Arduino iniciado.")
    
    while hilo_listener_arduino_activo:
        if not arduino_conectado or not arduino_serial or not arduino_serial.is_open:
            print("Listener: Arduino no conectado. Intentando reconectar en 5s...")
            time.sleep(5)
            if hilo_listener_arduino_activo: # Volver a chequear por si se cerró la app
                 conectar_a_arduino() # Intenta reconectar
            continue # Vuelve al inicio del bucle while

        try:
            if arduino_serial.in_waiting > 0:
                linea_bytes = arduino_serial.readline()
                linea_str = linea_bytes.decode('utf-8', errors='ignore').strip()

                if linea_str:
                    # print(f"ARD->PY: {linea_str}") # Descomentar para depuración RAW
                    if linea_str.startswith("DATOS;"):
                        partes = linea_str.split(';')
                        if len(partes) == 7: # DATOS + 6 campos
                            with lock_datos_hardware:
                                try:
                                    datos_hardware["sp1_distancia"] = float(partes[1].split(':')[1])
                                    datos_hardware["sp2_distancia"] = float(partes[2].split(':')[1])
                                    datos_hardware["s1_estado"] = int(partes[3].split(':')[1])
                                    datos_hardware["s2_estado"] = int(partes[4].split(':')[1])
                                    datos_hardware["e_estado"] = int(partes[5].split(':')[1])
                                    rfid_leido = partes[6].split(':')[1]
                                    if rfid_leido != "NADA": # Solo actualiza si es un UID real
                                        datos_hardware["rfid_uid"] = rfid_leido
                                    # Si es "NADA" y ya teníamos un UID, lo mantenemos en la GUI
                                    # hasta que llegue uno nuevo o lo resetemos explícitamente.
                                    # O podríamos ponerlo a "NADA" aquí si queremos que se limpie.
                                    # Por ahora, lo dejamos así.
                                except ValueError as ve:
                                    print(f"Error de Valor al parsear datos: {ve} -> Línea: {linea_str}")
                                except IndexError as ie:
                                    print(f"Error de Índice al parsear datos: {ie} -> Línea: {linea_str}")
                        else:
                            print(f"Paquete de datos malformado: {linea_str}")
                    # Aquí podríamos procesar otros tipos de mensajes de Arduino si los hubiera
        
        except serial.SerialException as se:
            print(f"Error Serial en listener (Arduino desconectado?): {se}")
            arduino_conectado = False # Marcar como desconectado
            if arduino_serial and arduino_serial.is_open:
                arduino_serial.close()
            # El bucle intentará reconectar
        except Exception as e:
            print(f"Error inesperado en listener_arduino: {e}")
            time.sleep(1) # Pequeña pausa ante errores desconocidos
        
        time.sleep(0.01) # Pequeña pausa para no consumir 100% CPU si no hay datos

    print("Hilo listener de Arduino terminado.")


# --- FUNCIÓN PRINCIPAL ---
if __name__ == "__main__":
    if conectar_a_arduino():
        # Iniciar el hilo que escucha a Arduino
        hilo_escucha = threading.Thread(target=escuchar_datos_arduino, daemon=True)
        hilo_escucha.start()

        # Crear y ejecutar la interfaz gráfica
        app = InterfazGrafica()
        app.mainloop()
        
        # Esperar a que el hilo de escucha termine si se cerró la ventana
        if hilo_escucha.is_alive():
             hilo_escucha.join(timeout=2) # Esperar un poco
    else:
        print("No se pudo iniciar la aplicación porque Arduino no está conectado.")
        # Podríamos mostrar un mensaje y salir, o permitir reintentar.
        # Por ahora, si no conecta al inicio, el programa principal no lanza la GUI.
        # Se podría modificar para que la GUI se lance y tenga un botón "Conectar".