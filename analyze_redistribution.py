import os
import django
import sys
from django.utils import timezone

current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.append(current_dir)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import MaquinaConfig, Scenario
from produccion.gantt_logic import get_gantt_data, find_compatible_machines

def analyze_tsugami_redistribution():
    maquinas = list(MaquinaConfig.objects.all())
    tsugami = next(m for m in maquinas if 'TSUGAMI' in m.nombre)
    
    print(f"Buscando maquinas compatibles con {tsugami.nombre}:")
    compatible = find_compatible_machines(tsugami, maquinas)
    
    for m, score in compatible:
        print(f" - {m.nombre} (Score: {score})")

    # Si hay compatibles con Score 100, la capacidad adaptativa deberia funcionar 
    # SI EL USUARIO LA EJECUTA.
    
if __name__ == "__main__":
    analyze_tsugami_redistribution()
