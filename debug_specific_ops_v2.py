import os
import django
import json
from datetime import datetime
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data
from produccion.models import MaquinaConfig, PrioridadManual, MantenimientoMaquina
from django.test import RequestFactory
from django.utils import timezone

def ser(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)

def run_dump():
    factory = RequestFactory()
    request = factory.get('/produccion/planificacion-visual/?run=1')
    from django.contrib.sessions.middleware import SessionMiddleware
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    
    data = get_gantt_data(request)

    # Añadir 47652 y otros que falten
    relevant_ids = ['47659', '47649', '47658', '47648', '47647', '47656', '47652', '47655']
    results = []

    for row in data['timeline_data']:
        machine = row['machine']
        # Mantenimiento check
        mants = MantenimientoMaquina.objects.filter(maquina=machine).exclude(estado='FINALIZADO')
        mant_list = [{'start': m.fecha_inicio, 'end': m.fecha_fin, 'motivo': m.motivo} for m in mants]

        for task in row['tasks']:
            tid = str(task.get('Idorden'))
            if tid in relevant_ids:
                overlap_pct = 0.0
                try:
                    manual = PrioridadManual.objects.using('default').filter(id_orden=tid).first()
                    if manual:
                        overlap_pct = manual.porcentaje_solapamiento or 0.0
                except: pass

                preds = data['dependency_map'].get(tid, [])
                predecessor_details = []
                for pid in preds:
                    p_end = "Not found"
                    for r2 in data['timeline_data']:
                        for t2 in r2['tasks']:
                            if str(t2.get('Idorden')) == pid:
                                p_end = t2.get('end_date')
                                break
                    predecessor_details.append({'id': pid, 'end_date': p_end})

                results.append({
                    'machine': machine.nombre,
                    'id': tid,
                    'start': task.get('start_date'),
                    'end': task.get('end_date'),
                    'duration_hours': task.get('Tiempo_Proceso'),
                    'overlap_percentage': overlap_pct,
                    'predecessors': predecessor_details,
                    'critical': task.get('is_critical', False),
                    'delayed': task.get('is_delayed', False),
                    'delay_days': task.get('delay_days', 0),
                    'machine_maints': mant_list,
                    'tipo_maquina': task.get('MAQUINAD') # Para ver si hay discrepancia
                })

    print(json.dumps(results, default=ser, indent=2))

if __name__ == "__main__":
    run_dump()
