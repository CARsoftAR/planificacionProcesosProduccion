"""
Traza la lógica del gantt_logic.py para la tarea 47468 paso a paso.
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from collections import defaultdict
from produccion.models import PrioridadManual, Scenario, MaquinaConfig, HiddenTask
from produccion.services import get_planificacion_data

TASK_ID = '47468'

# Simular lo que hace gantt_logic.py
print("=" * 60)
print("Simulando gantt_logic.py para la tarea 47468")
print("=" * 60)

# 1. Cargar overrides como hace la función
scenario = Scenario.objects.using('default').filter(es_principal=True).first()
manual_entries = PrioridadManual.objects.using('default').filter(scenario=scenario)
virtual_overrides = {}
for entry in manual_entries:
    virtual_overrides[str(entry.id_orden)] = {
        'maquina': entry.maquina,
        'prioridad': entry.prioridad,
    }

print(f"\n1. virtual_overrides para tarea {TASK_ID}: {virtual_overrides.get(TASK_ID, 'NO ENCONTRADO')}")

# 2. Construir tasks_moved_in_map
tasks_moved_in_map = defaultdict(list)
for tid, override in virtual_overrides.items():
    if override.get('maquina'):
        key = str(override['maquina']).strip().upper()
        tasks_moved_in_map[key].append(tid)

print(f"\n2. tasks_moved_in_map para 'MAC08': {tasks_moved_in_map.get('MAC08', 'VACÍO')}")
print(f"   Todas las claves en tasks_moved_in_map: {list(tasks_moved_in_map.keys())}")

# 3. Cargar tareas del ERP
all_tasks_raw = get_planificacion_data({'proyectos': ['26-021', '25-072']})
task_in_raw = next((t for t in all_tasks_raw if str(t.get('Idorden')) == TASK_ID), None)
print(f"\n3. Tarea {TASK_ID} en all_tasks_raw: {'✅ ENCONTRADA' if task_in_raw else '❌ NO ENCONTRADA'}")
if task_in_raw:
    print(f"   MachineID original en ERP: {task_in_raw.get('Idmaquina')}")
    print(f"   MachineName original en ERP: {task_in_raw.get('MAQUINAD')}")

# 4. Simular el bucle de HAAS (MAC08)
haas_config = MaquinaConfig.objects.using('default').filter(id_maquina='MAC08').first()
print(f"\n4. MaquinaConfig para HAAS: {haas_config.id_maquina}/{haas_config.nombre}")

machine_id = str(haas_config.id_maquina).strip()
current_machine_name = str(haas_config.nombre).strip().upper()

moved_in_ids = []
if machine_id.upper() in tasks_moved_in_map:
    moved_in_ids.extend(tasks_moved_in_map[machine_id.upper()])
if current_machine_name.upper() in tasks_moved_in_map:
    for i in tasks_moved_in_map[current_machine_name.upper()]:
        if i not in moved_in_ids: moved_in_ids.append(i)

print(f"\n5. moved_in_ids para HAAS: {moved_in_ids}")

if TASK_ID in moved_in_ids:
    print(f"   ✅ La tarea {TASK_ID} está en moved_in_ids")
    task_found = next((tx for tx in all_tasks_raw if str(tx['Idorden']) == TASK_ID), None)
    print(f"   Buscando en all_tasks_raw: {'✅ ENCONTRADA' if task_found else '❌ NO ENCONTRADA'}")
else:
    print(f"   ❌ La tarea {TASK_ID} NO está en moved_in_ids")
    print(f"      Esto es el bug principal. El override dice MAC08 pero no llega al bucle de HAAS.")

