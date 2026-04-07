import os
import django
import sys

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data
from produccion.models import HiddenTask, Scenario, PrioridadManual, MaquinaConfig

def analyze_projects_tasks(project_list):
    print(f"ANÁLISIS DE TAREAS PARA PROYECTOS: {project_list}")
    print("-" * 50)
    
    # 1. Fetch raw data from SQL Server using the system's service
    # This includes the exclude_completed=True by default
    filtros = {'proyectos': project_list}
    raw_data = get_planificacion_data(filtros)
    
    # 2. Get hidden tasks from SQLite
    hidden_ids = set(HiddenTask.objects.using('default').values_list('id_orden', flat=True))
    
    # 3. Get manual overrides/moves from SQLite (Scenario specific)
    # We use the principal scenario as it's the default
    active_scenario = Scenario.objects.using('default').filter(es_principal=True).first()
    overrides = {}
    if active_scenario:
        overrides = {p.id_orden: p.maquina for p in PrioridadManual.objects.using('default').filter(scenario=active_scenario)}
    
    # 4. Map machine IDs to Names if local config exists
    local_machines = MaquinaConfig.objects.using('default').all()
    id_to_name = {m.id_maquina.strip(): m.nombre.strip() for m in local_machines}
    
    # Process and group
    grouped = {}
    
    for item in raw_data:
        id_orden = str(item.get('Idorden'))
        
        # Skip if hidden
        if id_orden in hidden_ids:
            continue
            
        # Determine machine (respecting manual moves)
        final_machine_id = overrides.get(id_orden, item.get('Idmaquina', 'SIN ASIGNAR'))
        if not final_machine_id: final_machine_id = 'SIN ASIGNAR'
        
        # Translate to Name
        machine_name = id_to_name.get(final_machine_id, item.get('MAQUINAD', final_machine_id))
        if not machine_name: machine_name = 'SIN ASIGNAR'
        
        grouped[machine_name] = grouped.get(machine_name, 0) + 1
        
        # If it's TSUGAMI, we can track it separately for debugging
        if 'TSUGAMI' in machine_name.upper():
            pass # Keep track if needed
            
    # Print results
    print(f"{'MÁQUINA':<30} | {'OPERACIONES':<10}")
    print("-" * 50)
    for machine, count in sorted(grouped.items(), key=lambda x: x[1], reverse=True):
        print(f"{machine:<30} | {count:<10}")
    
    total = sum(grouped.values())
    print("-" * 50)
    print(f"{'TOTAL':<30} | {total:<10}")

if __name__ == "__main__":
    analyze_projects_tasks(['26-021', '25-072'])
