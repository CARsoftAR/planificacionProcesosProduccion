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
            background-color: rgb(11, 15, 25);
            background-image: 
                radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.15) 0%, transparent 40%),
                radial-gradient(circle at 90% 80%, rgba(168, 85, 247, 0.12) 0%, transparent 40%);
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            overflow: hidden;
            box-sizing: border-box;
        }
        .container {
            text-align: center;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            padding: 2rem;
        }
        .logo-wrapper {
            position: relative;
            margin-bottom: 2.5rem;
        }
        .loader-ring {
            width: 130px;
            height: 130px;
            border-radius: 50%;
            border: 3px solid transparent;
            border-top-color: rgb(99, 102, 241);
            border-bottom-color: rgb(168, 85, 247);
            animation: spin 3s linear infinite;
        }
        .loader-ring-inner {
            position: absolute;
            top: 10px;
            left: 10px;
            width: 110px;
            height: 110px;
            border-radius: 50%;
            border: 3px solid transparent;
            border-left-color: rgb(236, 72, 153);
            border-right-color: rgb(59, 130, 246);
            animation: spin-reverse 2s linear infinite;
        }
        .logo-center {
            position: absolute;
            top: 25px;
            left: 25px;
            width: 80px;
            height: 80px;
            background: linear-gradient(135deg, rgb(30, 27, 75) 0%, rgb(15, 23, 42) 100%);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 50%;
            display: flex;
            justify-content: center;
            align-items: center;
            box-shadow: 0 0 30px rgba(99, 102, 241, 0.25);
        }
        .logo-icon {
            color: rgb(255, 255, 255);
            font-size: 38px;
            font-weight: 800;
            text-shadow: 0 0 10px rgba(99, 102, 241, 0.5);
            letter-spacing: -1px;
        }
        h1 {
            margin: 0 0 12px 0;
            font-size: 32px;
            font-weight: 800;
            letter-spacing: -0.5px;
            color: rgb(255, 255, 255);
            text-shadow: 0 2px 10px rgba(0,0,0,0.5);
        }
        h1 span {
            background: linear-gradient(90deg, rgb(99, 102, 241), rgb(168, 85, 247), rgb(236, 72, 153));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        p {
            margin: 0 0 8px 0;
            font-size: 14px;
            color: rgb(148, 163, 184);
            font-weight: 500;
            letter-spacing: 0.5px;
        }
        .status-pill {
            background: rgba(99, 102, 241, 0.1);
            border: 1px solid rgba(99, 102, 241, 0.2);
            padding: 6px 18px;
            border-radius: 50px;
            font-size: 11px;
            color: rgb(199, 210, 254);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1.5px;
            display: flex;
            align-items: center;
            gap: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            animation: pulse 2s infinite ease-in-out;
        }
        .status-dot {
            width: 6px;
            height: 6px;
            background-color: rgb(52, 211, 153);
            border-radius: 50%;
            box-shadow: 0 0 8px rgb(52, 211, 153);
        }
        .footer-brand {
            position: absolute;
            bottom: 30px;
            font-size: 12px;
            color: rgba(148, 163, 184, 0.4);
            letter-spacing: 2px;
            font-weight: 600;
            text-transform: uppercase;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        @keyframes spin-reverse {
            0% { transform: rotate(360deg); }
            100% { transform: rotate(0deg); }
        }
        @keyframes pulse {
            0% { opacity: 0.7; transform: scale(0.98); }
            50% { opacity: 1; transform: scale(1); }
            100% { opacity: 0.7; transform: scale(0.98); }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo-wrapper">
            <div class="loader-ring"></div>
            <div class="loader-ring-inner"></div>
            <div class="logo-center">
                <div class="logo-icon" style="font-size: 24px; font-weight: 900; letter-spacing: 0.5px;">PLIF</div>
            </div>
        </div>
        <h1>ABBAMAT <span>PLIF</span></h1>
        <p>Optimizando secuencias de fabricación</p>
        <div style="height: 20px;"></div>
        <div class="status-pill">
            <div class="status-dot"></div>
            <span>Inicializando Sistema</span>
        </div>
    </div>
    <div class="footer-brand">Tecnología de Procesos</div>
</body>
</html>
"""

def main():
    # Obtener puerto dinámico para evitar conflictos si hay otra cosa en el 8000
    port = get_free_port()
    
    # Arrancar Django en un Daemon Thread
    django_thread = threading.Thread(target=start_django, args=(port,), daemon=True)
    django_thread.start()
    
    # Intentar obtener las dimensiones de la pantalla para el splash frameless
    try:
        screens = webview.screens
        if screens:
            screen_width = screens[0].width
            screen_height = screens[0].height
        else:
            screen_width = 1920
            screen_height = 1080
    except Exception:
        screen_width = 1920
        screen_height = 1080

    # Crear ventana de splash (cargando) con tamaño inicial estándar, oculta por defecto
    splash = webview.create_window(
        'ABBAMAT PLIF - Cargando...',
        html=SPLASH_HTML,
        width=800,
        height=600,
        frameless=True,
        easy_drag=True,
        on_top=True,
        hidden=True,
        background_color='#0b0f19'
    )
    
    def check_and_launch():
        # Forzar redimensionamiento y maximización del splash programáticamente
        try:
            screens = webview.screens
            if screens:
                splash.resize(screens[0].width, screens[0].height)
            splash.maximize()
        except Exception:
            pass
        
        # Mostrar el splash ya maximizado y listo
        splash.show()

        # Esperamos 6 segundos a que Django levante
        time.sleep(6)
        
        # Crear ventana principal oculta
        url = f"http://127.0.0.1:{port}"
        print(f"[WebView] Abriendo {url}...")
        
        main_win = webview.create_window(
            'ABBAMAT PLIF - Desktop',
            url,
            width=1280,
            height=800,
            min_size=(800, 600),
            frameless=False,
            maximized=True,
            hidden=True,
            background_color='#0b0f19'
        )
        
        def show_main():
            main_win.show()
            try:
                splash.destroy()
            except Exception:
                pass
        
        # Conectar al evento loaded de pywebview
        main_win.events.loaded += show_main
        
    webview.start(check_and_launch)

if __name__ == '__main__':
    main()
