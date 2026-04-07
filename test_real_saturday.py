"""
Test with real production data - check Saturday tasks in the actual database.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime, timedelta
from produccion.gantt_logic import get_gantt_data

print("=" * 70)
print("REAL DATA SATURDAY TEST")
print("=" * 70)

# Create a mock request with session
class MockRequest:
    def __init__(self):
        self.GET = {
            'run': '1',
            'fecha_desde': '2026-03-16',  # Week containing Saturday March 21
        }
        self.session = {}
        self.method = 'GET'

request = MockRequest()

# Run the Gantt calculation
print("Running Gantt calculation...")
data = get_gantt_data(request, force_run=True)

print(f"\nMachines processed: {len(data['timeline_data'])}")
print(f"Time columns: {len(data['time_columns'])}")
print(f"Global hours: {data['global_min_h']} - {data['global_max_h']}")

# Find Saturday tasks
saturday_tasks = []
for row in data['timeline_data']:
    machine = row['machine']
    for task in row['tasks']:
        start = task.get('start_date')
        end = task.get('end_date')
        if start and end:
            if start.weekday() == 5 or end.weekday() == 5:  # Saturday
                saturday_tasks.append({
                    'machine': machine.nombre if hasattr(machine, 'nombre') else str(machine),
                    'id_orden': task.get('Idorden'),
                    'start': start,
                    'end': end,
                    'duration_real': task.get('duration_real'),
                    'visual_left': task.get('visual_left'),
                    'visual_width': task.get('visual_width'),
                })

print(f"\nSaturday tasks found: {len(saturday_tasks)}")

bugs = []
for t in saturday_tasks:
    if t['end'].weekday() == 5:  # Ends on Saturday
        sat_limit = datetime.combine(t['end'].date(), datetime.strptime("13:00", "%H:%M").time())
        if t['end'] > sat_limit:
            bugs.append(t)
            print(f"\n[BUG] Machine: {t['machine']}")
            print(f"  Task {t['id_orden']}: {t['start'].strftime('%a %H:%M')} -> {t['end'].strftime('%a %H:%M')}")
            print(f"  Duration: {t['duration_real']:.2f}h")
            print(f"  Visual: left={t['visual_left']}px, width={t['visual_width']}px")

if bugs:
    print(f"\n{'='*70}")
    print(f"BUGS FOUND: {len(bugs)} Saturday tasks exceed 13:00 boundary")
    print(f"{'='*70}")
else:
    print(f"\n{'='*70}")
    print(f"NO BUGS: All Saturday tasks end within 13:00 boundary")
    print(f"{'='*70}")

# Show sample of Saturday tasks
if saturday_tasks:
    print("\nSample Saturday tasks:")
    for t in saturday_tasks[:10]:
        print(f"  {t['machine']}: Task {t['id_orden']} -> {t['end'].strftime('%a %H:%M')}")
