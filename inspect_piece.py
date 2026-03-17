
import os
import django
import sys
from collections import defaultdict

# Add parent directory to path to ensure modules are found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

def inspect_project_data(project_code):
    data = get_planificacion_data({'proyectos': [project_code]})
    print(f"Total tasks for {project_code}: {len(data)}")
    
    tasks_by_desc = defaultdict(list)
    for t in data:
        desc = str(t.get('Descri', '')).strip()
        # Get piece name (everything before the last process)
        if " - " in desc:
            parts = desc.split(" - ")
            if len(parts) > 1:
                key = " - ".join(parts[:-1]).strip()
                tasks_by_desc[key].append(t)
    
    # Check specifically for BUJE ROSCADO 0121
    key_of_interest = "07-0121 - BUJE ROSCADO"
    print(f"\n--- PIECE: {key_of_interest} ---")
    relevant_tasks = tasks_by_desc.get(key_of_interest, [])
    relevant_tasks.sort(key=lambda x: (float(x.get('Nivel_Planificacion') or 0)), reverse=True)
    for t in relevant_tasks:
        print(f"  ID: {t.get('Idorden')}, Lvl: {t.get('Nivel_Planificacion')}, Machine: {t.get('MAQUINAD')}, Desc: {t.get('Descri')}")

if __name__ == "__main__":
    inspect_project_data('26-021')
