import face_recognition
import pickle
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
    # pero esto es una solución temporal, el problema de importación debe arreglarse.
    class constants_stub:
        ARCHIVO_ENCODINGS_FACIALES_PKL = "encodings_faciales_fallback.pkl"
        ROSTROS_CONOCIDOS_DIR = "rostros_conocidos_fallback"
    constants = constants_stub()
try:
    from db_manager import obtener_usuario_por_nombre_bd 
except ImportError:
    print("ADVERTENCIA: No se pudo importar 'obtener_usuario_por_nombre_bd' desde db_manager.py para facial_recognition_utils.py.")
    def obtener_usuario_por_nombre_bd(nombre_completo): return None

# --- Constantes del Módulo ---
ROSTROS_CONOCIDOS_DIR = "rostros_conocidos" 


# Define los usuarios de prueba y las rutas a sus imágenes
# CLAVE: El 'nombre' aquí debe coincidir con el 'nombre_completo' que tienes
# en tu base de datos SQLite si quieres que la validación RFID + Facial funcione
# encontrando el encoding correcto por nombre.
USUARIOS_DE_PRUEBA_IMAGENES = {
    # Ejemplo:
    # "Nikola Tesla": "rostro_nikola.jpg",    # Ej: rostro_nikola.jpg en la carpeta rostros_conocidos
    # "Fabrizio Reyes": "rostro_fabrizio.jpg", # Ej: rostro_fabrizio.jpg
    # Debes actualizar este diccionario con tus usuarios e imágenes reales
}

# --- Variable Global del Módulo para Encodings Cargados ---
encodings_faciales_cargados_global = [] # Formato: [{"nombre": ..., "encoding_array": ..., ...otros datos de BD...}]
USUARIOS_DE_PRUEBA_IMAGENES = {
    "Fabrizio Reyes": "rostro_fabrizio.jpg", 
    # "Nikola Tesla": "rostro_nikola.jpg", 
}

def crear_encodings_de_rostros_conocidos(directorio_imagenes=constants.ROSTROS_CONOCIDOS_DIR,  archivo_salida_pickle=constants.ARCHIVO_ENCODINGS_FACIALES_PKL):
    """
    Procesa imágenes en 'directorio_imagenes', extrae encodings faciales,
    y los guarda en 'archivo_salida_pickle'.
    El diccionario USUARIOS_DE_PRUEBA_IMAGENES mapea nombres de usuario a nombres de archivo de imagen.
    """
    print(f"Generando encodings faciales desde la carpeta: '{os.path.abspath(directorio_imagenes)}'")
    if not os.path.exists(directorio_imagenes):
        try:
            os.makedirs(directorio_imagenes)
            print(f"ADVERTENCIA: Carpeta '{directorio_imagenes}' no existía y ha sido creada.")
            print("Por favor, añade imágenes de rostros allí (ej: nombre_usuario.jpg) y configura 'USUARIOS_DE_PRUEBA_IMAGENES'.")
            print("Luego, vuelve a ejecutar este script o la función de generación.")
            return False # Indicar que no se hizo nada
        except OSError as e:
            print(f"Error creando directorio '{directorio_imagenes}': {e}")
            return False


    encodings_para_guardar_en_pickle = [] # Lista de {"nombre": nombre, "encoding": array_numpy}

    if not USUARIOS_DE_PRUEBA_IMAGENES:
        print(f"ADVERTENCIA: El diccionario 'USUARIOS_DE_PRUEBA_IMAGENES' está vacío en 'facial_recognition_utils.py'.")
        print(f"             No se generarán encodings. Edita este diccionario con tus usuarios e imágenes.")
        return False

    for nombre_usuario, nombre_archivo_imagen in USUARIOS_DE_PRUEBA_IMAGENES.items():
        ruta_completa_imagen = os.path.join(directorio_imagenes, nombre_archivo_imagen)
        if not os.path.exists(ruta_completa_imagen):
            print(f"ADVERTENCIA: Imagen no encontrada para '{nombre_usuario}' en '{ruta_completa_imagen}'. Saltando.")
            continue
        try:
            print(f"Procesando imagen para '{nombre_usuario}': {ruta_completa_imagen}")
            imagen_cargada = face_recognition.load_image_file(ruta_completa_imagen)
            lista_encodings_rostro_en_imagen = face_recognition.face_encodings(imagen_cargada) 

            if lista_encodings_rostro_en_imagen:
                encoding_rostro_numpy = lista_encodings_rostro_en_imagen[0] # Tomar el primer rostro
                encodings_para_guardar_en_pickle.append({
                    "nombre": nombre_usuario, 
                    "encoding": encoding_rostro_numpy # Guardamos el array NumPy directamente
                })
                print(f"   Encoding generado para: {nombre_usuario}")
            else:
                print(f"ADVERTENCIA: No se detectaron rostros en la imagen de '{nombre_usuario}' ({ruta_completa_imagen}).")
        except Exception as e:
            print(f"Error procesando imagen para '{nombre_usuario}': {e}")

    if encodings_para_guardar_en_pickle:
        try:
            with open(archivo_salida_pickle, "wb") as f_pickle:
                pickle.dump(encodings_para_guardar_en_pickle, f_pickle)
            print(f"Total de {len(encodings_para_guardar_en_pickle)} encodings faciales de prueba guardados en '{archivo_salida_pickle}'.")
            return True
        except IOError as e_io:
            print(f"ERROR AL GUARDAR el archivo pickle '{archivo_salida_pickle}': {e_io}")
            return False
    else:
        print("No se generaron nuevos encodings. Verifica las imágenes y rutas en la carpeta 'rostros_conocidos'.")
        # Si el archivo pkl ya existe y no se generaron nuevos, podría ser ok, o podría ser un error si se esperaban.
        return False # Indicar que no se guardó nada nuevo.

