import sqlite3
import os
import pickle # Para serializar/deserializar el facial_encoding
import sys

# Determinar la ubicación de la base de datos
if getattr(sys, 'frozen', False):
    # Si estamos en un ejecutable
    application_path = os.path.dirname(sys.executable)
else:
    # Si estamos en modo desarrollo
    application_path = os.path.dirname(os.path.abspath(__file__))

NOMBRE_BD = os.path.join(application_path, "sistema_acceso.db")

# --- Constantes del Módulo (podrían moverse a un constants.py general) ---
CARPETA_REPORTES = "reportes_acceso" # Necesario para inicializar_bd si crea la carpeta

# ==============================================================================
# FUNCIONES DE LA BASE DE DATOS (SQLite)
# ==============================================================================

def inicializar_bd():
    """
    Inicializa la base de datos si no existe.
    Crea la tabla de usuarios con todos los campos necesarios.
    """
    conn = sqlite3.connect(NOMBRE_BD)
    cursor = conn.cursor()
    
    # Crear la tabla si no existe
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id_usuario INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre_completo TEXT NOT NULL,
            dni TEXT UNIQUE NOT NULL,
            nivel_usuario TEXT NOT NULL,
            area_trabajo TEXT NOT NULL,
            uid_rfid TEXT UNIQUE NOT NULL,
            horario_trabajo_inicio TEXT,
            horario_trabajo_fin TEXT,
            facial_encoding BLOB
        )
    ''')
    
    conn.commit()
    conn.close()

def agregar_usuario_bd(datos_usuario):
    """
    Agrega un nuevo usuario a la base de datos.
    'datos_usuario' es un diccionario con las claves:
    'nombre', 'dni', 'nivel', 'area', 'uid_rfid', 
    'h_inicio' (opcional), 'h_fin' (opcional),
    'facial_encoding_array' (opcional, array NumPy del encoding).
    Devuelve (True, "mensaje") o (False, "mensaje de error").
    """
    conn = sqlite3.connect(NOMBRE_BD)
    cursor = conn.cursor()
    
    encoding_serializado = None
    if datos_usuario.get('facial_encoding_array') is not None: # Usamos la clave consistente
        encoding_serializado = pickle.dumps(datos_usuario['facial_encoding_array'])
    
    try:
        cursor.execute('''
            INSERT INTO usuarios (nombre_completo, dni, nivel_usuario, area_trabajo, uid_rfid, 
                                  horario_trabajo_inicio, horario_trabajo_fin, facial_encoding)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (datos_usuario['nombre'], datos_usuario['dni'], datos_usuario['nivel'], datos_usuario['area'], 
              datos_usuario['uid_rfid'], datos_usuario.get('h_inicio'), datos_usuario.get('h_fin'), 
              encoding_serializado))
        conn.commit()
        return True, "Usuario agregado exitosamente a la base de datos."
    except sqlite3.IntegrityError as e:
        if "UNIQUE constraint failed: usuarios.dni" in str(e):
            return False, "Error: El DNI ya está registrado en la base de datos."
        elif "UNIQUE constraint failed: usuarios.uid_rfid" in str(e):
            return False, "Error: El UID RFID ya está registrado en la base de datos."
        return False, f"Error de integridad en la base de datos: {e}"
    except Exception as e:
        print(f"Error general al agregar usuario a BD: {e}")
        return False, f"Error inesperado al agregar usuario: {e}"
    finally:
        conn.close()

def obtener_usuario_por_rfid_bd(uid_rfid):
    """
    Obtiene la información completa de un usuario por su UID RFID.
    Devuelve un diccionario con los datos del usuario (incluyendo 'facial_encoding_array') o None.
    """
    conn = sqlite3.connect(NOMBRE_BD)
    cursor = conn.cursor()
    cursor.execute("SELECT id_usuario, nombre_completo, dni, nivel_usuario, area_trabajo, horario_trabajo_inicio, horario_trabajo_fin, facial_encoding FROM usuarios WHERE uid_rfid = ?", (uid_rfid,))
    data = cursor.fetchone()
    conn.close()
    if data:
        encoding_np = pickle.loads(data[7]) if data[7] else None
        return {"id_usuario": data[0], "nombre": data[1], "dni": data[2], "nivel": data[3], 
                "area": data[4], "h_inicio": data[5], "h_fin": data[6], "uid_rfid": uid_rfid, 
                "facial_encoding_array": encoding_np} # Clave consistente para el array NumPy
    return None

