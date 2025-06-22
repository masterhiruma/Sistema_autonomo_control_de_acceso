SISTEMA DE CONTROL DE ACCESO - INSTRUCCIONES DE USO
====================================================

Este sistema permite gestionar el acceso mediante RFID, QR y reconocimiento facial.

INSTRUCCIONES PARA EJECUTAR EL PROGRAMA
----------------------------------------
1. Dirígete a la carpeta 'dist' generada por PyInstaller:
   dist/ControlAcceso.exe

2. Copia los siguientes archivos y carpetas junto al ejecutable si vas a moverlo a otra PC:
   - sistema_acceso.db (base de datos, si ya tienes usuarios registrados)
   - encodings_faciales.pkl (encodings faciales)
   - La carpeta 'rostros_conocidos' (imágenes de referencia)
   - La carpeta 'reportes_acceso' (para reportes y logs)

3. Conecta el Arduino y asegúrate de que el puerto esté disponible.

4. Haz doble clic en 'ControlAcceso.exe' para iniciar el sistema.

5. Usa la interfaz gráfica para:
   - Conectar el Arduino
   - Registrar, editar o borrar usuarios
   - Visualizar y exportar reportes diarios
   - Supervisar el estado de sensores y accesos

REQUISITOS DEL SISTEMA
----------------------
- Windows 10 o superior
- Drivers de Arduino instalados
- Cámara web conectada y funcional
- Lector RFID y/o lector QR conectados según tu hardware

NOTAS IMPORTANTES
-----------------
- Si el sistema no detecta la cámara o el Arduino, revisa las conexiones y los drivers.
- Los archivos de reportes se guardan en la carpeta 'reportes_acceso'.
- Si necesitas cambiar la base de datos o los encodings, reemplaza los archivos correspondientes.
- Si quieres personalizar el ícono del ejecutable, agrega un archivo 'icon.ico' y recompila con PyInstaller.

SOPORTE
-------
Para dudas o soporte, contacta al desarrollador del sistema.

¡Gracias por usar el Sistema de Control de Acceso! 