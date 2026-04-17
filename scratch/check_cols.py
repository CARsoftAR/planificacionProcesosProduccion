
import os
import django
import sys

# Setup paths
PROJECT_ROOT = r'c:\Sistemas ABBAMAT\planificacionProcesosProductivos EN DESARROLLO'
sys.path.append(PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def check_cols():
    try:
        with connections['production'].cursor() as cursor:
            cursor.execute("SELECT TOP 1 * FROM Tman050")
            print(f"Columns in Tman050: {[col[0] for col in cursor.description]}")
    except Exception as e:
        print(f"ERROR: {str(e)}")

if __name__ == "__main__":
    check_cols()
