import tkinter as tk # Solo para el messagebox de error si la GUI no carga
from tkinter import messagebox
import threading
import time
import cv2 # Para cv2.destroyAllWindows() al final
import queue # <--- 1. Importar el módulo de colas

# --- Importar nuestros módulos ---
# Estos deben estar en la misma carpeta o en el PYTHONPATH
try:
    import gui_manager
    import arduino_comms
    import state_machine_logic
    import db_manager 
    import reporting_logging 
    import facial_recognition_utils 
    import constants # Si tienes constantes definidas allí
except ImportError as e:
    print(f"Error CRÍTICO: No se pudo importar un módulo necesario: {e}")
    print("Asegúrate de que todos los archivos .py del proyecto estén en la misma carpeta y no tengan errores de sintaxis.")
    try:
        root_error = tk.Tk()
        root_error.withdraw() 
        messagebox.showerror("Error de Importación de Módulo", 
                             f"No se pudo importar un módulo: {e}\n\n"
                             "Asegúrate de que todos los archivos del proyecto (.py) estén presentes y correctos.")
        root_error.destroy()
    except Exception:
        pass 
    exit()

# --- Referencia global a la instancia de la GUI (opcional, pero útil para algunos módulos) ---
# Se asignará después de crear la instancia de InterfazGrafica.
# Los módulos pueden importarlo si lo necesitan (con precaución para evitar circularidad excesiva).
# Por ejemplo, reporting_logging.py lo usa para messageboxes.
# state_machine_logic.py lo usa para actualizar mensajes en cambiar_estado.

app_gui_instancia_global = None

# ==============================================================================
# FUNCIÓN PRINCIPAL DE ORQUESTACIÓN
# ==============================================================================
def iniciar_aplicacion():
    global app_gui_instancia_global

    print("Iniciando Sistema de Control de Acceso Modularizado...")

    # 2. Crear la cola de comunicación para la UI
    ui_queue = queue.Queue()

    # 3. Modificar la creación de la GUI y los hilos para inyectar la cola
    app_gui_instancia_global = gui_manager.InterfazGrafica(ui_queue)
    
    # Inyectar la cola en los módulos que la usarán como productores de eventos
    state_machine_logic.asignar_cola_ui(ui_queue)
    arduino_comms.asignar_cola_ui(ui_queue)
    reporting_logging.asignar_cola_ui(ui_queue)
    
    # 4. Iniciar el bucle principal de la GUI
    if app_gui_instancia_global:
        try:
            print("Lanzando interfaz gráfica...")
            app_gui_instancia_global.mainloop()
        except Exception as e_gui:
            print(f"Error fatal en el bucle principal de la GUI: {e_gui}")
            import traceback
            traceback.print_exc()
        finally:
            print("Bucle principal de la GUI terminado.")
            # La lógica de cierre de hilos y recursos ahora está en al_cerrar_ventana de la GUI
            # y en el bloque finally de este if __name__ == "__main__" como doble seguro.

# ==============================================================================
# BLOQUE PRINCIPAL DE EJECUCIÓN
# ==============================================================================
if __name__ == "__main__":
    # --- Generación de Encodings (Solo ejecutar una vez o cuando se actualizan imágenes) ---
    # Descomentar la siguiente sección si necesitas generar/regenerar 'encodings_faciales.pkl'
    # Asegúrate de que la función 'crear_encodings_de_rostros_conocidos' esté definida
    # en 'facial_recognition_utils.py' y que tengas imágenes en 'rostros_conocidos/'.
    '''
    try:
        print("Intentando generar/actualizar encodings faciales...")
        # Asumimos que facial_recognition_utils tiene la función correcta
        if hasattr(facial_recognition_utils, 'crear_encodings_de_rostros_conocidos'):
            # Antes de llamar, podrías definir o importar USUARIOS_DE_PRUEBA_IMAGENES si esa función lo espera
            # facial_recognition_utils.USUARIOS_DE_PRUEBA_IMAGENES = {
            #     "Tu Nombre": "tu_foto.jpg", 
            #     # ... otros ...
            # }
            facial_recognition_utils.crear_encodings_de_rostros_conocidos() 
            print("--- Generación de encodings faciales completada (o no necesaria). ---")
        else:
            print("ADVERTENCIA: La función 'crear_encodings_de_rostros_conocidos' no está en facial_recognition_utils.py.")
        # input("Presiona Enter para continuar con la aplicación principal...") # Pausa opcional
    except Exception as e_enc:
        print(f"Error durante la generación de encodings: {e_enc}")
    '''

    try:
        iniciar_aplicacion()
    except KeyboardInterrupt:
        print("\nCierre solicitado por el usuario (Ctrl+C).")
    except Exception as e_main:
        print(f"Error fatal en la aplicación principal: {e_main}")
        import traceback
        traceback.print_exc()
    finally:
        print("Iniciando secuencia de cierre final del programa (desde main_app)...")
        
        # Los flags de los hilos deberían ser puestos a False por al_cerrar_ventana de la GUI
        # o por el método accion_conectar_desconectar si el usuario se desconecta.
        # Aquí es una salvaguarda.
        if hasattr(arduino_comms, 'hilo_listener_arduino_activo'):
            arduino_comms.hilo_listener_arduino_activo = False
        if hasattr(state_machine_logic, 'hilo_maquina_estados_activo'):
            state_machine_logic.hilo_maquina_estados_activo = False

        # Liberar cámara si aún estuviera activa (doble chequeo)
        if hasattr(state_machine_logic, 'cap_camara') and \
           state_machine_logic.cap_camara and state_machine_logic.cap_camara.isOpened():
            print("Liberando cámara facial (cierre final desde main_app)...")
            state_machine_logic.cap_camara.release()
        
        # Cerrar todas las ventanas de OpenCV
        try:
            cv2.destroyAllWindows() 
        except Exception as e_cv_destroy:
            print(f"Nota: Error menor al intentar cv2.destroyAllWindows(): {e_cv_destroy} (puede ser normal si no se usó OpenCV)")

        time.sleep(0.3) # Dar un pequeño tiempo a los hilos para que reaccionen a los flags

        if hasattr(arduino_comms, 'hilo_listener_arduino') and \
           arduino_comms.hilo_listener_arduino is not None and \
           arduino_comms.hilo_listener_arduino.is_alive():
            print("Esperando al hilo listener (desde main_app)...")
            arduino_comms.hilo_listener_arduino.join(timeout=1)
        
        if hasattr(state_machine_logic, 'hilo_maquina_estados') and \
           state_machine_logic.hilo_maquina_estados is not None and \
           state_machine_logic.hilo_maquina_estados.is_alive():
            print("Esperando al hilo de máquina de estados (desde main_app)...")
            state_machine_logic.hilo_maquina_estados.join(timeout=1)

        print("Programa terminado (desde main_app).")