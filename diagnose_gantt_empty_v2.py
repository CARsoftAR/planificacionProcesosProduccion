import os
import django
import sys
from datetime import datetime

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data
from produccion.models import Scenario, PlannedTask
from produccion.services import get_planificacion_data

class MockRequest:
    def __init__(self, projects):
        self.GET = {'proyectos': projects, 'plan_mode': 'manual'}
        self.session = {}
        self.user = 'debug'

def run_diagnose():
    # Projects from screenshot
    test_projects = '26-021, 26-028, 23-037'
    print(f"--- Diagnosing Projects: {test_projects} ---")
    
    proyectos_list = [p.strip() for p in test_projects.split(',')]
    
    # 1. Check PlannedTask entries
    scenario = Scenario.objects.filter(es_principal=True).first()
    print(f"Active Scenario: {scenario.nombre} (ID: {scenario.id})")
    
    planned_all = PlannedTask.objects.filter(scenario=scenario)
    print(f"Total PlannedTask for scenario: {planned_all.count()}")
    
    planned_with_proj = PlannedTask.objects.filter(scenario=scenario, proyecto_code__in=proyectos_list)
    print(f"PlannedTask matching these projects: {planned_with_proj.count()}")
    
    if planned_all.exists() and planned_with_proj.count() == 0:
        print("WARNING: PlannedTask entries exist but NONE match the project codes!")
        print("Sample project codes in PlannedTask:")
        print(list(planned_all.values_list('proyecto_code', flat=True).distinct()[:5]))

    # 2. Check get_planificacion_data behavior (Exclude Completed vs Include)
    filtros = {'proyectos': proyectos_list}
    data_inc = get_planificacion_data(filtros, exclude_completed=False)
    data_exc = get_planificacion_data(filtros, exclude_completed=True)
    
    print(f"\nERP Data (Include Completed): {len(data_inc)}")
    print(f"ERP Data (Exclude Completed): {len(data_exc)}")
    
    if len(data_inc) > len(data_exc):
        diff = len(data_inc) - len(data_exc)
        print(f"INFO: {diff} tasks are filtered out because they are marked as completed/anulada/cerrada in ERP.")
        # Show some of them
        exc_ids = {t['Idorden'] for t in data_exc}
        filtered = [t for t in data_inc if t['Idorden'] not in exc_ids]
        for t in filtered[:5]:
            print(f"  Filtered Task {t['Idorden']}: Status {t.get('Estadod')} - Pendiente {t.get('cantidad_pendiente')}")

    # 3. Test the specific filtering logic in gantt_logic.py
    print("\n--- Testing gantt_logic.py filtering logic ---")
    planned_ids = list(PlannedTask.objects.filter(
        scenario=scenario,
        proyecto_code__in=proyectos_list
    ).values_list('id_orden', flat=True))
    
    if planned_ids:
        print(f"Found {len(planned_ids)} planned IDs by project filter.")
        deps_filter = {'id_orden_in': planned_ids}
    else:
        print("No planned IDs found by project filter. Falling back to project list filter.")
        deps_filter = {'proyectos': proyectos_list}
    
    tasks_found = get_planificacion_data(deps_filter, exclude_completed=True)
    print(f"Tasks found for Gantt: {len(tasks_found)}")

if __name__ == "__main__":
    run_diagnose()
