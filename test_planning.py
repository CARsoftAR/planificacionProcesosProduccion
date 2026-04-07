
import os
import django
import sys
from datetime import datetime

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data
from django.test import RequestFactory
from django.contrib.sessions.middleware import SessionMiddleware

def test_planning():
    print("="*60)
    print("EJECUCION DE PLANIFICACION ABBA: 26-021 y 25-072")
    print("="*60)
    
    rf = RequestFactory()
    # Simular un request con los proyectos indicados
    request = rf.get('/planificacion/visual/', {'proyectos': '26-021,25-072', 'run': '1'})
    
    # Mock session
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    
    try:
        data = get_gantt_data(request, force_run=True)
        
        print("\n[RESULTADOS GENERALES]")
        print(f"Total maquinas procesadas: {len(data['timeline_data'])}")
        
        total_tasks = 0
        tasks_per_machine = {}
        for row in data['timeline_data']:
            m = row['machine']
            tasks = row['tasks']
            total_tasks += len(tasks)
            if tasks:
                tasks_per_machine[m.nombre] = len(tasks)
        
        print(f"Total de tareas planificadas: {total_tasks}")
        for m_name, count in sorted(tasks_per_machine.items(), key=lambda x: x[1], reverse=True):
            print(f" - {m_name}: {count} tareas")

        print("\n[ALERTAS DE RETRASO (PREDICTIVAS)]")
        alerts = data['analysis']['project_alerts']
        if not alerts:
            print(" (OK) Todos los proyectos estan EN FECHA (Vto vs Fin Planificado).")
        else:
            for alert in alerts:
                delay = alert['delay_days']
                vto = alert['vto'].strftime('%d/%m/%Y') if alert['vto'] else 'N/A'
                fin = alert['max_end'].strftime('%d/%m/%Y') if alert['max_end'] else 'N/A'
                print(f" (ALERTA) Proyecto {alert['proyecto']}: {delay} dias de atraso (Vto: {vto}, Fin Est.: {fin})")
                print(f"    - Causas: {', '.join([c['desc'] for c in alert['culprits']])}")

        print("\n[VERIFICACION DE FIN DE SEMANA (SABADO/DOMINGO)]")
        found_sat_sun = False
        for row in data['timeline_data']:
            for t in row['tasks']:
                s = t.get('start_date')
                e = t.get('end_date')
                if s and (s.weekday() == 5 or s.weekday() == 6):
                    print(f" (ALERTA BUG!) Tarea {t.get('Idorden')} programada el {s.strftime('%A %d/%m %H:%M')}")
                    found_sat_sun = True
                if e and (e.weekday() == 5 or e.weekday() == 6):
                    if not (e.weekday() == 5 and e.hour == 0 and e.minute == 0):
                         print(f" (ALERTA BUG!) Tarea {t.get('Idorden')} termina el {e.strftime('%A %d/%m %H:%M')}")
                         found_sat_sun = True
        
        if not found_sat_sun:
            print(" (OK) VERIFICADO: No hay tareas programadas en fines de semana.")

    except Exception as e:
        import traceback
        print(f" (ERROR) EN LA PLANIFICACION: {str(e)}")
        traceback.print_exc()

if __name__ == "__main__":
    test_planning()
