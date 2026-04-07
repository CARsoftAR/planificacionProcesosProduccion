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
from produccion.gantt_logic import get_gantt_data
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
    request.GET = {'fecha_desde': '2026-03-19', 'plan_mode': 'manual'}
    request.session = {}
    esc = Scenario.objects.filter(es_principal=True).first()
    if esc: request.session['last_scenario_id'] = str(esc.id)

    data = get_gantt_data(request, force_run=True)
    rows = data.get('rows', [])
    
    # Check all rows to see if any task that SHOULD be in Tsugami moved elsewhere
    # We identify tasks by Idorden + Operation name
    
    # First, list tasks currently in Tsugami row
    tsugami_row = next((r for r in rows if tsugami.nombre in r['maquina']), None)
    if tsugami_row:
        print(f"\nTareas actualmente en la fila de {tsugami.nombre}:")
        for t in tsugami_row.get('tasks', []):
            print(f" - {t['text']} | Inicio: {t['start_date']} | Fin: {t['end_date']}")
    else:
        print(f"\nNo se encontro la fila de {tsugami.nombre} en el Gantt.")

    # Second, check if any task is "delayed" or in "non-assigned"
    mac00_row = next((r for r in rows if 'MAC00' in r['id_maquina'] or 'SIN ASIGNAR' in r['maquina'].upper()), None)
    if mac00_row:
        print(f"\nTareas en SIN ASIGNAR:")
        for t in mac00_row.get('tasks', []):
             print(f" - {t['text']} | Inicio: {t['start_date']} (POSIBLE DESPLAZAMIENTO)")

    # Third, check alerts
    capacity_alerts = data.get('capacity_alerts', [])
    if capacity_alerts:
        print("\nALERTAS DE CAPACIDAD:")
        for alert in capacity_alerts:
            print(f" - {alert['message']}")

if __name__ == "__main__":
    check_tsugami_tasks()
