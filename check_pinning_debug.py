import os
import django
import sys

# Setup Django environment
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, MaquinaConfig

def check_task_2654():
    print("--- Checking Task 2654 ---")
    try:
        pm = PrioridadManual.objects.get(id_orden=2654)
        print(f"FOUND Override for 2654:")
        print(f"   Maquina: '{pm.maquina}'")
        print(f"   Prioridad: {pm.prioridad}")
        print(f"   Inicio Manual: {pm.fecha_inicio_manual}")
    except PrioridadManual.DoesNotExist:
        print("NOT FOUND: No PrioridadManual entry found for 2654.")

def list_machines():
    print("\n--- Checking Machine Configs ---")
    machines = MaquinaConfig.objects.all()
    for m in machines:
        print(f"   ID: '{m.id_maquina}' -> Name: '{m.nombre}'")

if __name__ == "__main__":
    check_task_2654()
    list_machines()
