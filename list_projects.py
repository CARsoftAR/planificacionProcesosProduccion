import os
import django
import sys
from django.db import connections

# Setup Django
sys.path.append(r'c:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def list_projects():
    print("Listing projects by prefix:")
    sql = """
    SELECT DISTINCT TOP 20 Formula 
    FROM Tman050 
    WHERE MSTNMBR=0 AND Formula IS NOT NULL
    ORDER BY Formula DESC
    """
    with connections['production'].cursor() as cursor:
        cursor.execute(sql)
        for row in cursor.fetchall():
            print(f"  {row[0]}")

if __name__ == "__main__":
    list_projects()
