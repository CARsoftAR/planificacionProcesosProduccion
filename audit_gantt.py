import os
import django
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'carsoftar.settings')
django.setup()

from django.test import RequestFactory
from produccion.views import get_gantt_data
from produccion.models import Scenario

def run_audit():
    # Encuentra el escenario activo (es_principal=True)
    scenario = Scenario.objects.using('default').filter(es_principal=True).first()
    if not scenario:
        print("No se encontro escenario principal.")
        return

    # Usamos RequestFactory para simular la peticion
    factory = RequestFactory()
    request = factory.get(f'/api/get_gantt_data/?scenario_id={scenario.id}&plan_mode=manual')
    
    # Inyectamos session vacia
    from django.contrib.sessions.middleware import SessionMiddleware
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    
    # Hacemos que get_gantt_data procese la info
    from produccion.gantt_logic import get_gantt_data as logic_get_gantt_data
    try:
        data = logic_get_gantt_data(request)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return
        
    timeline_data = data.get('timeline_data', [])
    
    print(f"=== AUDITORIA DE GANTT (Escenario: {scenario.nombre}) ===")
    
    for machine_data in timeline_data:
        maquina = machine_data['machine']
        tasks = machine_data['tasks']
        
        # Filtramos solo si hay tareas o si es VF2 para el reporte detallado
        machine_name = getattr(maquina, 'nombre', '') if not isinstance(maquina, dict) else maquina.get('nombre', '')
        machine_id = getattr(maquina, 'id_maquina', '') if not isinstance(maquina, dict) else maquina.get('id_maquina', '')
        
        if not tasks:
            continue
            
        print(f"\n--- MAQUINA: {machine_name} ({machine_id}) ---")
        
        # Agrupar las tareas (segmentos) por id_orden
        task_segments = {}
        for t in tasks:
            oid = str(t.get('Idorden', ''))
            if oid not in task_segments:
                task_segments[oid] = []
            task_segments[oid].append(t)
            
        # Ordenar tareas por inicio del primer segmento
        sorted_tasks = sorted(task_segments.values(), key=lambda segs: min(s['start_date'] for s in segs))
        
        prev_end = None
        for segs in sorted_tasks:
            # Una tarea puede tener varios segmentos (por descansos). Calculamos su inicio y fin total.
            t_start = min(s['start_date'] for s in segs)
            t_end = max(s['end_date'] for s in segs)
            
            # Tomar info del primer segmento
            first_seg = segs[0]
            op_num = first_seg.get('Idorden', '')
            proyecto = first_seg.get('ProyectoCode', '')
            duracion = sum(s.get('duration_real', 0) for s in segs)
            
            print(f"OP {op_num:<8} | Proyecto: {proyecto:<8} | Inicio: {t_start.strftime('%Y-%m-%d %H:%M:%S')} | Fin: {t_end.strftime('%Y-%m-%d %H:%M:%S')} | Duracion: {duracion:.2f}h")
            
            if prev_end is not None:
                gap = t_start - prev_end
                gap_hours = gap.total_seconds() / 3600.0
                
                # Report gap if greater than 0
                if gap_hours > 0:
                    # Validar si el gap es simplemente el horario no laboral. 
                    # Una forma simple es ver si es la mañana siguiente
                    is_overnight = (t_start.date() > prev_end.date())
                    
                    if is_overnight:
                        print(f"   -> [INFO] Salto de jornada: {gap_hours:.2f}h")
                    else:
                        print(f"   -> [ERROR] Hueco fantasma detectado de {gap_hours:.2f}h en el mismo dia!")
            
            prev_end = t_end

if __name__ == '__main__':
    run_audit()
