import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data

class FakeRequest:
    GET = {}
    session = {}

req = FakeRequest()
req.GET = {'graficar': '1', 'scenario_id': '150', 'plan_mode': 'manual'}

gantt_data = get_gantt_data(req)

td = gantt_data.get('timeline_data', [])
for row in td:
    tasks = row.get('tasks', [])
    if tasks:
        # Print all keys of row and first task
        print("ROW KEYS:", list(row.keys()))
        print("TASK KEYS:", list(tasks[0].keys()))
        break
