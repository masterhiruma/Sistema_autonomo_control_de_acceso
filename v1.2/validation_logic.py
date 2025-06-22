import datetime

# ==============================================================================
# FUNCIONES DE VALIDACIÓN DE HORARIOS
# ==============================================================================

def verificar_horario_trabajador(h_inicio_str, h_fin_str):
    """
    Verifica si la hora y día actual caen dentro del horario laboral
    definido (Lunes a Viernes, entre h_inicio_str y h_fin_str).

    Args:
        h_inicio_str (str): Hora de inicio en formato "HH:MM".
        h_fin_str (str): Hora de fin en formato "HH:MM".

    Returns:
        bool: True si está en horario laboral, False en caso contrario.
    """
    if not h_inicio_str or not h_fin_str: 
        # print("Debug Horario Trabajador: Horarios no definidos.")
        return False 
    
    try:
        ahora = datetime.datetime.now()
        dia_semana_actual = ahora.weekday() # Lunes=0, Martes=1, ..., Viernes=4, Sábado=5, Domingo=6
        
        if not (0 <= dia_semana_actual <= 4): # Si no es Lunes a Viernes
            # print(f"Debug Horario Trabajador: Fuera de día laboral (Día: {dia_semana_actual}).")
            return False

        hora_actual = ahora.time()
        horario_inicio_bd = datetime.datetime.strptime(h_inicio_str, "%H:%M").time()
        horario_fin_bd = datetime.datetime.strptime(h_fin_str, "%H:%M").time()

        # print(f"Debug Horario Trabajador: Actual={hora_actual}, InicioBD={horario_inicio_bd}, FinBD={horario_fin_bd}, DíaOK={0 <= dia_semana_actual <= 4}")
        return horario_inicio_bd <= hora_actual < horario_fin_bd
    except ValueError:
        print(f"ERROR: Formato de horario incorrecto para trabajador en la base de datos: Inicio='{h_inicio_str}', Fin='{h_fin_str}'")
        return False
    except Exception as e:
        print(f"Error inesperado en verificar_horario_trabajador: {e}")
        return False

def verificar_horario_visitante():
    """
    Verifica si la hora y día actual caen dentro del horario de visita
    definido (Miércoles de 9:00 AM a 10:00 AM).

    Returns:
        bool: True si está en horario de visita, False en caso contrario.
    """
    try:
        ahora = datetime.datetime.now()
        dia_semana_actual = ahora.weekday() # Miércoles es 2
        
        if dia_semana_actual != 2: # Si no es Miércoles
            # print(f"Debug Horario Visitante: No es Miércoles (Día: {dia_semana_actual}).")
            return False
        
        hora_actual = ahora.time()
        horario_visita_inicio = datetime.time(9, 0)  # 9:00 AM
        horario_visita_fin = datetime.time(10, 0) # 10:00 AM (No inclusivo, hasta las 09:59:59)
        
        # print(f"Debug Horario Visitante: Actual={hora_actual}, InicioVisita={horario_visita_inicio}, FinVisita={horario_visita_fin}, EsMiércoles={dia_semana_actual == 2}")
        return horario_visita_inicio <= hora_actual < horario_visita_fin
    except Exception as e:
        print(f"Error inesperado en verificar_horario_visitante: {e}")
        return False

# --- Bloque de prueba (opcional, para ejecutar este módulo directamente) ---
if __name__ == '__main__':
    print("Ejecutando pruebas del módulo validation_logic.py...")

    # Pruebas para horario de trabajador
    print("\n--- Pruebas Horario Trabajador ---")
    # Simular diferentes momentos
    # Para probar esto, necesitarías una forma de "simular" la hora actual,
    # o ejecutarlo en los momentos adecuados.
    # Por ahora, solo llamamos a la función con horarios de ejemplo.
    
    # Ejemplo 1: Dentro de horario laboral en día laboral
    # (Asumir que hoy es un día laboral para esta prueba manual)
    print(f"Trabajador (09:00-17:00) - ¿Acceso permitido ahora?: {verificar_horario_trabajador('09:00', '17:00')}")

    # Ejemplo 2: Horario malformado
    print(f"Trabajador (horario mal) - ¿Acceso permitido?: {verificar_horario_trabajador('9', '17:00')}")
    
    # Ejemplo 3: Horarios no definidos
    print(f"Trabajador (sin horarios) - ¿Acceso permitido?: {verificar_horario_trabajador(None, None)}")


    # Pruebas para horario de visitante
    print("\n--- Pruebas Horario Visitante ---")
    # (Asumir que hoy es Miércoles entre 9 y 10 AM para esta prueba manual, o no)
    print(f"Visitante - ¿Acceso permitido ahora?: {verificar_horario_visitante()}")

    print("\nPruebas de validation_logic.py finalizadas.")