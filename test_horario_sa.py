"""
Test horario SA 07:00-13:00 - exactamente como lo tiene configurado el usuario.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime, timedelta
from produccion.models import MaquinaConfig, HorarioMaquina

print("=" * 70)
print("TEST HORARIO SA 07:00-13:00")
print("=" * 70)

# Buscar el TSUGAMI
tsugami = MaquinaConfig.objects.using('default').filter(nombre__icontains='TSUGAMI').first()

if tsugami:
    print(f"\nTSUGAMI: {tsugami.nombre}")
    print("Horarios en DB:")
    for h in tsugami.horarios.all():
        print(f"  {h.dia}: {h.hora_inicio.strftime('%H:%M')} - {h.hora_fin.strftime('%H:%M')}")
        print(f"    hora_fin.hour = {h.hora_fin.hour}")
        print(f"    hora_fin.minute = {h.hora_fin.minute}")

    # Test: Start Saturday 07:00, task that needs 6 hours
    from produccion.planning_service import calculate_timeline

    task = {
        'Idorden': 99999,
        'Descri': 'TEST 6hs',
        'Tiempo_Proceso': 6.0,
        'Cantidad': 100,
        'Cantidadpp': 0,
    }

    # Test 1: Start Saturday 07:00
    print("\n--- Test 1: 6 horas, inicia SA 07:00 ---")
    result = calculate_timeline(
        tsugami, [task],
        start_date=datetime(2026, 3, 21, 7, 0),
        non_working_days=set(),
        half_day_holidays=set()
    )
    if result:
        for seg in result:
            print(f"  Segmento {seg.get('segment_index', 0)}: {seg['start_date'].strftime('%H:%M')} -> {seg['end_date'].strftime('%H:%M')}")
            print(f"  Duracion real: {seg.get('duration_real', 0):.2f}h")

    # Test 2: Start Saturday 07:00, task that needs 5 hours
    print("\n--- Test 2: 5 horas, inicia SA 07:00 ---")
    task2 = task.copy()
    task2['Tiempo_Proceso'] = 5.0
    result2 = calculate_timeline(
        tsugami, [task2],
        start_date=datetime(2026, 3, 21, 7, 0),
        non_working_days=set(),
        half_day_holidays=set()
    )
    if result2:
        for seg in result2:
            print(f"  Segmento {seg.get('segment_index', 0)}: {seg['start_date'].strftime('%H:%M')} -> {seg['end_date'].strftime('%H:%M')}")
            print(f"  Duracion real: {seg.get('duration_real', 0):.2f}h")

    # Test 3: Start Saturday 08:00, task that needs 5 hours
    print("\n--- Test 3: 5 horas, inicia SA 08:00 ---")
    result3 = calculate_timeline(
        tsugami, [task2],
        start_date=datetime(2026, 3, 21, 8, 0),
        non_working_days=set(),
        half_day_holidays=set()
    )
    if result3:
        for seg in result3:
            print(f"  Segmento {seg.get('segment_index', 0)}: {seg['start_date'].strftime('%H:%M')} -> {seg['end_date'].strftime('%H:%M')}")
            print(f"  Duracion real: {seg.get('duration_real', 0):.2f}h")

    # Test 4: Start Saturday 07:00, task that needs 7 hours (spans to Monday)
    print("\n--- Test 4: 7 horas, inicia SA 07:00 (cruza al Lunes) ---")
    task4 = task.copy()
    task4['Tiempo_Proceso'] = 7.0
    result4 = calculate_timeline(
        tsugami, [task4],
        start_date=datetime(2026, 3, 21, 7, 0),
        non_working_days=set(),
        half_day_holidays=set()
    )
    if result4:
        total = 0
        for seg in result4:
            total += seg.get('duration_real', 0)
            print(f"  Segmento {seg.get('segment_index', 0)}: {seg['start_date'].strftime('%a %H:%M')} -> {seg['end_date'].strftime('%a %H:%M')} ({seg.get('duration_real', 0):.2f}h)")
        print(f"  Total: {total:.2f}h")

else:
    print("TSUGAMI no encontrado!")
