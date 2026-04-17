
import os
import django
import sys

# Setup paths
PROJECT_ROOT = r'c:\Sistemas ABBAMAT\planificacionProcesosProductivos EN DESARROLLO'
sys.path.append(PROJECT_ROOT)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections
from produccion.models import PlannedTask, Scenario

def test_confirm():
    project_code = '26-028'
    active_scenario = Scenario.objects.using('default').filter(es_principal=True).first()
    
    print(f"Testing for project {project_code} in scenario {active_scenario.nombre}")
    
    try:
        # Check if production connection exists
        if 'production' not in connections:
            print("ERROR: Connection 'production' not found in settings.databases")
            return
            
        with connections['production'].cursor() as cursor:
            cursor.execute("SELECT TOP 10 Idorden FROM Tman050 WHERE Proyecto = %s", [project_code])
            rows = cursor.fetchall()
            project_op_ids = [str(row[0]) for row in rows]
        
        print(f"Found {len(project_op_ids)} OPs in ERP for this project (sample).")
        if project_op_ids:
            print(f"Sample IDs: {project_op_ids[:5]}")
        
        # Test the delete query syntax (not execution)
        if project_op_ids:
            query = PlannedTask.objects.using('default').filter(
                scenario=active_scenario,
                id_orden__in=project_op_ids
            )
            print(f"Query check: {query.query}")
            
        print("Test passed without exceptions.")
    except Exception as e:
        import traceback
        print(traceback.format_exc())

if __name__ == "__main__":
    test_confirm()
