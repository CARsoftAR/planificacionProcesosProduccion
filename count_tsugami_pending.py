import os
import django
from django.db import connections

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def count_tsugami_pending_tasks():
    # Use the same logic as services.py
    sql = """
    SELECT COUNT(*) as Cantidad
    FROM Tman050 T
    INNER JOIN tman050 T2 ON T.MSTNMBR = T2.IdOrden
    WHERE T.Idmaquina = 'MAC38'
      AND T.Idestado NOT IN ('3', '4', '5')
      AND T2.Idestado NOT IN ('3', '4', '5')
    """
    
    with connections['production'].cursor() as cursor:
        cursor.execute(sql)
        row = cursor.fetchone()
        print(f"Tareas PENDIENTES asignadas a TSUGAMI (MAC38): {row[0]}")

if __name__ == "__main__":
    count_tsugami_pending_tasks()
