import os
import sys
import django
from collections import defaultdict

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data
from produccion.models import PrioridadManual

def debug_dependencies():
    # Filter for Project 25-005
    filtros = {'proyectos': ['25-005']} 
    print("Fetching tasks for project 25-005...")
    tasks = get_planificacion_data(filtros)
    
    # Load Overrides
    manual_entries = PrioridadManual.objects.all()
    virtual_overrides = {}
    for entry in manual_entries:
        virtual_overrides[entry.id_orden] = {
            'nivel_manual': entry.nivel_manual,
            'maquina': entry.maquina
        }
        
    print(f"\nLoaded {len(virtual_overrides)} overrides.")

    # Apply Overrides (Mimic gantt_logic)
    ids_of_interest = ['44948', '45363', '45364']
    
    print("\n--- Task Data (After Overrides) ---")
    
    final_tasks = []
    
    for task in tasks:
        p_id = task.get('Idorden')
        # Robust ID check
        ov_data = None
        if p_id in virtual_overrides:
             ov_data = virtual_overrides[p_id]
        else:
             try:
                 p_id_int = int(p_id)
                 if p_id_int in virtual_overrides:
                     ov_data = virtual_overrides[p_id_int]
             except: pass
        
        # Apply Nivel Manual
        if ov_data and ov_data.get('nivel_manual') is not None:
             task['Nivel_Planificacion'] = ov_data['nivel_manual']
             task['IS_MANUAL_NIVEL'] = True
        else:
             task['IS_MANUAL_NIVEL'] = False
             
        # Apply Machine Manual
        if ov_data and ov_data.get('maquina'):
            task['MAQUINAD'] = ov_data['maquina']
             
        if str(p_id) in ids_of_interest:
            print(f"ID: {p_id}")
            print(f"  Desc: {task.get('Descripcion')}")
            print(f"  Maq: {task.get('MAQUINAD')}")
            print(f"  Nivel Plan: {task.get('Nivel_Planificacion')} (Manual: {task.get('IS_MANUAL_NIVEL')})")
            print(f"  Nivel DB Clean: {task.get('Nivel')}")
        
        final_tasks.append(task)

    # Build Dependency Map
    print("\n--- Building Dependency Map ---")
    orders_map = defaultdict(list)
    for task in final_tasks:
        formula = task.get('ProyectoCode')
        if formula:
            orders_map[formula].append(task)
            
    dependency_map = {}
    
    def get_nivel(t):
        try:
            val = t.get('Nivel_Planificacion')
            if val is None: return 0
            return float(val)
        except: return 0

    for formula, tasks_in_order in orders_map.items():
        if formula != '25-005': continue
        
        tasks_sorted = sorted(tasks_in_order, key=get_nivel, reverse=True)
        # Filter assigned only?
        tasks_assigned = [t for t in tasks_sorted] # Mimic logic: if t.get('MAQUINAD') and t.get('MAQUINAD') != 'SIN ASIGNAR']
        
        print(f"Project {formula} has {len(tasks_assigned)} tasks.")
        
        nivel_groups = {}
        for task in tasks_assigned:
            nivel = get_nivel(task)
            if nivel not in nivel_groups:
                nivel_groups[nivel] = []
            nivel_groups[nivel].append(task)
            
        sorted_niveles = sorted(nivel_groups.keys(), reverse=True)
        print(f"Sorted Niveles: {sorted_niveles}")
        
        for i in range(len(sorted_niveles) - 1):
            higher_nivel = sorted_niveles[i]
            lower_nivel = sorted_niveles[i + 1]
            
            print(f"  Linking Level {higher_nivel} -> Level {lower_nivel}")
            
            for successor in nivel_groups[lower_nivel]:
                succ_id = successor.get('Idorden')
                for predecessor in nivel_groups[higher_nivel]:
                    pred_id = predecessor.get('Idorden')
                    
                    print(f"    Dependency: {pred_id} (L{higher_nivel}) -> {succ_id} (L{lower_nivel})")
                    
                    if succ_id not in dependency_map: dependency_map[succ_id] = []
                    if pred_id not in dependency_map[succ_id]: dependency_map[succ_id].append(pred_id)

if __name__ == "__main__":
    debug_dependencies()
