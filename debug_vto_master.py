import os
import django
import json
from datetime import datetime
from django.db import connections

# Setup Django
import sys
sys.path.append(r'c:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def check_raw_sql(project_code):
    print(f"Checking raw SQL for project: {project_code}")
    sql = """
    SELECT 
        T.Idorden, 
        T.Vto as TaskVto, 
        T2.Vto as MasterVto,
        T.Descri as TaskDesc,
        T2.Descri as MasterDesc
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    WHERE T2.Formula = %s
    """
    
    with connections['production'].cursor() as cursor:
        cursor.execute(sql, [project_code])
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
    for r in rows:
        print(f"  OP {r['Idorden']}: TaskVto={r['TaskVto']}, MasterVto={r['MasterVto']}")

if __name__ == "__main__":
    check_raw_sql('25-013')
    print("\n" + "="*40 + "\n")
    check_raw_sql('25-092')
