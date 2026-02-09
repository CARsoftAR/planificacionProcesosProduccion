import os
import django
import sys

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual

def unpin_task_45364():
    try:
        task = PrioridadManual.objects.get(id_orden=45364)
        print(f"Found PIN for 45364: {task.fecha_inicio_manual}")
        task.fecha_inicio_manual = None
        task.save()
        print("Successfully removed PIN for 45364.")
    except PrioridadManual.DoesNotExist:
        print("No manual override found for 45364.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    unpin_task_45364()
