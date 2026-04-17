import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def debug_task_comparison():
    try:
        with connections['production'].cursor() as cursor:
            sql = """
            SELECT T.IdOrden, T.Idmaquina, M.MAQUINAD, T.MSTNMBR, T.Articulo
            FROM Tman050 T
            LEFT JOIN Tman010 M ON T.Idmaquina = M.Idmaquina
            WHERE T.IdOrden IN (47631, 47632, 47647, 47648)
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            print("--- Task Comparison Debug ---")
            for r in rows:
                print(r)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_task_comparison()
