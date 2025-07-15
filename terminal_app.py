#!/usr/bin/env python3
"""
Terminal de Acceso BioEntry
Aplicación para Raspberry Pi con pantalla táctil 800x400 vertical
Funciona en modo online (API) y offline (lector de huellas AS608)
"""

import cv2
import numpy as np
import os
import time
import requests
import json
import threading
import queue
from datetime import datetime
from picamera2 import Picamera2
from typing import Optional, Dict, Any
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
import io
import sqlite3

# Configuración de la terminal
TERMINAL_CONFIG = {
    "terminal_id": "TERMINAL_001",
    "api_key": "terminal_key_001",
    "api_base_url": "http://localhost:8000",  # Cambiar por la URL de la API
    "camera_resolution": (640, 480),
    "preview_size": (400, 300),
    "face_cascade_paths": [
        '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
        '/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml',
        '/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
        'haarcascade_frontalface_default.xml'
    ],
    "face_detection_timeout": 3.0,  # Segundos para detectar cara antes de capturar
    "connection_timeout": 10,  # Timeout para conexión API
    "offline_db_path": "terminal_offline.db"
}

class FaceDetector:
    """Maneja la detección facial con OpenCV y Haar Cascades"""
    
    def __init__(self):
        self.face_cascade = self._load_face_cascade()
        
    def _load_face_cascade(self):
        """Carga el clasificador de caras Haar"""
        for path in TERMINAL_CONFIG["face_cascade_paths"]:
            if os.path.exists(path):
                cascade = cv2.CascadeClassifier(path)
                if not cascade.empty():
                    print(f"Clasificador cargado desde: {path}")
                    return cascade
        
        raise Exception("No se pudo cargar el clasificador de caras")
    
    def detect_faces(self, frame):
        """Detecta caras en un frame"""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(50, 50),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        return faces
    
    def draw_faces(self, frame, faces):
        """Dibuja rectángulos alrededor de las caras detectadas"""
        for (x, y, w, h) in faces:
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            cv2.putText(frame, 'Cara Detectada', (x, y-10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        return frame

class APIClient:
    """Cliente para comunicación con la API de BioEntry"""
    
    def __init__(self):
        self.base_url = TERMINAL_CONFIG["api_base_url"]
        self.terminal_id = TERMINAL_CONFIG["terminal_id"]
        self.api_key = TERMINAL_CONFIG["api_key"]
        self.timeout = TERMINAL_CONFIG["connection_timeout"]
    
    def check_connection(self) -> bool:
        """Verifica si hay conexión con la API"""
        try:
            response = requests.get(
                f"{self.base_url}/version",
                timeout=3
            )
            return response.status_code == 200
        except:
            return False
    
    def verify_face_auto(self, image_bytes: bytes, lat: Optional[float] = None, lng: Optional[float] = None) -> Dict[str, Any]:
        """Envía imagen para verificación automática"""
        try:
            files = {
                'image': ('capture.jpg', image_bytes, 'image/jpeg')
            }
            
            data = {
                'terminal_id': self.terminal_id
            }
            
            if lat is not None and lng is not None:
                data['lat'] = lat
                data['lng'] = lng
            
            headers = {
                'X-API-Key': self.api_key
            }
            
            response = requests.post(
                f"{self.base_url}/verify-terminal/auto",
                files=files,
                data=data,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                error_detail = response.json().get('detail', 'Error desconocido')
                raise Exception(f"Error API: {error_detail}")
                
        except requests.RequestException as e:
            raise Exception(f"Error de conexión: {str(e)}")
        except Exception as e:
            raise Exception(f"Error en verificación: {str(e)}")

class OfflineDatabase:
    """Maneja la base de datos local para modo offline"""
    
    def __init__(self):
        self.db_path = TERMINAL_CONFIG["offline_db_path"]
        self.init_database()
    
    def init_database(self):
        """Inicializa la base de datos SQLite"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS usuarios (
                    cedula TEXT PRIMARY KEY,
                    nombre TEXT NOT NULL,
                    empresa TEXT NOT NULL,
                    huella_template BLOB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.execute('''
                CREATE TABLE IF NOT EXISTS registros_offline (
                    id TEXT PRIMARY KEY,
                    cedula TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    tipo_registro TEXT NOT NULL,
                    verificado INTEGER DEFAULT 1,
                    synced INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def save_offline_record(self, cedula: str, tipo_registro: str) -> str:
        """Guarda un registro offline"""
        import uuid
        record_id = str(uuid.uuid4())
        timestamp = datetime.utcnow().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                INSERT INTO registros_offline (id, cedula, timestamp, tipo_registro)
                VALUES (?, ?, ?, ?)
            ''', (record_id, cedula, timestamp, tipo_registro))
            conn.commit()
        
        return record_id
    
    def get_user_by_cedula(self, cedula: str) -> Optional[Dict]:
        """Obtiene usuario por cédula"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                'SELECT cedula, nombre, empresa FROM usuarios WHERE cedula = ?',
                (cedula,)
            )
            row = cursor.fetchone()
            if row:
                return {
                    'cedula': row[0],
                    'nombre': row[1],
                    'empresa': row[2]
                }
        return None

class TerminalUI:
    """Interfaz de usuario para terminal táctil 800x400 vertical"""
    
    def __init__(self, terminal_app):
        self.terminal_app = terminal_app
        self.root = tk.Tk()
        self.setup_ui()
        self.camera_running = False
        
    def setup_ui(self):
        """Configura la interfaz principal"""
        # Configuración de ventana para pantalla 800x400 vertical
        self.root.title("Terminal BioEntry")
        self.root.geometry("800x400")
        self.root.configure(bg='#2c3e50')
        
        # Eliminar decoraciones de ventana (para pantalla completa)
        self.root.overrideredirect(True)
        
        # Frame principal
        main_frame = tk.Frame(self.root, bg='#2c3e50')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Título
        title_label = tk.Label(
            main_frame,
            text="Terminal de Acceso",
            font=('Arial', 24, 'bold'),
            bg='#2c3e50',
            fg='white'
        )
        title_label.pack(pady=(0, 20))
        
        # Frame para cámara
        self.camera_frame = tk.Frame(main_frame, bg='#34495e', relief=tk.RAISED, bd=2)
        self.camera_frame.pack(pady=10)
        
        # Label para mostrar la cámara
        self.camera_label = tk.Label(
            self.camera_frame,
            text="Cámara no disponible",
            width=50,
            height=15,
            bg='#34495e',
            fg='white',
            font=('Arial', 12)
        )
        self.camera_label.pack(padx=10, pady=10)
        
        # Frame para mensajes
        self.message_frame = tk.Frame(main_frame, bg='#2c3e50')
        self.message_frame.pack(fill=tk.X, pady=10)
        
        # Label para mensajes
        self.message_label = tk.Label(
            self.message_frame,
            text="Colóquese frente a la cámara",
            font=('Arial', 16),
            bg='#2c3e50',
            fg='#ecf0f1',
            wraplength=750
        )
        self.message_label.pack()
        
        # Frame para estado
        status_frame = tk.Frame(main_frame, bg='#2c3e50')
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Labels de estado
        self.online_status = tk.Label(
            status_frame,
            text="● Offline",
            font=('Arial', 12),
            bg='#2c3e50',
            fg='#e74c3c'
        )
        self.online_status.pack(side=tk.LEFT)
        
        self.time_label = tk.Label(
            status_frame,
            text="",
            font=('Arial', 12),
            bg='#2c3e50',
            fg='#ecf0f1'
        )
        self.time_label.pack(side=tk.RIGHT)
        
        # Actualizar tiempo cada segundo
        self.update_time()
        
    def update_time(self):
        """Actualiza la hora en pantalla"""
        current_time = datetime.now().strftime("%H:%M:%S - %d/%m/%Y")
        self.time_label.config(text=current_time)
        self.root.after(1000, self.update_time)
    
    def update_status(self, online: bool):
        """Actualiza el estado de conexión"""
        if online:
            self.online_status.config(text="● Online", fg='#27ae60')
        else:
            self.online_status.config(text="● Offline", fg='#e74c3c')
    
    def show_message(self, message: str, color: str = '#ecf0f1'):
        """Muestra un mensaje en pantalla"""
        self.message_label.config(text=message, fg=color)
        
    def show_success(self, message: str):
        """Muestra mensaje de éxito"""
        self.show_message(message, '#27ae60')
        self.root.after(3000, lambda: self.show_message("Colóquese frente a la cámara"))
        
    def show_error(self, message: str):
        """Muestra mensaje de error"""
        self.show_message(message, '#e74c3c')
        self.root.after(3000, lambda: self.show_message("Colóquese frente a la cámara"))
    
    def update_camera_frame(self, frame):
        """Actualiza el frame de la cámara"""
        # Redimensionar frame para la UI
        height, width = frame.shape[:2]
        new_width = 400
        new_height = int(height * new_width / width)
        
        frame_resized = cv2.resize(frame, (new_width, new_height))
        
        # Convertir de BGR a RGB
        frame_rgb = cv2.cvtColor(frame_resized, cv2.COLOR_BGR2RGB)
        
        # Convertir a formato PIL
        img_pil = Image.fromarray(frame_rgb)
        img_tk = ImageTk.PhotoImage(img_pil)
        
        # Actualizar label
        self.camera_label.configure(image=img_tk, text="")
        self.camera_label.image = img_tk  # Mantener referencia
    
    def run(self):
        """Ejecuta la interfaz"""
        self.root.mainloop()

class BioEntryTerminal:
    """Aplicación principal del terminal"""
    
    def __init__(self):
        self.face_detector = FaceDetector()
        self.api_client = APIClient()
        self.offline_db = OfflineDatabase()
        self.ui = TerminalUI(self)
        
        # Inicializar cámara
        self.picam2 = Picamera2()
        self.setup_camera()
        
        # Variables de estado
        self.is_online = False
        self.last_detection_time = 0
        self.processing = False
        
        # Colas para comunicación entre threads
        self.frame_queue = queue.Queue(maxsize=2)
        
    def setup_camera(self):
        """Configura la cámara"""
        config = self.picam2.create_preview_configuration(
            main={"size": TERMINAL_CONFIG["camera_resolution"]}
        )
        self.picam2.configure(config)
        
    def check_online_status(self):
        """Verifica periódicamente el estado de conexión"""
        def check():
            while True:
                try:
                    online = self.api_client.check_connection()
                    if online != self.is_online:
                        self.is_online = online
                        self.ui.update_status(online)
                        print(f"Estado de conexión: {'Online' if online else 'Offline'}")
                except:
                    pass
                time.sleep(5)  # Verificar cada 5 segundos
        
        thread = threading.Thread(target=check, daemon=True)
        thread.start()
    
    def camera_loop(self):
        """Loop principal de la cámara"""
        try:
            self.picam2.start()
            time.sleep(2)
            
            while True:
                try:
                    # Capturar frame
                    frame = self.picam2.capture_array()
                    frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                    
                    # Detectar caras
                    faces = self.face_detector.detect_faces(frame)
                    
                    # Dibujar caras detectadas
                    frame_with_faces = self.face_detector.draw_faces(frame, faces)
                    
                    # Actualizar UI con el frame
                    try:
                        if not self.frame_queue.full():
                            self.frame_queue.put(frame_with_faces, block=False)
                    except queue.Full:
                        pass
                    
                    # Si hay cara detectada y no estamos procesando
                    if len(faces) > 0 and not self.processing:
                        current_time = time.time()
                        
                        # Esperar un tiempo para asegurar detección estable
                        if current_time - self.last_detection_time > TERMINAL_CONFIG["face_detection_timeout"]:
                            self.last_detection_time = current_time
                            self.process_verification(frame)
                    
                    time.sleep(0.1)  # Pequeña pausa para no sobrecargar
                    
                except Exception as e:
                    print(f"Error en camera_loop: {e}")
                    time.sleep(1)
                    
        except Exception as e:
            print(f"Error crítico en cámara: {e}")
            self.ui.show_error("Error en cámara")
    
    def process_verification(self, frame):
        """Procesa la verificación facial"""
        if self.processing:
            return
            
        self.processing = True
        
        def verify():
            try:
                self.ui.show_message("Procesando...", '#f39c12')
                
                # Convertir frame a bytes para envío
                success, img_encoded = cv2.imencode('.jpg', frame)
                if not success:
                    raise Exception("Error al codificar imagen")
                
                img_bytes = img_encoded.tobytes()
                
                if self.is_online:
                    # Modo online: usar API
                    result = self.api_client.verify_face_auto(img_bytes)
                    
                    if result.get('verified', False):
                        message = result.get('mensaje', 'Verificación exitosa')
                        self.ui.show_success(message)
                        print(f"Verificación exitosa: {result}")
                    else:
                        self.ui.show_error("Verificación fallida")
                        print(f"Verificación fallida: {result}")
                        
                else:
                    # Modo offline: usar lector de huellas (por implementar)
                    self.ui.show_error("Modo offline no disponible aún")
                    print("Modo offline: Función pendiente de implementar")
                    
            except Exception as e:
                error_msg = f"Error: {str(e)}"
                self.ui.show_error(error_msg)
                print(f"Error en verificación: {e}")
                
            finally:
                self.processing = False
        
        # Ejecutar verificación en thread separado
        thread = threading.Thread(target=verify, daemon=True)
        thread.start()
    
    def ui_update_loop(self):
        """Loop para actualizar la UI con frames de cámara"""
        def update():
            try:
                while True:
                    try:
                        frame = self.frame_queue.get(timeout=0.1)
                        self.ui.update_camera_frame(frame)
                    except queue.Empty:
                        pass
                    except Exception as e:
                        print(f"Error actualizando UI: {e}")
                    
                    time.sleep(0.033)  # ~30 FPS
            except Exception as e:
                print(f"Error en ui_update_loop: {e}")
        
        thread = threading.Thread(target=update, daemon=True)
        thread.start()
    
    def run(self):
        """Ejecuta la aplicación terminal"""
        print("Iniciando Terminal BioEntry...")
        
        try:
            # Iniciar threads
            self.check_online_status()
            
            # Iniciar loop de actualización de UI
            self.ui_update_loop()
            
            # Iniciar cámara en thread separado
            camera_thread = threading.Thread(target=self.camera_loop, daemon=True)
            camera_thread.start()
            
            # Ejecutar UI (thread principal)
            self.ui.run()
            
        except KeyboardInterrupt:
            print("\nDeteniendo terminal...")
        except Exception as e:
            print(f"Error crítico: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Limpia recursos al cerrar"""
        try:
            if hasattr(self, 'picam2'):
                self.picam2.stop()
            print("Terminal terminado correctamente")
        except:
            pass

if __name__ == "__main__":
    # Verificar que estamos en Raspberry Pi
    try:
        from picamera2 import Picamera2
    except ImportError:
        print("Error: Este código está diseñado para Raspberry Pi con PiCamera")
        print("Para testing en PC, usar una versión modificada sin PiCamera")
        exit(1)
    
    terminal = BioEntryTerminal()
    terminal.run()