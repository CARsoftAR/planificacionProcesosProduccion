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
    # BASE_DIR: Donde está el ejecutable (para la base de datos persistente)
    BASE_DIR = Path(sys.executable).resolve().parent
    sys.path.append(str(BUNDLE_DIR))
    # Forzar que Django busque los archivos en el bundle
    os.environ['DJANGO_BUNDLE_DIR'] = str(BUNDLE_DIR)
else:
    BASE_DIR = Path(__file__).resolve().parent
    BUNDLE_DIR = BASE_DIR
    sys.path.append(str(BASE_DIR))

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
        print(f"[Django] Iniciando en puerto {port}...")
        call_command('runserver', f'127.0.0.1:{port}', '--noreload')
    except Exception as e:
        print(f"[Django ERROR] No se pudo iniciar el servidor: {e}")
        import traceback
        traceback.print_exc()

def main():
    # Obtener puerto dinámico para evitar conflictos si hay otra cosa en el 8000
    port = get_free_port()
    
    # Arrancar Django en un Daemon Thread
    django_thread = threading.Thread(target=start_django, args=(port,), daemon=True)
    django_thread.start()
    
    # Esperar 2 segundos para dar tiempo a que Django inicialice la base de datos y sirva las páginas
    time.sleep(2)
    
    # Abrir la ventana de escritorio con pywebview
    url = f"http://127.0.0.1:{port}"
    print(f"[WebView] Abriendo {url}...")
    
    window = webview.create_window(
        'ABBAMAT PROD - Desktop',
        url,
        width=1280,
        height=800,
        min_size=(800, 600),
        frameless=False
    )
    
    # Iniciar el motor web (Chrome/Edge en Windows)
    webview.start()

if __name__ == '__main__':
    main()
