from datetime import timedelta, datetime
from .models import HorarioMaquina, Feriado

def get_active_maintenances(maquina):
    from .models import MantenimientoMaquina
    try:
        mants = MantenimientoMaquina.objects.filter(maquina=maquina).exclude(estado='FINALIZADO')
        res = []
        from django.utils import timezone
        for m in mants:
            s, e = m.fecha_inicio, m.fecha_fin
            # Always convert to local time for consistency with TimeFields
            if s:
                if timezone.is_naive(s): s = timezone.make_aware(s)
                else: s = timezone.localtime(s)
            if e:
                if timezone.is_naive(e): e = timezone.make_aware(e)
                else: e = timezone.localtime(e)
            res.append({'start': s, 'end': e, 'motivo': m.motivo})
        return res
    except:
        return []



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
    from django.utils import timezone
    if start_date is None:
        start_date = timezone.localtime(timezone.now())
        # Round to next hour
        if start_date.minute > 0 or start_date.second > 0:
            start_date = (start_date + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    else:
        # Always work in local time for comparison with HorarioMaquina (TimeFields)
        if timezone.is_aware(start_date):
            start_date = timezone.localtime(start_date)
        else:
            start_date = timezone.make_aware(start_date)


    # format: {'LV': [{'start': time, 'end': time}, ...], 'SA': [...]}
    from collections import defaultdict
    schedules = defaultdict(list)
    
    # Detection of 'SIN ASIGNAR' row (MAC00)
    if isinstance(maquina, dict):
        m_id = str(maquina.get('id_maquina', '')).strip()
        m_name = str(maquina.get('nombre', '')).strip().upper()
    else:
        m_id = str(getattr(maquina, 'id_maquina', '')).strip()
        m_name = str(getattr(maquina, 'nombre', '')).strip().upper()
    is_unassigned_row = (m_id == 'MAC00') or ('SIN ASIGNAR' in m_name)

    if is_unassigned_row:
        # MAC00 strict schedule: 07:00 - 22:00 LV
        schedules['LV'] = [{'start': datetime.strptime("07:00", "%H:%M").time(), 'end': datetime.strptime("22:00", "%H:%M").time()}]
    else:
        for h in maquina.horarios.all().order_by('hora_inicio'):
            schedules[h.dia].append({'start': h.hora_inicio, 'end': h.hora_fin})

        if not schedules:
            # Fallback 07:00 - 16:00 LV
            schedules['LV'] = [{'start': datetime.strptime("07:00", "%H:%M").time(), 'end': datetime.strptime("16:00", "%H:%M").time()}]

        
    active_maints = []
    if not isinstance(maquina, dict):
        m_name_check = getattr(maquina, 'nombre', '').upper()
        if 'MAC00' not in m_name_check and 'SIN ASIGNAR' not in m_name_check:
            active_maints = get_active_maintenances(maquina)
            
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
             
        # Detection of 'SIN ASIGNAR' row (MAC00)
        if isinstance(maquina, dict):
            m_id = str(maquina.get('id_maquina', '')).strip()
            m_name = str(maquina.get('nombre', '')).strip().upper()
        else:
            m_id = str(getattr(maquina, 'id_maquina', '')).strip()
            m_name = str(getattr(maquina, 'nombre', '')).strip().upper()
        
        is_unassigned_row = (m_id == 'MAC00') or ('SIN ASIGNAR' in m_name)

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
             from django.utils import timezone
             # Always convert to local time for consistency
             if timezone.is_aware(forced_time):
                 forced_time = timezone.localtime(forced_time)
             else:
                 forced_time = timezone.make_aware(forced_time)
                 
             if current_time and timezone.is_aware(current_time):
                 current_time = timezone.localtime(current_time)
             elif current_time:
                 current_time = timezone.make_aware(current_time)

             # El inicio forzado (Pin) es respetado, pero ya no forzamos secuencialidad artificial.
             current_time = forced_time

        # No constraints, current_time remains as is (or machine availability)

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
                    segment['duration_task'] = duration_hours # Preserve total duration
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
            
            # --- MAINTENANCE CHECK ---
            is_in_maint = False
            maint_end_time = None
            for maint in active_maints:
                if maint['start'] <= current_time < maint['end']:
                    is_in_maint = True
                    maint_end_time = maint['end']
                    break
                    
            if is_in_maint:
                if segment_start is not None:
                     segment_end = current_time
                     is_new_day = False
                     if len(task_segments) > 0:
                         if segment_start.date() != task_segments[-1]['end_date'].date():
                             is_new_day = True
                     segment = task.copy()
                     segment['start_date'] = segment_start
                     segment['end_date'] = segment_end
                     segment['duration_real'] = (segment_end - segment_start).total_seconds() / 3600.0
                     segment['duration_task'] = duration_hours 
                     segment['debug_info'] = f"Mantenimiento"
                     segment['is_new_day'] = is_new_day
                     if qty > 0:
                         segment['progress_percent'] = min(100.0, (produced / qty) * 100.0)
                     else:
                         segment['progress_percent'] = 0.0
                     task_segments.append(segment)
                     segment_start = None
                
                # Jump to end of maintenance
                current_time = maint_end_time
                print(f"    MANTENIMIENTO: Saltando a {current_time}")
                continue

            # Ensure current_time is Aware and strictly Local for comparison with TimeFields
            from django.utils import timezone
            if timezone.is_naive(current_time):
                current_time = timezone.make_aware(current_time)
            else:
                current_time = timezone.localtime(current_time)


            # Check if current_time is within working hours
            is_working_time = False
            
            # Determine Day Type
            weekday = current_time.weekday() # 0=Mon, 6=Sun
            day_type = None
            if 0 <= weekday <= 4:
                day_type = 'LV'
            elif weekday == 5:
                day_type = 'SA'
            elif weekday == 6:
                day_type = 'DO'

            
            if day_type in schedules:
                matches = schedules[day_type]
                current_time_time = current_time.time()
                is_half = is_half_day_holiday(current_time, half_day_holidays)
                
                active_shift = None
                for sch in matches:
                    s = sch['start']
                    e = sch['end']
                    
                    if is_half: e = datetime.strptime("12:00", "%H:%M").time()
                    
                    if s < e:
                        if s <= current_time_time < e:
                            is_working_time = True
                            active_shift = {'start': s, 'end': e}
                            break
                    else: # Wrap midnight
                        if current_time_time >= s or current_time_time < e:
                            is_working_time = True
                            active_shift = {'start': s, 'end': e}
                            break
                
                if is_half and is_working_time:
                    if current_time_time >= datetime.strptime("12:00", "%H:%M").time():
                        is_working_time = False
                        active_shift = None
            else:
                 is_working_time = False

            
            if is_working_time and active_shift:
                if task_start is None:
                    task_start = current_time
                
                if segment_start is None:
                    segment_start = current_time
                    
                s = active_shift['start']
                e = active_shift['end']

                
                available_seconds = 0
                if s < e:
                    shift_end_datetime = datetime.combine(current_time.date(), e, tzinfo=current_time.tzinfo)
                    available_seconds = (shift_end_datetime - current_time).total_seconds()
                else:
                    current_time_time = current_time.time()
                    if current_time_time >= s:
                        next_day = (current_time + timedelta(days=1)).replace(hour=0, minute=0, second=0)
                        available_seconds = (next_day - current_time).total_seconds()
                    elif current_time_time < e:
                        shift_end_datetime = datetime.combine(current_time.date(), e, tzinfo=current_time.tzinfo)
                        available_seconds = (shift_end_datetime - current_time).total_seconds()
                
                available_hours = available_seconds / 3600.0
                
                # RESTRICCIÓN POR MANTENIMIENTOS FUTUROS
                for maint in active_maints:
                     if current_time <= maint['start'] < (current_time + timedelta(hours=available_hours)):
                          time_until_maint = (maint['start'] - current_time).total_seconds() / 3600.0
                          if time_until_maint < available_hours:
                               available_hours = time_until_maint
                
                if available_hours <= 0:
                     current_time += timedelta(hours=1)
                     continue
                
                time_to_consume = min(remaining_hours, available_hours)
                segment_will_end_at_shift_boundary = (time_to_consume >= available_hours - 0.001)

                # ===================================================================
                # ROBUST SHIFT BOUNDARY: Always compute exact shift_end_dt and snap.
                # This prevents floating-point drift from pushing tasks past the 
                # schedule limit (e.g., past 13:00 on Saturdays).
                # ===================================================================
                _e_now = active_shift['end'] if active_shift else None
                if _e_now and is_half_day_holiday(current_time, half_day_holidays):
                    _e_now = datetime.strptime("12:00", "%H:%M").time()
                shift_end_dt = datetime.combine(current_time.date(), _e_now, tzinfo=current_time.tzinfo) if _e_now else None


                if segment_will_end_at_shift_boundary and shift_end_dt:
                    # SNAP directly to shift boundary — eliminates all floating-point drift.
                    # Recalculate time_to_consume based on actual elapsed time since segment start.
                    if segment_start:
                        time_to_consume = max(0.0, (shift_end_dt - segment_start).total_seconds() / 3600.0)
                    current_time = shift_end_dt
                else:
                    current_time = current_time + timedelta(hours=time_to_consume)
                    # Extra safety: hard cap to shift end even for partial consumption
                    if shift_end_dt and current_time > shift_end_dt:
                        current_time = shift_end_dt
                
                remaining_hours -= time_to_consume
                
                # Create a segment if:
                # 1. Task is complete (no more hours remaining), OR
                # 2. We've reached the end of this shift
                if remaining_hours <= 0.001 or segment_will_end_at_shift_boundary:
                    # TRIPLE DEFENSE: hard-cap segment_end to shift boundary
                    segment_end = current_time
                    if shift_end_dt and segment_end > shift_end_dt:
                        segment_end = shift_end_dt
                    
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
                    
                    task_segments.append(segment)
                    segment_start = None
                
                original_curr = current_time
                current_time = _jump_to_next_start(current_time, schedules, non_working_days, half_day_holidays)
                
                # SAFETY: If time didn't advance (infinite loop protection), force +1 min/hour
                if current_time <= original_curr:
                     current_time += timedelta(minutes=30)
        
        # Distribuir el porcentaje de progreso visualmente a través de todos los segmentos (de izquierda a derecha)
        if task_segments:
            global_progress_fraction = min(1.0, produced / qty) if qty > 0 else 0.0
            total_duration = sum(seg.get('duration_real', 0) for seg in task_segments)
            hours_to_paint = total_duration * global_progress_fraction
            
            for seg in task_segments:
                seg_dur = seg.get('duration_real', 0)
                if hours_to_paint >= seg_dur and seg_dur > 0:
                    seg['progress_percent'] = 100.0
                    hours_to_paint -= seg_dur
                elif hours_to_paint > 0 and seg_dur > 0:
                    seg['progress_percent'] = (hours_to_paint / seg_dur) * 100.0
                    hours_to_paint = 0
                else:
                    seg['progress_percent'] = 0.0
                    
        # Add all segments to calculated_tasks
        calculated_tasks.extend(task_segments)
        
    return calculated_tasks

def _jump_to_next_start(current_time, schedules, non_working_days=None, half_day_holidays=None):
    """
    Helper to jump from a non-working non-started time to the next working start time.
    Also skips non-working holidays.
    """
    next_check = current_time
    
    from django.utils import timezone
    if timezone.is_aware(next_check):
        next_check = timezone.localtime(next_check)
    else:
        next_check = timezone.make_aware(next_check)

    
    # Limit lookahead
    for _ in range(14): 
        # Primero verificar si es feriado no laborable
        if is_non_working_holiday(next_check, non_working_days):
            # Saltar al siguiente día
            next_check = (next_check + timedelta(days=1)).replace(hour=0, minute=0, second=0)
            continue
        
        weekday = next_check.weekday()
        day_type = 'LV' if 0 <= weekday <= 4 else ('SA' if weekday == 5 else ('DO' if weekday == 6 else None))
        
        if day_type and day_type in schedules:
            matches = schedules[day_type]
            is_half = is_half_day_holiday(next_check, half_day_holidays)
            
            for sch in matches:
                s = sch['start']
                e = sch['end']
                if is_half: e = datetime.strptime("12:00", "%H:%M").time()
                
                sch_start = datetime.combine(next_check.date(), s, tzinfo=next_check.tzinfo)
                sch_end = datetime.combine(next_check.date(), e, tzinfo=next_check.tzinfo)
                
                if s < e:
                    if next_check < sch_start:
                        return sch_start
                    if sch_start <= next_check < sch_end:
                         return next_check
                else: # Wrap around
                    sch_end_morning = datetime.combine(next_check.date(), e, tzinfo=next_check.tzinfo)
                    if next_check < sch_end_morning: return next_check
                    if sch_end_morning <= next_check < sch_start: return sch_start
                    if next_check >= sch_start: return next_check

            
        # Move to next day start
        next_check = (next_check + timedelta(days=1)).replace(hour=0, minute=0, second=0)
        
    # Restore tzinfo if originally present? No, simulation is usually naive.
    return next_check + timedelta(hours=1)

def get_machine_capacity(maquina, start_date, end_date, non_working_days=None, half_day_holidays=None):
    """
    Calculates total working hours for a machine between two dates.
    """
    from collections import defaultdict
    schedules = defaultdict(list)
    for h in maquina.horarios.all().order_by('hora_inicio'):
        schedules[h.dia].append({'start': h.hora_inicio, 'end': h.hora_fin})

    if not schedules:
        # Fallback 07-16 LV
        schedules['LV'] = [{'start': datetime.strptime("07:00", "%H:%M").time(), 'end': datetime.strptime("16:00", "%H:%M").time()}]


    total_hours = 0.0
    # Clean dates to start of day
    current = start_date.replace(hour=0, minute=0, second=0, microsecond=0)
    limit = end_date.replace(hour=23, minute=59, second=59)
    
    while current <= limit:
        if not is_non_working_holiday(current, non_working_days):
            weekday = current.weekday()
            day_type = 'LV' if 0 <= weekday <= 4 else ('SA' if weekday == 5 else ('DO' if weekday == 6 else None))
            
            if day_type in schedules:
                matches = schedules[day_type]

                is_half = is_half_day_holiday(current, half_day_holidays)
                
                for sch in matches:
                    s = sch['start']
                    e = sch['end']
                    
                    if is_half:
                        limit_time = datetime.strptime("12:00", "%H:%M").time()
                        if e > limit_time: e = limit_time
                    
                    if s < e:
                        day_h = (datetime.combine(current.date(), e, tzinfo=current.tzinfo) - datetime.combine(current.date(), s, tzinfo=current.tzinfo)).total_seconds() / 3600.0
                        total_hours += max(0, day_h)
                    else: # Wrap midnight
                        total_hours += (24.0 - (s.hour + s.minute/60.0)) + (e.hour + e.minute/60.0)

                    
        current += timedelta(days=1)
    
    return total_hours
