import os, django, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()
from produccion.gantt_logic import _build_gantt_timeline
from produccion.services import get_planificacion_data

# Fetch tasks for project 26-075
tasks_qs = get_planificacion_data({'proyectos': ['26-075']}, exclude_completed=False)
tasks = list(tasks_qs)
print(f"Tasks fetched: {len(tasks)}")

valid_dates = [datetime.datetime.now().date() + datetime.timedelta(days=i) for i in range(10)]
date_start_col = {d: i*24 for i, d in enumerate(valid_dates)}

# Call the builder directly to see what timeline it generates
from produccion.models import Scenario
active_scenario = Scenario.objects.filter(es_principal=True).first()

try:
    timeline_data = _build_gantt_timeline(tasks, 'manual', valid_dates, date_start_col, {}, None, active_scenario, None)
    for row in timeline_data:
        machine = row['machine'].nombre if hasattr(row['machine'], 'nombre') else str(row['machine'])
        for t in row['tasks']:
            print(f"[{machine}] OP {t.get('Idorden')} - Solap: {t.get('porcentaje_solapamiento')}%")
            print(f"   Start: {t.get('start_date')}")
            print(f"   End: {t.get('end_date')}")
except Exception as e:
    import traceback
    traceback.print_exc()
