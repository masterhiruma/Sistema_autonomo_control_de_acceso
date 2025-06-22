import serial
import serial.tools.list_ports
import time
import threading
from tkinter import messagebox # Para mostrar errores de conexión si app_gui está disponible

import constants # Importar el módulo de constantes

# --- Variables Globales del Módulo ---
# Estas variables mantendrán el estado de la conexión y los datos del hardware.
# Otros módulos importarán estas variables o usarán funciones getter para acceder a ellas.

arduino_serial = None  # Objeto de la conexión serial
arduino_conectado = False # Flag del estado de la conexión
lock_datos_hardware = threading.Lock() # Lock para el acceso seguro al diccionario de datos

datos_hardware = {
    "sp1_distancia": 999.0,
    "sp2_distancia": 999.0,
    "s1_estado": 1,       # 1 = HIGH (no presionado), 0 = LOW (presionado)
    "s2_estado": 1,       # 1 = HIGH (no presionado), 0 = LOW (presionado)
    "e_estado": 1,        # 1 = HIGH (no emergencia), 0 = LOW (emergencia activa)
    "rfid_uid": "NADA",
    "ultimo_rfid_procesado_para_acceso": "NADA" # Usado por la máquina de estados
}

hilo_listener_arduino = None # Referencia al objeto Thread del listener
hilo_listener_arduino_activo = False # Flag para controlar el bucle del listener

# Referencia a la instancia de la GUI para mostrar mensajes (se asignará desde main_app o gui_manager)
# Esto es para evitar importaciones circulares directas si es posible,
# aunque para messagebox a veces es inevitable o se pasa como argumento.
# Por simplicidad, lo mantenemos global aquí y se asigna desde fuera.
app_gui_ref = None 

# --- Constantes del Módulo (ahora desde constants.py) ---
# VELOCIDAD_ARDUINO y TIMEOUT_SERIAL se obtienen de constants.py

def asignar_app_gui_referencia(gui_instance):
    """Permite que el módulo principal asigne la instancia de la GUI."""
    global app_gui_ref
    app_gui_ref = gui_instance

def conectar_a_arduino(puerto_seleccionado_str):
    """
    Intenta establecer la conexión serial con Arduino en el puerto especificado.
    Actualiza las variables globales arduino_serial y arduino_conectado.
    """
    global arduino_serial, arduino_conectado
    
    # Desconectar si ya hay una conexión (para reconectar)
    if arduino_conectado and arduino_serial and arduino_serial.is_open:
        print(f"Cerrando conexión existente en {arduino_serial.port} antes de reconectar.")
        arduino_serial.close()
        arduino_conectado = False
        time.sleep(0.5) # Pequeña pausa

    if not puerto_seleccionado_str or puerto_seleccionado_str == "No hay puertos":
        print("Error de conexión: Puerto no válido o no seleccionado.")
        if app_gui_ref: messagebox.showerror("Error Conexión", "Puerto no válido o no seleccionado.")
        return False
    try:
        print(f"Intentando conectar a Arduino en {puerto_seleccionado_str}...")
        arduino_serial = serial.Serial(puerto_seleccionado_str, constants.VELOCIDAD_ARDUINO, timeout=constants.TIMEOUT_SERIAL)
        time.sleep(2) # Esperar a que Arduino se reinicie y esté listo
        
        # Enviar un byte de "ping" o esperar "ARDUINO_LISTO"
        # arduino_serial.write(b'P') # Ejemplo de ping si Arduino lo espera
        timeout_inicio = time.time()
        arduino_listo_recibido = False
        buffer_entrada = ""

        while time.time() - timeout_inicio < 5: # Timeout de 5 segundos para ARDUINO_LISTO
            if arduino_serial.in_waiting > 0:
                try:
                    byte_leido = arduino_serial.read(1)
                    char_leido = byte_leido.decode('utf-8', errors='ignore')
                    buffer_entrada += char_leido
                    if "ARDUINO_LISTO" in buffer_entrada:
                        arduino_listo_recibido = True
                        break
                    if '\n' in buffer_entrada: # Limpiar buffer si no es ARDUINO_LISTO
                        buffer_entrada = buffer_entrada.split('\n', 1)[-1] 
                except Exception as e_decode:
                    print(f"Error decodificando respuesta inicial de Arduino: {e_decode}")
                    buffer_entrada = "" # Limpiar buffer en error
            time.sleep(0.05)

        if arduino_listo_recibido:
            arduino_conectado = True
            print(f"Arduino conectado y LISTO en {puerto_seleccionado_str}.")
            return True
        else:
            print(f"Error: No se recibió 'ARDUINO_LISTO' de Arduino en {puerto_seleccionado_str} dentro del timeout.")
            if arduino_serial and arduino_serial.is_open:
                arduino_serial.close()
            arduino_conectado = False
            if app_gui_ref: messagebox.showerror("Error Conexión", f"No se recibió 'ARDUINO_LISTO' de {puerto_seleccionado_str}.")
            return False

    except serial.SerialException as e:
        print(f"Error Serial al conectar a {puerto_seleccionado_str}: {e}")
        if app_gui_ref: messagebox.showerror("Error de Conexión", f"No se pudo conectar a {puerto_seleccionado_str}.\nVerifique el puerto y que Arduino esté conectado.\nError: {e}")
        arduino_conectado = False
        return False
    except Exception as e_gen:
        print(f"Error general inesperado al conectar a {puerto_seleccionado_str}: {e_gen}")
        if app_gui_ref: messagebox.showerror("Error de Conexión", f"Error inesperado al conectar a {puerto_seleccionado_str}.\nError: {e_gen}")
        arduino_conectado = False
        return False

