"""
Test de visualizacion completa - igual que lo que ve el usuario.
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
            'fecha_desde': '2026-03-16',  # Semana con sabado
        }
        self.session = {}
        self.method = 'GET'

print("=" * 70)
print("TEST DE VISUALIZACION COMPLETA")
print("=" * 70)

request = MockRequest()
data = get_gantt_data(request, force_run=True)

print(f"\nglobal_min_h: {data['global_min_h']}")
print(f"global_max_h: {data['global_max_h']}")
print(f"slots_per_day: {data['global_max_h'] - data['global_min_h']}")
print(f"Total time_columns: {len(data['time_columns'])}")

# Encontrar tareas del TSUGAMI
print("\n--- TAREAS DEL TSUGAMI ---")
COL_WIDTH = 40

for row in data['timeline_data']:
    machine_name = row['machine'].nombre if hasattr(row['machine'], 'nombre') else str(row['machine'])
    if 'TSUGAMI' in machine_name.upper():
        print(f"\n{machine_name}:")

        for task in row['tasks']:
            start = task.get('start_date')
            end = task.get('end_date')
            if start and start.weekday() == 5:  # Sabado
                duration_real = task.get('duration_real', 0)
                visual_left = task.get('visual_left', 0)
                visual_width = task.get('visual_width', 0)

                print(f"  Task {task.get('Idorden')}:")
                print(f"    start: {start.strftime('%H:%M')}")
                print(f"    end: {end.strftime('%H:%M')}")
                print(f"    duration_real: {duration_real:.2f}h")
                print(f"    visual_left: {visual_left}px")
                print(f"    visual_width: {visual_width}px")
                print(f"    visual_end: {visual_left + visual_width}px")

                # Calcular que hora seria el final visual
                slots_per_day = data['global_max_h'] - data['global_min_h']
                end_col = (visual_left + visual_width) / COL_WIDTH
                end_hour = data['global_min_h'] + end_col
                print(f"    end_hour visual: {end_hour:.1f} ({data['global_min_h']} + {end_col:.1f})")

                # Verificar si excede 13hs
                if end.hour > 13 or (end.hour == 13 and end.minute > 0):
                    print(f"    [BUG] END DATE excede 13:00!")

# Mostrar columnas del sabado
print("\n--- COLUMNAS DEL SABADO ---")
saturday_cols = [(i, c) for i, c in enumerate(data['time_columns']) if c.weekday() == 5]
if saturday_cols:
    print(f"Primera columna sabado: {saturday_cols[0][0]} = {saturday_cols[0][1].strftime('%H:%M')}")
    print(f"Ultima columna sabado: {saturday_cols[-1][0]} = {saturday_cols[-1][1].strftime('%H:%M')}")

    # Mostrar columnas entre 12 y 14
    for i, col in saturday_cols:
        if 12 <= col.hour <= 14:
            print(f"  Columna {i}: {col.strftime('%H:%M')} (posicion: {i * COL_WIDTH}px)")
