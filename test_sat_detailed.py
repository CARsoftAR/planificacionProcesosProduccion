"""
Test especifico para encontrar por que una tarea de sabado termina a las 14:00.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime
from produccion.gantt_logic import get_gantt_data

class MockRequest:
    def __init__(self):
        self.GET = {
            'run': '1',
            'fecha_desde': '2026-03-16',
        }
        self.session = {}
        self.method = 'GET'

print("=" * 70)
print("BUSCANDO TAREAS QUE TERMINAN DESPUES DE LAS 13:00 EN SABADO")
print("=" * 70)

request = MockRequest()
data = get_gantt_data(request, force_run=True)

# Buscar todas las tareas de sabado que terminan DESPUES de las 13:00
bugs = []
for row in data['timeline_data']:
    machine = row['machine']
    machine_name = machine.nombre if hasattr(machine, 'nombre') else str(machine)
    
    for task in row['tasks']:
        start = task.get('start_date')
        end = task.get('end_date')
        
        if start and end and start.weekday() == 5:  # Sabado
            # Verificar si termina despues de las 13:00
            if end.hour > 13 or (end.hour == 13 and end.minute > 0):
                bugs.append({
                    'machine': machine_name,
                    'task_id': task.get('Idorden'),
                    'start': start,
                    'end': end,
                    'duration': task.get('duration_real'),
                    'end_hour': f"{end.hour}:{end.minute:02d}"
                })

if bugs:
    print(f"\n[ERROR] Se encontraron {len(bugs)} tareas que exceden las 13:00 en sabado:")
    for b in bugs[:20]:  # Mostrar max 20
        print(f"\n  Maquina: {b['machine']}")
        print(f"  Task ID: {b['task_id']}")
        print(f"  Start: {b['start']}")
        print(f"  End: {b['end']} ({b['end_hour']})")
        print(f"  Duration: {b['duration']:.2f}h")
        print(f"  -> Deberia terminar a las 13:00, termina a las {b['end_hour']}")
else:
    print("\n[OK] No se encontraron tareas que excedan las 13:00 en sabado")

# Mostrar algunas tareas de TSUGAMI para comparar
print("\n" + "=" * 70)
print("TAREAS DEL TSUGAMI EN SABADO (primeros 10):")
print("=" * 70)

count = 0
for row in data['timeline_data']:
    machine = row['machine']
    if hasattr(machine, 'nombre') and 'TSUGAMI' in machine.nombre.upper():
        for task in row['tasks']:
            start = task.get('start_date')
            end = task.get('end_date')
            if start and start.weekday() == 5:
                count += 1
                if count <= 10:
                    print(f"\n  Task {task.get('Idorden')}:")
                    print(f"    Start: {start}")
                    print(f"    End: {end}")
                    print(f"    Duration: {task.get('duration_real', 0):.2f}h")
                    if end.hour > 13 or (end.hour == 13 and end.minute > 0):
                        print(f"    [BUG] EXCEDE 13:00!")

print(f"\nTotal TSUGAMI sabado tasks: {count}")
