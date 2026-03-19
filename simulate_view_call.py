import os
import django
import sys
import json
from django.test import RequestFactory
from django.db import connections

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.views import planificacion_list
from produccion.models import Scenario

def simulate_view(proyectos_str):
    print(f"--- SIMULANDO VISTA PARA: {proyectos_str} ---")
    factory = RequestFactory()
    
    # Get active scenario if any
    s = Scenario.objects.using('default').filter(nombre='Primer planificacion').first()
    scenario_id = s.id if s else None
    
    url = f"/planificacion/?proyectos={proyectos_str}&plan_mode=manual"
    if scenario_id:
        url += f"&scenario_id={scenario_id}"
        
    request = factory.get(url)
    
    # Session handling
    from django.contrib.sessions.middleware import SessionMiddleware
    def get_response(request): return None
    middleware = SessionMiddleware(get_response)
    middleware.process_request(request)
    request.session.save()
    
    response = planificacion_list(request)
    print(f"Status Code: {response.status_code}")
    
    if hasattr(response, 'context_data'):
         context = response.context_data
         all_machines = context.get('all_machines_list', [])
         print(f"Maquinas en contexto: {len(all_machines)}")
         for m in all_machines:
             if m.get('count', 0) > 0:
                 print(f"  > {m['nombre']}: {m['count']} tareas")
    else:
         print("La respuesta no tiene context_data (ya está renderizada)")

if __name__ == "__main__":
    simulate_view('25-074, 25-032')
