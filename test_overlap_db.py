import os
import sys
import django

sys.path.append(r"c:\Sistemas ABBAMAT\planificacionProcesosProductivos EN DESARROLLO")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "planificacion.settings")
django.setup()

from django.test import RequestFactory
from produccion.gantt_logic import get_gantt_data
from produccion.models import Scenario
from produccion.models import PlannedTask

factory = RequestFactory()
request = factory.get('/planificacion/')

from django.contrib.sessions.middleware import SessionMiddleware
middleware = SessionMiddleware(lambda r: None)
middleware.process_request(request)
request.session.save()

scenario = Scenario.objects.filter(es_principal=True).first()
if not scenario:
    scenario = Scenario.objects.first()
request.session['active_scenario_id'] = scenario.id
request.session['last_plan_mode'] = 'manual'

db_proyectos = list(PlannedTask.objects.using('default').filter(
    scenario=scenario
).values_list('proyecto_code', flat=True).distinct())

if db_proyectos:
    proyectos_value = ','.join(p for p in db_proyectos if p)
else:
    proyectos_value = ''

request.GET = {'plan_mode': 'manual', 'proyectos': proyectos_value}

print("Calling get_gantt_data...")
gantt_data = get_gantt_data(request)
print("Finished!")

for row in gantt_data.get('timeline_data', []):
    machine = row['machine'].nombre
    for task in row['tasks']:
        solap = float(task.get('porcentaje_solapamiento', 0.0) or 0.0)
        if solap > 0:
            print(f"Machine: {machine}")
            print(f"  OP {task.get('Idorden')} (Proj: {task.get('ProyectoCode')}): Start {task.get('start_date')} | End {task.get('end_date')} | Solap: {solap} | modo: {task.get('modo_solapamiento')}")
