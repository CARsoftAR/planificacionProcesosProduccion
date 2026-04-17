import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def debug_op_47635():
    try:
        with connections['production'].cursor() as cursor:
            sql = """
            SELECT T.IdOrden, T.Idmaquina, M.MAQUINAD, T.Articulo
            FROM Tman050 T
            LEFT JOIN Tman010 M ON T.Idmaquina = M.Idmaquina
            WHERE T.IdOrden = 47635
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            print("--- Debug 47635 ---")
            for r in rows:
                print(r)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_op_47635()
