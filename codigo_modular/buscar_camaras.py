import cv2

def listar_y_probar_camaras():
    index = 0
    camaras_disponibles = []
    print("Intentando detectar cámaras disponibles...")

    # Intentar abrir cámaras hasta que falle o lleguemos a un límite razonable (ej. 10)
    for i in range(10): 
        # Usar cv2.CAP_DSHOW en Windows a menudo ayuda con la detección
        cap = cv2.VideoCapture(i, cv2.CAP_DSHOW) 
        if cap.isOpened():
            print(f"Cámara encontrada en el índice: {i}")
            camaras_disponibles.append(i)
            cap.release() # Liberar la cámara inmediatamente después de verificar
        else:
            # A veces, si un índice no es válido, los siguientes tampoco lo serán.
            # Pero es mejor seguir probando unos cuantos más por si acaso.
            # print(f"No se encontró cámara en el índice: {i}")
            pass
            
    if not camaras_disponibles:
        print("No se encontraron cámaras activas con OpenCV.")
        return

    print("\nÍndices de cámaras disponibles:", camaras_disponibles)
    print("--------------------------------------------------")
    print("Se intentará abrir cada cámara disponible una por una.")
    print("Presiona 'q' en la ventana de la cámara para pasar a la siguiente o salir.")
    print("Anota el índice que corresponda a DroidCam (o la cámara que deseas usar).\n")

    for idx in camaras_disponibles:
        print(f"Probando cámara en índice {idx}...")
        cap_test = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap_test.isOpened():
            print(f"  Cámara {idx} abierta. Mostrando vídeo...")
            window_name = f"Test Camara Indice {idx} (Presiona 'q')"
            while True:
                ret, frame = cap_test.read()
                if not ret:
                    print(f"  No se pudo leer frame de la cámara {idx}.")
                    break
                cv2.imshow(window_name, frame)
                # Esperar 30ms o hasta que se presione 'q'
                if cv2.waitKey(30) & 0xFF == ord('q'): 
                    break
            cap_test.release()
            cv2.destroyWindow(window_name) # Cerrar la ventana específica
            print(f"  Cámara {idx} cerrada.\n")
        else:
            print(f"  No se pudo abrir la cámara en el índice {idx} para la prueba visual.")
    
    cv2.destroyAllWindows() # Asegurarse de que todas las ventanas de OpenCV se cierren al final
    print("Prueba de cámaras finalizada.")

if __name__ == '__main__':
    # ASEGÚRATE DE QUE DROIDCAM ESTÉ CONECTADO Y FUNCIONANDO ANTES DE EJECUTAR ESTO
    print("Asegúrate de que DroidCam (o la cámara que quieres probar) esté activa.")
    input("Presiona Enter para comenzar la detección de cámaras...")
    listar_y_probar_camaras()