import os
import django
import sys
from django.db import connections

# Setup Django
sys.path.append(r'c:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def check_creation_date(project_code):
    print(f"Checking details for project: {project_code}")
    sql = """
    SELECT T.Idorden, T.Fecha, T.VTO, T.Descri, T.Detalle, T.MSTNMBR
    FROM Tman050 T
    WHERE T.Formula = %s AND T.MSTNMBR = T.Idorden
    """
    with connections['production'].cursor() as cursor:
        cursor.execute(sql, [project_code])
        row = cursor.fetchone()
        if row:
            print(f"  OP {row[0]}:")
            print(f"    Fecha: {row[1]}")
            print(f"    Vto:   {row[2]}")
            print(f"    Desc:  {row[3]}")
            print(f"    Detail: {row[4]}")
        else:
            print("  Project header not found.")

if __name__ == "__main__":
    check_creation_date('25-013')
    print("-" * 20)
    check_creation_date('25-101')