def cargar_encodings_faciales_al_inicio(archivo_pickle=constants.ARCHIVO_ENCODINGS_FACIALES_PKL): # Usa la constante importada
    global encodings_faciales_cargados_global
    """
    Carga los encodings faciales desde el archivo pickle.
    Para cada encoding cargado con un 'nombre', intenta buscar la información
    completa del usuario en la base de datos usando ese nombre y la fusiona.
    Puebla la variable global 'encodings_faciales_cargados_global'.
    """
    encodings_faciales_cargados_global = [] # Limpiar antes de cargar
    
    if os.path.exists(archivo_pickle):
        try:
            with open(archivo_pickle, "rb") as f:
                datos_cargados_del_pickle = pickle.load(f) # Lista de {"nombre": str, "encoding": np.array}
            
            if isinstance(datos_cargados_del_pickle, list):
                for item_del_pickle in datos_cargados_del_pickle:
                    if isinstance(item_del_pickle, dict) and "nombre" in item_del_pickle and "encoding" in item_del_pickle:
                        nombre_en_pickle = item_del_pickle["nombre"]
                        encoding_numpy_de_pickle = item_del_pickle["encoding"] 
                        
                        # Intentar obtener información completa del usuario desde la BD
                        info_usuario_de_bd = obtener_usuario_por_nombre_bd(nombre_en_pickle) 
                        
                        if info_usuario_de_bd:
                            # Usuario encontrado en BD. Usamos sus datos.
                            # El encoding_numpy_de_pickle es el que queremos usar.
                            # Lo añadimos a la info de la BD para la lista en memoria.
                            # La clave "facial_encoding_array" será la que use la lógica de reconocimiento.
                            info_usuario_de_bd["facial_encoding_array"] = encoding_numpy_de_pickle 
                            encodings_faciales_cargados_global.append(info_usuario_de_bd)
                        else:
                            # Usuario del pickle no está en la BD, crear una entrada básica para usar el encoding.
                            print(f"Advertencia Facial: El nombre '{nombre_en_pickle}' del archivo de encodings"
                                  f" no se encontró en la BD de usuarios. Se usará con datos limitados.")
                            encodings_faciales_cargados_global.append({
                                "nombre": nombre_en_pickle,
                                "facial_encoding_array": encoding_numpy_de_pickle, # Clave consistente
                                "dni": f"PKL_ONLY_{nombre_en_pickle[:10]}", 
                                "nivel": "Visitante", # Asignar un nivel por defecto o "Desconocido"
                                "area": "N/A",
                                "uid_rfid": None, 
                                "h_inicio": None,
                                "h_fin": None,
                                "id_usuario": None # No tiene ID de la BD
                                # 'facial_encoding' (el BLOB) sería None aquí porque no vino de la BD.
                            })
                    else:
                        print(f"Advertencia: Formato de item incorrecto en '{archivo_pickle}': {item_del_pickle}")
            
            if encodings_faciales_cargados_global:
                nombres_cargados = [u.get("nombre", "SinNombre") for u in encodings_faciales_cargados_global]
                print(f"--- Encodings faciales cargados y procesados para {len(encodings_faciales_cargados_global)} perfiles: {', '.join(nombres_cargados)} ---")
            else:
                print(f"ADVERTENCIA: Archivo '{archivo_pickle}' está vacío o no contiene encodings válidos para procesar.")

        except ModuleNotFoundError as e_mod: # Específicamente para pickle si falta una clase que se guardó
             print(f"ERROR FATAL al cargar encodings: {e_mod}. Puede que el archivo .pkl haya sido creado con una versión de código/librería diferente.")
             encodings_faciales_cargados_global = []
        except Exception as e:
            print(f"ERROR FATAL al cargar o procesar encodings faciales desde '{archivo_pickle}': {e}")
            encodings_faciales_cargados_global = []
    else:
        print(f"ADVERTENCIA: Archivo de encodings '{archivo_pickle}' no encontrado. El reconocimiento facial no funcionará.")

