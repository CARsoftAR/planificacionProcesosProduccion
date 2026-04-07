"""
Test con horarios EXACTOS de la DB del TSUGAMI.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime
from produccion.models import MaquinaConfig
from produccion.planning_service import calculate_timeline

print("=" * 70)
print("TEST CON HORARIOS EXACTOS DEL TSUGAMI")
print("=" * 70)

# Obtener horarios del TSUGAMI desde la DB
tsugami = MaquinaConfig.objects.using('default').prefetch_related('horarios').filter(nombre__icontains='TSUGAMI').first()

if tsugami:
    print(f"\nTSUGAMI: {tsugami.nombre}")
    print("\nHorarios en DB:")
    schedules = {}
    for h in tsugami.horarios.all():
        print(f"  {h.dia}: {h.hora_inicio.strftime('%H:%M')} - {h.hora_fin.strftime('%H:%M')}")
        schedules[h.dia] = {'start': h.hora_inicio, 'end': h.hora_fin}

    print(f"\nSchedules dict: {schedules}")

    # Test: Sabado 07:00, tarea de 6 horas
    print("\n" + "=" * 70)
    print("TEST: Sabado 07:00, 6 horas")
    print("=" * 70)

    # Verificar que schedules tiene SA
    print(f"\nSA en schedules: {'SA' in schedules}")
    if 'SA' in schedules:
        print(f"SA schedule: {schedules['SA']}")

        # Calcular available_hours para SA 07:00
        current_time = datetime(2026, 3, 21, 7, 0)  # Saturday
        s = schedules['SA']['start']
        e = schedules['SA']['end']
        shift_end_dt = datetime.combine(current_time.date(), e)
        available_seconds = (shift_end_dt - current_time).total_seconds()
        available_hours = available_seconds / 3600.0

        print(f"\nCurrent time: {current_time}")
        print(f"Shift start: {s}")
        print(f"Shift end: {e}")
        print(f"Shift end datetime: {shift_end_dt}")
        print(f"Available hours: {available_hours}")

    # Ejecutar calculate_timeline
    task = {
        'Idorden': 99999,
        'Descri': 'TEST 6hs SA',
        'Tiempo_Proceso': 6.0,
        'Cantidad': 100,
        'Cantidadpp': 0,
    }

    result = calculate_timeline(
        tsugami, [task],
        start_date=datetime(2026, 3, 21, 7, 0),
        non_working_days=set(),
        half_day_holidays=set()
    )

    print("\n--- RESULTADO ---")
    if result:
        for seg in result:
            print(f"Segmento {seg.get('segment_index', 0)}:")
            print(f"  start: {seg['start_date'].strftime('%H:%M:%S')}")
            print(f"  end: {seg['end_date'].strftime('%H:%M:%S')}")
            print(f"  duration: {seg.get('duration_real', 0):.2f}h")

            # Verificar si excede 13:00
            if seg['end_date'].hour > 13 or (seg['end_date'].hour == 13 and seg['end_date'].minute > 0):
                print(f"  [BUG] EXCEDE 13:00!")
    else:
        print("Sin segmentos!")
else:
    print("TSUGAMI no encontrado!")
