import face_recognition
import pickle
import os

ROSTROS_CONOCIDOS_DIR = "rostros_conocidos" # Carpeta en el mismo directorio que este script
ARCHIVO_ENCODINGS_PKL = "encodings_faciales.pkl"

# Define los usuarios de prueba y las rutas a sus imágenes
# CLAVE: El 'nombre' aquí debe coincidir con el 'nombre_completo' que tienes
# en tu base de datos SQLite si quieres que la validación RFID + Facial funcione
# encontrando el encoding correcto por nombre.
USUARIOS_DE_PRUEBA_IMAGENES = {
    "Nikola Tesla": "rostro_nikola.jpg",    # Ej: rostro_nikola.jpg en la carpeta rostros_conocidos
    "Fabrizio Reyes": "rostro_fabrizio.jpg", # Ej: rostro_fabrizio.jpg en la carpeta rostros_conocidos
    "Fernando Mallco": "rostro_fernando.jpg",
    "Jean Ponciano": "rostro_jean.jpg",
    # "Elon Musk": "rostro_elon.jpg", # Si tienes otro usuario en la BD
    # "Walter White": "rostro_walter.jpg"
}

def crear_encodings_de_rostros_conocidos():
    print(f"Buscando imágenes en la carpeta: '{os.path.abspath(ROSTROS_CONOCIDOS_DIR)}'")
    if not os.path.exists(ROSTROS_CONOCIDOS_DIR):
        os.makedirs(ROSTROS_CONOCIDOS_DIR)
        print(f"ADVERTENCIA: Carpeta '{ROSTROS_CONOCIDOS_DIR}' no existía y ha sido creada.")
        print("Por favor, añade imágenes de rostros allí (ej: nombre_usuario.jpg) y vuelve a ejecutar.")
        return

    encodings_conocidos_para_guardar = []

    for nombre_usuario, nombre_archivo_imagen in USUARIOS_DE_PRUEBA_IMAGENES.items():
        ruta_completa_imagen = os.path.join(ROSTROS_CONOCIDOS_DIR, nombre_archivo_imagen)
        if not os.path.exists(ruta_completa_imagen):
            print(f"ADVERTENCIA: Imagen no encontrada para '{nombre_usuario}' en '{ruta_completa_imagen}'. Saltando.")
            continue
        try:
            print(f"Procesando imagen para '{nombre_usuario}': {ruta_completa_imagen}")
            imagen_cargada = face_recognition.load_image_file(ruta_completa_imagen)
            # Asumimos una cara por imagen para simplificar el enrollment inicial
            lista_encodings_rostro_en_imagen = face_recognition.face_encodings(imagen_cargada) 

            if lista_encodings_rostro_en_imagen:
                # Usar el primer encoding encontrado en la imagen
                encoding_rostro = lista_encodings_rostro_en_imagen[0]
                encodings_conocidos_para_guardar.append({
                    "nombre": nombre_usuario, # Este nombre es la clave para la búsqueda
                    "encoding": encoding_rostro
                })
                print(f"   Encoding generado para: {nombre_usuario}")
            else:
                print(f"ADVERTENCIA: No se detectaron rostros en la imagen de '{nombre_usuario}' ({ruta_completa_imagen}).")
        except Exception as e:
            print(f"Error procesando imagen para '{nombre_usuario}': {e}")

    if encodings_conocidos_para_guardar:
        with open(ARCHIVO_ENCODINGS_PKL, "wb") as f_pickle:
            pickle.dump(encodings_conocidos_para_guardar, f_pickle)
        print(f"Total de {len(encodings_conocidos_para_guardar)} encodings faciales de prueba guardados en '{ARCHIVO_ENCODINGS_PKL}'.")
    else:
        print("No se generaron encodings. Verifica las imágenes y rutas en la carpeta 'rostros_conocidos'.")

if __name__ == "__main__":
    # Ejecuta esta función para crear/actualizar el archivo de encodings
    crear_encodings_de_rostros_conocidos()