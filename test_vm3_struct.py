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

print("Keys in gantt_data:", list(gantt_data.keys()))
td = gantt_data.get('timeline_data', [])
print(f"Total rows in timeline_data: {len(td)}")
for row in td:
    machine_id = row.get('machine_id') or row.get('maquina_id') or row.get('id') or '???'
    name = row.get('machine_name') or row.get('nombre') or '???'
    tasks = row.get('tasks', [])
    print(f"  Row: id={machine_id} name={name} tasks={len(tasks)}")
