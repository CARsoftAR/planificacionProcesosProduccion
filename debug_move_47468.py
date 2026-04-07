"""
Diagnostica exactamente por qué la tarea 47468 no aparece en MAC08 (HAAS) después de redistribuirse.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario, MaquinaConfig
from produccion.services import get_planificacion_data

TASK_ID = '47468'

print("=" * 60)
print("PASO 1: ¿Está el override guardado en PrioridadManual?")
print("=" * 60)
p = PrioridadManual.objects.using('default').filter(id_orden=TASK_ID).first()
if p:
    print(f"  ✅ Sí. Orden={p.id_orden}, Maquina='{p.maquina}', Prioridad={p.prioridad}")
    print(f"     Escenario ID: {p.scenario_id}")
else:
    print(f"  ❌ NO está en PrioridadManual. No se guardó el movimiento.")

print()
print("=" * 60)
print("PASO 2: ¿Cuál es el escenario PRINCIPAL activo?")
print("=" * 60)
scenario = Scenario.objects.using('default').filter(es_principal=True).first()
if scenario:
    print(f"  Escenario principal: ID={scenario.id}, Nombre='{scenario.nombre}'")
    # Check if PrioridadManual belongs to this scenario
    if p and str(p.scenario_id) == str(scenario.id):
        print(f"  ✅ El override pertenece al escenario principal.")
    else:
        print(f"  ❌ MISMATCH: Override en escenario {p.scenario_id if p else 'N/A'} != Escenario Principal {scenario.id}")
        print(f"     *** ESTE ES EL BUG: El override está en el escenario equivocado ***")
else:
    print("  ❌ No hay escenario principal")

print()
print("=" * 60)
print("PASO 3: ¿La tarea 47468 existe en el ERP?")
print("=" * 60)
all_tasks = get_planificacion_data({})
task_in_erp = next((t for t in all_tasks if str(t.get('Idorden')) == TASK_ID), None)
if task_in_erp:
    print(f"  ✅ Existe. MachineID='{task_in_erp.get('Idmaquina')}', MachineName='{task_in_erp.get('MAQUINAD')}'")
    print(f"     Proyecto: {task_in_erp.get('ProyectoCode')}")
else:
    print(f"  ❌ NO encontrada en ERP (sin filtros). Puede estar oculta o excluida.")

print()
print("=" * 60)
print("PASO 4: ¿Cómo están configuradas HAAS y TSUGAMI en MaquinaConfig?")
print("=" * 60)
for m in MaquinaConfig.objects.using('default').all():
    if 'HAAS' in m.nombre.upper() or 'TSUGAMI' in m.nombre.upper():
        print(f"  ID='{m.id_maquina}', Nombre='{m.nombre}'")
