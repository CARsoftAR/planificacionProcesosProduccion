import os
import django
from django.db import connections

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def count_tsugami_tasks():
    sql = """
    SELECT COUNT(*) as Cantidad
    FROM Tman050 T
    WHERE T.Idmaquina = 'MAC38'
    """
    
    with connections['production'].cursor() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        print(f"Total de tareas asignadas a TSUGAMI (MAC38) en SQL Server: {row[0]}")

if __name__ == "__main__":
    count_tsugami_tasks()
