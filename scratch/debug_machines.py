import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def debug_machines():
    try:
        with connections['production'].cursor() as cursor:
            sql = "SELECT Idmaquina, MAQUINAD FROM Tman010"
            cursor.execute(sql)
            rows = cursor.fetchall()
            print("--- Machine Master Debug ---")
            for r in rows:
                print(r)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_machines()
