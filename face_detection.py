#!/usr/bin/env python3
import cv2
import numpy as np
import os
from picamera2 import Picamera2, Preview
import time

# Verificar OpenCV
print(f"Versión de OpenCV: {cv2.__version__}")

# Cargar el clasificador de caras con rutas manuales
cascade_paths = [
    '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
    '/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml',
    '/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
    'haarcascade_frontalface_default.xml'  # Si está en el directorio actual
]

face_cascade = None
for path in cascade_paths:
    if os.path.exists(path):
        face_cascade = cv2.CascadeClassifier(path)
        if not face_cascade.empty():
            print(f"Clasificador cargado desde: {path}")
            break

if face_cascade is None or face_cascade.empty():
    print("Error: No se pudo cargar el clasificador de caras")
    print("Verificar que opencv-data esté instalado")
    exit(1)

# Inicializar la cámara
picam2 = Picamera2()

# Configuración optimizada para pantalla 800x400 en vertical
# Usar resolución que quepa en la pantalla
preview_config = picam2.create_preview_configuration(main={"size": (400, 300)})
picam2.configure(preview_config)

# Iniciar la cámara
picam2.start()
time.sleep(2)

print("Detección facial iniciada. Presiona 'q' para salir.")

try:
    while True:
        # Capturar frame
        frame = picam2.capture_array()
        
        # Convertir de RGB a BGR para OpenCV
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # Convertir a escala de grises para detección (más rápido)
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detectar caras
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,        # Qué tan rápido escala la búsqueda
            minNeighbors=5,         # Cuántas detecciones vecinas confirman una cara
            minSize=(30, 30),       # Tamaño mínimo de cara
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        
        # Dibujar rectángulos alrededor de las caras detectadas
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            # Opcional: agregar texto
            cv2.putText(frame, 'Cara', (x, y-10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Mostrar número de caras detectadas
        cv2.putText(frame, f'Caras: {len(faces)}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
        
        # Mostrar el frame en ventana redimensionada para la pantalla
        cv2.namedWindow('Deteccion Facial', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Deteccion Facial', 380, 280)  # Deja margen en la pantalla
        cv2.moveWindow('Deteccion Facial', 10, 10)      # Posicionar en esquina superior
        cv2.imshow('Deteccion Facial', frame)
        
        # Salir con 'q'
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
            
except KeyboardInterrupt:
    print("\nDeteniendo detección facial...")

finally:
    # Limpiar
    picam2.stop()
    cv2.destroyAllWindows()
    print("Detección facial finalizada.")