"""
Script to fix tasks that were incorrectly moved to another machine.
Deletes manual overrides for tasks 45364 and 44948 so they return to their original machines.
"""

import os
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual

# Tasks that should NOT be on MAC20 (VF3-2)
tasks_to_fix = [45364, 44948]

print("=" * 60)
print("FIXING INCORRECTLY MOVED TASKS")
print("=" * 60)

for task_id in tasks_to_fix:
    entries = PrioridadManual.objects.using('default').filter(id_orden=task_id)
    
    if entries.exists():
        for entry in entries:
            print(f"Task {task_id}: Found on machine {entry.maquina}")
            print(f"  -> Deleting manual override...")
            entry.delete()
            print(f"  OK Deleted")
    else:
        print(f"Task {task_id}: No manual override found (already clean)")

print("\n" + "=" * 60)
print("DONE! Refresh the Gantt in 'Automatic' mode to see original positions")
print("=" * 60)
