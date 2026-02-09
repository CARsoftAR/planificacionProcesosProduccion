"""
Script to debug Gantt task placement and duration calculation.
Shows where tasks are being rendered vs. where they should be.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

# Get tasks for the problematic machines
print("=" * 80)
print("DEBUGGING TASK PLACEMENT - TM1 vs VM3")
print("=" * 80)

# Fetch all tasks without machine filter to see raw data
all_tasks = get_planificacion_data({})

# Filter for TM1 and VM3
tm1_tasks = [t for t in all_tasks if t.get('Maquina_Descripcion') == 'TM1']
vm3_tasks = [t for t in all_tasks if t.get('Maquina_Descripcion') == 'VM3']

print(f"\nTM1 Tasks Found: {len(tm1_tasks)}")
for task in tm1_tasks:
    print(f"  ID: {task.get('Idorden')}")
    print(f"    Proyecto: {task.get('Proyecto')}")
    print(f"    Tiempo: {task.get('Tiempo_Proceso')} h")
    print(f"    Máquina: {task.get('Maquina_Descripcion')} (ID: {task.get('Maquina')})")
    print()

print(f"\nVM3 Tasks Found: {len(vm3_tasks)}")
for task in vm3_tasks:
    print(f"  ID: {task.get('Idorden')}")
    print(f"    Proyecto: {task.get('Proyecto')}")
    print(f"    Tiempo: {task.get('Tiempo_Proceso')} h")
    print(f"    Máquina: {task.get('Maquina_Descripcion')} (ID: {task.get('Maquina')})")
    print()

# Check if there are manual overrides affecting this
from produccion.models import PrioridadManual

print("\n" + "=" * 80)
print("MANUAL OVERRIDES (PrioridadManual)")
print("=" * 80)

all_overrides = PrioridadManual.objects.using('default').all()
for override in all_overrides:
    print(f"Task {override.id_orden}:")
    print(f"  Machine Override: {override.maquina}")
    print(f"  Time Override: {override.tiempo_manual}")
    print(f"  Manual Start: {override.fecha_inicio_manual}")
    print()

# Summary
print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)
tm1_total_time = sum(t.get('Tiempo_Proceso', 0) for t in tm1_tasks)
vm3_total_time = sum(t.get('Tiempo_Proceso', 0) for t in vm3_tasks)

print(f"TM1 Total Time (from SQL): {tm1_total_time:.2f} hours")
print(f"VM3 Total Time (from SQL): {vm3_total_time:.2f} hours")
print(f"\nIf Gantt shows different values, there's a calculation issue.")
