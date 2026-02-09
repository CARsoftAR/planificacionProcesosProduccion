import os
import django
import sys

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual

def remove_manual_pin_46403():
    try:
        task = PrioridadManual.objects.get(id_orden=46403)
        if task.fecha_inicio_manual:
            print(f"Task 46403 has manual PIN at: {task.fecha_inicio_manual}")
            task.fecha_inicio_manual = None
            task.save()
            print("Successfully removed PIN for 46403.")
        else:
            print("Task 46403 has NO manual pin.")
            
    except PrioridadManual.DoesNotExist:
        print("Task 46403 not found in Manual Overrides.")

if __name__ == "__main__":
    remove_manual_pin_46403()
