import os
import django
import json
from datetime import datetime
from django.utils import timezone

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data
from produccion.models import MaquinaConfig, HorarioMaquina
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware

def run():
    factory = RequestFactory()
    request = factory.get('/produccion/planificacion-visual/?run=1')
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    
    data = get_gantt_data(request)
    
    # 1. Tareas de la máquina MAC06 en las fechas críticas
    machine_id = 'MAC06'
    tasks_found = []
    
    for row in data['timeline_data']:
        if str(row['machine'].id_maquina) == machine_id:
            for t in row['tasks']:
                sd = t.get('start_date')
                if sd and sd.month == 4 and 8 <= sd.day <= 15:
                    tasks_found.append({
                        'id': t.get('Idorden'),
                        'desc': t.get('Descri'),
                        'start': sd.isoformat(),
                        'end': t.get('end_date').isoformat(),
                        'proyecto': t.get('ProyectoCode')
                    })
    
    # 2. Configuración de horarios para MAC06
    m = MaquinaConfig.objects.using('default').get(id_maquina=machine_id)
    schedules = []
    for h in m.horarios.all():
        schedules.append({
            'dia': h.dia,
            'start': str(h.hora_inicio),
            'end': str(h.hora_fin)
        })

    output = {
        'tasks_on_mac06': sorted(tasks_found, key=lambda x: x['start']),
        'machine_schedules': schedules
    }
    
    print(json.dumps(output, indent=2))

if __name__ == "__main__":
    run()