def obtener_usuario_por_nombre_bd(nombre_completo):
    """
    Obtiene la información completa de un usuario por su nombre_completo.
    Usado para vincular encodings faciales cargados del pickle con la info de la BD.
    Devuelve un diccionario con los datos del usuario (incluyendo 'facial_encoding_array') o None.
    """
    conn = sqlite3.connect(NOMBRE_BD)
    cursor = conn.cursor()
    cursor.execute("SELECT id_usuario, nombre_completo, dni, nivel_usuario, area_trabajo, uid_rfid, horario_trabajo_inicio, horario_trabajo_fin, facial_encoding FROM usuarios WHERE nombre_completo = ?", (nombre_completo,))
    data = cursor.fetchone()
    conn.close()
    if data:
        encoding_np = pickle.loads(data[8]) if data[8] else None # El BLOB de la BD
        return {"id_usuario": data[0], "nombre": data[1], "dni": data[2], "nivel": data[3], 
                "area": data[4], "uid_rfid": data[5], "h_inicio": data[6], "h_fin": data[7], 
                "facial_encoding_array": encoding_np}
    return None

def obtener_usuario_por_id_bd(id_usuario):
    """
    Obtiene la información completa de un usuario por su id_usuario.
    Usado para poblar el formulario de edición.
    Devuelve un diccionario con los datos del usuario (incluyendo 'facial_encoding_array') o None.
    """
    conn = sqlite3.connect(NOMBRE_BD)
    cursor = conn.cursor()
    cursor.execute("SELECT id_usuario, nombre_completo, dni, nivel_usuario, area_trabajo, uid_rfid, horario_trabajo_inicio, horario_trabajo_fin, facial_encoding FROM usuarios WHERE id_usuario = ?", (id_usuario,))
    data = cursor.fetchone()
    conn.close()
    if data:
        encoding_np = pickle.loads(data[8]) if data[8] else None
        return {"id_usuario": data[0], "nombre": data[1], "dni": data[2], "nivel": data[3], 
                "area": data[4], "uid_rfid": data[5], "h_inicio": data[6], "h_fin": data[7], 
                "facial_encoding_array": encoding_np}
    return None

def verificar_uid_existente_bd(uid_rfid, excluir_id_usuario=None):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor(); query = "SELECT nombre_completo FROM usuarios WHERE uid_rfid = ?"; params = [uid_rfid]
    if excluir_id_usuario: query += " AND id_usuario != ?"; params.append(excluir_id_usuario)
    cursor.execute(query, tuple(params)); resultado = cursor.fetchone(); conn.close()
    return resultado[0] if resultado else None

def verificar_dni_existente_bd(dni, excluir_id_usuario=None):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor(); query = "SELECT nombre_completo FROM usuarios WHERE dni = ?"; params = [dni]
    if excluir_id_usuario: query += " AND id_usuario != ?"; params.append(excluir_id_usuario)
    cursor.execute(query, tuple(params)); resultado = cursor.fetchone(); conn.close()
    return resultado[0] if resultado else None

def obtener_todos_los_usuarios_bd():
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    cursor.execute("SELECT id_usuario, nombre_completo, dni, nivel_usuario, uid_rfid FROM usuarios ORDER BY nombre_completo")
    usuarios = cursor.fetchall(); conn.close(); return usuarios

