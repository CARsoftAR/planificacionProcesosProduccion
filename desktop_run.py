try:
    import clr
except ImportError:
    # Diagnóstico: clr (pythonnet) no está disponible
    pass
import webview
import webview.platforms.winforms as winforms
import os
import sys
import threading
import time
import socket
from pathlib import Path

# Fix para PyInstaller
if getattr(sys, 'frozen', False):
    # Si estamos en el bundle de PyInstaller
    # BUNDLE_DIR: Donde están el código y recursos (templates/static)
    BUNDLE_DIR = Path(sys._MEIPASS).resolve()
    # BASE_DIR: Carpeta raíz de la aplicación portátil (donde reside el lanzador y la base de datos sqlite3)
    exe_dir = Path(sys.executable).resolve().parent
    if exe_dir.name == '_internal':
        BASE_DIR = exe_dir.parent
    else:
        BASE_DIR = exe_dir
    sys.path.append(str(BUNDLE_DIR))
    # Forzar que Django busque los archivos en el bundle
    os.environ['DJANGO_BUNDLE_DIR'] = str(BUNDLE_DIR)
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR
    sys.path.append(str(BASE_DIR))

# --- Inicialización de Base de Datos Persistente ---
import shutil
persistent_db = BASE_DIR / 'db.sqlite3'
# En PyInstaller la base de datos inicial empaquetada se encuentra en BUNDLE_DIR
bundled_db = BUNDLE_DIR / 'db.sqlite3'

if getattr(sys, 'frozen', False):
    # Si no existe la DB persistente en la carpeta del ejecutable o está vacía (0 bytes)
    if not persistent_db.exists() or persistent_db.stat().st_size == 0:
        if bundled_db.exists():
            print(f"[DB] Inicializando base de datos persistente desde plantilla empaquetada en {persistent_db}...")
            shutil.copy2(bundled_db, persistent_db)
        else:
            print(f"[DB WARN] No se encontró la base de datos plantilla en {bundled_db}")

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
import django
from django.core.management import call_command

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def start_django(port):
    """
    Inicia el servidor de desarrollo de Django en el hilo secundario.
    Se usa --noreload porque el recargador automático de Django choca con PyInstaller/threading.
    """
    try:
        django.setup()
        
        # Ejecutar migraciones automáticas en la DB persistente al arrancar
        print("[Django] Verificando y aplicando migraciones de base de datos...")
        try:
            call_command('migrate', interactive=False)
            print("[Django] Migraciones completadas con éxito.")
        except Exception as em:
            print(f"[Django ERROR] Error al aplicar migraciones: {em}")
            
        # Inicializar escenarios por defecto
        try:
            from init_scenarios import init_scenarios
            print("[Django] Inicializando escenarios por defecto...")
            init_scenarios()
        except Exception as es:
            print(f"[Django WARN] No se pudieron inicializar los escenarios: {es}")

        print(f"[Django] Iniciando en puerto {port}...")
        call_command('runserver', f'127.0.0.1:{port}', '--noreload')
    except Exception as e:
        print(f"[Django ERROR] No se pudo iniciar el servidor: {e}")
        import traceback
        traceback.print_exc()

SPLASH_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {
            margin: 0;
            padding: 0;
            width: 100vw;
            height: 100vh;
            background: linear-gradient(135deg, #f3f4f6 0%, #e5e7eb 100%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: 'Segoe UI', system-ui, sans-serif;
            overflow: hidden;
            box-sizing: border-box;
            border: 1px solid rgba(255, 255, 255, 0.7);
        }
        .container {
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
        }
        .logo-container {
            position: relative;
            width: 80px;
            height: 80px;
            margin-bottom: 24px;
        }
        .logo-glow {
            position: absolute;
            top: -10px;
            left: -10px;
            width: 100px;
            height: 100px;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.35) 0%, rgba(168, 85, 247, 0.05) 75%);
            border-radius: 50%;
            filter: blur(12px);
            animation: pulse-glow 3s infinite ease-in-out;
        }
        .logo {
            position: absolute;
            top: 0;
            left: 0;
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, #818cf8 0%, #c084fc 100%);
            border-radius: 24px;
            display: flex;
            justify-content: center;
            align-items: center;
            box-shadow: 0 10px 25px rgba(129, 140, 248, 0.2);
            animation: float 4s infinite ease-in-out;
        }
        .logo-icon {
            color: white;
            font-size: 36px;
            font-weight: 800;
        }
        h1 {
            margin: 0 0 8px 0;
            font-size: 26px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: #1f2937;
        }
        h1 span {
            color: #6366f1;
        }
        p {
            margin: 0;
            font-size: 14px;
            color: #6b7280;
            font-weight: 500;
        }
        .loader-track {
            width: 200px;
            height: 4px;
            background: rgba(99, 102, 241, 0.1);
            border-radius: 10px;
            margin-top: 32px;
            overflow: hidden;
            position: relative;
        }
        .loader-bar {
            width: 80px;
            height: 100%;
            background: linear-gradient(90deg, #818cf8, #c084fc);
            border-radius: 10px;
            position: absolute;
            animation: loading 1.8s infinite ease-in-out;
        }
        @keyframes float {
            0% { transform: translateY(0px) rotate(0deg); }
            50% { transform: translateY(-8px) rotate(2deg); }
            100% { transform: translateY(0px) rotate(0deg); }
        }
        @keyframes pulse-glow {
            0% { transform: scale(0.9); opacity: 0.5; }
            50% { transform: scale(1.2); opacity: 0.9; }
            100% { transform: scale(0.9); opacity: 0.5; }
        }
        @keyframes loading {
            0% { left: -80px; }
            50% { left: 100px; width: 100px; }
            100% { left: 200px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo-container">
            <div class="logo-glow"></div>
            <div class="logo">
                <div class="logo-icon">A</div>
            </div>
        </div>
        <h1>ABBAMAT <span>PROD</span></h1>
        <p>Iniciando sistema de planificación...</p>
        <div class="loader-track">
            <div class="loader-bar"></div>
        </div>
    </div>
</body>
</html>
"""

def main():
    # Obtener puerto dinámico para evitar conflictos si hay otra cosa en el 8000
    port = get_free_port()
    
    # Arrancar Django en un Daemon Thread
    django_thread = threading.Thread(target=start_django, args=(port,), daemon=True)
    django_thread.start()
    
    # Crear ventana de splash (cargando)
    splash = webview.create_window(
        'ABBAMAT PROD - Cargando...',
        html=SPLASH_HTML,
        width=500,
        height=320,
        frameless=True,
        easy_drag=True,
        on_top=True
    )
    
    def check_and_launch():
        # Esperamos 3 segundos a que Django levante
        time.sleep(3)
        
        # Crear ventana principal
        url = f"http://127.0.0.1:{port}"
        print(f"[WebView] Abriendo {url}...")
        
        webview.create_window(
            'ABBAMAT PROD - Desktop',
            url,
            width=1280,
            height=800,
            min_size=(800, 600),
            frameless=False
        )
        
        # Cerrar el splash
        splash.destroy()
        
    webview.start(check_and_launch)

if __name__ == '__main__':
    main()
