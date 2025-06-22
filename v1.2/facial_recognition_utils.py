import face_recognition
# import pickle # Ya no se necesita aquí para cargar/guardar encodings
import os
import sqlite3 # Para buscar info de usuario por nombre al cargar encodings
# Necesitaremos acceso a algunas funciones de db_manager.py o definir stubs
# Por ahora, asumiremos que db_manager.py existe y podemos importar de él.
# Al inicio de facial_recognition_utils.py
try:
    import constants # <--- ASEGÚRATE QUE ESTÉ AQUÍ ARRIBA
except ImportError:
    print("ADVERTENCIA CRÍTICA: constants.py no encontrado en facial_recognition_utils.py.")
    # Definir un placeholder para que el script no crashee inmediatamente si constants falta
    class constants_stub:
        # ARCHIVO_ENCODINGS_FACIALES_PKL = "encodings_faciales_fallback.pkl" # Ya no se usa
        # ROSTROS_CONOCIDOS_DIR = "rostros_conocidos_fallback" # Ya no se usa
        pass # No se necesitan stubs para estas constantes si no se usan
    constants = constants_stub()
try:
    from db_manager import obtener_usuario_por_nombre_bd, obtener_todos_los_usuarios_con_encodings_faciales_bd 
except ImportError:
    print("ADVERTENCIA: No se pudo importar 'obtener_usuario_por_nombre_bd' o 'obtener_todos_los_usuarios_con_encodings_faciales_bd' desde db_manager.py para facial_recognition_utils.py.")
    def obtener_usuario_por_nombre_bd(nombre_completo): return None
    def obtener_todos_los_usuarios_con_encodings_faciales_bd(): return []

# --- Constantes del Módulo ---
# ROSTROS_CONOCIDOS_DIR se obtiene de constants.py (pero ya no se usará directamente para cargar)


# Define los usuarios de prueba y las rutas a sus imágenes
# CLAVE: El 'nombre' aquí debe coincidir con el 'nombre_completo' que tienes
# en tu base de datos SQLite si quieres que la validación RFID + Facial funcione
# encontrando el encoding correcto por nombre.
# USUARIOS_DE_PROBACION_IMAGENES = { # ELIMINADO
#     # Ejemplo:
#     # "Nikola Tesla": "rostro_nikola.jpg",    # Ej: rostro_nikola.jpg en la carpeta rostros_conocidos
#     # "Fabrizio Reyes": "rostro_fabrizio.jpg", # Ej: rostro_fabrizio.jpg
#     # Debes actualizar este diccionario con tus usuarios e imágenes reales
# }

# --- Variable Global del Módulo para Encodings Cargados ---
encodings_faciales_cargados_global = [] # Formato: [{"nombre": ..., "encoding_array": ..., ...otros datos de BD...}]
nombres_usuarios_cargados_global = [] # Nueva variable global para nombres (simplifica el acceso)
# USUARIOS_DE_PRUEBA_IMAGENES = { # ELIMINADO
#     "Fabrizio Reyes": "rostro_fabrizio.jpg", 
#     # "Nikola Tesla": "rostro_nikola.jpg", 
# }

# def crear_encodings_de_rostros_conocidos(directorio_imagenes=constants.ROSTROS_CONOCIDOS_DIR,  archivo_salida_pickle=constants.ARCHIVO_ENCODINGS_FACIALES_PKL): # ELIMINADO
#     """
#     Procesa imágenes en 'directorio_imagenes', extrae encodings faciales,
#     y los guarda en 'archivo_salida_pickle'.
#     El diccionario USUARIOS_DE_PRUEBA_IMAGENES mapea nombres de usuario a nombres de archivo de imagen.
#     """
# ... existing code ...
# def cargar_encodings_faciales_al_inicio(archivo_pickle=constants.ARCHIVO_ENCODINGS_FACIALES_PKL): # YA NO TOMA ARGUMENTO archivo_pickle
def cargar_encodings_faciales_al_inicio():
    global encodings_faciales_cargados_global, nombres_usuarios_cargados_global
    """
    Carga los encodings faciales directamente desde la base de datos.
    Puebla la variable global 'encodings_faciales_cargados_global' con la información completa del usuario.
    """
    print("Cargando encodings faciales desde la base de datos...")
    encodings_faciales_cargados_global = [] # Limpiar antes de cargar
    nombres_usuarios_cargados_global = [] # Limpiar también los nombres

    usuarios_con_encodings = obtener_todos_los_usuarios_con_encodings_faciales_bd()

    if usuarios_con_encodings:
        for usuario_info in usuarios_con_encodings:
            # Asumimos que usuario_info ya viene con 'facial_encoding_array' como un array NumPy
            if usuario_info.get("facial_encoding_array") is not None:
                encodings_faciales_cargados_global.append(usuario_info["facial_encoding_array"])
                nombres_usuarios_cargados_global.append(usuario_info.get("nombre", "Desconocido")) # Guardar nombres para referencia
        
        if encodings_faciales_cargados_global:
            print(f"--- Encodings faciales cargados desde la BD para {len(encodings_faciales_cargados_global)} perfiles. ---")
            # print(f"Nombres cargados: {nombres_usuarios_cargados_global}") # Descomentar para depurar nombres
        else:
            print("ADVERTENCIA: No se encontraron encodings faciales válidos en la base de datos.")
    else:
        print("ADVERTENCIA: No se encontraron usuarios con encodings faciales en la base de datos.")

# --- Bloque de prueba (opcional, para ejecutar este módulo directamente) ---
if __name__ == '__main__':
    print("Ejecutando facial_recognition_utils.py directamente...")
    
    # 1. Inicializar la BD (necesario para que obtener_usuario_por_nombre_bd funcione)
    # Se asume que db_manager.py ya maneja la inicialización al ser importado y usado
    # Si este script se ejecuta de forma totalmente autónoma, deberías importar db_manager
    # y llamar db_manager.inicializar_bd() aquí.
    # from db_manager import inicializar_bd, agregar_usuario_bd # Añadir estas importaciones para pruebas autónomas
    # if not os.path.exists(constants.NOMBRE_BD): # Necesitaría importar constants
    #     print(f"Base de datos '{constants.NOMBRE_BD}' no encontrada. Creando una de prueba.")
    #     inicializar_bd()
    #     # Ejemplo de añadir un usuario con encoding falso para probar la carga:
    #     # import numpy as np
    #     # datos_prueba = {"nombre": "Test User", "dni": "000TEST", "nivel": "Visitante", "area": "Test", "uid_rfid": "TESTRFID", "facial_encoding_array": np.random.rand(128).astype(np.float64)}
    #     # agregar_usuario_bd(datos_prueba)

    # 2. Probar la carga de los encodings desde la BD
    print("\n--- Intentando cargar encodings faciales desde la base de datos ---")
    cargar_encodings_faciales_al_inicio()
    
    if encodings_faciales_cargados_global:
        print("\nContenido de encodings_faciales_cargados_global (primeros 5):")
        for i, encoding in enumerate(encodings_faciales_cargados_global):
            if i >= 5: break
            print(f"  Encoding {i+1} (nombre: {nombres_usuarios_cargados_global[i]}): {encoding[:5]}...") # Muestra solo los primeros 5 elementos del array
    else:
        print("No se cargaron encodings para mostrar.")

    print("\nPruebas de facial_recognition_utils.py finalizadas.")