def enviar_comando_a_arduino(comando_str):
    """Envía un comando formateado a Arduino si está conectado."""
    global arduino_conectado, arduino_serial
    if arduino_conectado and arduino_serial and arduino_serial.is_open:
        try:
            mensaje_completo = f"COMANDO:{comando_str}\n"
            arduino_serial.write(mensaje_completo.encode('utf-8'))
            # print(f"PY->ARD: {mensaje_completo.strip()}") # Descomentar para depurar
        except serial.SerialException as se:
            print(f"Error Serial al enviar comando '{comando_str}': {se}. Desconectando.")
            desconectar_arduino_emergencia() # Llamar a una función de desconexión de emergencia
        except Exception as e:
            print(f"Error al enviar comando '{comando_str}' a Arduino: {e}")
    # else:
        # print(f"Intento de enviar comando '{comando_str}' pero Arduino no está conectado.")

def escuchar_datos_arduino(): 
    """
    Bucle principal del hilo listener que lee y parsea datos de Arduino.
    Actualiza el diccionario global datos_hardware.
    """
    global arduino_conectado, hilo_listener_arduino_activo, datos_hardware, lock_datos_hardware, arduino_serial
    
    print("Hilo listener de Arduino iniciado.")
    buffer_parcial = "" # Para manejar líneas incompletas

    while hilo_listener_arduino_activo:
        if not arduino_conectado or not arduino_serial or not arduino_serial.is_open:
            # print("Listener: Arduino no conectado. Esperando conexión...") # Puede ser muy verboso
            time.sleep(0.5) # Esperar antes de reintentar chequear conexión
            continue # Volver al inicio del bucle while

        try:
            if arduino_serial.in_waiting > 0:
                # Leer todos los bytes disponibles para evitar llenar el buffer de entrada
                bytes_recibidos = arduino_serial.read(arduino_serial.in_waiting)
                lineas_recibidas_str = bytes_recibidos.decode('utf-8', errors='replace')
                
                # Procesar el buffer parcial más los nuevos datos
                datos_completos = buffer_parcial + lineas_recibidas_str
                lineas_a_procesar = datos_completos.split('\n')

                # El último elemento podría ser una línea incompleta, guardarla para el próximo ciclo
                buffer_parcial = lineas_a_procesar.pop() if not datos_completos.endswith('\n') else ""
                
                for linea_str in lineas_a_procesar:
                    linea_str = linea_str.strip() # Quitar \r si existe
                    if linea_str and linea_str.startswith("DATOS;"):
                        # print(f"ARD->PY (Línea procesada): {linea_str}") # Debug
                        partes = linea_str.split(';')
                        if len(partes) == 7: 
                            with lock_datos_hardware:
                                try:
                                    datos_hardware["sp1_distancia"] = float(partes[1].split(':')[1])
                                    datos_hardware["sp2_distancia"] = float(partes[2].split(':')[1])
                                    datos_hardware["s1_estado"] = int(partes[3].split(':')[1]) 
                                    datos_hardware["s2_estado"] = int(partes[4].split(':')[1]) 
                                    datos_hardware["e_estado"] = int(partes[5].split(':')[1])   
                                    # Solo actualizar rfid_uid si es diferente de NADA,
                                    # o si queremos que NADA limpie el valor anterior.
                                    # La lógica actual de la máquina de estados maneja "NADA".
                                    datos_hardware["rfid_uid"] = partes[6].split(':')[1] 
                                except (ValueError, IndexError) as e: 
                                    print(f"Error de parseo en datos de Arduino: {e} -> Línea: {linea_str}")
                        # else:
                            # print(f"Paquete de datos malformado (no 7 partes): {linea_str}")
                    # elif linea_str: # Otros mensajes de Arduino (ej: INFO)
                        # print(f"ARD->PY (Otro): {linea_str}")
            else:
                time.sleep(0.01) # Pequeña pausa si no hay datos para no consumir 100% CPU

        except serial.SerialException as se:
            print(f"Error SerialException en listener: {se}. Marcando como desconectado.")
            desconectar_arduino_emergencia()
        except IOError as ioe: # Podría ocurrir si el puerto se cierra abruptamente
             print(f"Error IOError en listener: {ioe}. Marcando como desconectado.")
             desconectar_arduino_emergencia()
        except Exception as e: 
            print(f"Error inesperado en listener_arduino: {e}")
            # Considerar si desconectar aquí también o solo loguear y continuar.
            # desconectar_arduino_emergencia() # Descomentar si se quiere desconectar ante cualquier error
            time.sleep(1) 
            
    print("Hilo listener de Arduino terminado.")

