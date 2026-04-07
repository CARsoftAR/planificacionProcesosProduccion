"""
Debug TSUGAMI Saturday visual rendering.
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
print("DEBUG TSUGAMI VISUAL RENDERING")
print("=" * 70)

request = MockRequest()
data = get_gantt_data(request, force_run=True)

print(f"\nglobal_min_h: {data['global_min_h']}")
print(f"global_max_h: {data['global_max_h']}")
print(f"slots_per_day: {data['global_max_h'] - data['global_min_h']}")
print(f"total time_columns: {len(data['time_columns'])}")

# Find TSUGAMI tasks
print("\n--- TSUGAMI Saturday Tasks ---")
for row in data['timeline_data']:
    machine_name = row['machine'].nombre if hasattr(row['machine'], 'nombre') else str(row['machine'])
    if 'TSUGAMI' in machine_name.upper():
        for task in row['tasks']:
            start = task.get('start_date')
            end = task.get('end_date')
            if start and start.weekday() == 5:  # Saturday
                duration = task.get('duration_real', 0)
                visual_left = task.get('visual_left', 0)
                visual_width = task.get('visual_width', 0)
                print(f"\nTask {task.get('Idorden')}:")
                print(f"  Start: {start.strftime('%a %Y-%m-%d %H:%M')}")
                print(f"  End: {end.strftime('%a %Y-%m-%d %H:%M')}")
                print(f"  Duration: {duration:.2f}h")
                print(f"  Visual Left: {visual_left}px")
                print(f"  Visual Width: {visual_width}px")

                # Calculate where it SHOULD end visually
                slots_per_day = data['global_max_h'] - data['global_min_h']
                start_hour_offset = (start.hour - data['global_min_h']) + (start.minute / 60.0)
                end_hour_offset = start_hour_offset + duration
                print(f"  Hour offset start: {start_hour_offset:.2f}h into day")
                print(f"  Hour offset end: {end_hour_offset:.2f}h into day")
                print(f"  Should end at visual column: {end_hour_offset:.2f} * 40 = {end_hour_offset * 40:.0f}px")
                print(f"  Should be at hour: {data['global_min_h'] + end_hour_offset:.2f}")

                # Check if end hour is within Saturday schedule
                print(f"  SATURDAY SCHEDULE: Should end at or before 13:00")

# Show what columns are generated
print("\n--- Time Columns for Saturday ---")
saturday_cols = [c for c in data['time_columns'] if c.weekday() == 5]
print(f"Saturday columns count: {len(saturday_cols)}")
if saturday_cols:
    first_sat = saturday_cols[0]
    print(f"First Saturday column: {first_sat.strftime('%H:%M')}")
    last_sat = saturday_cols[-1]
    print(f"Last Saturday column: {last_sat.strftime('%H:%M')}")

    # Show columns around 13:00
    for col in saturday_cols:
        if col.hour >= 12 and col.hour <= 14:
            idx = data['time_columns'].index(col)
            print(f"  Column {idx}: {col.strftime('%H:%M')} (visual position: {idx * 40}px)")
