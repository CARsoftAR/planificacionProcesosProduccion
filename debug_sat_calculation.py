"""
Debug - Verificar qué horario se usa para calcular el limite del sabado.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime, timedelta

# Simular el calculo de planning_service para ver exactamente que pasa
# con el horario SA 07:00-13:00

def debug_schedule_calculation():
    print("=" * 70)
    print("DEBUG: Como se calcula el limite del turno SA")
    print("=" * 70)

    # Horarios del TSUGAMI
    schedules = {
        'LV': {'start': datetime.strptime("07:00", "%H:%M").time(), 'end': datetime.strptime("16:00", "%H:%M").time()},
        'SA': {'start': datetime.strptime("07:00", "%H:%M").time(), 'end': datetime.strptime("13:00", "%H:%M").time()},
    }

    current_time = datetime(2026, 3, 21, 7, 0)  # Saturday
    weekday = current_time.weekday()  # 5 = Saturday

    print(f"\nFecha: {current_time.strftime('%Y-%m-%d %H:%M')} ({weekday})")
    print(f"weekday == 5: {weekday == 5}")

    day_type = None
    if 0 <= weekday <= 4:
        day_type = 'LV'
    elif weekday == 5:
        day_type = 'SA'

    print(f"day_type determinado: {day_type}")

    if day_type in schedules:
        sch = schedules[day_type]
        s = sch['start']
        e = sch['end']

        print(f"\nHorario para {day_type}:")
        print(f"  start: {s} ({s.hour}:{s.minute})")
        print(f"  end: {e} ({e.hour}:{e.minute})")

        # Calcular available_hours
        shift_end_datetime = datetime.combine(current_time.date(), e)
        available_seconds = (shift_end_datetime - current_time).total_seconds()
        available_hours = available_seconds / 3600.0

        print(f"\nCalculo de available_hours:")
        print(f"  shift_end_datetime: {shift_end_datetime}")
        print(f"  available_seconds: {available_seconds}")
        print(f"  available_hours: {available_hours}")

        # Simular consumo de 6 horas
        duration_needed = 6.0
        time_to_consume = min(duration_needed, available_hours)
        print(f"\nSimulando tarea de {duration_needed}h:")
        print(f"  time_to_consume: {time_to_consume}")

        # Verificar si llega al limite del turno
        segment_will_end_at_shift_boundary = (time_to_consume >= available_hours - 0.001)
        print(f"  segment_will_end_at_shift_boundary: {segment_will_end_at_shift_boundary}")

        if segment_will_end_at_shift_boundary:
            # Snap directo
            end_time = shift_end_datetime
            print(f"  -> End time (snapped): {end_time.strftime('%H:%M:%S')}")
        else:
            end_time = current_time + timedelta(hours=time_to_consume)
            print(f"  -> End time (calculated): {end_time.strftime('%H:%M:%S')}")

        print(f"\n*** RESULTADO: La tarea de {duration_needed}h termina a las {end_time.strftime('%H:%M')} ***")

        if end_time.hour > e.hour:
            print(f"[ERROR] Termina DESPUES del horario limite!")
        elif end_time.hour == e.hour and end_time.minute > 0:
            print(f"[ERROR] Termina DESPUES del minuto 0 del horario limite!")

    print("\n" + "=" * 70)

debug_schedule_calculation()
