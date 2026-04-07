"""
Test exhaustivo para encontrar donde se agrega 1 hora extra.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime, timedelta, time
from produccion.models import MaquinaConfig, Feriado

# Obtener horarios del TSUGAMI
tsugami = MaquinaConfig.objects.using('default').prefetch_related('horarios').filter(nombre__icontains='TSUGAMI').first()

print("=" * 70)
print("TEST EXHAUSTIVO: Simular exactamente lo que hace la aplicacion")
print("=" * 70)

if tsugami:
    print(f"\nTSUGAMI: {tsugami.nombre}")
    print("Horarios en DB:")
    for h in tsugami.horarios.all():
        print(f"  {h.dia}: {h.hora_inicio} - {h.hora_fin}")

    # Simular el calculo paso a paso como lo hace calculate_timeline
    schedules = {}
    for h in tsugami.horarios.all():
        schedules[h.dia] = {'start': h.hora_inicio, 'end': h.hora_fin}

    print(f"\nSchedules: {schedules}")

    # Test: Sabado 2026-03-21 a las 07:00
    current_time = datetime(2026, 3, 21, 7, 0)
    print(f"\n=== TEST: current_time = {current_time} ===")
    print(f"weekday = {current_time.weekday()} (0=Lun, 5=Sab)")

    # Determinar day_type
    weekday = current_time.weekday()
    day_type = None
    if 0 <= weekday <= 4:
        day_type = 'LV'
    elif weekday == 5:
        day_type = 'SA'
    print(f"day_type = {day_type}")

    if day_type in schedules:
        sch = schedules[day_type]
        s = sch['start']
        e = sch['end']
        print(f"\nHorario para {day_type}:")
        print(f"  start: {s}")
        print(f"  end: {e}")

        # Calcular shift_end_datetime
        shift_end_datetime = datetime.combine(current_time.date(), e)
        print(f"  shift_end_datetime: {shift_end_datetime}")

        # Calcular available_seconds y available_hours
        available_seconds = (shift_end_datetime - current_time).total_seconds()
        available_hours = available_seconds / 3600.0
        print(f"  available_seconds: {available_seconds}")
        print(f"  available_hours: {available_hours}")

        # Test con 6 horas
        duration_hours = 6.0
        remaining_hours = duration_hours
        segment_start = current_time
        print(f"\n--- Tarea de {duration_hours} horas ---")
        print(f"remaining_hours inicial: {remaining_hours}")
        print(f"segment_start: {segment_start}")

        # Paso 1: is_working_time check
        current_time_time = current_time.time()
        print(f"\nPaso 1: Verificar is_working_time")
        print(f"  s < e: {s < e}")
        print(f"  s <= current_time_time: {s <= current_time_time}")
        print(f"  current_time_time < e: {current_time_time < e}")
        print(f"  is_working_time: {s <= current_time_time < e}")

        # Paso 2: Calcular time_to_consume
        time_to_consume = min(remaining_hours, available_hours)
        print(f"\nPaso 2: Calcular time_to_consume")
        print(f"  min({remaining_hours}, {available_hours}) = {time_to_consume}")

        # Paso 3: Verificar si llega al limite del turno
        segment_will_end_at_shift_boundary = (time_to_consume >= available_hours - 0.001)
        print(f"\nPaso 3: Verificar segment_will_end_at_shift_boundary")
        print(f"  {time_to_consume} >= {available_hours} - 0.001 = {time_to_consume >= available_hours - 0.001}")
        print(f"  segment_will_end_at_shift_boundary = {segment_will_end_at_shift_boundary}")

        # Paso 4: Calcular end time
        print(f"\nPaso 4: Calcular end time")
        if segment_will_end_at_shift_boundary:
            # Snap directo
            time_to_consume = max(0.0, (shift_end_datetime - segment_start).total_seconds() / 3600.0)
            current_time = shift_end_datetime
            print(f"  -> SNAP directo a shift_end_datetime")
            print(f"  time_to_consume recalculado: {time_to_consume}")
        else:
            current_time = current_time + timedelta(hours=time_to_consume)
            print(f"  -> timedelta(hours={time_to_consume})")

        print(f"\nRESULTADO:")
        print(f"  segment_start: {segment_start}")
        print(f"  end time: {current_time}")
        print(f"  duration: {(current_time - segment_start).total_seconds() / 3600.0:.2f}h")

        # Verificar si esta bien
        if current_time.hour > 13 or (current_time.hour == 13 and current_time.minute > 0):
            print(f"\n  [BUG] Termina DESPUES de las 13:00!")

        # Ahora test real con calculate_timeline
        print("\n" + "=" * 70)
        print("TEST REAL con calculate_timeline:")
        print("=" * 70)

        from produccion.planning_service import calculate_timeline

        task = {
            'Idorden': 99999,
            'Descri': 'TEST EXACTO',
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

        if result:
            for seg in result:
                print(f"\nSegmento {seg.get('segment_index', 0)}:")
                print(f"  start: {seg['start_date']}")
                print(f"  end: {seg['end_date']}")
                print(f"  duration: {seg.get('duration_real', 0):.2f}h")

                if seg['end_date'].hour > 13 or (seg['end_date'].hour == 13 and seg['end_date'].minute > 0):
                    print(f"  [BUG] EXCEDE 13:00!")
else:
    print("TSUGAMI no encontrado!")
