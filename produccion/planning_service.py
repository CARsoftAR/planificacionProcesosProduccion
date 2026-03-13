from datetime import timedelta, datetime
from .models import HorarioMaquina, Feriado

def is_non_working_holiday(date_obj, non_working_days=None):
    """
    Verifica si una fecha es un feriado que NO se trabaja.
    """
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    
    if non_working_days is not None:
        return date_obj in non_working_days
    
    return Feriado.objects.filter(fecha=date_obj, activo=True, tipo_jornada='NO').exists()

def is_half_day_holiday(date_obj, half_day_holidays=None):
    """
    Verifica si una fecha es feriado de MEDIO DIA.
    """
    if isinstance(date_obj, datetime):
        date_obj = date_obj.date()
    
    if half_day_holidays is not None:
        return date_obj in half_day_holidays
    
    return Feriado.objects.filter(fecha=date_obj, activo=True, tipo_jornada='MEDIO').exists()


def calculate_timeline(maquina, tasks, start_date=None, task_min_start_times=None, task_force_start_times=None, non_working_days=None, half_day_holidays=None):
    """
    Calculates the start and end datetime for a list of tasks for a specific machine,
    respecting the machine's configured schedule (LV, SA) and non-working holidays.
    """
    if start_date is None:
        start_date = datetime.now()
        # Round to next hour
        if start_date.minute > 0 or start_date.second > 0:
            start_date = (start_date + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)

    # 1. Load Schedule into a usable format
    # format: {'LV': {'start': time, 'end': time}, 'SA': {'start': time, 'end': time}}
    schedules = {}
    for h in maquina.horarios.all():
        schedules[h.dia] = {'start': h.hora_inicio, 'end': h.hora_fin}

    if not schedules:
        # Fallback: If no schedule, assume 24/7 or 08-17? 
        # For safety, let's assume 07:00 - 16:00 Mon-Fri if nothing defined, or better, return user error?
        # Let's assume a default standard 07-16 LV for safety to avoid infinite loops
        schedules['LV'] = {'start': datetime.strptime("07:00", "%H:%M").time(), 'end': datetime.strptime("16:00", "%H:%M").time()}
        
    current_time = start_date
    calculated_tasks = []

    for idx, task in enumerate(tasks):
        # task is a dict from get_planificacion_data
        
        # 'Tiempo' is Unit Time (Time per piece)
        unit_time = float(task.get('Tiempo', 0) or 0)
        
        qty = float(task.get('Cantidad', 1) or 1)
        produced = float(task.get('Cantidadpp', 0) or 0)
        
        # Calculate Pending Quantity (for debug info only)
        pending_qty = qty - produced
        
        # ONLY use Tiempo_Proceso from database
        # If Tiempo_Proceso = 0, the task should not be planned
        try:
             duration_hours = float(task.get('Tiempo_Proceso', 0) or 0)
        except (ValueError, TypeError):
             duration_hours = 0.0
        
        # If duration is 0 or negative (task completed/overproduced), skip.
        if duration_hours <= 0.001:
             continue
             
        # Safety check for minimal duration
        # Safety check for minimal duration
        if duration_hours < 0.001:
            duration_hours = 0.001 # Minimum visibility

        remaining_hours = duration_hours
        
        # Check Force Start (Pinning) - Overrides machine availability
        forced_time = None
        if task_force_start_times:
            raw_id = task.get('Idorden')
            # Helper to check various types
            for check_id in [raw_id, int(raw_id) if str(raw_id).isdigit() else None, str(raw_id)]:
                if check_id in task_force_start_times:
                    forced_time = task_force_start_times[check_id]
                    break
        
        if forced_time:
             # Force the time (Collision allowed!)
             current_time = forced_time
             
             # If the forced time is timezone-aware (UTC from DB), convert to local time
             if current_time.tzinfo is not None:
                 from django.utils import timezone as django_tz
                 # Convert from UTC to local timezone
                 current_time = current_time.astimezone(django_tz.get_current_timezone())
                 # Now remove timezone info (but it's already in local time)
                 current_time = current_time.replace(tzinfo=None)
                 
             print(f"DEBUG: Task {task.get('Idorden')} FORCED to {current_time}")

        # Check for dependencies / constraints (Soft Limits)
        # ONLY IF NOT FORCED (Manual override wins over Physics)
        if not forced_time and task_min_start_times:
            raw_id = task.get('Idorden')
            t_ids_to_try = []
            
            # Try plain value
            if raw_id is not None:
                t_ids_to_try.append(raw_id)
            
            # Try integer conversion
            try:
                val_int = int(raw_id)
                t_ids_to_try.append(val_int)
            except (ValueError, TypeError):
                pass
                
            # Try string conversion
            try:
                val_str = str(raw_id)
                t_ids_to_try.append(val_str)
            except (ValueError, TypeError):
                pass
            
            found_min_start = None
            for tid in t_ids_to_try:
                if tid in task_min_start_times:
                    start_candidate = task_min_start_times[tid]
                    if found_min_start is None or (start_candidate and start_candidate > found_min_start):
                         found_min_start = start_candidate
            
            if found_min_start:
                 # Ensure we don't start before the dependency ends
                 if found_min_start > current_time:
                     current_time = found_min_start
                     # print(f"DEBUG: Task {raw_id} delayed start to {current_time} due to dependency")
        
        # Instead of one block per task, create multiple segments if task spans multiple days
        task_segments = []
        task_start = None
        segment_start = None
        

        
        # Safety breaker
        loop_count = 0
        max_loops = 10000 # 1 year approx in hours

        while remaining_hours > 0 and loop_count < max_loops:
            loop_count += 1
            
            # PRIMERO: Verificar si es un feriado no laborable
            if is_non_working_holiday(current_time, non_working_days):
                # Es feriado que NO se trabaja - saltar al siguiente día laborable
                print(f"    FERIADO detectado en {current_time.date()}, saltando...")
                
                if segment_start is not None:
                    # Cerrar segmento actual antes del feriado
                    segment_end = current_time
                    
                    is_new_day = False
                    if len(task_segments) > 0:
                        prev_segment = task_segments[-1]
                        if segment_start.date() != prev_segment['end_date'].date():
                            is_new_day = True
                    
                    segment = task.copy()
                    segment['start_date'] = segment_start
                    segment['end_date'] = segment_end
                    segment['duration_real'] = (segment_end - segment_start).total_seconds() / 3600.0
                    segment['debug_info'] = f"TP: {duration_hours:.2f}h (Seg: {len(task_segments)+1})"
                    segment['is_new_day'] = is_new_day
                    
                    # Add progress percentage
                    if qty > 0:
                        segment['progress_percent'] = min(100.0, (produced / qty) * 100.0)
                    else:
                        segment['progress_percent'] = 0.0
                        
                    task_segments.append(segment)
                    segment_start = None
                
                # Saltar al siguiente día laborable (inicio del horario)
                next_day = (current_time + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                current_time = _jump_to_next_start(next_day, schedules, non_working_days, half_day_holidays)
                print(f"    Saltando a: {current_time}")
                continue
            
            # Ensure current_time is Naive
            if current_time.tzinfo is not None:
                current_time = current_time.replace(tzinfo=None)

            # Check if current_time is within working hours
            is_working_time = False
            
            # Determine Day Type
            weekday = current_time.weekday() # 0=Mon, 6=Sun
            day_type = None
            if 0 <= weekday <= 4:
                day_type = 'LV'
            elif weekday == 5:
                day_type = 'SA'
            
            if day_type in schedules:
                sch = schedules[day_type]
                current_time_time = current_time.time()
                
                s = sch['start']
                e = sch['end']
                
                # CHEQUEO DE MEDIO DIA
                is_half = is_half_day_holiday(current_time, half_day_holidays)
                if is_half:
                     # Forzamos fin a las 12:00. 
                     e = datetime.strptime("12:00", "%H:%M").time()
                
                if s <e:
                    if s <= current_time_time < e:
                        is_working_time = True
                else: 
                     # Wrap around midnight
                    if current_time_time >= s or current_time_time < e:
                        is_working_time = True
                
                # HARD OVERRIDE: If Half Day and time >= 12:00, INVALID.
                if is_half and is_working_time:
                    limit_time = datetime.strptime("12:00", "%H:%M").time()
                    if current_time_time >= limit_time:
                        is_working_time = False
            else:
                 # No schedule for this day (e.g. Sunday if not in schedules)
                 is_working_time = False
            
            if is_working_time:
                if task_start is None:
                    task_start = current_time
                
                if segment_start is None:
                    segment_start = current_time
                    
                sch = schedules[day_type]
                s = sch['start']
                e = sch['end']
                
                # RE-CHECK FOR HALF DAY (needed again for calculation of available time)
                if is_half_day_holiday(current_time, half_day_holidays):
                     e = datetime.strptime("12:00", "%H:%M").time()
                
                available_seconds = 0
                if s < e:
                    shift_end_datetime = datetime.combine(current_time.date(), e)
                    available_seconds = (shift_end_datetime - current_time).total_seconds()
                else:
                    current_time_time = current_time.time()
                    if current_time_time >= s:
                        next_day = (current_time + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                        available_seconds = (next_day - current_time).total_seconds()
                    elif current_time_time < e:
                        shift_end_datetime = datetime.combine(current_time.date(), e)
                        available_seconds = (shift_end_datetime - current_time).total_seconds()
                
                available_hours = available_seconds / 3600.0
                
                if available_hours <= 0:
                     current_time += timedelta(hours=1)
                     continue
                
                time_to_consume = min(remaining_hours, available_hours)
                segment_will_end_at_shift_boundary = (time_to_consume >= available_hours - 0.001)
                
                # print(f"    Working: avail={available_hours:.2f}h, consume={time_to_consume:.2f}h, remaining={remaining_hours:.2f}h, at_boundary={segment_will_end_at_shift_boundary}")
                
                current_time += timedelta(hours=time_to_consume)
                remaining_hours -= time_to_consume
                
                # Create a segment if:
                # 1. Task is complete (no more hours remaining), OR
                # 2. We've reached the end of this shift
                if remaining_hours <= 0.001 or segment_will_end_at_shift_boundary:
                    segment_end = current_time
                    
                    # print(f"    -> Creating segment: {segment_start} to {segment_end}")
                    
                    # Check if this segment starts on a new day compared to previous segment
                    is_new_day = False
                    if len(task_segments) > 0:
                        prev_segment = task_segments[-1]
                        if segment_start.date() != prev_segment['end_date'].date():
                            is_new_day = True
                    
                    # Create a segment for this work period
                    segment = task.copy()
                    segment['start_date'] = segment_start
                    segment['end_date'] = segment_end
                    segment['duration_real'] = (segment_end - segment_start).total_seconds() / 3600.0
                    segment['debug_info'] = f"TP: {duration_hours:.2f}h (Seg: {len(task_segments)+1})"
                    segment['is_new_day'] = is_new_day
                    
                    # Add progress percentage
                    if qty > 0:
                        segment['progress_percent'] = min(100.0, (produced / qty) * 100.0)
                    else:
                        segment['progress_percent'] = 0.0
                    
                    task_segments.append(segment)
                    segment['segment_index'] = len(task_segments) - 1 # 0-based index of this segment
                    
                    # Reset segment_start for next segment
                    segment_start = None
                    
            else:
                # Not working time - if we have an open segment, close it
                if segment_start is not None:
                    segment_end = current_time
                    
                    # Check if this segment starts on a new day
                    is_new_day = False
                    if len(task_segments) > 0:
                        prev_segment = task_segments[-1]
                        if segment_start.date() != prev_segment['end_date'].date():
                            is_new_day = True
                    
                    segment = task.copy()
                    segment['start_date'] = segment_start
                    segment['end_date'] = segment_end
                    segment['duration_real'] = (segment_end - segment_start).total_seconds() / 3600.0
                    segment['debug_info'] = f"TP: {duration_hours:.2f}h (U:{unit_time:.2f}*P:{pending_qty:.2f})"
                    segment['is_new_day'] = is_new_day
                    
                    # Add progress percentage
                    if qty > 0:
                        segment['progress_percent'] = min(100.0, (produced / qty) * 100.0)
                    else:
                        segment['progress_percent'] = 0.0
                        
                    task_segments.append(segment)
                    segment_start = None
                
                original_curr = current_time
                current_time = _jump_to_next_start(current_time, schedules, non_working_days, half_day_holidays)
                
                # SAFETY: If time didn't advance (infinite loop protection), force +1 min/hour
                if current_time <= original_curr:
                     current_time += timedelta(minutes=30)
        
        # Add all segments to calculated_tasks
        calculated_tasks.extend(task_segments)
        
    return calculated_tasks

def _jump_to_next_start(current_time, schedules, non_working_days=None, half_day_holidays=None):
    """
    Helper to jump from a non-working non-started time to the next working start time.
    Also skips non-working holidays.
    """
    next_check = current_time
    
    # Ensure next_check is naive for comparison with naive schedules
    if next_check.tzinfo is not None:
        next_check = next_check.replace(tzinfo=None)
    
    # Limit lookahead
    for _ in range(14): 
        # Primero verificar si es feriado no laborable
        if is_non_working_holiday(next_check, non_working_days):
            # Saltar al siguiente día
            next_check = (next_check + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            continue
        
        weekday = next_check.weekday()
        day_type = 'LV' if 0 <= weekday <= 4 else ('SA' if weekday == 5 else None)
        
        if day_type and day_type in schedules:
            sch = schedules[day_type]
            s = sch['start']
            e = sch['end']
            
            # CHECK FOR HALF DAY
            if is_half_day_holiday(next_check, half_day_holidays):
                 e = datetime.strptime("12:00", "%H:%M").time()
            
            sch_start = datetime.combine(next_check.date(), s)
            
            if s < e:
                sch_end = datetime.combine(next_check.date(), e)
                if next_check < sch_start:
                    return sch_start
                if sch_start <= next_check < sch_end:
                     return next_check
            else:
                # Wrapped schedule
                sch_end_morning = datetime.combine(next_check.date(), e)
                # 00:00 - End
                if next_check < sch_end_morning:
                    return next_check
                # Gap (End - Start)
                if sch_end_morning <= next_check < sch_start:
                    return sch_start
                # Start - 24:00
                if next_check >= sch_start:
                    return next_check
            
        # Move to next day start
        next_check = (next_check + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        
    # Restore tzinfo if originally present? No, simulation is usually naive.
    return next_check + timedelta(hours=1)

def get_machine_capacity(maquina, start_date, end_date, non_working_days=None, half_day_holidays=None):
    """
    Calculates total working hours for a machine between two dates.
    """
    schedules = {}
    for h in maquina.horarios.all():
        schedules[h.dia] = {'start': h.hora_inicio, 'end': h.hora_fin}

    if not schedules:
        # Fallback 07-16 LV
        schedules['LV'] = {'start': datetime.strptime("07:00", "%H:%M").time(), 'end': datetime.strptime("16:00", "%H:%M").time()}

    total_hours = 0.0
    # Clean dates to start of day
    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    limit = end_date.replace(hour=23, minute=59, second=59)
    
    while current <= limit:
        if not is_non_working_holiday(current, non_working_days):
            weekday = current.weekday()
            day_type = 'LV' if 0 <= weekday <= 4 else ('SA' if weekday == 5 else None)
            
            if day_type in schedules:
                sch = schedules[day_type]
                s = sch['start']
                e = sch['end']
                
                if is_half_day_holiday(current, half_day_holidays):
                    # Half day limit is 12:00
                    limit_time = datetime.strptime("12:00", "%H:%M").time()
                    if e > limit_time:
                         e = limit_time
                
                if s < e:
                    day_h = (datetime.combine(current.date(), e) - datetime.combine(current.date(), s)).total_seconds() / 3600.0
                    total_hours += max(0, day_h)
                else:
                    # Wrap around midnight
                    total_hours += (24.0 - (s.hour + s.minute/60.0)) + (e.hour + e.minute/60.0)
                    
        current += timedelta(days=1)
    
    return total_hours
