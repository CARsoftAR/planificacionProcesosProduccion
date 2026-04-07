"""
Verify day_max_hours calculation.
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
print("VERIFY DAY MAX HOURS")
print("=" * 70)

request = MockRequest()
data = get_gantt_data(request, force_run=True)

print(f"\nday_max_hours:")
for d, h in sorted(data.get('day_max_hours', {}).items()):
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d.weekday()]
    print(f"  {d} ({wd}): max_h = {h}")

print(f"\ndate_start_col:")
for d, col in sorted(data.get('date_start_col', {}).items())[:10]:
    wd = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d.weekday()]
    print(f"  {d} ({wd}): col = {col}")

print(f"\ntime_columns count: {len(data['time_columns'])}")

# Show Saturday columns
saturday_cols = [c for c in data['time_columns'] if c.weekday() == 5]
print(f"Saturday columns: {len(saturday_cols)}")
if saturday_cols:
    print(f"  First: {saturday_cols[0].strftime('%H:%M')}")
    print(f"  Last: {saturday_cols[-1].strftime('%H:%M')}")

# Show Monday columns
monday_cols = [c for c in data['time_columns'] if c.weekday() == 0]
print(f"\nMonday columns: {len(monday_cols)}")
if monday_cols:
    print(f"  First: {monday_cols[0].strftime('%H:%M')}")
    print(f"  Last: {monday_cols[-1].strftime('%H:%M')}")
