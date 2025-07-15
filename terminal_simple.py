#!/usr/bin/env python3
"""
Terminal BioEntry - Versión Simplificada
Para testing de pantalla completa
"""

import tkinter as tk
import cv2
import numpy as np
from picamera2 import Picamera2
import threading
import time
from PIL import Image, ImageTk

class SimpleTerminal:
    def __init__(self):
        self.root = tk.Tk()
        self.setup_window()
        self.setup_camera()
        self.running = True
        
    def setup_window(self):
        """Configurar ventana en pantalla completa"""
        # Configuración básica
        self.root.title("Terminal BioEntry")
        self.root.configure(bg='black', cursor='none')
        
        # Pantalla completa
        self.root.attributes('-fullscreen', True)
        
        # Obtener dimensiones
        self.root.update_idletasks()
        self.width = self.root.winfo_screenwidth()
        self.height = self.root.winfo_screenheight()
        
        print(f"Pantalla: {self.width}x{self.height}")
        
        # Label para video
        self.video_label = tk.Label(self.root, bg='black')
        self.video_label.pack(fill=tk.BOTH, expand=True)
        
        # Título superpuesto
        self.title_label = tk.Label(
            self.root,
            text="TERMINAL DE ACCESO",
            font=('Arial', 20, 'bold'),
            bg='black',
            fg='white'
        )
        self.title_label.place(x=self.width//2-150, y=20)
        
        # Mensaje inferior
        self.message_label = tk.Label(
            self.root,
            text="COLÓQUESE FRENTE A LA CÁMARA",
            font=('Arial', 16, 'bold'),
            bg='black',
            fg='#00ff00'
        )
        self.message_label.place(x=self.width//2-200, y=self.height-80)
        
        # Teclas de salida
        self.root.bind('<Escape>', self.exit_app)
        self.root.bind('<q>', self.exit_app)
        self.root.focus_set()
    
    def setup_camera(self):
        """Configurar cámara"""
        self.picam2 = Picamera2()
        config = self.picam2.create_preview_configuration(
            main={"size": (640, 480)}
        )
        self.picam2.configure(config)
        
        # Cargar detector de caras
        self.face_cascade = cv2.CascadeClassifier(
            '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml'
        )
    
    def camera_loop(self):
        """Loop de cámara"""
        self.picam2.start()
        time.sleep(1)
        
        while self.running:
            try:
                # Capturar frame
                frame = self.picam2.capture_array()
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                
                # Detectar caras
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                
                # Dibujar caras
                for (x, y, w, h) in faces:
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
                    cv2.putText(frame, 'CARA DETECTADA', (x, y-10), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                # Redimensionar para pantalla completa
                frame_resized = cv2.resize(frame, (self.width, self.height))
                
                # Convertir para Tkinter
                frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
                img_pil = Image.fromarray(frame_rgb)
                img_tk = ImageTk.PhotoImage(img_pil)
                
                # Actualizar UI en thread principal
                self.root.after_idle(self.update_video, img_tk)
                
                time.sleep(0.033)  # ~30 FPS
                
            except Exception as e:
                print(f"Error en cámara: {e}")
                time.sleep(0.1)
    
    def update_video(self, img_tk):
        """Actualizar video en UI"""
        if self.running:
            self.video_label.configure(image=img_tk)
            self.video_label.image = img_tk
    
    def exit_app(self, event=None):
        """Salir de la aplicación"""
        self.running = False
        if hasattr(self, 'picam2'):
            self.picam2.stop()
        self.root.quit()
        self.root.destroy()
    
    def run(self):
        """Ejecutar aplicación"""
        try:
            # Iniciar cámara en thread separado
            camera_thread = threading.Thread(target=self.camera_loop, daemon=True)
            camera_thread.start()
            
            # Ejecutar UI
            self.root.mainloop()
            
        except KeyboardInterrupt:
            print("Interrumpido por usuario")
        finally:
            self.exit_app()

if __name__ == "__main__":
    try:
        terminal = SimpleTerminal()
        terminal.run()
    except Exception as e:
        print(f"Error: {e}")