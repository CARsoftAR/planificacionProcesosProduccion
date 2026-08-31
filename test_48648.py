import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()
from produccion.gantt_logic import get_gantt_data
from produccion.models import PlannedTask, Scenario
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware

# Let's get the project code for OP 48648
task = PlannedTask.objects.using('default').filter(id_orden='48648').first()
if task:
    print(f"Task 48648 Project is: {task.proyecto_code}")
    proj = task.proyecto_code
else:
    print("Task not found!")
    exit(1)

scenario = Scenario.objects.filter(es_principal=True).first()
if not scenario:
    scenario = Scenario.objects.first()

factory = RequestFactory()
request = factory.get(f'/planificacion/?plan_mode=manual&proyectos={proj}')
middleware = SessionMiddleware(lambda r: None)
middleware.process_request(request)
request.session.save()
request.session['active_scenario_id'] = scenario.id
request.session['last_plan_mode'] = 'manual'

print("Running Gantt Logic...")
gantt_data = get_gantt_data(request)
print("Done!")

for row in gantt_data.get('timeline_data', []):
    machine = row['machine'].nombre
    for t in row['tasks']:
        if t.get('ProyectoCode') == proj:
            print(f"[{machine}] OP {t.get('Idorden')} (Proj: {t.get('ProyectoCode')}) - Solap: {t.get('porcentaje_solapamiento')}%")
            print(f"   Start: {t.get('start_date')}")
            print(f"   End:   {t.get('end_date')}")
            print(f"   Visual Left: {t.get('visual_left')}")