def actualizar_usuario_bd(id_usuario, datos_actualizacion):
    """
    Actualiza un usuario existente en la base de datos.
    'datos_actualizacion' es un diccionario con las claves a actualizar.
    Debe incluir 'facial_encoding_array' si se va a actualizar el rostro.
    """
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    
    set_clauses = []
    params = []

    # Campos que siempre se actualizan si están presentes en datos_actualizacion
    campos_texto = ["nombre_completo", "dni", "nivel_usuario", "area_trabajo", "uid_rfid", 
                    "horario_trabajo_inicio", "horario_trabajo_fin"]
    
    for campo in campos_texto:
        if campo in datos_actualizacion: # Usar el nombre de la columna en la BD
            col_nombre_bd = campo # En este caso coinciden
            if campo == "nombre": col_nombre_bd = "nombre_completo" # Adaptar si las claves del dict son diferentes
            elif campo == "nivel": col_nombre_bd = "nivel_usuario"
            elif campo == "area": col_nombre_bd = "area_trabajo"
            elif campo == "h_inicio": col_nombre_bd = "horario_trabajo_inicio"
            elif campo == "h_fin": col_nombre_bd = "horario_trabajo_fin"

            set_clauses.append(f"{col_nombre_bd} = ?")
            params.append(datos_actualizacion[campo])

    # Manejo especial para facial_encoding
    if 'facial_encoding_array' in datos_actualizacion: # Si se proporciona, se actualiza
        encoding_serializado = pickle.dumps(datos_actualizacion['facial_encoding_array']) if datos_actualizacion['facial_encoding_array'] is not None else None
        set_clauses.append("facial_encoding = ?")
        params.append(encoding_serializado)
    
    if not set_clauses:
        return False, "No hay datos para actualizar."

    params.append(id_usuario)
    query_update = f"UPDATE usuarios SET {', '.join(set_clauses)} WHERE id_usuario = ?"
    
    try:
        cursor.execute(query_update, tuple(params))
        conn.commit(); return True, "Usuario actualizado exitosamente."
    except sqlite3.IntegrityError as e:
        if "dni" in str(e): return False, "Error: El DNI proporcionado ya está registrado para otro usuario."
        if "uid_rfid" in str(e): return False, "Error: El UID RFID proporcionado ya está registrado para otro usuario."
        return False, f"Error de integridad en la base de datos al actualizar: {e}"
    except Exception as e_gen:
        print(f"Error general al actualizar usuario: {e_gen}")
        return False, f"Error inesperado al actualizar: {e_gen}"
    finally: conn.close()

def borrar_usuario_bd(id_usuario):
    conn = sqlite3.connect(NOMBRE_BD); cursor = conn.cursor()
    try: cursor.execute("DELETE FROM usuarios WHERE id_usuario = ?", (id_usuario,)); conn.commit(); return True, "Usuario borrado exitosamente."
    except Exception as e: return False, f"Error al borrar usuario de la BD: {e}"
    finally: conn.close()

# --- Bloque de prueba (opcional, para ejecutar este módulo directamente) ---
if __name__ == '__main__':
    print("Ejecutando pruebas del módulo db_manager.py...")
    inicializar_bd()
    print("Base de datos inicializada.")

    # Prueba agregar usuario
    # Nota: facial_encoding_array sería un array NumPy real si lo tuviéramos.
    # Para esta prueba, podemos usar None o un objeto simple serializable si no tenemos los encodings aún.
    # O generar uno falso con pickle.dumps(np.random.rand(128).astype(np.float64)) si np está importado.
    
    # Limpiar la tabla para pruebas limpias (¡CUIDADO EN PRODUCCIÓN!)
    # conn_test = sqlite3.connect(NOMBRE_BD)
    # conn_test.execute("DELETE FROM usuarios")
    # conn_test.commit()
    # conn_test.close()

    datos_admin = {
        "nombre": "Admin Root", "dni": "00000001", "nivel": "Admin", "area": "Sistemas",
        "uid_rfid": "ADMIN001", "h_inicio": None, "h_fin": None, "facial_encoding_array": None
    }
    exito, msg = agregar_usuario_bd(datos_admin)
    print(f"Agregar Admin: {exito} - {msg}")

    datos_trabajador = {
        "nombre": "Juan Perez", "dni": "12345678", "nivel": "Trabajador", "area": "Operaciones",
        "uid_rfid": "RFID0001", "h_inicio": "08:00", "h_fin": "17:00", "facial_encoding_array": None
    }
    exito, msg = agregar_usuario_bd(datos_trabajador)
    print(f"Agregar Trabajador: {exito} - {msg}")

    # Prueba obtener por RFID
    usuario = obtener_usuario_por_rfid_bd("RFID0001")
    if usuario:
        print(f"Usuario obtenido por RFID 'RFID0001': {usuario['nombre']}")
    else:
        print("Usuario 'RFID0001' no encontrado.")

    # Prueba obtener todos
    todos = obtener_todos_los_usuarios_bd()
    print(f"Total usuarios en BD: {len(todos)}")
    for u in todos:
        print(f"  ID: {u[0]}, Nombre: {u[1]}, DNI: {u[2]}, Nivel: {u[3]}, UID: {u[4]}")

    print("Pruebas de db_manager.py finalizadas.")