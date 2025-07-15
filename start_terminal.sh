#!/bin/bash

# Script de inicio para Terminal BioEntry
# Para Raspberry Pi con pantalla táctil 800x400

echo "=== Iniciando Terminal BioEntry ==="

# Directorio del terminal
TERMINAL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$TERMINAL_DIR"

# Verificar que estamos en Raspberry Pi
if ! grep -q "Raspberry Pi" /proc/cpuinfo 2>/dev/null; then
    echo "Advertencia: No se detectó Raspberry Pi"
fi

# Verificar Python 3
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 no está instalado"
    exit 1
fi

# Verificar dependencias críticas
echo "Verificando dependencias..."

# OpenCV
python3 -c "import cv2; print(f'OpenCV: {cv2.__version__}')" 2>/dev/null || {
    echo "Error: OpenCV no está instalado"
    echo "Instalar con: sudo apt install python3-opencv"
    exit 1
}

# PiCamera2
python3 -c "import picamera2; print('PiCamera2: OK')" 2>/dev/null || {
    echo "Error: PiCamera2 no está instalado"
    echo "Instalar con: sudo apt install python3-picamera2"
    exit 1
}

# Tkinter
python3 -c "import tkinter; print('Tkinter: OK')" 2>/dev/null || {
    echo "Error: Tkinter no está instalado"
    echo "Instalar con: sudo apt install python3-tk"
    exit 1
}

# Crear directorio de logs si no existe
mkdir -p logs

# Configurar variables de entorno para pantalla táctil
export DISPLAY=:0
export XDG_RUNTIME_DIR=/run/user/$(id -u)

# Configurar rotación de pantalla si es necesario (opcional)
# xrandr --output DSI-1 --rotate left 2>/dev/null || true

# Deshabilitar cursor del mouse (opcional para pantalla táctil)
# unclutter -idle 0.1 -root &

echo "Iniciando aplicación terminal..."
echo "Presiona Ctrl+C para detener"

# Logging con timestamp
LOG_FILE="logs/terminal_$(date +%Y%m%d_%H%M%S).log"

# Ejecutar aplicación con logging
python3 terminal_app.py 2>&1 | tee "$LOG_FILE"

echo "Terminal finalizado"