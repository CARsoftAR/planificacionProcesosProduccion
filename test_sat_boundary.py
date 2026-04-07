"""
Test script to verify Saturday shift boundary bug.
Tests if tasks exceed the 13:00 Saturday limit.
"""
import os
import sys
import django

# Setup Django
sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime, timedelta
from produccion.planning_service import calculate_timeline

class MockMaq:
    """Mock machine with Saturday 07:00-13:00 schedule"""
    class Horario:
        def __init__(self, dia, inicio, fin):
            self.dia = dia
            self.hora_inicio = datetime.strptime(inicio, "%H:%M").time()
            self.hora_fin = datetime.strptime(fin, "%H:%M").time()

    class Horarios:
        def __init__(self):
            self._horarios = [
                MockMaq.Horario('LV', '07:00', '18:00'),
                MockMaq.Horario('SA', '07:00', '13:00'),
            ]
        def all(self):
            return self._horarios
        def __iter__(self):
            return iter(self._horarios)

    def __init__(self):
        self.nombre = "TEST_MAQ"
        self.id_maquina = "TEST01"
        self.horarios = MockMaq.Horarios()

maquina = MockMaq()

# Test Case 1: Task that should END exactly at Saturday 13:00
# Start Saturday 07:00, 4 hours duration -> should end at 11:00
# Start Saturday 07:00, 6 hours duration -> should end at 13:00 (boundary)
# Start Saturday 07:00, 8 hours duration -> should end at 13:00 (saturday) + continue Monday

test_cases = [
    ("Sat 07:00, 4h (ends 11:00)", datetime(2026, 3, 21, 7, 0), 4.0),   # Saturday
    ("Sat 07:00, 6h (ends 13:00 boundary)", datetime(2026, 3, 21, 7, 0), 6.0),  # Saturday boundary
    ("Sat 07:00, 7h (spans Sat->Mon)", datetime(2026, 3, 21, 7, 0), 7.0),  # Saturday + Monday
    ("Sat 08:00, 5h (ends 13:00)", datetime(2026, 3, 21, 8, 0), 5.0),     # Saturday boundary
    ("Fri 14:00, 8h (spans Fri->Sat->Mon)", datetime(2026, 3, 20, 14, 0), 8.0),  # Friday + Saturday + Monday
]

print("=" * 70)
print("SATURDAY SHIFT BOUNDARY TEST")
print("=" * 70)
print(f"Machine: TEST_MAQ")
print(f"Saturday Schedule: 07:00 - 13:00")
print("=" * 70)

for name, start, duration in test_cases:
    print(f"\n--- {name} ---")
    print(f"Start: {start.strftime('%a %Y-%m-%d %H:%M')}")
    print(f"Duration: {duration}h")

    task = {
        'Idorden': 99999,
        'Descri': 'TEST TASK',
        'Tiempo_Proceso': duration,
        'Cantidad': 100,
        'Cantidadpp': 0,
    }

    result = calculate_timeline(
        maquina,
        [task],
        start_date=start,
        non_working_days=set(),
        half_day_holidays=set()
    )

    if result:
        for seg in result:
            s = seg['start_date']
            e = seg['end_date']
            print(f"  Segment {seg.get('segment_index', 0)}: {s.strftime('%a %H:%M')} -> {e.strftime('%a %H:%M')}")
            print(f"  Duration: {(e - s).total_seconds() / 3600:.2f}h")

            # Check boundary violations
            if s.weekday() == 5:  # Saturday
                sat_limit = datetime.combine(s.date(), datetime.strptime("13:00", "%H:%M").time())
                if e > sat_limit:
                    print(f"  [BUG] Task exceeds Saturday boundary! Ends at {e.strftime('%H:%M')}, should be <= 13:00")
                else:
                    print(f"  [OK] Ends within Saturday boundary")
    else:
        print("  No segments generated!")

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
