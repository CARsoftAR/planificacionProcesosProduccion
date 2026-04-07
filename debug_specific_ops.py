import os
import django
import json
from datetime import datetime
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data
from produccion.models import MaquinaConfig, PrioridadManual
from django.test import RequestFactory
from django.utils import timezone

def ser(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

def run_dump():
    factory = RequestFactory()
    # Simular una carga completa
    request = factory.get('/produccion/planificacion-visual/?run=1')
    from django.contrib.sessions.middleware import SessionMiddleware
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    
    data = get_gantt_data(request)

    relevant_ids = ['47659', '47649', '47658', '47648', '47647', '47656', '47652', '47655']
    results = []

    for row in data['timeline_data']:
        machine_name = row['machine'].nombre
        # Encontrar las tareas que buscamos
        for task in row['tasks']:
            tid = str(task.get('Idorden'))
            if tid in relevant_ids:
                # Recopilar campos solicitados por el usuario
                
                # Buscar override de solapamiento
                overlap_pct = 0.0
                try:
                    manual = PrioridadManual.objects.using('default').filter(id_orden=tid).first()
                    if manual:
                        overlap_pct = manual.porcentaje_solapamiento or 0.0
                except:
                    pass

                # Predecessor info
                # El sistema tiene un global_task_end_dates que se usó internamente. No se exporta en data.
                # Pero en la segunda pasada de planning_service.py se calcula min_start_times.
                # Lo sacaremos del dependency_map y buscaremos sus fines calculados.
                
                preds = data['dependency_map'].get(tid, [])
                predecessor_details = []
                for pid in preds:
                    # Encontrar el fin de este predecesor
                    p_end = "Not found"
                    for r2 in data['timeline_data']:
                        for t2 in r2['tasks']:
                            if str(t2.get('Idorden')) == pid:
                                p_end = t2.get('end_date')
                                break
                    predecessor_details.append({'id': pid, 'end_date': p_end})

                results.append({
                    'machine': machine_name,
                    'id': tid,
                    'start': task.get('start_date'),
                    'end': task.get('end_date'),
                    'duration_hours': task.get('Tiempo_Proceso'),
                    'overlap_percentage': overlap_pct,
                    'predecessors': predecessor_details,
                    'critical': task.get('is_critical', False),
                    'delayed': task.get('is_delayed', False),
                    'delay_days': task.get('delay_days', 0)
                })

    print(json.dumps(results, default=ser, indent=2))

if __name__ == "__main__":
    run_dump()
