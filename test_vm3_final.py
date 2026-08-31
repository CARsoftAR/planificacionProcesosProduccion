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

print("=== MAC23 / VM3 Tasks ===")
for row in td:
    maq = row.get('machine')
    tasks = row.get('tasks', [])
    if not tasks:
        continue
    # Check if any task is on MAC23
    mac23_tasks = [t for t in tasks if str(t.get('_mid', '') or t.get('Idmaquina', '')) == 'MAC23'
                   or str(t.get('MAQUINAD', '')) == 'VM3']
    if mac23_tasks:
        print(f"Machine: {maq}")
        for t in sorted(mac23_tasks, key=lambda x: x.get('start_date', '')):
            print(f"  OP {t.get('Idorden')}: start={t.get('start_date')} end={t.get('end_date')} solapamiento={t.get('porcentaje_solapamiento')}%")
        break

# Also check all tasks regardless of machine
print("\n=== ALL Tasks with solapamiento > 0 ===")
for row in td:
    for t in row.get('tasks', []):
        if float(t.get('porcentaje_solapamiento') or 0) > 0:
            print(f"  OP {t.get('Idorden')} on {t.get('MAQUINAD')}: start={t.get('start_date')} end={t.get('end_date')} solap={t.get('porcentaje_solapamiento')}%")
