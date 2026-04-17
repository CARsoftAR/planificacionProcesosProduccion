import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def debug_task_details():
    try:
        with connections['production'].cursor() as cursor:
            sql = """
            SELECT T.IdOrden, T.Idestado, T.Idmaquina, M.MAQUINAD, T.Cantidad, T.Cantidadpp, T.Articulo
            FROM Tman050 T
            LEFT JOIN Tman010 M ON T.Idmaquina = M.Idmaquina
            WHERE T.IdOrden IN (47632, 47647, 47648, 47634, 47636, 47649, 47650)
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            print("--- Detailed Task Debug ---")
            for r in rows:
                print(r)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_task_details()
