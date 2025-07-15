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

def load_config():
    """Carga configuración desde archivo JSON"""
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print("Archivo config.json no encontrado, usando configuración por defecto")
        return {
            "terminal": {
                "terminal_id": "TERMINAL_001",
                "api_key": "terminal_key_001"
            },
            "api": {
                "base_url": "http://localhost:8000",
                "timeout": 10
            },
            "camera": {
                "resolution": [640, 480],
                "face_detection_timeout": 3.0
            },
            "offline": {
                "database_path": "./terminal_offline.db"
            }
        }

# Cargar configuración
CONFIG = load_config()

# Configuración de la terminal (compatibilidad)
TERMINAL_CONFIG = {
    "terminal_id": CONFIG["terminal"]["terminal_id"],
    "api_key": CONFIG["terminal"]["api_key"],
    "api_base_url": CONFIG["api"]["base_url"],
    "camera_resolution": tuple(CONFIG["camera"]["resolution"]),
    "face_cascade_paths": [
        '/usr/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
        '/usr/share/opencv/haarcascades/haarcascade_frontalface_default.xml',
        '/usr/local/share/opencv4/haarcascades/haarcascade_frontalface_default.xml',
        'haarcascade_frontalface_default.xml'
    ],
    "face_detection_timeout": CONFIG["camera"]["face_detection_timeout"],
    "connection_timeout": CONFIG["api"]["timeout"],
    "offline_db_path": CONFIG["offline"]["database_path"]
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
            # Rectángulo principal verde
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 3)
            
            # Rectángulo interior semi-transparente
            overlay = frame.copy()
            cv2.rectangle(overlay, (x, y), (x+w, y+h), (0, 255, 0), -1)
            cv2.addWeighted(overlay, 0.1, frame, 0.9, 0, frame)
            
            # Texto más grande y visible
            font_scale = 1.0
            thickness = 2
            text = 'CARA DETECTADA'
            
            # Calcular posición del texto centrado
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)[0]
            text_x = x + (w - text_size[0]) // 2
            text_y = y - 15 if y > 30 else y + h + 25
            
            # Fondo del texto
            cv2.rectangle(frame, (text_x - 5, text_y - text_size[1] - 5), 
                         (text_x + text_size[0] + 5, text_y + 5), (0, 0, 0), -1)
            
            # Texto
            cv2.putText(frame, text, (text_x, text_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 255, 0), thickness)
            
            # Esquinas de enfoque
            corner_length = 20
            corner_thickness = 4
            
            # Esquina superior izquierda
            cv2.line(frame, (x, y), (x + corner_length, y), (0, 255, 0), corner_thickness)
            cv2.line(frame, (x, y), (x, y + corner_length), (0, 255, 0), corner_thickness)
            
            # Esquina superior derecha
            cv2.line(frame, (x + w, y), (x + w - corner_length, y), (0, 255, 0), corner_thickness)
            cv2.line(frame, (x + w, y), (x + w, y + corner_length), (0, 255, 0), corner_thickness)
            
            # Esquina inferior izquierda
            cv2.line(frame, (x, y + h), (x + corner_length, y + h), (0, 255, 0), corner_thickness)
            cv2.line(frame, (x, y + h), (x, y + h - corner_length), (0, 255, 0), corner_thickness)
            
            # Esquina inferior derecha
            cv2.line(frame, (x + w, y + h), (x + w - corner_length, y + h), (0, 255, 0), corner_thickness)
            cv2.line(frame, (x + w, y + h), (x + w, y + h - corner_length), (0, 255, 0), corner_thickness)
            
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
        self.screen_width = 800  # Valor por defecto
        self.screen_height = 400  # Valor por defecto
        self.setup_ui()
        self.camera_running = False
        
    def setup_ui(self):
        """Configura la interfaz principal para pantalla completa vertical"""
        # Configuración de ventana para pantalla completa
        self.root.title("Terminal BioEntry")
        self.root.configure(bg='black')
        
        # Configurar pantalla completa real
        self.root.attributes('-fullscreen', True)
        self.root.overrideredirect(True)
        
        # Obtener dimensiones reales de la pantalla
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        print(f"Pantalla detectada: {screen_width}x{screen_height}")
        
        # Actualizar dimensiones para usar en la aplicación
        self.screen_width = screen_width
        self.screen_height = screen_height
        
        # Label para cámara de fondo (pantalla completa usando dimensiones reales)
        self.camera_label = tk.Label(
            self.root,
            text="Iniciando cámara...",
            bg='black',
            fg='white',
            font=('Arial', 20)
        )
        self.camera_label.place(x=0, y=0, width=screen_width, height=screen_height)
        
        # Frame superior transparente para título y estado
        top_frame = tk.Frame(self.root, bg='black', height=120)
        top_frame.place(x=0, y=0, width=screen_width, height=120)
        
        # Título superpuesto
        title_label = tk.Label(
            top_frame,
            text="TERMINAL\nDE ACCESO",
            font=('Arial', 18, 'bold'),
            bg='black',
            fg='white',
            relief=tk.FLAT,
            justify=tk.CENTER
        )
        title_label.pack(pady=(15, 0))
        
        # Hora (centrado en la parte superior)
        self.time_label = tk.Label(
            top_frame,
            text="",
            font=('Arial', 12, 'bold'),
            bg='black',
            fg='white',
            justify=tk.CENTER
        )
        self.time_label.place(x=screen_width//2-50, y=85)
        
        # Estado de conexión (esquina superior derecha)
        self.online_status = tk.Label(
            self.root,
            text="● OFFLINE",
            font=('Arial', 11, 'bold'),
            bg='black',
            fg='#e74c3c'
        )
        self.online_status.place(x=screen_width-120, y=15)
        
        # Frame inferior para mensajes
        bottom_frame = tk.Frame(self.root, bg='black', height=140)
        bottom_frame.place(x=0, y=screen_height-140, width=screen_width, height=140)
        
        # Label para mensajes superpuesto
        self.message_label = tk.Label(
            bottom_frame,
            text="COLÓQUESE FRENTE\nA LA CÁMARA",
            font=('Arial', 16, 'bold'),
            bg='black',
            fg='#00ff00',
            wraplength=screen_width-50,
            justify=tk.CENTER
        )
        self.message_label.pack(expand=True)
        
        # Botón de salida oculto (esquina inferior derecha)
        exit_button = tk.Button(
            self.root,
            text="×",
            font=('Arial', 16, 'bold'),
            bg='#e74c3c',
            fg='white',
            width=2,
            height=1,
            relief=tk.FLAT,
            command=self.exit_app
        )
        exit_button.place(x=screen_width-50, y=screen_height-50)
        
        # Vincular teclas de escape
        self.root.bind('<Escape>', lambda e: self.exit_app())
        self.root.bind('<Key-q>', lambda e: self.exit_app())
        self.root.focus_set()  # Permitir captura de teclas
        
        # Actualizar tiempo cada segundo
        self.update_time()
    
    def exit_app(self):
        """Cierra la aplicación"""
        self.root.quit()
        
    def update_time(self):
        """Actualiza la hora en pantalla"""
        current_time = datetime.now().strftime("%H:%M")
        current_date = datetime.now().strftime("%d/%m")
        self.time_label.config(text=f"{current_time}\n{current_date}")
        self.root.after(1000, self.update_time)
    
    def update_status(self, online: bool):
        """Actualiza el estado de conexión"""
        if online:
            self.online_status.config(text="● ONLINE", fg='#00ff00')
        else:
            self.online_status.config(text="● OFFLINE", fg='#ff0000')
    
    def show_message(self, message: str, color: str = '#00ff00'):
        """Muestra un mensaje en pantalla"""
        self.message_label.config(text=message.upper(), fg=color)
        
    def show_success(self, message: str):
        """Muestra mensaje de éxito"""
        self.show_message(message, '#00ff00')
        self.root.after(3000, lambda: self.show_message("COLÓQUESE FRENTE A LA CÁMARA"))
        
    def show_error(self, message: str):
        """Muestra mensaje de error"""
        self.show_message(message, '#ff0000')
        self.root.after(3000, lambda: self.show_message("COLÓQUESE FRENTE A LA CÁMARA"))
    
    def update_camera_frame(self, frame):
        """Actualiza el frame de la cámara en pantalla completa"""
        # Redimensionar frame para pantalla completa usando dimensiones reales
        frame_resized = cv2.resize(frame, (self.screen_width, self.screen_height))
        
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
        """Configura la cámara para pantalla 400x800 vertical"""
        # Configurar cámara con resolución optimizada para vertical
        config = self.picam2.create_preview_configuration(
            main={"size": (480, 640)}  # Resolución vertical para mejor calidad
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