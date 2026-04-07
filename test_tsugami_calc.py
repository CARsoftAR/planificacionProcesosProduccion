"""
Test specific TSUGAMI task calculation.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime, timedelta
from produccion.planning_service import calculate_timeline
from produccion.models import MaquinaConfig

print("=" * 70)
print("TEST TSUGAMI TASK CALCULATION")
print("=" * 70)

# Get TSUGAMI machine from DB
tsugami = MaquinaConfig.objects.using('default').prefetch_related('horarios').filter(nombre__icontains='TSUGAMI').first()

if tsugami:
    print(f"\nMachine: {tsugami.nombre} (ID: {tsugami.id_maquina})")
    print("Horarios:")
    for h in tsugami.horarios.all():
        print(f"  {h.dia}: {h.hora_inicio.strftime('%H:%M')} - {h.hora_fin.strftime('%H:%M')}")

    # Test task: start Saturday 07:00, 6 hours
    print("\n--- Task: Start Sat 07:00, 6 hours ---")

    task = {
        'Idorden': 99999,
        'Descri': 'TEST TSUGAMI',
        'Tiempo_Proceso': 6.0,
        'Cantidad': 100,
        'Cantidadpp': 0,
    }

    # Saturday 2026-03-21 at 07:00
    start_sat = datetime(2026, 3, 21, 7, 0)

    result = calculate_timeline(
        tsugami,
        [task],
        start_date=start_sat,
        non_working_days=set(),
        half_day_holidays=set()
    )

    print(f"\nStart: {start_sat.strftime('%a %Y-%m-%d %H:%M')}")
    print(f"Duration requested: 6.0h")

    if result:
        for seg in result:
            print(f"\nSegment {seg.get('segment_index', 0)}:")
            print(f"  start_date: {seg['start_date'].strftime('%a %H:%M:%S')}")
            print(f"  end_date: {seg['end_date'].strftime('%a %H:%M:%S')}")
            print(f"  duration_real: {seg.get('duration_real', 0):.2f}h")

            # Verify no overflow
            if seg['start_date'].weekday() == 5:  # Saturday
                sat_end = datetime.combine(seg['start_date'].date(), datetime.strptime("13:00", "%H:%M").time())
                if seg['end_date'] > sat_end:
                    print(f"  [BUG] Ends AFTER 13:00!")
                elif seg['end_date'] == sat_end:
                    print(f"  [OK] Ends exactly at 13:00")
                else:
                    print(f"  [OK] Ends before 13:00")
    else:
        print("No segments generated!")

    # Also test a task that spans multiple days
    print("\n--- Task: Start Fri 14:00, 12 hours (spans Fri->Sat) ---")

    task2 = {
        'Idorden': 99998,
        'Descri': 'TEST SPANS',
        'Tiempo_Proceso': 12.0,
        'Cantidad': 100,
        'Cantidadpp': 0,
    }

    start_fri = datetime(2026, 3, 20, 14, 0)

    result2 = calculate_timeline(
        tsugami,
        [task2],
        start_date=start_fri,
        non_working_days=set(),
        half_day_holidays=set()
    )

    print(f"\nStart: {start_fri.strftime('%a %Y-%m-%d %H:%M')}")
    print(f"Duration requested: 12.0h")

    if result2:
        total_hours = 0
        for seg in result2:
            dur = seg.get('duration_real', 0)
            total_hours += dur
            print(f"\nSegment {seg.get('segment_index', 0)}:")
            print(f"  start: {seg['start_date'].strftime('%a %H:%M')}")
            print(f"  end: {seg['end_date'].strftime('%a %H:%M')}")
            print(f"  duration: {dur:.2f}h")

            # Verify Saturday doesn't overflow
            if seg['end_date'].weekday() == 5:
                sat_end = datetime.combine(seg['end_date'].date(), datetime.strptime("13:00", "%H:%M").time())
                if seg['end_date'] > sat_end:
                    print(f"  [BUG] Saturday segment ends AFTER 13:00!")
                else:
                    print(f"  [OK] Saturday segment ends at or before 13:00")

        print(f"\nTotal duration: {total_hours:.2f}h (expected 12.0h)")
else:
    print("TSUGAMI machine not found!")
