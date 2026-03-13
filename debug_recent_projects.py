import os
import django
import sys
from django.db import connections

# Setup Django
sys.path.append(r'c:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def check_recent_project(project_code):
    print(f"Checking project: {project_code}")
    sql = """
    SELECT T.Idorden, T.Vto, T.Descri
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    WHERE T2.Formula = %s
    """
    with connections['production'].cursor() as cursor:
        cursor.execute(sql, [project_code])
        for row in cursor.fetchall():
            print(f"  OP {row[0]}: Vto={row[1]}")

if __name__ == "__main__":
    check_recent_project('25-101')
    print("\n" + "="*40 + "\n")
    check_recent_project('25-102')
