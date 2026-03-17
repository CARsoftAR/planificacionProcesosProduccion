
import os
import django
import sys

# Add parent directory to path to ensure modules are found
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

def inspect_project_data(project_code):
    data = get_planificacion_data({'proyectos': [project_code]})
    print(f"Total tasks for {project_code}: {len(data)}")
    
    # Filter by some machine to see its sequence
    machines_of_interest = ['HAAS', 'DMG 800V', 'VF2']
    
    tasks_by_machine = {}
    for t in data:
        m = t.get('MAQUINAD')
        if m not in tasks_by_machine: tasks_by_machine[m] = []
        tasks_by_machine[m].append(t)
        
    for m in machines_of_interest:
        print(f"\n--- MACHINE: {m} ---")
        machine_tasks = tasks_by_machine.get(m, [])
        # Sort by level to see process order
        machine_tasks.sort(key=lambda x: (float(x.get('Nivel_Planificacion') or 0)), reverse=True)
        for t in machine_tasks:
             print(f"  ID: {t.get('Idorden')}, Lvl: {t.get('Nivel_Planificacion')}, Desc: {t.get('Descri')}")

if __name__ == "__main__":
    inspect_project_data('26-021')
