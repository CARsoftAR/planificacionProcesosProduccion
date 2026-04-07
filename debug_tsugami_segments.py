"""
Debug TSUGAMI segments on Saturday.
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
print("DEBUG TSUGAMI SEGMENTS")
print("=" * 70)

request = MockRequest()
data = get_gantt_data(request, force_run=True)

# Calculate visual positions (same as views.py)
COL_WIDTH = 40
global_min_h = data['global_min_h']
global_max_h = data['global_max_h']
valid_dates = data['valid_dates']
date_to_visual_index = { d: i for i, d in enumerate(valid_dates) }
slots_per_day = global_max_h - global_min_h

print(f"\nglobal_min_h: {global_min_h}")
print(f"global_max_h: {global_max_h}")
print(f"slots_per_day: {slots_per_day}")
print(f"valid_dates count: {len(valid_dates)}")

# Find TSUGAMI Saturday segments
for row in data['timeline_data']:
    machine_name = row['machine'].nombre if hasattr(row['machine'], 'nombre') else str(row['machine'])
    if 'TSUGAMI' in machine_name.upper():
        print(f"\n=== Machine: {machine_name} ===")

        # Get machine schedules
        if hasattr(row['machine'], 'horarios'):
            for h in row['machine'].horarios.all():
                print(f"  Schedule: {h.dia} {h.hora_inicio.strftime('%H:%M')}-{h.hora_fin.strftime('%H:%M')}")

        for task in row['tasks']:
            start = task.get('start_date')
            end = task.get('end_date')
            if start and end and start.weekday() == 5:  # Saturday
                print(f"\n  Task {task.get('Idorden')}:")
                print(f"    Segments:")

                # Check if task has multiple segments
                segment_index = task.get('segment_index', 0)
                print(f"    - segment_index: {segment_index}")
                print(f"    - start: {start.strftime('%H:%M:%S')}")
                print(f"    - end: {end.strftime('%H:%M:%S')}")
                print(f"    - duration_real: {task.get('duration_real', 0):.2f}h")
                print(f"    - duration_task: {task.get('duration_task', 0):.2f}h")

                # Calculate visual position
                t_date = start.date()
                day_visual_idx = date_to_visual_index.get(t_date, 0)
                hour_diff = (start.hour - global_min_h) + (start.minute / 60.0)
                col_index = (day_visual_idx * slots_per_day) + hour_diff
                visual_left = col_index * COL_WIDTH
                visual_width = task.get('duration_real', 0) * COL_WIDTH

                print(f"    - day_visual_idx: {day_visual_idx}")
                print(f"    - hour_diff: {hour_diff:.2f}")
                print(f"    - visual_left: {visual_left}px")
                print(f"    - visual_width: {visual_width}px")
                print(f"    - Visual end position: {visual_left + visual_width}px")
                print(f"    - Would end at column: {(visual_left + visual_width) / COL_WIDTH:.1f}")
                print(f"    - Equivalent hour: {global_min_h + (visual_left + visual_width) / COL_WIDTH:.1f}")

                # What SHOULD happen for Saturday 7-13
                sat_hours = 6  # 7:00 to 13:00 = 6 hours
                correct_width = sat_hours * COL_WIDTH
                print(f"    - CORRECT for SA (6h): width={correct_width}px, end_col={sat_hours}")

# Show valid_dates and their indices
print("\n--- Valid Dates ---")
for i, d in enumerate(valid_dates[:10]):
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d.weekday()]
    print(f"  {i}: {d} ({wd})")