# --- Bloque de prueba (opcional, para ejecutar este módulo directamente) ---
if __name__ == '__main__':
    print("Ejecutando facial_recognition_utils.py directamente...")
    
    # 1. Inicializar la BD (necesario para que obtener_usuario_por_nombre_bd funcione)
    #    En un proyecto real, db_manager.py se importaría y se llamaría su inicializar_bd()
    #    Aquí simulamos o asumimos que ya existe si lo ejecutas después del main_app.
    #    Para que este script sea autónomo para pruebas de encodings:
    if not os.path.exists(NOMBRE_BD):
        print(f"Base de datos '{NOMBRE_BD}' no encontrada. Creando una de prueba para facial_recognition_utils.")
        inicializar_bd() # Llama a la función local de db_manager
        # Podrías añadir algunos usuarios de prueba a la BD aquí si es necesario.
        # Ejemplo:
        # db_manager.agregar_usuario_bd({"nombre": "Nikola Tesla", "dni": "TESTDNI001", "nivel": "Admin", "area": "Lab", "uid_rfid": "TESTUID001"})
        # db_manager.agregar_usuario_bd({"nombre": "Fabrizio Reyes", "dni": "TESTDNI002", "nivel": "Trabajador", "area": "Dev", "uid_rfid": "TESTUID002", "h_inicio":"08:00", "h_fin":"17:00"})


    # 2. (Re)Generar el archivo de encodings
    print("\n--- Intentando generar encodings_faciales.pkl ---")
    # Actualiza USUARIOS_DE_PRUEBA_IMAGENES con los nombres de archivo de tus imágenes en rostros_conocidos/
    USUARIOS_DE_PRUEBA_IMAGENES = {
         "Fabrizio Reyes": "rostro_fabrizio.jpg", # Cambia "rostro_fabrizio.jpg" por tu nombre de archivo
         # "Nikola Tesla": "rostro_nikola.jpg", # Descomenta y ajusta si tienes la imagen
    }
    if not USUARIOS_DE_PRUEBA_IMAGENES:
        print("Por favor, edita 'USUARIOS_DE_PRUEBA_IMAGENES' en este script con tus usuarios e imágenes.")
    else:
        crear_encodings_de_rostros_conocidos()

    # 3. Probar la carga de los encodings
    print("\n--- Intentando cargar encodings_faciales.pkl ---")
    cargar_encodings_faciales_al_inicio()
    
    if encodings_faciales_cargados_global:
        print("\nContenido de encodings_faciales_cargados_global:")
        for perfil in encodings_faciales_cargados_global:
            print(f"  Nombre: {perfil.get('nombre')}, DNI: {perfil.get('dni')}, Nivel: {perfil.get('nivel')}, Tiene Encoding: {perfil.get('facial_encoding_array') is not None}")
    else:
        print("No se cargaron encodings para mostrar.")

    print("\nPruebas de facial_recognition_utils.py finalizadas.")