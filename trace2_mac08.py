"""
Verifica cuántas tareas están en MAC08 (HAAS) en total y si 47468 está entre las visibles.
También verifica en qué fecha queda la tarea 47468 después del cálculo.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario
from produccion.services import get_planificacion_data

TASK_ID = '47468'

scenario = Scenario.objects.using('default').filter(es_principal=True).first()
manual_entries = PrioridadManual.objects.using('default').filter(scenario=scenario, maquina='MAC08')

print(f"Total de tareas movidas a MAC08 en escenario '{scenario.nombre}': {manual_entries.count()}")
print()
print(f"Tareas del escenario actual movidas a MAC08:")
for m in manual_entries.order_by('prioridad'):
    print(f"  Orden {m.id_orden} - Prioridad: {m.prioridad}")
print()

# Check specifically tasks 47467-47468 área
ids = [str(m.id_orden) for m in manual_entries]
all_tasks = get_planificacion_data({})
mac08_tasks = [t for t in all_tasks if str(t.get('Idorden')) in ids]

print(f"De esas {len(ids)} ordenes, están en el ERP actualmente: {len(mac08_tasks)} tareas")
print()
print("Buscando tarea 47468 específicamente:")
t = next((t for t in mac08_tasks if str(t.get('Idorden')) == TASK_ID), None)
if t:
    print(f"  ✅ Encontrada: {t.get('Idorden')} - Proyecto: {t.get('ProyectoCode')} - TiempoProceso: {t.get('Tiempo_Proceso')}")
else:
    print(f"  ❌ No encontrada en las tareas del ERP (puede estar completada o excluida)")
    # Check if it's in raw without filters
    all_raw = get_planificacion_data({'id_orden': TASK_ID})
    if all_raw:
        r = all_raw[0]
        print(f"  En ERP sin filtros: Idorden={r.get('Idorden')}, Estado={r.get('Idestado')}")
    else:
        print(f"  Tampoco encontrada sin filtros. Probablemente completada/excluida del ERP.")
