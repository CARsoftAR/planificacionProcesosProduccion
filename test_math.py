import os
import sys
import django

sys.path.append(r"c:\Sistemas ABBAMAT\planificacionProcesosProductivos EN DESARROLLO")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "planificacion.settings")
django.setup()

from produccion.gantt_logic import get_gantt_data
from produccion.models import Scenario
from django.test import RequestFactory

# Create a mock request
factory = RequestFactory()
request = factory.get('/planificacion/')

# Mock the session
from django.contrib.sessions.middleware import SessionMiddleware
middleware = SessionMiddleware(lambda r: None)
middleware.process_request(request)
request.session.save()

# We need an active scenario
scenario = Scenario.objects.first()
if not scenario:
    scenario = Scenario.objects.create(nombre="Test Scenario", activo=True)
else:
    scenario.activo = True
    scenario.save()
request.session['active_scenario_id'] = scenario.id

# Run get_gantt_data
# Wait, get_gantt_data fetches data from the DB. We need to mock the data it fetches, or just inject a mock task list!
# In get_gantt_data: all_tasks_raw = get_planificacion_data(...)
# It's better to just extract the overlap logic and test it directly to see what start_time it produces.

from datetime import datetime, timedelta

def mock_overlap_logic(t_maq, t_op, tiempo_proceso_predecesora, solapamiento_porcentaje):
    horas_anticipadas = 0
    if solapamiento_porcentaje > 0 and tiempo_proceso_predecesora > 0:
        horas_anticipadas = tiempo_proceso_predecesora * (solapamiento_porcentaje / 100.0)
        # Simplified subtract_working_hours for test (assuming 24/7 machine for simple math)
        t_op = t_op - timedelta(hours=horas_anticipadas)
    
    start_time = max(t_maq, t_op)
    return start_time, t_op

t_maq = datetime(2026, 8, 27, 8, 0, 0)
t_op = datetime(2026, 8, 27, 14, 0, 0) # Predecessor ends at 14:00 (took 6 hours)
tiempo_proceso = 6.0
solap = 50.0

start, top_new = mock_overlap_logic(t_maq, t_op, tiempo_proceso, solap)
print(f"Predecessor End: {t_op}")
print(f"Machine Available: {t_maq}")
print(f"Overlap %: {solap}")
print(f"New t_op: {top_new}")
print(f"Final Start Time (max(t_maq, t_op)): {start}")
