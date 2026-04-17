import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def debug_task_formulas():
    try:
        with connections['production'].cursor() as cursor:
            sql = """
            SELECT T.IdOrden, T.Formula, T.Articulo, T.Descri
            FROM Tman050 T
            WHERE T.IdOrden IN (47631, 47632, 47634, 47636, 47647, 47648)
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            print("--- Task Formula Debug ---")
            for r in rows:
                print(r)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_task_formulas()
