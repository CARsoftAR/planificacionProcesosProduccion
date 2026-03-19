from datetime import datetime, timedelta
from collections import defaultdict
import json
from operator import itemgetter
from django.db.models import Q
from .models import MaquinaConfig, PrioridadManual, HiddenTask
from .services import get_planificacion_data
from .planning_service import calculate_timeline, get_machine_capacity

def get_gantt_data(request, force_run=False):
    """
    Shared logic for Visual Scheduler and Excel Export.
    Returns a dictionary with calculated timeline data and grid configuration.
    """
    from .models import Scenario, TaskDependency # Import here to avoid circular
    
    # --- PERSISTENCE LOGIC (Remember last selection) ---
    if 'proyectos' in request.GET:
        raw_proyectos = request.GET.get('proyectos')
        request.session['last_proyectos'] = raw_proyectos
    else:
        raw_proyectos = request.session.get('last_proyectos')

    if 'scenario_id' in request.GET:
        scenario_id = request.GET.get('scenario_id')
        request.session['last_scenario_id'] = scenario_id
    else:
        scenario_id = request.session.get('last_scenario_id')

    # 1. Get Local Machines
    maquinas = list(MaquinaConfig.objects.using('default').prefetch_related('horarios').all().order_by('id_maquina'))
    
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
    plan_mode = request.GET.get('plan_mode', 'manual') 
    
    # SCENARIO HANDLING
    active_scenario = None
    
    if scenario_id:
        try:
            active_scenario = Scenario.objects.using('default').get(pk=scenario_id)
        except Scenario.DoesNotExist:
            pass
            
    if not active_scenario:
        # Default to principal
        active_scenario = Scenario.objects.using('default').filter(es_principal=True).first()
        # Update session to reflect fallback
        if active_scenario and not request.session.get('last_scenario_id'):
            request.session['last_scenario_id'] = str(active_scenario.id)
        
    virtual_overrides = {}
    
    # ONLY load overrides if mode is MANUAL. 
    # If mode is 'original' (Automatico), we want pure ERP data.
    if plan_mode == 'manual':
        if active_scenario:
            # print(f"[INFO] Loading Scenario: {active_scenario.nombre} ({active_scenario.id})")
            manual_entries = PrioridadManual.objects.using('default').filter(scenario=active_scenario)
            
            for entry in manual_entries:
                ov_data = {
                    'maquina': entry.maquina,
                    'prioridad': entry.prioridad,
                    'tiempo_manual': entry.tiempo_manual,
                    'nivel_manual': entry.nivel_manual,
                    'porcentaje_solapamiento': entry.porcentaje_solapamiento if entry.porcentaje_solapamiento is not None else 0.0,
                    'manual_start': entry.fecha_inicio_manual 
                }
                virtual_overrides[entry.id_orden] = ov_data
        else:
            pass # print("[WARN] No Active Scenario found. Loading EMPTY overrides.")
    else:
        pass # print("[INFO] AUTOMATIC MODE: Ignoring manual overrides (Rerouting, Pinning, etc.)")
        
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
            'ran_calculation': False,
            'active_scenario': active_scenario,
            'analysis': {
                'machines': [],
                'project_alerts': []
            },
            'system_alerts': []
        }

    # --- AUTOMATIC DEPENDENCIES (Option B: Nivel) ---
    # print("\n" + "=" * 70)
    # print("[INFO] SHARED GANTT LOGIC: Dependencias Automaticas por Nivel")
    # print("=" * 70)

    # NEW FEATURE: Automatic or Manual Overlap (Default to False/0%)
    auto_overlap = False

    deps_filter = {}
    if raw_proyectos:
         deps_filter['proyectos'] = [p.strip() for p in raw_proyectos.split(',') if p.strip()]
    if request.GET.get('id_orden'):
        deps_filter['id_orden'] = request.GET.get('id_orden')
    
    all_tasks_raw = get_planificacion_data(deps_filter)

    # OPCION A: Exclude tasks with no machine assigned from the Gantt entirely.
    # These tasks have Idmaquina empty or MAQUINAD = 'SIN ASIGNAR'.
    all_tasks_for_deps = [
        t for t in all_tasks_raw
        if str(t.get('Idmaquina', '')).strip() != ''
        and str(t.get('MAQUINAD', '')).strip().upper() != 'SIN ASIGNAR'
    ]
    
    print(f"[INFO] Tareas totales: {len(all_tasks_raw)}, Tareas con maquina asignada: {len(all_tasks_for_deps)} (excluidas sin maquina: {len(all_tasks_raw) - len(all_tasks_for_deps)})")

    # Pre-group tasks by machine for internal loop efficiency
    all_tasks_by_machine = defaultdict(list)
    # Harmonization map for ERP IDs based on local MaquinaConfig
    # This ensures if ERP says 'VF2' but we mapped it to 'MAC10', we group by 'MAC10'
    m_config_map = {m.id_maquina.strip(): m.id_maquina.strip() for m in maquinas}
    # Also add reverse map from Name to ID in case ERP uses Name as ID
    name_to_id = {m.nombre.strip(): m.id_maquina.strip() for m in maquinas}

    for t in all_tasks_for_deps:
        mid_code = str(t.get('Idmaquina', '')).strip()
        # Harmonize: If this ID is a name in our config, use the corresponding ID
        if mid_code in name_to_id:
            mid_code = name_to_id[mid_code]
        
        all_tasks_by_machine[mid_code].append(t)
        
    # Fetch Holidays once
    from .models import Feriado
    all_feriados = Feriado.objects.using('default').filter(activo=True)
    non_working_days = set(f.fecha for f in all_feriados if f.tipo_jornada == 'NO')
    half_day_holidays = set(f.fecha for f in all_feriados if f.tipo_jornada == 'MEDIO')
    # --- DETECT COMPLETED PROJECTS ---
    system_alerts = []
    if raw_proyectos:
        requested_list = [p.strip() for p in raw_proyectos.split(',') if p.strip()]
        # Use all_tasks_raw so projects with only unassigned tasks aren't wrongly flagged as "completed"
        found_active_projects = set(t.get('ProyectoCode') for t in all_tasks_raw)
        
        for req in requested_list:
            if req not in found_active_projects:
                # Check status
                raw_check = get_planificacion_data({'proyectos': [req]}, exclude_completed=False)
                if raw_check:
                    # It exists but was filtered
                    status = raw_check[0].get('Estadod', 'DESCONOCIDO')
                    system_alerts.append({
                        'type': 'warning',
                        'message': f"El proyecto <strong>{req}</strong> ya se terminó y está <strong>{status}</strong>. No se incluirá en la planificación."
                    })

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
        """
        Robust level resolution.
        Priority: Nivel_Planificacion (manual) > Nivel (ERP).
        """
        try:
            # We treat 0 as 'not set' or 'legacy level' in this context
            plan_lvl = t.get('Nivel_Planificacion')
            if plan_lvl is not None and float(plan_lvl) != 0:
                return float(plan_lvl)
            
            erp_lvl = t.get('Nivel')
            if erp_lvl is not None:
                return float(erp_lvl)
            
            return 0.0
        except (ValueError, TypeError):
            return 0.0

    for formula, tasks_in_order in orders_map.items():
        # Component key: Prefix of Descri before the last process name
        def get_dep_key(t):
            desc = str(t.get('Descri', '')).strip().upper()
            
            # 1. Clean common prefixes that shouldn't split a component into different groups
            # (e.g. 'ARMADO REPUESTO' should group with 'REPUESTO')
            prefixes_to_ignore = ["ARMADO ", "MATERIAL ", "COMPRA ", "RECEPCION ", "SERVICIO ", "TERCERO "]
            trimmed_desc = desc
            for p in prefixes_to_ignore:
                if trimmed_desc.startswith(p):
                    trimmed_desc = trimmed_desc[len(p):].strip()

            # 2. Use the ' - ' separator to identify the component prefix
            if " - " in trimmed_desc:
                parts = trimmed_desc.split(" - ")
                if len(parts) > 1:
                    return " - ".join(parts[:-1]).strip()
            
            # 3. If no separator, the trimmed description itself is the grouping key
            # (unless it is empty, then fallback to project code)
            if trimmed_desc:
                return trimmed_desc

            return f"DEFAULT_GROUP_{t.get('ProyectoCode', 'UNKNOWN')}"

        # IMPORTANT: Use all_tasks_raw to include unassigned tasks in the dependency chain
        project_tasks_raw = [t for t in all_tasks_raw if t.get('ProyectoCode') == formula]
        
        parts_groups = defaultdict(list)
        for t in project_tasks_raw:
            key = get_dep_key(t)
            parts_groups[key].append(t)

        # For each piece/component, link its operations in descending order of Nivel_Planificacion
        for part_key, part_tasks in parts_groups.items():
            # Sort by level descending (e.g. 10 -> 9 -> 7 -> 5)
            # Higher numbers (e.g. 10) are starting operations, lower numbers (e.g. 1) are assembly/final.
            p_tasks_sorted = sorted(part_tasks, key=get_nivel, reverse=True)
            
            for j in range(len(p_tasks_sorted) - 1):
                predecessor = p_tasks_sorted[j]
                successor = p_tasks_sorted[j+1]
                
                pred_id = str(predecessor.get('Idorden'))
                succ_id = str(successor.get('Idorden'))
                
                if pred_id and succ_id and pred_id != succ_id:
                    if succ_id not in dependency_map:
                        dependency_map[succ_id] = []
                    if pred_id not in dependency_map[succ_id]:
                        dependency_map[succ_id].append(pred_id)

    global_task_end_dates = {}

    # --- PASS 0: Calculate Virtual End Dates for UNASSIGNED tasks ---
    # This ensures that assigned tasks waiting for "SIN ASIGNAR" predecessors have a start time.
    unassigned_tasks = [
        t for t in all_tasks_raw 
        if str(t.get('Idmaquina', '')).strip() == '' or str(t.get('MAQUINAD', '')).strip().upper() == 'SIN ASIGNAR'
    ]
    # Simple virtual calculation (Sequential by level within piece, starting from start_simulation)
    # We don't respect full calendar here, just a rough estimate to unblock successors.
    for formula, tasks in orders_map.items():
        pass # The loop above already builds the map. 
        
    for ut in sorted(unassigned_tasks, key=get_nivel, reverse=True):
        tid = str(ut.get('Idorden'))
        duration = float(ut.get('Tiempo_Proceso', 0.1) or 0.1)
        
        # Start time is either start_simulation or end of predecessor
        v_start = start_simulation
        if tid in dependency_map:
            preds = dependency_map[tid]
            max_p_end = start_simulation
            for pid in preds:
                if pid in global_task_end_dates:
                    if global_task_end_dates[pid] > max_p_end:
                        max_p_end = global_task_end_dates[pid]
            v_start = max_p_end
            
        global_task_end_dates[tid] = v_start + timedelta(hours=duration)

    print(f"\n  [OK] Created {len(dependency_map)} robust dependencies including {len(unassigned_tasks)} virtual tasks")

    # Load Explicit Database Dependencies
    db_deps = TaskDependency.objects.all()
    print(f"  [INFO] Loading {db_deps.count()} explicit dependencies from DB")
    for dep in db_deps:
        s_succ = str(dep.successor_id)
        s_pred = str(dep.predecessor_id)
        
        if s_succ not in dependency_map:
            dependency_map[s_succ] = []
        if s_pred not in dependency_map[s_succ]:
            dependency_map[s_succ].append(s_pred)

    print(f"\n  [OK] Final Dependency Map: {len(dependency_map)} tasks have dependencies")

    # --- SIMULATION ---
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
    # print("=" * 60)
    # print("DEPENDENCY RESOLUTION: FIRST PASS")
    # print("=" * 60)
    
    # OPCION A: Do NOT create virtual SIN ASIGNAR row.
    # Tasks without a machine were already excluded above.

    # Ensure no duplicates in maquinas list by id_maquina
    unique_maquinas_list = []
    seen_machine_ids = set()
    for m in maquinas:
        m_id = str(m.id_maquina).strip()
        if m_id not in seen_machine_ids:
            unique_maquinas_list.append(m)
            seen_machine_ids.add(m_id)
    maquinas = unique_maquinas_list

    for maquina in maquinas:
        machine_id = str(maquina.id_maquina).strip()
        current_machine_code = machine_id
        current_machine_name = str(maquina.nombre).strip().upper()
        
        # USE PRE-FETCHED DATA
        if current_machine_code == 'MAC00' or 'SIN ASIGNAR' in current_machine_name:
            # Collect all tasks that are truly unassigned
            native_tasks = [t for t in all_tasks_for_deps if str(t.get('Idmaquina', '')).strip() == '' or str(t.get('Idmaquina', '')).strip() == 'MAC00' or str(t.get('MAQUINAD', '')).strip().upper() == 'SIN ASIGNAR']
        else:
            native_tasks = all_tasks_by_machine.get(current_machine_code, [])
            if not native_tasks and current_machine_name in all_tasks_by_machine:
                 native_tasks = all_tasks_by_machine[current_machine_name]
        
        # Filter Move Out/In
        active_tasks = []

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
            # USE PRE-FETCHED DATA for moved-in tasks too
            # We already have all tasks in all_tasks_for_deps if filter was global
            # If not, we found them in all_tasks_by_machine anyway
            for t_id in moved_in_ids:
                # Find the task in all_tasks_for_deps
                task_found = next((tx for tx in all_tasks_for_deps if str(tx['Idorden']) == str(t_id)), None)
                if task_found and task_found['Idorden'] not in hidden_ids:
                     active_tasks.append(task_found)
        
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
                 
                 if ov_data.get('manual_start'):
                     force_start_times_pass1[p_id] = ov_data['manual_start']
                     item['is_pinned'] = True

             else:
                 item['OrdenVisual'] = default_prio
             
             # NORMALIZE FOR TEMPLATE
             if 'Cantidad' not in item:
                 item['Cantidad'] = item.get('cantidad_final', item.get('Cantidad_Proyecto', 0))
             if 'Cantidadpp' not in item:
                 item['Cantidadpp'] = item.get('cantidad_producida', 0)
                 
        tasks.sort(key=lambda x: x.get('OrdenVisual', 999999))
        
        machine_tasks_map[machine_id] = {'maquina': maquina, 'tasks': tasks}
        
        calculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, 
                                            task_min_start_times=None, task_force_start_times=force_start_times_pass1,
                                            non_working_days=non_working_days, half_day_holidays=half_day_holidays)
        
        for ct in calculated_tasks:
             ct_id = str(ct.get('Idorden')) # Normalize to String
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
        calculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, 
                                            task_min_start_times=None, task_force_start_times=force_start_times_pass1,
                                            non_working_days=non_working_days, half_day_holidays=half_day_holidays)
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
        NUM_PASSES = 5
        
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
                        force_start_times[t_id_str] = man_start
    
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
                        
                        # Use overlap ONLY if explicitly set to > 0%
                        use_overlap = (overlap_pct > 0)
                        calc_overlap_pct = overlap_pct

                        if use_overlap and pass_idx > 0:
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
                                            porcentaje_minimo=calc_overlap_pct
                                        )
                                        if inicio_optimo > pred_info['start_date']:
                                            calculated_start_times.append(inicio_optimo)
                                        else:
                                            calculated_start_times.append(pred_info['end_date'])
                                    except:
                                        calculated_start_times.append(pred_info['end_date'])
                            
                            # CRITICAL FIX: Assign the calculated times to min_start_times
                            if calculated_start_times:
                                min_start_times[t_id_str] = max(calculated_start_times)
                            else:
                                # Fallback to standard wait if overlap calculation failed or yielded no results
                                max_pred_end = None
                                for pid in preds:
                                    if pid in global_task_end_dates:
                                        end_date = global_task_end_dates[pid]
                                        if max_pred_end is None or end_date > max_pred_end:
                                            max_pred_end = end_date
                                if max_pred_end:
                                    min_start_times[t_id_str] = max_pred_end
                        else:
                            # Standard Wait-for-End
                            max_pred_end = None
                            for pid in preds: # pid is String
                                if pid in global_task_end_dates: # global_task_end_dates must use String keys
                                    end_date = global_task_end_dates[pid]
                                    if max_pred_end is None or end_date > max_pred_end:
                                        max_pred_end = end_date
                            
                            if max_pred_end:
                                min_start_times[t_id_str] = max_pred_end
    
                # Sort tasks
                def get_sort_key(t):
                     tid = str(t.get('Idorden'))
                     nivel = get_nivel(t)
                     
                     visual_order = t.get('OrdenVisual', 999999)
                     
                     min_start = min_start_times.get(tid, start_simulation)
                     if min_start and min_start.tzinfo: min_start = min_start.replace(tzinfo=None)
                     
                     # Tie-breaker: Use ID descending for stability and matching Machine Table
                     try: tid_num = -int(tid)
                     except: tid_num = 0

                     if tid in force_start_times:
                         fst = force_start_times[tid]
                         if fst and fst.tzinfo: fst = fst.replace(tzinfo=None)
                         return (0, fst, -nivel, visual_order, tid_num) 
                     
                     return (1, -nivel, min_start, visual_order, tid_num)
                
                tasks.sort(key=get_sort_key)
                
                recalculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, 
                                                      task_min_start_times=min_start_times, task_force_start_times=force_start_times,
                                                      non_working_days=non_working_days, half_day_holidays=half_day_holidays)
                
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

    # Expand global range based on ALL processed machines (including virtual ones)
    for row in timeline_data:
        m = row['machine']
        # If it's a model instance, use horarios. If it's our Mock, it's already handled.
        if hasattr(m, 'horarios'):
            for h in m.horarios.all():
                has_schedules = True
                if h.hora_inicio.hour < global_min_h: global_min_h = h.hora_inicio.hour
                if h.hora_fin.hour > global_max_h: global_max_h = h.hora_fin.hour

    # Expandir rango basado en Tareas (para incluir pinning fuera de hora)
    for row in timeline_data:
        # Avoid letting 'SIN ASIGNAR' (MAC00) machine expand the timeline infinitely
        # if it has hundreds of pending tasks.
        if row['machine'].id_maquina == 'MAC00':
            continue

        for t in row['tasks']:
            s = t.get('start_date')
            e = t.get('end_date')
            if s:
                if s.hour < global_min_h: global_min_h = s.hour
                if s.hour > global_max_h: global_max_h = s.hour + 1
            if e:
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
    
    # CALCULATE MAX DATE (With safety cap)
    calc_max_date = min_date + timedelta(hours=48)
    for row in timeline_data:
        # Only allow real machines or explicit moves to expand the calendar
        if row['machine'].id_maquina == 'MAC00': continue

        for t in row['tasks']:
            if t['end_date'] and t['end_date'] > calc_max_date:
                calc_max_date = t['end_date']
    
    # SAFETY CAP: Max 30 days of Gantt to avoid browser crash
    absolute_max_date = min_date + timedelta(days=30)
    if calc_max_date > absolute_max_date:
        calc_max_date = absolute_max_date
        print(f"[WARN] GANTT: Timeline capped at 30 days to protect performance.")

    # Valid Dates (Mon-Fri + Sat if needed)
    show_saturdays = False
    # Check all machines in current timeline_data
    for row in timeline_data:
        m = row['machine']
        if hasattr(m, 'horarios'):
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
    
    # Cap day count to 30 as a final safety measure
    day_count = min((end_date_limit - day_pointer).days + 5, 45) 
    
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
             
    # --- ANALYSIS & ALERTS ---
    machine_analysis = []
    project_alerts = []
    
    # 1. Machine Load (Next 7 days)
    lookahead_days = 7
    analysis_end = start_simulation + timedelta(days=lookahead_days)
    
    for row in timeline_data:
        maquina = row['machine']
        tasks = row['tasks']
        
        # Calculate Capacity
        avail_hours = get_machine_capacity(maquina, start_simulation, analysis_end, 
                                         non_working_days=non_working_days, half_day_holidays=half_day_holidays)
        
        # Sum Task Durations in this period (Only the part within the period)
        task_hours = 0.0
        for t in tasks:
            t_start = t.get('start_date')
            t_end = t.get('end_date')
            if t_start and t_start < analysis_end:
                # If task ends after end of analysis, only count up to analysis_end
                actual_end = min(t_end, analysis_end)
                # This is a bit rough because calculate_timeline already handles work hours
                # Let's just sum the duration_real of tasks that start in the window
                task_hours += t.get('duration_real', 0)
        
        load_pct = (task_hours / avail_hours * 100) if avail_hours > 0 else 0
        
        machine_analysis.append({
            'id': maquina.id_maquina,
            'nombre': maquina.nombre,
            'load_pct': round(load_pct, 1),
            'hours': round(task_hours, 1),
            'capacity': round(avail_hours, 1),
            'tasks': [
                {
                    'id_orden': t.get('Idorden'),
                    'proyecto': t.get('ProyectoCode', 'S/P'),
                    'proceso': t.get('Denominacion', '-'),
                    'elemento': t.get('Descri', '-'),
                    'tiempo': round(t.get('duration_real', 0), 2),
                    'start': t.get('start_date'),
                    'end': t.get('end_date')
                }
                for t in tasks if t.get('start_date') and t.get('start_date') < analysis_end
            ]
        })
        
    # 2. Project Delays
    # Pre-calculate project deadlines from the GLOBAL task list (all_tasks_for_deps)
    # to avoid misleading dates based only on visible tasks.
    global_p_vtos = {}
    for t in all_tasks_for_deps:
        p_code = t.get('ProyectoCode', 'S/P')
        vto = t.get('Vto_Proyecto') or t.get('Vto')
        if vto:
            if p_code not in global_p_vtos or vto > global_p_vtos[p_code]:
                global_p_vtos[p_code] = vto

    project_tasks = defaultdict(list)
    for row in timeline_data:
        for t in row['tasks']:
            p_code = t.get('ProyectoCode', 'S/P')
            project_tasks[p_code].append(t)
            
    for p_code, p_tasks in project_tasks.items():
        # Max End Date (Simulation)
        max_end = max((t['end_date'] for t in p_tasks if t.get('end_date')), default=None)
        # Use Global Project Due Date
        max_vto = global_p_vtos.get(p_code)
        
        if max_end and max_vto:
            # Ensure same type for comparison (date vs date)
            if max_end.date() > max_vto.date():
                # Identify culprit tasks (those ending after vto)
                culprits = [
                    {'orden': t.get('Idorden'), 'desc': t.get('Descri'), 'end': t['end_date'].strftime('%d/%m')}
                    for t in p_tasks if t.get('end_date') and t.get('end_date').date() > max_vto.date()
                ]
                
                delay_days = (max_end.date() - max_vto.date()).days
                
                project_alerts.append({
                    'proyecto': p_code,
                    'max_end': max_end,
                    'vto': max_vto,
                    'delay_days': delay_days,
                    'culprits': culprits[:3] # Show top 3 bottlenecks
                })

    return {
        'timeline_data': timeline_data,
        'maquinas': maquinas,
        'start_simulation': start_simulation,
        'time_columns': time_columns,
        'valid_dates': valid_dates,
        'dependency_map': dependency_map,
        'global_min_h': global_min_h,
        'global_max_h': global_max_h,
        'ran_calculation': True,
        'active_scenario': active_scenario,
        'analysis': {
            'machines': machine_analysis,
            'project_alerts': project_alerts
        },
        'system_alerts': system_alerts
    }
