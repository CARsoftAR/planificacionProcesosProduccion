"""
Simula exactamente qué haría el nuevo redistribute_tasks para la falla de TSUGAMI (MAC38).
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import Scenario, MantenimientoMaquina, HiddenTask
from django.utils import timezone

scenario = Scenario.objects.using('default').filter(es_principal=True).first()
print(f"Escenario: {scenario.nombre}")

now = timezone.now()
failure = MantenimientoMaquina.objects.using('default').filter(
    maquina_id='MAC38',
    estado='FALLA',
    fecha_inicio__lte=now,
    fecha_fin__gte=now
).first()

if not failure:
    print("❌ No hay falla activa en MAC38 (Tsugami). Buscar todas las fallas...")
    all_failures = MantenimientoMaquina.objects.using('default').filter(maquina_id='MAC38')
    for f in all_failures:
        print(f"  Falla: {f.estado} - Inicio: {f.fecha_inicio} - Fin: {f.fecha_fin}")
else:
    print(f"✅ Falla activa: {failure.motivo}")
    print(f"   Inicio: {failure.fecha_inicio}")
    print(f"   Fin:    {failure.fecha_fin}")
    
    # Simulate the gantt calculation
    from produccion.gantt_logic import get_gantt_data

    class MockRequest:
        def __init__(self):
            self.GET = {
                'run': '1',
                'fecha_desde': failure.fecha_inicio.strftime('%Y-%m-%d'),
                'proyectos': '26-021,25-072',
                'scenario_id': str(scenario.id),
                'plan_mode': 'manual'
            }
            self.session = {}

    print("\nCalculando Gantt para encontrar tareas que se solapan con la falla...")
    gantt_data = get_gantt_data(MockRequest(), force_run=True)
    hidden_ids = set(HiddenTask.objects.using('default').values_list('id_orden', flat=True))

    affected = []
    for row in gantt_data['timeline_data']:
        if str(row['machine'].id_maquina).strip().upper() == 'MAC38':
            print(f"\nMáquina encontrada: {row['machine'].nombre} - Total tareas planned: {len(row['tasks'])}")
            for task in row['tasks']:
                ts = task.get('start_date')
                te = task.get('end_date')
                if not ts or not te:
                    continue
                if ts.tzinfo is None:
                    ts = timezone.make_aware(ts)
                if te.tzinfo is None:
                    te = timezone.make_aware(te)
                overlaps = ts <= failure.fecha_fin and te >= failure.fecha_inicio
                oid = str(task.get('Idorden'))
                print(f"  Orden {oid}: Start={ts.strftime('%d/%m %H:%M')} End={te.strftime('%d/%m %H:%M')} → {'⚠️  AFECTADA' if overlaps else '✅ OK'}")
                if overlaps and oid not in hidden_ids:
                    affected.append(oid)
            break

    print(f"\n{'='*50}")
    print(f"Tareas que se moverían a HAAS: {affected}")
    print(f"Total: {len(affected)}")
