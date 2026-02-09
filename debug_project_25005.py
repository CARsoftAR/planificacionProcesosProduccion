"""
Debug project 25-005 operations - where they should be vs where they appear
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data
from produccion.models import PrioridadManual

print("=" * 80)
print("PROJECT 25-005 OPERATIONS DEBUG")
print("=" * 80)

# Get all tasks for project 25-005
all_tasks = get_planificacion_data({'proyectos': ['25-005']})

print(f"\nTotal operations found for project 25-005: {len(all_tasks)}\n")

for i, task in enumerate(all_tasks, 1):
    print(f"Operation {i}:")
    print(f"  ID Orden: {task.get('Idorden')}")
    print(f"  Proyecto: {task.get('Proyecto')}")
    print(f"  Denominación: {task.get('Denominacion', 'N/A')}")
    print(f"  Máquina (Code): {task.get('Maquina')} ")
    print(f"  Máquina (Desc): {task.get('Maquina_Descripcion', 'N/A')}")
    print(f"  Tiempo Proceso: {task.get('Tiempo_Proceso')} horas")
    print(f"  Cantidad: {task.get('Cantidad', 1)}")
    print(f"  Nivel: {task.get('Nivel_Planificacion', 'N/A')}")
    print()

# Check for manual overrides
print("\n" + "=" * 80)
print("MANUAL OVERRIDES FOR PROJECT 25-005")
print("=" * 80)

task_ids = [t.get('Idorden') for t in all_tasks]
overrides = PrioridadManual.objects.using('default').filter(id_orden__in=task_ids)

if overrides.exists():
    for override in overrides:
        print(f"\nTask {override.id_orden} has manual override:")
        print(f"  Original machine from SQL: ?")
        print(f"  Override machine: {override.maquina}")
        print(f"  Override time: {override.tiempo_manual} h")
        print(f"  Manual start: {override.fecha_inicio_manual}")
else:
    print("\nNo manual overrides found for these tasks.")

# Summary by machine
print("\n" + "=" * 80)
print("SUMMARY BY MACHINE (FROM SQL SERVER)")
print("=" * 80)

from collections import defaultdict
machine_summary = defaultdict(lambda: {'count': 0, 'total_time': 0})

for task in all_tasks:
    machine = task.get('Maquina_Descripcion', task.get('Maquina', 'Unknown'))
    time = task.get('Tiempo_Proceso', 0)
    
    machine_summary[machine]['count'] += 1
    machine_summary[machine]['total_time'] += time

for machine, data in sorted(machine_summary.items()):
    print(f"{machine}: {data['count']} ops, {data['total_time']:.2f} hours total")

print("\n" + "=" * 80)
print("If the Gantt shows different values, the calculation logic is wrong.")
print("=" * 80)