def desconectar_arduino_emergencia():
    """Función para manejar una desconexión inesperada."""
    global arduino_conectado, arduino_serial, hilo_maquina_estados_activo, app_gui_ref
    
    print("Iniciando desconexión de emergencia de Arduino...")
    if arduino_serial and arduino_serial.is_open:
        try:
            arduino_serial.close()
            print("Puerto serial cerrado por emergencia.")
        except Exception as e_close:
            print(f"Error al intentar cerrar puerto serial en desconexión de emergencia: {e_close}")
    
    arduino_conectado = False
    arduino_serial = None
    
    # Señalar a la máquina de estados para que se detenga si la conexión se pierde
    # Esto es importante para evitar que la máquina de estados siga corriendo sin datos.
    # La máquina de estados debería tener su propio chequeo de arduino_conectado.
    # hilo_maquina_estados_activo = False # Comentado, la máquina de estados debería pausarse si arduino_conectado es False

    if app_gui_ref and hasattr(app_gui_ref, 'lbl_estado_conexion') and hasattr(app_gui_ref, 'btn_conectar'):
        try:
            # Usar app_gui_ref.after para asegurar que se ejecuta en el hilo de la GUI
            app_gui_ref.after(0, lambda: app_gui_ref.lbl_estado_conexion.config(text="Error. Desconectado.", foreground="red"))
            app_gui_ref.after(0, lambda: app_gui_ref.btn_conectar.config(text="Conectar"))
            if hasattr(app_gui_ref, 'habilitar_deshabilitar_gui_por_conexion'):
                app_gui_ref.after(0, lambda: app_gui_ref.habilitar_deshabilitar_gui_por_conexion(False))
        except Exception as e_gui_update:
            print(f"Error actualizando GUI en desconexión de emergencia: {e_gui_update}")


def get_datos_hardware_copia():
    """Devuelve una copia segura del diccionario de datos_hardware."""
    with lock_datos_hardware:
        return datos_hardware.copy()

def is_arduino_conectado():
    """Devuelve el estado de la conexión con Arduino."""
    return arduino_conectado