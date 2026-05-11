import os
import django
import sys
from datetime import datetime
from django.utils import timezone

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data
from produccion.models import MaquinaConfig

class MockRequest:
    def __init__(self, projects):
        self.GET = {'proyectos': projects, 'plan_mode': 'manual', 'run': '1'}
        self.session = {}
        self.user = 'debug'

def run_test():
    # Projects from screenshot
    projects = '26-021, 23-037'
    print(f"Testing Gantt for projects: {projects}")
    
    req = MockRequest(projects)
    data = get_gantt_data(req, force_run=True)
    
    timeline = data.get('timeline_data', [])
    print(f"Total rows in timeline: {len(timeline)}")
    
    target_machine = "BANCO TRABAJO 1"
    machine_row = next((r for r in timeline if r['machine'].nombre == target_machine), None)
    
    if machine_row:
        tasks = machine_row['tasks']
        print(f"Tasks for {target_machine}: {len(tasks)}")
        for t in tasks[:10]:
            print(f"  OP {t.get('Idorden')}: Start={t.get('start_date')}, End={t.get('end_date')}, Dur={t.get('duration_real')}")
    else:
        print(f"Machine {target_machine} not found in timeline!")

if __name__ == "__main__":
    run_test()
