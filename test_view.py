import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.test import RequestFactory
from produccion.views import planificacion_list
from produccion.models import Scenario

def test_view():
    factory = RequestFactory()
    
    # 1. Obtener escenario 106 (el que usamos en test_integration)
    scenario = Scenario.objects.using('default').filter(id=106).first()
    if not scenario:
        print("Escenario 106 no encontrado")
        return
        
    print(f"Probando vista para escenario {scenario.id} con plan_mode=manual")
    request = factory.get(f'/planificacion/?scenario_id={scenario.id}&plan_mode=manual')
    # session middleware no corre en factory.get a menos que se agregue
    from django.contrib.sessions.middleware import SessionMiddleware
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    
    response = planificacion_list(request)
    print(f"Respuesta HTTP status: {response.status_code}")
    
    # Como queremos ver la lista ANTES de que se renderice, vamos a hacer un mock de render
    # o mejor, podemos extraer los datos procesados si interceptamos
    # Pero la vista ya imprime los logs DEBUG ORDEN.
    # Como corre en el mismo proceso de Django, los prints de la vista saldrán aquí en la consola.
    
if __name__ == '__main__':
    test_view()
