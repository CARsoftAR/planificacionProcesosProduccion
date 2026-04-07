import os
import django
import sys
from datetime import datetime, timedelta
from django.utils import timezone

# Add current path to sys.path for imports
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.append(current_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import MaquinaConfig, MantenimientoMaquina, PrioridadManual, Scenario
from produccion.gantt_logic import get_gantt_data
from django.test import RequestFactory

def check_tsugami_failure():
    print("="*60)
    print("REVISANDO FALLA TSUGAMI Y REDISTRIBUCION")
    print("="*60)
    
    # 1. Buscar la maquina
    tsugami = MaquinaConfig.objects.filter(nombre__icontains='TSUGAMI').first()
    if not tsugami:
        print("No se encontro la maquina TSUGAMI")
        return

    print(f"Maquina: {tsugami.nombre} (ID: {tsugami.id_maquina})")

    # 2. Buscar mantenimientos o fallas activas
    start_falla = timezone.make_aware(datetime(2026, 3, 19, 12, 0))
    end_falla = timezone.make_aware(datetime(2026, 3, 26, 0, 0))
    
    maints = MantenimientoMaquina.objects.filter(
        maquina=tsugami,
        fecha_inicio__lte=end_falla,
        fecha_fin__gte=start_falla
    )
    
    if maints.exists():
        for m in maints:
            print(f"FALLA/MANTENCION ENCONTRADA: {m.fecha_inicio} a {m.fecha_fin} (Estado: {m.estado})")
    else:
        print("No se encontro registro de falla en la DB para esas fechas.")

    # 3. Correr planificacion y ver donde terminaron las tareas originales de TSUGAMI
    # Mocking request correctly
    factory = RequestFactory()
    request = factory.get('/')
    request.GET = {
        'fecha_desde': '2026-03-19',
        'plan_mode': 'manual'
    }
    request.session = {}
    
    # Asegurar escenario principal
    esc = Scenario.objects.filter(es_principal=True).first()
    if esc:
        request.session['last_scenario_id'] = str(esc.id)

    data = get_gantt_data(request, force_run=True)
    
    # 4. Revisar si hay tareas en TSUGAMI durante la falla
    rows = data.get('rows', [])
    tsugami_row = next((r for r in rows if tsugami.nombre in r['maquina']), None)
    
    if tsugami_row:
        tasks = tsugami_row.get('tasks', [])
        print(f"\nTareas en {tsugami.nombre}:")
        for t in tasks:
            # t['start_date'] is string or datetime? get_gantt_data converts to str for JSON
            s_dt = t['start_date'] # format usually 'YYYY-MM-DD HH:MM'
            try:
                dt_task = datetime.strptime(s_dt, '%Y-%m-%d %H:%M')
                # dt_task is naive, usually simulation is aware now
                # In get_gantt_data, dates are converted to string.
                if '2026-03-19' <= s_dt <= '2026-03-26':
                    print(f" !!! Tarea DURANTE FALLA: {t['text']} (Inicio: {s_dt})")
                elif s_dt > '2026-03-26':
                    print(f" - Tarea DESPUES de falla: {t['text']} (Inicio: {s_dt})")
            except:
                print(f" - Tarea: {t['text']} (Inicio: {s_dt})")
            
    # 5. Ver si hay recomendaciones de Adaptive Capacity
    capacity_alerts = data.get('capacity_alerts', [])
    if capacity_alerts:
        print("\nRECOMENDACIONES DE CAPACIDAD ADAPTATIVA:")
        for alert in capacity_alerts:
             # Look for Tsugami in recommendation or warnings
             if tsugami.nombre in alert.get('message', '') or 'MAC14' in alert.get('message', ''):
                 print(f" (ALERTA) {alert['message']}")
    else:
        print("\nNo hay alertas de capacidad adaptativa.")

if __name__ == "__main__":
    check_tsugami_failure()
