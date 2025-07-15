# Terminal BioEntry - Raspberry Pi

Terminal de acceso con reconocimiento facial para Raspberry Pi con pantalla táctil 800x400 vertical.

## Características

### Modo Online
- ✅ **Identificación automática**: No requiere cédula ni selección de entrada/salida
- ✅ **Detección facial en tiempo real**: Usando OpenCV + Haar Cascades
- ✅ **Verificación por API**: Usa endpoint `/verify-terminal/auto`
- ✅ **Interfaz táctil**: Optimizada para pantalla 800x400 vertical
- ✅ **Estado de conexión**: Indica online/offline en tiempo real

### Modo Offline (Pendiente)
- 🔄 **Lector de huellas AS608**: Para verificación sin conexión
- 🔄 **Base de datos local**: SQLite para usuarios y registros
- 🔄 **Sincronización**: Auto-sync cuando se recupera conexión

## Requisitos de Hardware

- **Raspberry Pi 4** (recomendado) o Pi 3B+
- **Cámara**: Pi Camera Module v2 o compatible
- **Pantalla**: LCD táctil 4" 800x400 (vertical)
- **Lector de huellas**: AS608 (para modo offline)
- **Memoria**: MicroSD de al menos 16GB

## Instalación

### 1. Preparar Raspberry Pi OS

```bash
# Actualizar sistema
sudo apt update && sudo apt upgrade -y

# Instalar dependencias del sistema
sudo apt install -y python3-pip python3-opencv python3-tk python3-picamera2
sudo apt install -y git sqlite3 unclutter

# Habilitar cámara
sudo raspi-config
# Ir a: Interface Options > Camera > Enable
```

### 2. Clonar y configurar terminal

```bash
# Ir al directorio del proyecto
cd /home/pi/BioEntry/terminal_firmware2

# Instalar dependencias Python
pip3 install -r requirements.txt

# Verificar instalación
python3 -c "import cv2, picamera2, tkinter; print('Dependencias OK')"
```

### 3. Configuración

Editar `config.json`:

```json
{
  "terminal": {
    "terminal_id": "TERMINAL_001",
    "api_key": "terminal_key_001",
    "location": "Entrada Principal"
  },
  "api": {
    "base_url": "http://IP_DEL_SERVIDOR:8000"
  }
}
```

### 4. Configurar API

En el servidor, agregar la terminal a `config.py`:

```python
API_KEYS = {
    "TERMINAL_001": "terminal_key_001"
}
```

## Uso

### Inicio Manual

```bash
cd /home/pi/BioEntry/terminal_firmware2
./start_terminal.sh
```

### Inicio Automático

Crear servicio systemd:

```bash
sudo nano /etc/systemd/system/bioentry-terminal.service
```

```ini
[Unit]
Description=BioEntry Terminal
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/BioEntry/terminal_firmware2
ExecStart=/home/pi/BioEntry/terminal_firmware2/start_terminal.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable bioentry-terminal.service
sudo systemctl start bioentry-terminal.service
```

## Interfaz de Usuario

### Pantalla Principal
- **Preview de cámara**: Muestra video en tiempo real con detección facial
- **Mensajes**: Estado actual y resultados de verificación
- **Indicadores**: Estado online/offline y hora actual

### Flujo de Verificación
1. Usuario se coloca frente a la cámara
2. Sistema detecta cara automáticamente
3. Captura imagen después de 3 segundos de detección estable
4. Envía a API para identificación y verificación
5. Muestra resultado en pantalla

### Códigos de Color
- 🟢 **Verde**: Verificación exitosa
- 🔴 **Rojo**: Error o verificación fallida  
- 🟡 **Amarillo**: Procesando
- ⚪ **Blanco**: Estado normal

## Configuración de Pantalla

### Para pantalla táctil 800x400 vertical:

```bash
# Editar config.txt
sudo nano /boot/config.txt

# Agregar configuración de pantalla
hdmi_group=2
hdmi_mode=87
hdmi_cvt=800 400 60 6 0 0 0
display_rotate=1
```

### Rotación automática:

```bash
# En el script de inicio o .bashrc
export DISPLAY=:0
xrandr --output DSI-1 --rotate left
```

## Logs y Debugging

### Ver logs en tiempo real:
```bash
tail -f logs/terminal_$(date +%Y%m%d)*.log
```

### Logs del sistema:
```bash
sudo journalctl -u bioentry-terminal.service -f
```

### Debug de cámara:
```bash
# Probar cámara básica
python3 face_detection.py

# Verificar dispositivos
ls /dev/video*
v4l2-ctl --list-devices
```

## API Endpoints Utilizados

- `GET /version`: Verificar conexión
- `POST /verify-terminal/auto`: Verificación automática

### Ejemplo de request:

```bash
curl -X POST "http://IP:8000/verify-terminal/auto" \
  -H "X-API-Key: terminal_key_001" \
  -F "terminal_id=TERMINAL_001" \
  -F "image=@capture.jpg"
```

### Ejemplo de response:

```json
{
  "record_id": "123e4567-e89b-12d3-a456-426614174000",
  "verified": true,
  "distance": 0.23,
  "cedula": "12345678",
  "nombre": "Juan Pérez",
  "tipo_registro": "entrada",
  "timestamp": "2025-01-15T10:30:00.000Z",
  "mensaje": "¡Bienvenido Juan Pérez! Registro de entrada exitoso."
}
```

## Solución de Problemas

### Cámara no detectada:
```bash
# Verificar módulo cámara
sudo modprobe bcm2835-v4l2
```

### Error de permisos:
```bash
# Agregar usuario a grupos necesarios
sudo usermod -a -G video,audio,gpio pi
```

### Pantalla táctil no responde:
```bash
# Verificar drivers
dmesg | grep -i touch
sudo apt install xserver-xorg-input-evdev
```

### Problemas de conexión:
- Verificar IP del servidor en `config.json`
- Comprobar firewall: `sudo ufw status`
- Ping al servidor: `ping IP_SERVIDOR`

## Desarrollo

### Estructura del código:
- `terminal_app.py`: Aplicación principal
- `face_detection.py`: Detección facial básica (para testing)
- `config.json`: Configuración del terminal
- `start_terminal.sh`: Script de inicio

### Para testing sin Raspberry Pi:
Crear versión mock para desarrollo en PC sin PiCamera.

## Próximas Funciones

- [ ] Integración con lector de huellas AS608
- [ ] Modo offline completo
- [ ] Sincronización automática
- [ ] Configuración remota via API
- [ ] Logs estructurados con rotación
- [ ] Actualización OTA (Over-The-Air)