import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def debug_task_status():
    try:
        with connections['production'].cursor() as cursor:
            sql = "SELECT IdOrden, Idestado, IdMaquina FROM Tman050 WHERE IdOrden IN (47647, 47648, 47649, 47650, 47651, 47652, 47634, 47636)"
            cursor.execute(sql)
            rows = cursor.fetchall()
            print("--- Task Status Debug ---")
            for r in rows:
                print(r)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_task_status()
