import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def debug_macros():
    proyecto = "26-028"
    sql = "SELECT DISTINCT Articulo, Descri, IsMacro, MacroPK, MSTNMBR, IdOrden FROM Tman050 WHERE Formula LIKE %s"
    try:
        with connections['production'].cursor() as cursor:
            cursor.execute(sql, [f"%{proyecto}%"])
            rows = cursor.fetchall()
            print(f"Total rows for {proyecto}: {len(rows)}")
            for r in rows:
                print(r)
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_macros()
