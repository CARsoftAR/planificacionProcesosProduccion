import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

# Buscar las tareas específicas usando filtros
target_ids = [46762, 46759]
found_tasks = []

print("Buscando tareas 46762 y 46759...")
print("="*60)

# Buscar cada tarea individualmente
for task_id in target_ids:
    tasks = get_planificacion_data({'id_orden_in': [task_id]})
    if tasks:
        found_tasks.extend(tasks)
        print(f"\nEncontrada tarea {task_id}: {len(tasks)} resultado(s)")
    else:
        print(f"\nNo se encontro tarea {task_id}")

print(f"\n\nTotal de tareas encontradas: {len(found_tasks)}")
print("="*60)

# Mostrar detalles de cada tarea encontrada
for task in found_tasks:
    print(f"\n{'='*60}")
    print(f"Tarea ID: {task.get('Idorden')}")
    print(f"Mstnmbr: {task.get('Mstnmbr')}")
    print(f"Nivel: {task.get('Nivel')}")
    print(f"Nivel_Planificacion: {task.get('Nivel_Planificacion')}")
    print(f"Maquina: {task.get('MAQUINAD')}")
    print(f"Proyecto: {task.get('ProyectoCode')}")
    print(f"Descripcion: {task.get('Descri')}")
    print(f"{'='*60}")

# Verificar si comparten Mstnmbr
if len(found_tasks) == 2:
    mstnmbr_1 = found_tasks[0].get('Mstnmbr')
    mstnmbr_2 = found_tasks[1].get('Mstnmbr')
    
    print(f"\n\n{'='*60}")
    print("ANÁLISIS DE DEPENDENCIA:")
    print(f"{'='*60}")
    print(f"Tarea 46762 - Mstnmbr: {mstnmbr_1}")
    print(f"Tarea 46759 - Mstnmbr: {mstnmbr_2}")
    
    if mstnmbr_1 == mstnmbr_2:
        print("\n[OK] Comparten el mismo Mstnmbr - DEBERIAN estar vinculadas")
        
        # Ordenar por nivel
        sorted_tasks = sorted(found_tasks, key=lambda x: x.get('Nivel_Planificacion', 0), reverse=True)
        print("\nOrden esperado (por Nivel_Planificacion descendente):")
        for i, t in enumerate(sorted_tasks, 1):
            print(f"  {i}. ID {t.get('Idorden')} - Nivel {t.get('Nivel_Planificacion')} - {t.get('MAQUINAD')}")
    else:
        print("\n[ERROR] NO comparten el mismo Mstnmbr - NO se vincularan automaticamente")
        print("  -> Necesitas vincularlas manualmente desde el Gantt")
else:
    print(f"\n[ADVERTENCIA] Solo se encontraron {len(found_tasks)} de las 2 tareas buscadas")
