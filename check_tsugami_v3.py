import os
import django
import sys
from datetime import datetime
from django.utils import timezone

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.append(current_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import MaquinaConfig, MantenimientoMaquina, PrioridadManual, Scenario
from produccion.gantt_logic import get_gantt_data, get_adaptive_capacity_alerts
from django.test import RequestFactory

def check_tsugami_tasks():
    tsugami = MaquinaConfig.objects.filter(nombre__icontains='TSUGAMI').first()
    if not tsugami:
        print("No se encontro TSUGAMI")
        return

    print(f"Buscando tareas para {tsugami.nombre} (ID: {tsugami.id_maquina})")

    # Mock request
    factory = RequestFactory()
    request = factory.get('/')
    request.GET = {'fecha_desde': '2026-03-19', 'plan_mode': 'manual', 'run': '1'}
    request.session = {}
    esc = Scenario.objects.filter(es_principal=True).first()
    if esc: request.session['last_scenario_id'] = str(esc.id)

    data = get_gantt_data(request, force_run=True)
    rows = data.get('timeline_data', [])
    
    # First, list tasks currently in Tsugami row
    # The key in the row is 'machine' (the object)
    tsugami_row = next((r for r in rows if r['machine'].id_maquina == tsugami.id_maquina), None)
    
    if tsugami_row:
        print(f"\nTareas actualmente en la fila de {tsugami.nombre}:")
        tasks = tsugami_row.get('tasks', [])
        if not tasks:
            print(" - (Sin tareas en esta maquina)")
        for t in tasks:
            print(f" - {t['text']} | Inicio: {t['start_date']} | Fin: {t['end_date']}")
    else:
        print(f"\nNo se encontro la fila de {tsugami.nombre} ({tsugami.id_maquina}) en el Gantt.")
        # Let's see what machines are there
        print("Maquinas encontradas en el Gantt:", [r['machine'].nombre for r in rows])

    # Check if any task is in SIN ASIGNAR
    sin_asignar_row = next((r for r in rows if r['machine'].id_maquina == 'MAC00' or 'SIN ASIGNAR' in r['machine'].nombre.upper()), None)
    if sin_asignar_row:
        print(f"\nTareas en SIN ASIGNAR:")
        for t in sin_asignar_row.get('tasks', []):
             print(f" - {t['text']} | Inicio: {t['start_date']}")

    # Check for adaptive capacity alerts
    # We call get_adaptive_capacity_alerts explicitly as it might not be in the output dict if not called by view
    # Actually gantt_logic has it.
    from produccion.gantt_logic import get_adaptive_capacity_alerts
    maquinas = list(MaquinaConfig.objects.all())
    alerts = get_adaptive_capacity_alerts(rows, maquinas)
    
    if alerts:
        print("\nRECOMENDACIONES DE CAPACIDAD ADAPTATIVA:")
        for alert in alerts:
            if alert['machine_id'] == tsugami.id_maquina:
                print(f" !!! FALLA EN {alert['machine']}: {alert['failure_reason']}")
                print(f"     Desde: {alert['failure_start']} Hasta: {alert['failure_end']}")
                print(f"     Tareas afectadas: {alert['affected_tasks_count']}")
                print(f"     MAQUINAS COMPATIBLES SUGERIDAS:")
                for comp in alert['compatible_machines']:
                    print(f"      -> {comp['name']} (Score: {comp['score']})")

if __name__ == "__main__":
    check_tsugami_tasks()
