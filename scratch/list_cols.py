import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def list_cols():
    try:
        with connections['production'].cursor() as cursor:
            cursor.execute("SELECT TOP 1 * FROM Tman050")
            cols = [col[0] for col in cursor.description]
            print(cols)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_cols()
