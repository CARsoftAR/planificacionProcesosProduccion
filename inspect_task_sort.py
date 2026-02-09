import os
import django
import sys
from datetime import datetime

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import VTman, PrioridadManual

def inspect_tasks():
    ids = [45363, 45364, 46402]
    
    print(f"{'ID':<10} | {'Nivel':<10} | {'F. Inicio Man':<25} | {'Maquina'}")
    print("-" * 60)
    
    # Check VTman (Main Data) - Note: Nivel might not be in VTman model definition explicitly if it's dynamic or in another field, 
    # but let's check what fields we have or if it comes from raw SQL in services.py.
    # Actually models.py VTman definition provided earlier doesn't show 'nivel_planificacion'. 
    # It seems 'nivel_planificacion' is calculated or comes from a view not fully reflected in the simple model or is raw.
    # However, PrioridadManual definitely has 'nivel_manual'.
    
    # Since I can't easily query the raw 'nivel_planificacion' via ORM if it's not in the model, 
    # I will verify the Manual Overrides first, as that's often the culprit.
    
    for tid in ids:
        # Check Manual Priorities
        manual = PrioridadManual.objects.filter(id_orden=tid).first()
        man_date = "None"
        man_level = "None"
        
        if manual:
            if manual.fecha_inicio_manual:
                man_date = str(manual.fecha_inicio_manual)
            if manual.nivel_manual is not None:
                man_level = str(manual.nivel_manual)
        
        print(f"{tid:<10} | {man_level:<10} | {man_date:<25} |")

if __name__ == "__main__":
    inspect_tasks()
