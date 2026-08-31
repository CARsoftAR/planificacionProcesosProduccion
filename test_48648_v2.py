import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()
from produccion.gantt_logic import get_gantt_data
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware
from produccion.models import Scenario
scenario = Scenario.objects.filter(es_principal=True).first()
if not scenario: scenario = Scenario.objects.first()

factory = RequestFactory()
request = factory.get('/planificacion/?plan_mode=manual&proyectos=26-075')
middleware = SessionMiddleware(lambda r: None)
middleware.process_request(request)
request.session.save()
request.session['active_scenario_id'] = scenario.id
request.session['last_plan_mode'] = 'manual'
gantt_data = get_gantt_data(request)
for row in gantt_data.get('timeline_data', []):
    machine = row['machine'].nombre
    for t in row['tasks']:
        if t.get('ProyectoCode') == '26-075':
            print(f"[{machine}] OP {t.get('Idorden')} - Start: {t.get('start_date')} | End: {t.get('end_date')} | Solap: {t.get('porcentaje_solapamiento')}%")
