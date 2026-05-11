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
    # 1. Test projects from the screenshot
    test_projects = '26-021, 23-037'
    print(f"--- Diagnosing Projects: {test_projects} ---")
    
    # 2. Check raw data first
    filtros = {'proyectos': [p.strip() for p in test_projects.split(',')]}
    raw_data = get_planificacion_data(filtros, exclude_completed=True)
    print(f"Raw tasks found for projects: {len(raw_data)}")
    
    if raw_data:
        for t in raw_data[:5]:
            print(f"  Task {t.get('Idorden')}: {t.get('Descri')} - Machine: {t.get('MAQUINAD')} - Time Proceso: {t.get('Tiempo_Proceso')}")
    
    # 3. Check if they are in PlannedTask for the active scenario
    scenario = Scenario.objects.filter(es_principal=True).first()
    if scenario:
        print(f"Active Scenario: {scenario.nombre} (ID: {scenario.id})")
        planned = PlannedTask.objects.filter(scenario=scenario, proyecto_code__in=filtros['proyectos'])
        print(f"Tasks in PlannedTask for this scenario: {planned.count()}")
    else:
        print("No principal scenario found!")

    # 4. Run Gantt Logic
    print("\n--- Running get_gantt_data ---")
    req = MockRequest(test_projects)
    data = get_gantt_data(req)
    
    timeline_data = data.get('timeline_data', [])
    total_tasks = sum(len(row['tasks']) for row in timeline_data)
    print(f"Total tasks in Gantt Timeline: {total_tasks}")
    
    if total_tasks == 0:
        print("ALERT: Gantt is EMPTY!")
        print(f"Empty Reason from data: {data.get('gantt_empty_reason')}")
    else:
        for row in timeline_data:
            if row['tasks']:
                print(f"Machine {row['machine'].nombre}: {len(row['tasks'])} tasks")
                for t in row['tasks'][:2]:
                     print(f"  - {t.get('Idorden')}: {t.get('start_date')} to {t.get('end_date')}")

if __name__ == "__main__":
    run_diagnose()
