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
from produccion.planning_service import is_half_day_holiday
from datetime import datetime

class MockRequest:
    def __init__(self):
        self.GET = {'proyectos': '25-005', 'plan_mode': 'manual'}
        self.user = 'debug'

def run_debug():
    # Test Holiday Function
    dt = datetime(2025, 12, 24, 13, 0, 0)
    is_half = is_half_day_holiday(dt)
    print(f"TEST HOLIDAY for {dt}: {is_half}")

    print("Running Gantt Logic Debug...")
    req = MockRequest()
    try:
        data = get_gantt_data(req, force_run=True)
        print("Gantt Data obtained.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_debug()
