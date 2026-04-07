"""
Comprehensive Saturday boundary test - edge cases and floating point drift.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime, timedelta
from produccion.planning_service import calculate_timeline

class MockMaq:
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
bugs_found = 0
tests_passed = 0

print("=" * 70)
print("COMPREHENSIVE SATURDAY BOUNDARY TEST")
print("=" * 70)

# Test edge cases with floating point issues
edge_cases = [
    ("Exact 6h (boundary)", datetime(2026, 3, 21, 7, 0), 6.0),
    ("0.1h before boundary", datetime(2026, 3, 21, 6, 54), 6.1),  # 6:54 + 6.1h = 12:60 = 13:00
    ("0.2h after boundary", datetime(2026, 3, 21, 6, 53), 6.2),  # 6:53 + 6.2h = 13:00:12
    ("0.0001h over", datetime(2026, 3, 21, 7, 0), 6.0001),
    ("10 minutes", datetime(2026, 3, 21, 12, 50), 10/60),
    ("30 minutes", datetime(2026, 3, 21, 12, 30), 0.5),
    ("45 minutes", datetime(2026, 3, 21, 12, 15), 0.75),
    ("Complex fraction 3.333h", datetime(2026, 3, 21, 7, 0), 3.333),
    ("Complex fraction 5.555h", datetime(2026, 3, 21, 7, 0), 5.555),
    ("Boundary - 0.001h", datetime(2026, 3, 21, 7, 0), 5.999),
    ("Boundary + 0.001h", datetime(2026, 3, 21, 7, 0), 6.001),
]

print("\n--- Edge Cases (Saturday only) ---")
for name, start, duration in edge_cases:
    task = {
        'Idorden': 99999,
        'Descri': name,
        'Tiempo_Proceso': duration,
        'Cantidad': 100,
        'Cantidadpp': 0,
    }

    result = calculate_timeline(
        maquina, [task], start_date=start,
        non_working_days=set(), half_day_holidays=set()
    )

    for seg in result:
        s = seg['start_date']
        e = seg['end_date']
        if s.weekday() == 5:
            sat_limit = datetime.combine(s.date(), datetime.strptime("13:00", "%H:%M").time())
            if e > sat_limit:
                print(f"[FAIL] {name}: Ends at {e.strftime('%H:%M:%S')} > 13:00 (dur={duration}h)")
                bugs_found += 1
            else:
                print(f"[PASS] {name}: {s.strftime('%H:%M')} -> {e.strftime('%H:%M:%S')} (dur={duration}h)")
                tests_passed += 1

# Test half-day holiday on Saturday
print("\n--- Half-Day Holiday on Saturday (12:00 limit) ---")
half_day_holidays = {datetime(2026, 3, 21).date()}  # March 21 is Saturday 2026

task = {
    'Idorden': 99998,
    'Descri': 'Half-day holiday test',
    'Tiempo_Proceso': 4.0,
    'Cantidad': 100,
    'Cantidadpp': 0,
}

result = calculate_timeline(
    maquina, [task], start_date=datetime(2026, 3, 21, 7, 0),
    non_working_days=set(), half_day_holidays=half_day_holidays
)

for seg in result:
    s = seg['start_date']
    e = seg['end_date']
    if s.weekday() == 5:
        half_day_limit = datetime.combine(s.date(), datetime.strptime("12:00", "%H:%M").time())
        if e > half_day_limit:
            print(f"[FAIL] Half-day: Ends at {e.strftime('%H:%M')} > 12:00")
            bugs_found += 1
        else:
            print(f"[PASS] Half-day: {s.strftime('%H:%M')} -> {e.strftime('%H:%M')} (limit=12:00)")
            tests_passed += 1

print("\n" + "=" * 70)
print(f"RESULTS: {tests_passed} passed, {bugs_found} bugs found")
print("=" * 70)
