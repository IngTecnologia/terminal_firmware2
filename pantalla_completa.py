#!/usr/bin/env python3
import cv2
import numpy as np
from picamera2 import Picamera2, Preview
import time

# Inicializar la cámara
picam2 = Picamera2()

# Configuración para pantalla completa
preview_config = picam2.create_preview_configuration(main={"size": (400, 300)})
picam2.configure(preview_config)

# Cargar el clasificador de caras
face_cascade = cv2.CascadeClassifier('/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml')

if face_cascade.empty():
    print("Error: No se pudo cargar el clasificador de caras")
    exit(1)

# Iniciar la cámara
picam2.start()
time.sleep(2)

print("Detección facial iniciada. Presiona ESC para salir.")

try:
    while True:
        # Capturar frame
        frame = picam2.capture_array()
        
        # Convertir de RGB a BGR para OpenCV
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        
        # Convertir a escala de grises para detección
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        
        # Detectar caras
        faces = face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.2,
            minNeighbors=4,
            minSize=(20, 20),
            maxSize=(150, 150)
        )
        
        # Redimensionar frame para pantalla completa (800x400)
        frame_resized = cv2.resize(frame, (800, 400))
        
        # Ajustar coordenadas de las caras para la nueva resolución
        scale_x = 800 / 400
        scale_y = 400 / 300
        
        for (x, y, w, h) in faces:
            # Escalar coordenadas
            x_scaled = int(x * scale_x)
            y_scaled = int(y * scale_y)
            w_scaled = int(w * scale_x)
            h_scaled = int(h * scale_y)
            
            cv2.rectangle(frame_resized, (x_scaled, y_scaled), 
                         (x_scaled + w_scaled, y_scaled + h_scaled), (0, 255, 0), 3)
            cv2.putText(frame_resized, 'Cara', (x_scaled, y_scaled-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Mostrar información
        cv2.putText(frame_resized, f'Caras: {len(faces)}', (10, 30), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 0), 2)
        
        # Mostrar en pantalla completa
        cv2.namedWindow('Deteccion Facial', cv2.WND_PROP_FULLSCREEN)
        cv2.setWindowProperty('Deteccion Facial', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
        cv2.imshow('Deteccion Facial', frame_resized)
        
        # Salir con ESC
        if cv2.waitKey(1) & 0xFF == 27:  # ESC key
            break
            
except KeyboardInterrupt:
    print("\nDeteniendo detección facial...")

finally:
    # Limpiar
    picam2.stop()
    cv2.destroyAllWindows()
    print("Detección facial finalizada.")