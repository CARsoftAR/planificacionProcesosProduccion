from datetime import datetime, timedelta
from collections import defaultdict
import json
from operator import itemgetter
from django.db.models import Q
from .models import MaquinaConfig, PrioridadManual, HiddenTask
from .services import get_planificacion_data
from .planning_service import calculate_timeline

def get_gantt_data(request, force_run=False):
    """
    Shared logic for Visual Scheduler and Excel Export.
    Returns a dictionary with calculated timeline data and grid configuration.
    """
    # 1. Get Local Machines
    maquinas = MaquinaConfig.objects.using('default').prefetch_related('horarios').all().order_by('id_maquina')
    
    # 2. Prepare Start Date
    fecha_desde = request.GET.get('fecha_desde')
    if fecha_desde:
        try:
            start_simulation = datetime.strptime(fecha_desde, '%Y-%m-%d')
        except ValueError:
            start_simulation = datetime.now()
    else:
        start_simulation = datetime.now()
    
    # Start from 7:00 AM
    start_simulation = start_simulation.replace(hour=7, minute=0, second=0, microsecond=0)
    
    timeline_data = []
    
    # 3. Virtual Overrides (PrioridadManual)
    # Check MODE: 'manual' (default) vs 'original'
    # Use request param 'plan_mode' -> 'manual' or 'original'. Default to 'manual' if not specified? 
    # User asked: "If I filter... load original data". "Button to save".
    # Strategy: Defaults to 'original' (ignore DB). 'manual' loads DB.
    
    plan_mode = request.GET.get('plan_mode', 'manual') # Default to Manual (User Edits)
    
    virtual_overrides = {}
    virtual_overrides = {}
    
    # ALWAYS load manual entries to respect Machine Assignments and Priorities
    # even in "Original" (Auto-Schedule) mode.
    # The difference is that in 'original', we ignore 'manual_start' (Pinning).
    
    manual_entries = PrioridadManual.objects.using('default').all()
    for entry in manual_entries:
        ov_data = {
            'maquina': entry.maquina,
            'prioridad': entry.prioridad,
            'tiempo_manual': entry.tiempo_manual,
            'nivel_manual': entry.nivel_manual,
            'porcentaje_solapamiento': entry.porcentaje_solapamiento if entry.porcentaje_solapamiento is not None else 0.0,
            'manual_start': entry.fecha_inicio_manual 
        }
        
        # In 'original' mode, we IGNORE PINNING (manual_start) to allow auto-scheduling
        # But we RESPECT machine moves.
        if plan_mode != 'manual':
            ov_data['manual_start'] = None
            
        virtual_overrides[entry.id_orden] = ov_data

    if plan_mode != 'manual':
        print("ℹ️ GANTT INFO: Auto Mode - Loaded Assignments but Ignored Pins")
        
    tasks_moved_in_map = {}
    for oid, override_data in virtual_overrides.items():
        mid = str(override_data['maquina']).strip()
        if mid not in tasks_moved_in_map:
             tasks_moved_in_map[mid] = []
        tasks_moved_in_map[mid].append(oid)
    
    hidden_ids = set(HiddenTask.objects.using('default').values_list('id_orden', flat=True))

    # EXECUTION CHECK
    run_calculation = (request.GET.get('run') == '1') or force_run

    if not run_calculation:
        # Return empty structure
        for maquina in maquinas:
            timeline_data.append({
                'machine': maquina,
                'tasks': []
            })
        
        return {
            'timeline_data': timeline_data,
            'maquinas': maquinas,
            'start_simulation': start_simulation,
            'time_columns': [],
            'valid_dates': [],
            'dependency_map': {},
            'global_min_h': 7,
            'global_max_h': 22,
            'ran_calculation': False
        }

    # --- AUTOMATIC DEPENDENCIES (Option B: Nivel) ---
    print("\n" + "=" * 70)
    print("[INFO] SHARED GANTT LOGIC: Dependencias Automaticas por Nivel")
    print("=" * 70)

    deps_filter = {}
    if request.GET.get('proyectos'):
         raw_proyectos = request.GET.get('proyectos')
         deps_filter['proyectos'] = [p.strip() for p in raw_proyectos.split(',') if p.strip()]
    if request.GET.get('id_orden'):
        deps_filter['id_orden'] = request.GET.get('id_orden')
    
    all_tasks_for_deps = get_planificacion_data(deps_filter) 
    
    # Apply Manual Nivel Overrides
    for task in all_tasks_for_deps:
        p_id = task.get('Idorden')
        ov_data = None
        if p_id in virtual_overrides:
             ov_data = virtual_overrides[p_id]
        else:
             try:
                 p_id_int = int(p_id)
                 if p_id_int in virtual_overrides:
                     ov_data = virtual_overrides[p_id_int]
             except: pass
        
        if ov_data and ov_data.get('nivel_manual') is not None:
             task['Nivel_Planificacion'] = ov_data['nivel_manual']

    # Group by ProyectoCode
    orders_map = defaultdict(list)
    for task in all_tasks_for_deps:
        formula = task.get('ProyectoCode')
        if formula:
            orders_map[formula].append(task)

    dependency_map = {}

    def get_nivel(t):
        try:
            val = t.get('Nivel_Planificacion')
            if val is None: return 0
            return float(val)
        except (ValueError, TypeError):
            return 0

    for formula, tasks_in_order in orders_map.items():
        tasks_sorted = sorted(tasks_in_order, key=get_nivel, reverse=True)
        tasks_assigned = [t for t in tasks_sorted if t.get('MAQUINAD') and t.get('MAQUINAD') != 'SIN ASIGNAR']
        
        nivel_groups = {}
        for task in tasks_assigned:
            nivel = get_nivel(task)
            if nivel not in nivel_groups:
                nivel_groups[nivel] = []
            nivel_groups[nivel].append(task)
        
        sorted_niveles = sorted(nivel_groups.keys(), reverse=True)
        
        for i in range(len(sorted_niveles) - 1):
            higher_nivel = sorted_niveles[i]
            lower_nivel = sorted_niveles[i + 1]
            
            for successor in nivel_groups[lower_nivel]:
                succ_id = successor.get('Idorden')
                if not succ_id: continue
                
                for predecessor in nivel_groups[higher_nivel]:
                    pred_id = predecessor.get('Idorden')
                    if not pred_id or pred_id == succ_id: continue
                    
                    # Normalize to string for consistency
                    s_succ_id = str(succ_id)
                    s_pred_id = str(pred_id)
                    
                    if s_succ_id not in dependency_map:
                        dependency_map[s_succ_id] = []
                    
                    if s_pred_id not in dependency_map[s_succ_id]:
                        dependency_map[s_succ_id].append(s_pred_id)

    print(f"\n  [OK] Created {len(dependency_map)} automatic dependencies based on Nivel (Desc)")

    # --- SIMULATION ---
    global_task_end_dates = {}
    machine_tasks_map = {}
    
    # Pre-calculate Moved Tasks Map to handle Re-routing
    tasks_moved_in_map = defaultdict(list)
    for tid, override in virtual_overrides.items():
        if override.get('maquina'):
            target_machine = str(override['maquina']).strip()
            # We must map Target Machine -> List of moved Task IDs
            # so that when we iterate that machine, we pull these guests.
            tasks_moved_in_map[target_machine].append(tid)
            
    # Also handle normalized keys if needed? 
    # virtual_overrides keys are usually int or str. The fetch logic later handles the ID.
    
    print(f"DEBUG: tasks_moved_in_map: {dict(tasks_moved_in_map)}")

    # FIRST PASS
    print("=" * 60)
    print("DEPENDENCY RESOLUTION: FIRST PASS")
    print("=" * 60)

    for maquina in maquinas:
        machine_id = maquina.id_maquina
        
        filtros = request.GET.copy() # Use request params for filtering
        machine_filter = {'machine_ids': [machine_id]}
        if request.GET.get('proyectos'):
             raw_proyectos = request.GET.get('proyectos')
             machine_filter['proyectos'] = [p.strip() for p in raw_proyectos.split(',') if p.strip()]

        native_tasks = get_planificacion_data(machine_filter)
        
        # Filter Move Out/In
        active_tasks = []
        current_machine_code = str(machine_id).strip()
        current_machine_name = str(maquina.nombre).strip()

        for t in native_tasks:
            try: oid = int(t.get('Idorden', 0))
            except: oid = 0
            
            if oid in virtual_overrides:
                override = virtual_overrides[oid]
                target = str(override['maquina']).strip()
                if target == current_machine_code or target == current_machine_name:
                    if oid not in hidden_ids: active_tasks.append(t)
            else:
                 if oid not in hidden_ids: active_tasks.append(t)
                 
        moved_in_ids = []
        if current_machine_code in tasks_moved_in_map:
            moved_in_ids.extend(tasks_moved_in_map[current_machine_code])
        if current_machine_name in tasks_moved_in_map:
             new_ids = tasks_moved_in_map[current_machine_name]
             moved_in_ids.extend([i for i in new_ids if i not in moved_in_ids])
        
        if moved_in_ids:
            inbound_filter = {}
            if request.GET.get('proyectos'):
                 inbound_filter['proyectos'] = machine_filter['proyectos']
            inbound_filter['id_orden_in'] = moved_in_ids
            extra_tasks = get_planificacion_data(inbound_filter)
            
            existing_ids = set(t['Idorden'] for t in active_tasks)
            for t in extra_tasks:
                if t['Idorden'] not in existing_ids and t['Idorden'] not in hidden_ids:
                    active_tasks.append(t)
        
        # Deduplicate
        unique_tasks_map = {}
        for t in active_tasks:
            tid = str(t.get('Idorden'))
            if tid not in unique_tasks_map: unique_tasks_map[tid] = t
        tasks = list(unique_tasks_map.values())
        
        # Sorting & Manual Time & Force Start
        force_start_times_pass1 = {}
        for idx, item in enumerate(tasks):
             default_prio = (idx + 1) * 1000.0
             p_id = item['Idorden']
             
             ov_data = None
             if p_id in virtual_overrides: ov_data = virtual_overrides[p_id]
             else:
                 try: 
                     p_id_int = int(p_id)
                     if p_id_int in virtual_overrides: ov_data = virtual_overrides[p_id_int]
                 except: pass
             
             if ov_data:
                 item['OrdenVisual'] = float(ov_data['prioridad'])
                 if ov_data.get('tiempo_manual') is not None:
                     item['Tiempo_Proceso'] = float(ov_data['tiempo_manual'])
                     item['CalculadoManual'] = True
                 if ov_data.get('nivel_manual') is not None:
                      item['Nivel_Planificacion'] = ov_data['nivel_manual']
                 
                 # Collect Force Start for First Pass
                 if ov_data.get('manual_start'):
                     force_start_times_pass1[p_id] = ov_data['manual_start']
             else:
                 item['OrdenVisual'] = default_prio
                 
        tasks.sort(key=lambda x: x.get('OrdenVisual', 999999))
        
        machine_tasks_map[machine_id] = {'maquina': maquina, 'tasks': tasks}
        
        calculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, task_min_start_times=None, task_force_start_times=force_start_times_pass1)
        
        for ct in calculated_tasks:
             ct_id = ct.get('Idorden')
             ct_end = ct.get('end_date')
             if ct_id and ct_end:
                 if ct_id not in global_task_end_dates or ct_end > global_task_end_dates[ct_id]:
                     global_task_end_dates[ct_id] = ct_end


    # Build timeline_map from first pass for use in manual mode
    timeline_map = {}
    for machine_id, machine_data in machine_tasks_map.items():
        maquina = machine_data['maquina']
        tasks = machine_data['tasks']
        # Run basic timeline calculation with manual overrides
        calculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, task_min_start_times=None, task_force_start_times=force_start_times_pass1)
        timeline_map[machine_id] = {'machine': maquina, 'tasks': calculated_tasks}

    # SECOND PASS (Multi-Pass with Overlap Calculation)
    # SKIP THIS IN MANUAL MODE! We don't want to recalculate positions.
    # SECOND PASS (Multi-Pass with Overlap Calculation)
    # ENABLED FOR ALL MODES to support Dependencies across machines
    # In 'manual', Pinned tasks (with manual_start) will NOT move. Unpinned tasks WILL wait for dependencies.
    
    print("\n" + "=" * 60)
    print("DEPENDENCY RESOLUTION: SECOND PASS (Multi-Pass + Overlap)")
    print("=" * 60)
    
    # Always run dependency resolution
    if True:  
        from .overlap_calculator import calcular_inicio_optimo_sucesor
        from .overlap_calculator import calcular_inicio_optimo_sucesor
        
        final_timeline_map = {}
        NUM_PASSES = 3
        
        # Build task info map for overlap calculations
        task_info_map = {}  # task_id -> {duration, cantidad, start_date, end_date}
        
        for pass_idx in range(NUM_PASSES):
            print(f"\n--- Pass {pass_idx + 1}/{NUM_PASSES} ---")
        
            # SMART SORTING of MACHINES to speed up convergence
            # Process machines with higher hierarchy tasks first? 
            # Difficult to guess, but we can sort by name or just ensure determinism.
            sorted_machine_items = sorted(machine_tasks_map.items(), key=lambda x: x[0])

            for machine_id, machine_data in sorted_machine_items:
                maquina = machine_data['maquina']
                tasks = machine_data['tasks']
                
                min_start_times = {}
                force_start_times = {}
                
                for t in tasks:
                    t_id = t.get('Idorden')
                    t_id_str = str(t_id) # Normalize
                    
                    # Normalize ID for lookup in overrides (keys are integers in DB/Dict)
                    t_id_int = None
                    try: t_id_int = int(t_id)
                    except: pass
                    
                    # Check Manual Pinning
                    man_start = None
                    if t_id in virtual_overrides:
                         man_start = virtual_overrides[t_id].get('manual_start')
                    elif t_id_int and t_id_int in virtual_overrides:
                         man_start = virtual_overrides[t_id_int].get('manual_start')
    
                    if man_start:
                        force_start_times[t_id] = man_start
    
                    # Check Dependencies using STRING KEYS
                    if t_id_str in dependency_map:
                        preds = dependency_map[t_id_str] # List of String IDs
                        
                        # Get overlap percentage
                        overlap_pct = 0.0
                        if t_id in virtual_overrides:
                            overlap_pct = virtual_overrides[t_id].get('porcentaje_solapamiento', 0.0)
                        elif t_id_int and t_id_int in virtual_overrides:
                            overlap_pct = virtual_overrides[t_id_int].get('porcentaje_solapamiento', 0.0)
                        
                        # ... Logica de Solapamiento
                        calculated_start_times = []
                        if overlap_pct > 0 and pass_idx > 0:
                            for pid in preds: # pid is String
                                if pid in task_info_map: # task_info_map must use String keys
                                    pred_info = task_info_map[pid]
                                    succ_duration = t.get('Tiempo_Proceso', 0)
                                    succ_cantidad = t.get('Cantidad', 1)
                                    
                                    try:
                                        inicio_optimo, _ = calcular_inicio_optimo_sucesor(
                                            pred_start=pred_info['start_date'],
                                            pred_duration=pred_info['duration'],
                                            pred_cantidad=pred_info['cantidad'],
                                            succ_duration=succ_duration,
                                            succ_cantidad=succ_cantidad,
                                            porcentaje_minimo=overlap_pct
                                        )
                                        if inicio_optimo > pred_info['start_date']:
                                            calculated_start_times.append(inicio_optimo)
                                    except:
                                        calculated_start_times.append(pred_info['end_date'])
                                        
                            if calculated_start_times:
                                min_start_times[t_id] = max(calculated_start_times)
                        else:
                            # Standard Wait-for-End
                            max_pred_end = None
                            for pid in preds: # pid is String
                                if pid in global_task_end_dates: # global_task_end_dates must use String keys
                                    end_date = global_task_end_dates[pid]
                                    if max_pred_end is None or end_date > max_pred_end:
                                        max_pred_end = end_date
                            if max_pred_end:
                                min_start_times[t_id] = max_pred_end
    
                # Sort tasks
                def get_sort_key(t):
                     tid = t.get('Idorden')
                     
                     try: nivel = float(t.get('Nivel_Planificacion') or 0)
                     except: nivel = 0
                     
                     visual_order = t.get('OrdenVisual', 999999)
                     
                     min_start = min_start_times.get(tid, start_simulation)
                     if min_start and min_start.tzinfo: min_start = min_start.replace(tzinfo=None)
                     
                     if tid in force_start_times:
                         fst = force_start_times[tid]
                         if fst and fst.tzinfo: fst = fst.replace(tzinfo=None)
                         return (0, fst, -nivel, visual_order) 
                     
                     # If unpinned, prioritize Nivel but also consider if it CAN start early?
                     # No, Nivel is King for sequence.
                     return (1, -nivel, min_start, visual_order)
                
                tasks.sort(key=get_sort_key)
                
                recalculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, task_min_start_times=min_start_times, task_force_start_times=force_start_times)
                
                final_timeline_map[machine_id] = {'machine': maquina, 'tasks': recalculated_tasks}
    
                # UPDATE GLOBAL MAPS with STRING KEYS
                for ct in recalculated_tasks:
                     ct_id = str(ct.get('Idorden')) # Force String
                     ct_end = ct.get('end_date')
                     ct_start = ct.get('start_date')
                     
                     if ct_end:
                         global_task_end_dates[ct_id] = ct_end
                         
                         if ct_id not in task_info_map:
                             task_info_map[ct_id] = {
                                 'start_date': ct_start,
                                 'end_date': ct_end,
                                 'duration': ct.get('Tiempo_Proceso', 0),
                                 'cantidad': ct.get('Cantidad', 1)
                             }
                         else:
                             current_info = task_info_map[ct_id]
                             if ct_start < current_info['start_date']: current_info['start_date'] = ct_start
                             if ct_end > current_info['end_date']: current_info['end_date'] = ct_end
    else:
        # In MANUAL mode, use the FIRST PASS results only (no recalculation)
        # The manual overrides were already applied in the first pass
        final_timeline_map = timeline_map

    # Build Final Timeline Data
    for machine_id in machine_tasks_map.keys():
        if machine_id in final_timeline_map:
            timeline_data.append(final_timeline_map[machine_id])

    # --- GRID & COLUMNS ---
    global_min_h = 24
    global_max_h = 0
    has_schedules = False
    
    for m in maquinas:
        for h in m.horarios.all():
            has_schedules = True
            if h.hora_inicio.hour < global_min_h: global_min_h = h.hora_inicio.hour
            if h.hora_fin.hour > global_max_h: global_max_h = h.hora_fin.hour

    # Expandir rango basado en Tareas (para incluir pinning fuera de hora)
    for row in timeline_data:
        for t in row['tasks']:
            s = t.get('start_date')
            e = t.get('end_date')
            if s:
                if s.hour < global_min_h: global_min_h = s.hour
                if s.hour > global_max_h: global_max_h = s.hour + 1
            if e:
                # Si termina y tiene minutos (ej 18:30), necesitamos ver la hora 18
                # Si termina en punto (18:00), necesitamos ver hasta la 17.
                h_end = e.hour
                if e.minute > 0:
                    if h_end >= global_max_h: global_max_h = h_end + 1
                else:
                    if h_end > global_max_h: global_max_h = h_end
    
    if not has_schedules:
        global_min_h = 7
        global_max_h = 18
        
    if global_max_h <= global_min_h:
        global_max_h = 23
        global_min_h = 0
        
    min_date = start_simulation.replace(hour=global_min_h)
    calc_max_date = min_date + timedelta(hours=48)
    for row in timeline_data:
        for t in row['tasks']:
            if t['end_date'] and t['end_date'] > calc_max_date:
                calc_max_date = t['end_date']
                
    # Valid Dates (Mon-Fri + Sat if needed)
    show_saturdays = False
    for m in maquinas:
        for h in m.horarios.all():
            if h.dia == 'SA':
                show_saturdays = True
                break
        if show_saturdays: break
        
    # Collect Task Days to force show them (user pinning)
    task_days = set()
    for row in timeline_data:
        for t in row['tasks']:
            if t.get('start_date'):
                task_days.add(t['start_date'].date())

    valid_dates = []
    day_pointer = min_date.date()
    end_date_limit = calc_max_date.date()
    day_count = (end_date_limit - day_pointer).days + 5
    
    for d in range(day_count):
        current_day = day_pointer + timedelta(days=d)
        
        # Always include if a task is scheduled on this day
        if current_day in task_days:
            valid_dates.append(current_day)
            continue

        wd = current_day.weekday()
        if 0 <= wd <= 4:
            valid_dates.append(current_day)
        elif wd == 5 and show_saturdays:
            valid_dates.append(current_day)
    
    time_columns = []
    for d in valid_dates:
        for h in range(global_min_h, global_max_h):
             dt = datetime.combine(d, datetime.min.time()) + timedelta(hours=h)
             time_columns.append(dt)
             
    return {
        'timeline_data': timeline_data,
        'maquinas': maquinas,
        'start_simulation': start_simulation,
        'time_columns': time_columns,
        'valid_dates': valid_dates,
        'dependency_map': dependency_map,
        'global_min_h': global_min_h,
        'global_max_h': global_max_h,
        'ran_calculation': True
    }
