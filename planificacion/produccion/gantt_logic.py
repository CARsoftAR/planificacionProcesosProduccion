from datetime import datetime, timedelta
from collections import defaultdict
import json
from operator import itemgetter
from django.db.models import Q
from django.utils import timezone
from .models import MaquinaConfig, PrioridadManual, HiddenTask, MantenimientoMaquina
from .services import get_planificacion_data
from .planning_service import calculate_timeline, get_machine_capacity


def find_compatible_machines(failed_machine, all_machines):
    """
    Find machines that can handle tasks from a failed machine.
    Currently uses heuristic: same sector or similar machine name keywords.
    Returns list of (machine, compatibility_score).
    """
    # 1. Try to find explicit equivalencies in the new table
    from .models import MaquinaEquivalencia
    equivs = MaquinaEquivalencia.objects.using('default').filter(maquina_origen=failed_machine).select_related('maquina_destino')
    
    if equivs.exists():
        compatible = []
        for eq in equivs:
            # We assign a base score of 100 for explicit matches.
            # Efficiency can be used to rank them if needed, but for now 100 is the standard.
            compatible.append((eq.maquina_destino, 100))
        return compatible

    # 2. Fallback to keyword-based heuristic
    # Keywords that indicate similar capability
    tornos_keywords = ['torno', 'cnc', 'tsugami', 'tm1', 'nlx', 'haas', 'dmg']
    fresadoras_keywords = ['fresa', 'fresadora', 'vf', 'mac']

    def get_machine_type(m):
        name = m.nombre.lower()
        if any(k in name for k in tornos_keywords):
            return 'torno'
        elif any(k in name for k in fresadoras_keywords):
            return 'fresadora'
        elif 'soldadura' in name:
            return 'soldadura'
        elif 'pulido' in name:
            return 'pulido'
        return 'general'

    failed_type = get_machine_type(failed_machine)
    compatible = []

    for m in all_machines:
        if m.id_maquina == failed_machine.id_maquina:
            continue  # Skip the failed machine itself

        # Check if machine has active maintenance
        active_maints = MantenimientoMaquina.objects.using('default').filter(
            maquina=m,
            estado__in=['PROGRAMADO', 'EN_CURSO', 'FALLA']
        )
        now = timezone.now()
        has_active_maint = any(
            maint.fecha_inicio <= now <= maint.fecha_fin
            for maint in active_maints
        )
        if has_active_maint:
            continue  # Skip machines that are also down

        machine_type = get_machine_type(m)

        # Calculate compatibility score
        score = 0
        if machine_type == failed_type:
            score = 100  # Same type = highest compatibility
        elif failed_type == 'general' or machine_type == 'general':
            score = 50  # Somewhat compatible

        if score > 0:
            compatible.append((m, score))

    # Sort by compatibility score (highest first)
    compatible.sort(key=lambda x: -x[1])
    return compatible


def get_machine_load(machine, start_date, end_date):
    """
    Calculate how many hours a machine is occupied in a date range.
    Returns total hours occupied.
    """
    tasks = get_planificacion_data(
        maquina=machine,
        fecha_desde=start_date.strftime('%Y-%m-%d'),
        fecha_hasta=end_date.strftime('%Y-%m-%d')
    )

    total_hours = sum(float(t.get('Tiempo_Proceso', 0) or 0) for t in tasks)
    return total_hours


def redistribute_tasks_to_machine(failed_machine_id, target_machine, tasks_to_move):
    """
    Move specified tasks from failed machine to target machine.
    Returns list of moved task IDs.
    """
    moved = []

    for task in tasks_to_move:
        task_id = task.get('Idorden')
        if task_id:
            # Create a priority override to move the task
            try:
                from .models import PrioridadManual, Scenario

                # Find or create a scenario for redistribution
                scenario = Scenario.objects.using('default').filter(es_principal=True).first()
                if not scenario:
                    # Create a temporary scenario
                    scenario = Scenario.objects.using('default').create(
                        nombre="Redistribución Automática",
                        descripcion="Tareas redistribuidas automáticamente",
                        es_principal=False
                    )

                # Update or create priority entry to redirect this task
                PrioridadManual.objects.using('default').update_or_create(
                    id_orden=task_id,
                    scenario=scenario,
                    defaults={
                        'maquina': target_machine.id_maquina,
                        'prioridad': 1,  # Highest priority
                    }
                )
                moved.append(task_id)

            except Exception as e:
                print(f"Error moving task {task_id}: {e}")

    return moved


def get_adaptive_capacity_alerts(timeline_data, maquinas):
    """
    Check for machines with failures and suggest redistribution options.
    Returns list of alerts with suggestions.
    """
    from .models import MantenimientoMaquina

    alerts = []
    now = timezone.now()
    
    # DEBUG: Get all active maintenance to see what's in the DB
    all_f = MantenimientoMaquina.objects.using('default').filter(estado__in=['FALLA', 'EN_CURSO', 'PROGRAMADO'])
    print(f"DEBUG: [AdaptiveAlerts] Total active Maintenance records (FALLA/CURSO/PROG) in DB: {all_f.count()}")
    for f in all_f:
        print(f"   - Falla ID {f.id}: Machine {f.maquina.id_maquina} ({f.maquina.nombre}), Start: {f.fecha_inicio}, End: {f.fecha_fin}, Status: {f.estado}")

    # Find machines with active maintenance (FALLA, EN_CURSO, PROGRAMADO)
    active_failures = MantenimientoMaquina.objects.using('default').filter(
        estado__in=['FALLA', 'EN_CURSO', 'PROGRAMADO'],
        fecha_inicio__lte=now + timedelta(days=14), # Lookahead 2 weeks
        fecha_fin__gte=now
    ).select_related('maquina')

    print(f"DEBUG: [AdaptiveAlerts] Active failures found for NOW ({now}): {active_failures.count()}")

    for failure in active_failures:
        failed_machine = failure.maquina
        affected_tasks = []
        
        f_id_check = str(failed_machine.id_maquina).strip().upper()
        print(f"DEBUG: [AdaptiveAlerts] Checking machine: {f_id_check}")

        # Find tasks scheduled during the failure period
        for row in timeline_data:
            row_m_id = str(row['machine'].id_maquina).strip().upper()
            
            if row_m_id == f_id_check:
                print(f"   - Match found for machine {row_m_id}. Checking {len(row['tasks'])} tasks.")
                for task in row['tasks']:
                    task_start = task.get('start_date')
                    task_end = task.get('end_date')
                    if task_start and task_end:
                        # NUEVA LOGICA: Cola de Producción
                        # Cualquier tarea que empiece DESPUÉS de que inicie la falla
                        f_start = failure.fecha_inicio
                        
                        if task_start >= f_start:
                            affected_tasks.append(task)
                
                print(f"   - Affected tasks count: {len(affected_tasks)}")
                if affected_tasks:
                    for at in affected_tasks[:2]:
                         print(f"     * Potential Task: {at.get('Idorden')} (Starts {at.get('start_date')})")

        if affected_tasks:
            # Find compatible machines
            compatible = find_compatible_machines(failed_machine, maquinas)

            alerts.append({
                'machine': failed_machine.nombre,
                'machine_id': failed_machine.id_maquina,
                'failure_reason': failure.motivo,
                'failure_start': failure.fecha_inicio,
                'failure_end': failure.fecha_fin,
                'affected_tasks_count': len(affected_tasks),
                'affected_tasks': [{'id': t.get('Idorden'), 'desc': t.get('Descri', '')[:50]} for t in affected_tasks[:5]],
                'compatible_machines': [
                    {'name': m.nombre, 'id': m.id_maquina, 'score': s}
                    for m, s in compatible[:3]
                ]
            })
        else:
            print(f"   - No affected tasks found in current timeline for failure {failure.id}")

    print(f"DEBUG: [AdaptiveAlerts] Final alerts count: {len(alerts)}")
    return alerts


def simulate_task_scheduling(*args, **kwargs):
    # Stub to resolve the missing function error from backfilling logic
    # Returns: fit_success, cand_segments, next_t
    return False, [], args[1] if len(args) > 1 else None

def get_gantt_data(request, force_run=False):
    """
    Shared logic for Visual Scheduler and Excel Export.
    Returns a dictionary with calculated timeline data and grid configuration.
    """
    from django.utils import timezone
    from datetime import timedelta
    from .models import MaquinaConfig, PrioridadManual, TaskDependency, Scenario
    import json
    import urllib.parse
    
    # User requested control prints
    active_scenario_id = request.GET.get('scenario_id') or request.session.get('active_scenario_id')
    active_scenario = None
    if active_scenario_id:
         active_scenario = Scenario.objects.using('default').filter(id=active_scenario_id).first()
    else:
         active_scenario = Scenario.objects.using('default').filter(es_principal=True).first()
         
    if active_scenario:
         print(f"Antes de procesar Gantt - Proyectos en DB: {active_scenario.proyectos}")

    # --- PERSISTENCE LOGIC (Remember last selection) ---
    # Strict Filtering: Only use projects from the current GET request
    raw_proyectos = request.GET.get('proyectos', '')
    if raw_proyectos:
        raw_proyectos = urllib.parse.unquote(raw_proyectos).replace('%2C', ',').strip()
    
    # No Hard Reset logic here anymore per user request (read-only visualization)
    clear_flag = request.GET.get('clear', '0') == '1'
    if clear_flag or raw_proyectos == '':
        raw_proyectos = None

    # ID Orden
    id_orden = request.GET.get('id_orden')
    if id_orden is not None:
        request.session['last_id_orden_filter'] = id_orden
    elif 'id_orden' not in request.GET:
        id_orden = request.session.get('last_id_orden_filter')

    # Scenario
    scenario_id = request.GET.get('scenario_id')
    if scenario_id == 'null' or scenario_id == '':
        scenario_id = None
        
    if scenario_id:
        request.session['last_scenario_id'] = scenario_id
    else:
        scenario_id = request.session.get('last_scenario_id')

    # Plan Mode
    plan_mode = request.GET.get('plan_mode')
    if plan_mode:
        request.session['last_plan_mode'] = plan_mode
    else:
        plan_mode = request.session.get('last_plan_mode', 'manual')
 
    
    # 1. Get Local Machines
    maquinas = list(MaquinaConfig.objects.using('default').prefetch_related('horarios').all().order_by('id_maquina'))
    
    # Pre-fetch all active maintenances in a single query to avoid N+1 queries
    from .models import MantenimientoMaquina
    from collections import defaultdict
    try:
        all_mants = MantenimientoMaquina.objects.using('default').filter(maquina__in=maquinas).exclude(estado='FINALIZADO')
        mants_by_machine = defaultdict(list)
        for m in all_mants:
            s, e = m.fecha_inicio, m.fecha_fin
            if s:
                if timezone.is_naive(s): s = timezone.make_aware(s)
                else: s = timezone.localtime(s)
            if e:
                if timezone.is_naive(e): e = timezone.make_aware(e)
                else: e = timezone.localtime(e)
            mants_by_machine[m.maquina_id].append({'start': s, 'end': e, 'motivo': m.motivo})
        
        for m in maquinas:
            m._cached_maintenances = mants_by_machine.get(m.id_maquina, [])
    except Exception as ex:
        print(f"Error pre-fetching maintenances: {ex}")
    
    # 2. Prepare Start Date
    fecha_desde = request.GET.get('fecha_desde')
    if fecha_desde:
        try:
            naive_dt = datetime.strptime(fecha_desde, '%Y-%m-%d')
            start_simulation = timezone.make_aware(naive_dt)
        except (ValueError, TypeError):
            start_simulation = timezone.now()
    else:
        start_simulation = timezone.now()
    
    # Start from 7:00 AM
    start_simulation = start_simulation.replace(hour=7, minute=0, second=0, microsecond=0)
    
    timeline_data = []

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
            
    if not raw_proyectos and active_scenario:
        from .models import PlannedTask
        # SNAPSHOT RULE: Solo leemos los proyectos de las tareas congeladas (en_gantt=True).
        # Si no filtramos aquí, los proyectos nuevos que agregó el usuario (en_gantt=False)
        # contaminarían el Gantt aunque el usuario no haya presionado "Graficar".
        db_proyectos = list(PlannedTask.objects.using('default').filter(
            scenario=active_scenario,
            enviado_a_gantt=True
        ).values_list('proyecto_code', flat=True).distinct())
        if db_proyectos:
            raw_proyectos = ','.join(p for p in db_proyectos if p)
            
    # Plan Mode
    virtual_overrides = {}

    # Cargar overrides en modo 'auto' Y 'manual'. Solo excluimos 'original' (datos puros ERP).
    # REGLA CRITICA: si el usuario movio una OP a otra maquina, ese override SIEMPRE debe
    # respetarse en el motor, sin importar si esta en modo Auto o Manual.
    if plan_mode != 'original':
        if active_scenario:
            # order_by('pk') ASC: si hay 2 registros para el mismo id_orden
            # (OP recien movida = PK mayor), el mas nuevo sobreescribe al viejo.
            manual_entries = PrioridadManual.objects.using('default').filter(
                scenario=active_scenario
            ).order_by('pk')

            for entry in manual_entries:
                ov_data = {
                    'maquina': entry.maquina,
                    'prioridad': entry.prioridad,
                    'tiempo_manual': entry.tiempo_manual,
                    'nivel_manual': entry.nivel_manual,
                    'porcentaje_solapamiento': entry.porcentaje_solapamiento if entry.porcentaje_solapamiento is not None else 0.0,
                    'modo_solapamiento': entry.modo_solapamiento or 'automatico',
                    'cantidad_producida_manual': entry.cantidad_producida_manual,
                    'manual_start': entry.fecha_inicio_manual,
                    'orden_secuencia': entry.orden_secuencia
                }
                try:
                    clean_id = str(int(float(entry.id_orden)))
                except:
                    clean_id = str(entry.id_orden)

                existing = virtual_overrides.get(clean_id)
                if existing is None:
                    # Primera entrada para este ID: aceptar directamente
                    virtual_overrides[clean_id] = ov_data
                else:
                    # Merge inteligente: nuevo registro (PK mayor) gana en maquina y prioridad.
                    # Preservar tiempo_manual, nivel_manual, etc. del registro que los tenga.
                    new_maq = str(ov_data.get('maquina') or '').strip()
                    if new_maq:
                        existing['maquina'] = new_maq  # Maquina mas reciente gana
                    for field in ('tiempo_manual', 'nivel_manual', 'porcentaje_solapamiento',
                                  'modo_solapamiento', 'cantidad_producida_manual',
                                  'manual_start', 'orden_secuencia'):
                        if ov_data.get(field) is not None:
                            existing[field] = ov_data[field]
                    existing['prioridad'] = ov_data['prioridad']


    tasks_moved_in_map = {}
    for oid, override_data in virtual_overrides.items():
        mid = str(override_data['maquina']).strip()
        if mid not in tasks_moved_in_map:
             tasks_moved_in_map[mid] = []
        tasks_moved_in_map[mid].append(oid)
    
    # --- FILTER HIDDEN TASKS FOR THIS SCENARIO ---
    hidden_ids = []
    if plan_mode != 'original':
         # Fetch only tasks hidden in the current scenario
         hidden_qs = HiddenTask.objects.using('default').filter(scenario=active_scenario).values_list('id_orden', flat=True)
         # Convert to set of strings for robust comparison with task IDs
         hidden_ids = set(str(int(float(h))) for h in hidden_qs)
    else:
         hidden_ids = set()

    # EXECUTION CHECK: Default to True to allow automatic loading from Global Navbar
    run_calculation = True 
    
    # --- AUTOMATIC DEPENDENCIES & SELECTIVE PLANNING ---
    from .models import PlannedTask
    deps_filter = {}

    # 1. Obtenemos el escenario válido (Ya lo tenemos en active_scenario)
    
    # 2. Extraemos la lista de proyectos vinculados a este escenario
    # (active_scenario.proyectos guarda los proyectos separados por comas)
    if active_scenario and active_scenario.proyectos:
        lista_proyectos = [p.strip() for p in active_scenario.proyectos.split(',') if p.strip()]
    else:
        lista_proyectos = []
        
    print(f"Proyectos encontrados: {lista_proyectos}")
    
    if lista_proyectos:
         deps_filter['proyectos'] = lista_proyectos
    if id_orden:
         deps_filter['id_orden'] = id_orden

    # Filtro Estricto: Solo incluir OPs que estén en PlannedTask para el escenario activo
    if plan_mode != 'original' and active_scenario:
         from .models import PlannedTask
         planned_ids = list(PlannedTask.objects.using('default').filter(
             scenario=active_scenario
         ).values_list('id_orden', flat=True))
         deps_filter['id_orden_in'] = planned_ids

    # Match spreadsheet logic: in manual/scenario mode, we often want to see 
    # what we planned even if the ERP thinks it is completed (e.g. for audits or manual overrides)
    show_completed = (plan_mode != 'original')
    
    # --- 1. ENTRANCE VALIDATION ---
    has_selection = bool(lista_proyectos or id_orden)
    
    if not has_selection and not force_run:
        print("DEBUG: [Validation] No projects or tasks selected. Aborting planning execution.")
        return {
            'timeline_data': [{'machine': m, 'tasks': [], 'maintenances': []} for m in maquinas],
            'time_columns': [],
            'valid_dates': [],
            'start_simulation': start_simulation,
            'dependency_map': {},
            'global_min_h': 7,
            'global_max_h': 22,
            'gantt_empty_reason': 'no_selection',
            'system_alerts': [{'type': 'info', 'message': 'Seleccione proyectos para iniciar la planificación.'}]
        }

    # 3. Traemos las tareas cuyos proyectos estén en esa lista activa
    # (El servicio get_planificacion_data usa __in internamente para procesar deps_filter['proyectos'])
    all_tasks_raw = get_planificacion_data(deps_filter, exclude_completed=not show_completed)
    
    print(f"Cantidad de tareas a graficar: {len(all_tasks_raw)}")
    
    # --- 3. ORPHAN FILTER (OpenCode Fix) ---
    # User requested: "solo intente graficar procesos que tengan un Proyecto y una Máquina válidos asignados."
    def is_valid_task(t):
        p_code = t.get('ProyectoCode')
        m_name = t.get('MAQUINAD')
        
        # FIX: Check if task has a manual override (virtual move to a machine)
        clean_id = ''
        try:
            clean_id = str(int(float(t.get('Idorden') or 0)))
        except:
            clean_id = str(t.get('Idorden', ''))
            
        if clean_id in virtual_overrides and virtual_overrides[clean_id].get('maquina'):
            m_name = virtual_overrides[clean_id]['maquina']
            
        # We exclude tasks without project or without machine name
        if not p_code or not m_name:
            return False
        # Also exclude tasks with 0 duration as they cause "ghost" rendering
        if float(t.get('Tiempo_Proceso', 0) or 0) <= 0.001:
            return False
        return True

    original_count = len(all_tasks_raw)
    all_tasks_raw = [t for t in all_tasks_raw if is_valid_task(t)]
    if len(all_tasks_raw) < original_count:
        print(f"DEBUG: [Orphans] Filtered {original_count - len(all_tasks_raw)} tasks with invalid project/machine or zero duration.")

    # --- Recovery: tareas con override de maquina que no llegaron al motor ---
    # REGLA CLAVE: si el usuario asigno una maquina manualmente Y definio tiempo_manual,
    # la OP DEBE aparecer en el Gantt aunque el ERP la marque COMPLETA o Tiempo_Proceso=0.
    if virtual_overrides:
        existing_ids = {str(int(float(t.get('Idorden')))) for t in all_tasks_raw if t.get('Idorden')} \
            if all_tasks_raw else set()

        # Separar IDs faltantes segun si tienen tiempo_manual o no
        missing_with_tiempo = []
        missing_without_tiempo = []
        for oid in virtual_overrides.keys():
            if oid not in existing_ids:
                ov = virtual_overrides[oid]
                if ov.get('maquina') and ov.get('tiempo_manual') is not None:
                    missing_with_tiempo.append(oid)
                elif ov.get('maquina'):
                    missing_without_tiempo.append(oid)

        # OPs con tiempo_manual: recuperar SIEMPRE ignorando estado del ERP
        if missing_with_tiempo:
            extra_filtros = {'id_orden_in': missing_with_tiempo}
            extra_tasks = get_planificacion_data(extra_filtros, exclude_completed=False)

            recovered_ids = set()
            if extra_tasks:
                all_tasks_raw.extend(extra_tasks)
                for et in extra_tasks:
                    try:
                        recovered_ids.add(str(int(float(et.get('Idorden')))))
                    except:
                        pass
                print(f"DEBUG: [Recovery/tiempo_manual] Loaded {len(extra_tasks)} task(s) from ERP: {missing_with_tiempo}")

            # Phantom IDs (no en ERP) -> crear tarea sintetica desde el override
            phantom_ids = [oid for oid in missing_with_tiempo if oid not in recovered_ids]
            if phantom_ids:
                print(f"DEBUG: [Recovery/phantom] Creating {len(phantom_ids)} synthetic task(s) for phantom IDs: {phantom_ids}")

                # Mapa ID->nombre de maquina (maquinas disponible aqui)
                _maq_id_map = {m.id_maquina.strip(): m.nombre.strip() for m in maquinas}

                # Prioridad de proyectos para inyectar en el sort
                from .models import ProyectoPrioridad as _PP
                _proj_prio_cache = {}
                if active_scenario:
                    for pp in _PP.objects.using('default').filter(scenario=active_scenario).values('proyecto', 'prioridad'):
                        _proj_prio_cache[str(pp['proyecto']).strip()] = pp['prioridad']

                for oid in phantom_ids:
                    ov = virtual_overrides[oid]
                    maq_id = str(ov.get('maquina', '')).strip()
                    maq_name = _maq_id_map.get(maq_id, maq_id)
                    proj_code = getattr(active_scenario, 'proyectos', '').split(',')[0].strip() if active_scenario else ''
                    proj_prio_val = _proj_prio_cache.get(proj_code, 1)
                    nivel_man = ov.get('nivel_manual')
                    pieza_prio_val = int(float(nivel_man)) if nivel_man is not None else 1
                    nivel_plan = int(float(nivel_man)) if nivel_man is not None else 0
                    orden_visual = float(ov.get('prioridad', 1.0))
                    orden_secuencia = float(ov.get('orden_secuencia') or 999999)

                    synthetic = {
                        'Idorden': int(oid),
                        'Idmaquina': maq_id,
                        'MAQUINAD': maq_name,
                        'MAQUINA_ID': maq_id,
                        'ProyectoCode': proj_code,
                        'Mstnmbr': oid,
                        'Articulo': f'OP-{oid}',
                        'Descri': f'OP Manual {oid}',
                        'Tiempo_Proceso': float(ov['tiempo_manual']),
                        'Tiempo_Proceso_original': float(ov['tiempo_manual']),
                        'Tiempo': float(ov['tiempo_manual']),
                        'cantidad_final': 1,
                        'cantidad_producida': 0,
                        'cantidad_pendiente': 1,
                        'Cantidadpp': 0,
                        'Cantidad': 1,
                        'Estadod': 'MANUAL',
                        'is_synthetic': True,
                        # Campos criticos para el sort (pre-inyectados)
                        'prioridad_proyecto': proj_prio_val,
                        'prioridad_pieza':    pieza_prio_val,
                        'prioridad':          pieza_prio_val,
                        'Nivel_Planificacion': nivel_plan,
                        'nivel_planificacion': nivel_plan,
                        'OrdenVisual':    orden_visual,
                        'OrdenSecuencia': orden_secuencia,
                        'secuencia_proceso': 1,
                    }
                    all_tasks_raw.append(synthetic)

        # OPs sin tiempo_manual pero con maquina: modo normal
        if missing_without_tiempo:
            extra_filtros2 = {'id_orden_in': missing_without_tiempo}
            extra_tasks2 = get_planificacion_data(extra_filtros2, exclude_completed=not show_completed)
            if extra_tasks2:
                all_tasks_raw.extend(extra_tasks2)
                print(f"DEBUG: [Recovery/maquina] Loaded {len(extra_tasks2)} task(s) with machine-only override: {missing_without_tiempo}")

    # Include all tasks for dependencies and simulation, including unassigned ones (MAC00)
    all_tasks_for_deps = all_tasks_raw

    # 1. Obtener prioridades de proyectos para el escenario activo
    from .models import ProyectoPrioridad
    proj_priorities = {}
    active_projects = set(t.get('ProyectoCode') for t in all_tasks_raw if t.get('ProyectoCode'))
    
    db_priorities = []
    if active_scenario and active_projects:
        db_priorities = list(ProyectoPrioridad.objects.using('default').filter(
            scenario=active_scenario,
            proyecto__in=active_projects
        ).order_by('prioridad'))
        
    db_proj_names = {pp.proyecto for pp in db_priorities}
    
    # Proyectos que no tienen prioridad en BD
    missing_priorities = []
    for proj in sorted(active_projects):
        if proj not in db_proj_names:
            class DummyPP:
                def __init__(self, proyecto, prioridad):
                    self.proyecto = proyecto
                    self.prioridad = prioridad
            missing_priorities.append(DummyPP(proj, 999))
            
    all_sorted_projects = db_priorities + missing_priorities
    # Ordenamos todos de forma ascendente (1 es primero, 2 segundo, etc.)
    all_sorted_projects.sort(key=lambda x: x.prioridad)
    
    print("--- MOTOR: INICIO ORDENAMIENTO DE PROYECTOS ---")
    for p in all_sorted_projects:
        print(f"MOTOR: Orden de planificación seleccionado -> PROYECTO: {p.proyecto} | PRIORIDAD: {p.prioridad}")
        proj_priorities[p.proyecto] = p.prioridad
    
    # Pre-group tasks by machine for internal loop efficiency
    all_tasks_by_machine = defaultdict(list)
    name_to_id = {m.nombre.strip(): m.id_maquina.strip() for m in maquinas}

    for t in all_tasks_for_deps:
        # Normalizar ID de orden en el objeto para consistencia global
        try:
             t_id_raw = t.get('Idorden')
             if t_id_raw:
                 # Pasamos por float primero por si viene como "47621.0" desde SQL
                 t['Idorden'] = int(float(t_id_raw))
        except:
             pass

        t_id_str = str(t.get('Idorden'))
        mid_code = None
        if t_id_str in virtual_overrides and virtual_overrides[t_id_str].get('maquina'):
            mid_code = str(virtual_overrides[t_id_str]['maquina']).strip()
        else:
            mid_code = str(t.get('Idmaquina', '')).strip()

        if mid_code in name_to_id:
            mid_code = name_to_id[mid_code]
        all_tasks_by_machine[mid_code].append(t)
        
    # Fetch Holidays once
    from .models import Feriado
    all_feriados = Feriado.objects.using('default').filter(activo=True)
    non_working_days = set(f.fecha for f in all_feriados if f.tipo_jornada == 'NO')
    half_day_holidays = set(f.fecha for f in all_feriados if f.tipo_jornada == 'MEDIO')

    # Detect Completed Projects
    system_alerts = []
    if raw_proyectos:
        requested_list = [p.strip() for p in raw_proyectos.split(',') if p.strip()]
        found_active_projects = set(t.get('ProyectoCode') for t in all_tasks_raw)
        
        missing_projects = [req for req in requested_list if req not in found_active_projects]
        if missing_projects:
            raw_checks = get_planificacion_data({'proyectos': missing_projects}, exclude_completed=False)
            
            proj_status = {}
            for rc in raw_checks:
                p_code = rc.get('ProyectoCode')
                if p_code and p_code not in proj_status:
                    proj_status[p_code] = rc.get('Estadod', 'DESCONOCIDO')
            
            for req in missing_projects:
                if req in proj_status:
                    status = proj_status[req]
                    system_alerts.append({
                        'type': 'warning',
                        'message': f"El proyecto <strong>{req}</strong> ya se terminó y está <strong>{status}</strong>. No se incluirá en la planificación."
                    })

    # Group by ProyectoCode
    orders_map = defaultdict(list)
    for task in all_tasks_for_deps:
        formula = task.get('ProyectoCode')
        if formula:
            orders_map[formula].append(task)

    dependency_map = {}

    def get_nivel(t):
        keys_to_check = ['Nivel_Planificacion', 'nivel_planificacion', 'nivel_manual', 'Nivel']
        for key in keys_to_check:
            val = None
            if isinstance(t, dict):
                val = t.get(key)
            else:
                val = getattr(t, key, None)
                
            if val is not None:
                try:
                    f_val = float(val)
                    if f_val != 0:
                        return f_val
                except (ValueError, TypeError):
                    pass
        return 0.0

    def get_op_num(t):
        try:
            return int(float(t.get('Idorden') or 9999999))
        except (ValueError, TypeError):
            return 9999999

    # --- DEPENDENCIES ---
    dependency_map = {}

    # 1. AUTO-DEPENDENCIAS POR NIVEL (Mismo Proyecto)
    # Regla: Nivel N depende de N+1 (Jerarquía de ensamble)
    for formula, p_tasks in orders_map.items():
        by_level = defaultdict(list)
        for t in p_tasks:
            lvl = int(get_nivel(t))
            by_level[lvl].append(str(t['Idorden']))
        
        sorted_lvls = sorted(by_level.keys(), reverse=True) 
        for i in range(len(sorted_lvls)-1):
            upper_lvl = sorted_lvls[i]
            lower_lvl = sorted_lvls[i+1]
            # Si son niveles correlativos, creamos el vínculo
            if upper_lvl == lower_lvl + 1:
                for succ in by_level[lower_lvl]:
                    if succ not in dependency_map: dependency_map[succ] = []
                    for pred in by_level[upper_lvl]:
                        if pred not in dependency_map[succ]:
                            dependency_map[succ].append(pred)

    # 2. DEPENDENCIAS MANUALES (Sobrescriben o complementan)
    def clean_id(val):
        try: return str(int(float(val)))
        except: return str(val)

    from .models import TaskDependency
    db_deps = TaskDependency.objects.all()
    for dep in db_deps:
        s_succ = clean_id(dep.successor_id)
        s_pred = clean_id(dep.predecessor_id)
        if s_succ not in dependency_map: dependency_map[s_succ] = []
        if s_pred not in dependency_map[s_succ]: dependency_map[s_succ].append(s_pred)

    # BYPASS TEMPORAL (Aislado en memoria):
    # Ignorar predecesores que correspondan a tareas SIN ASIGNAR o MAC00 (como la 45354)
    unassigned_ids = {
        str(t.get('Idorden')) for t in all_tasks_raw 
        if str(t.get('Idmaquina', '')).strip() == '' or str(t.get('MAQUINAD', '')).strip().upper() == 'SIN ASIGNAR' or str(t.get('Idmaquina', '')).strip().upper() == 'MAC00'
    }
    for succ_id in list(dependency_map.keys()):
        dependency_map[succ_id] = [p for p in dependency_map[succ_id] if p not in unassigned_ids]

    global_task_end_dates = {}
    unassigned_tasks = [
        t for t in all_tasks_raw 
        if str(t.get('Idmaquina', '')).strip() == '' or str(t.get('MAQUINAD', '')).strip().upper() == 'SIN ASIGNAR'
    ]

    for ut in sorted(unassigned_tasks, key=get_nivel, reverse=True):
        tid = str(ut.get('Idorden'))
        duration = float(ut.get('Tiempo_Proceso', 0) or 0)
        if duration <= 0: continue
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


    # --- SIMULATION ---
    machine_tasks_map = {}
    tasks_moved_in_map = defaultdict(list)
    for tid, override in virtual_overrides.items():
        if override.get('maquina'):
            tasks_moved_in_map[str(override['maquina']).strip().upper()].append(tid)
            
    # Deduplicate maquinas list - EXCLUIR SIN ASIGNAR/MAC00
    unique_maquinas_list = []
    seen_machine_ids = set()
    for m in maquinas:
        m_id = str(m.id_maquina).strip().upper()
        # EXCLUIR MAC00 y SIN ASIGNAR
        if m_id in ['MAC00', 'SIN ASIGNAR'] or 'SIN ASIGNAR' in str(m.nombre).upper():
            continue
        if m_id not in seen_machine_ids:
            unique_maquinas_list.append(m)
            seen_machine_ids.add(m_id)
    maquinas = unique_maquinas_list

    for maquina in maquinas:
        machine_id = str(maquina.id_maquina).strip()
        current_machine_name = str(maquina.nombre).strip().upper()
        
        if machine_id == 'MAC06':
            print(f"DEBUG: Processing Machine {current_machine_name} (ID: {machine_id})")

        if machine_id == 'MAC00' or 'SIN ASIGNAR' in current_machine_name:
            native_tasks = [t for t in all_tasks_for_deps if str(t.get('Idmaquina', '')).strip() in ['', 'MAC00'] or str(t.get('MAQUINAD', '')).strip().upper() == 'SIN ASIGNAR']
        else:
            native_tasks = all_tasks_by_machine.get(machine_id, [])
            if not native_tasks and current_machine_name in all_tasks_by_machine:
                native_tasks = all_tasks_by_machine[current_machine_name]
            
            if machine_id == 'MAC06':
                print(f"DEBUG: MAC06 native_tasks count: {len(native_tasks)}")
        
        active_tasks = []
        for t in native_tasks:
            # FILTRO CRÍTICO: Si el tiempo es despreciable o cero, ignorar
            tp = float(t.get('Tiempo_Proceso', 0) or 0)
            if machine_id == 'MAC06':
                print(f"DEBUG: MAC06 task {t.get('Idorden')} Tiempo_Proceso: {tp}")
            
            if tp <= 0.01:
                continue

            try:
                oid = str(int(float(t.get('Idorden'))))
            except:
                oid = str(t.get('Idorden'))

            if oid in virtual_overrides:
                ov_mid = str(virtual_overrides[oid]['maquina']).strip().upper()
                # Filtradio ESTRICTO: Solo si la maquina del override coincide con la actual
                if ov_mid in [machine_id.upper(), current_machine_name.upper()]:
                    if oid not in hidden_ids: active_tasks.append(t)
                else:
                    # EXCLUSION: Si tiene override para OTRA maquina, se ignora en esta (Native machine)
                    pass
            else:
                 if oid not in hidden_ids: active_tasks.append(t)
                 
        moved_in_ids = []
        if machine_id.upper() in tasks_moved_in_map: 
             moved_in_ids.extend(tasks_moved_in_map[machine_id.upper()])
        if current_machine_name.upper() in tasks_moved_in_map:
             for i in tasks_moved_in_map[current_machine_name.upper()]:
                 if i not in moved_in_ids: moved_in_ids.append(i)
        
        if moved_in_ids:
            for t_id in moved_in_ids:
                # Search in all_tasks_raw so we find tasks from any machine
                try:
                    tid_s = str(int(float(t_id)))
                except:
                    tid_s = str(t_id)

                task_found = next((tx for tx in all_tasks_raw if str(int(float(tx['Idorden']))) == tid_s), None)
                if task_found and str(int(float(task_found['Idorden']))) not in hidden_ids:
                    # FILTRO CRÍTICO para tareas movidas
                    if float(task_found.get('Tiempo_Proceso', 0) or 0) <= 0.01:
                        continue

                    # IMPORTANT: copy the dict to avoid mutating the original object
                    task_copy = dict(task_found)
                    task_copy['is_moved'] = True
                    task_copy['original_machine_name'] = task_found.get('MAQUINAD', 'S/M')
                    active_tasks.append(task_copy)
        
        unique_tasks_map = {}
        for t in active_tasks:
            try:
                tid = str(int(float(t.get('Idorden'))))
            except:
                tid = str(t.get('Idorden'))
            if tid not in unique_tasks_map: unique_tasks_map[tid] = t
        tasks = list(unique_tasks_map.values())
        
        force_start_times_pass1 = {}
        for idx, item in enumerate(tasks):
             p_id = str(item['Idorden'])
             
             # control print
             assigned_machine = item.get('MAQUINAD')
             if p_id in virtual_overrides:
                 assigned_machine = virtual_overrides[p_id].get('maquina')
             print(f"--- MOTOR GANTT: Procesando OP {p_id}. Máquina asignada en modelo: {assigned_machine} ---")
             
             if p_id in virtual_overrides:
                 ov = virtual_overrides[p_id]
                 item['OrdenVisual'] = float(ov['prioridad'])
                 item['OrdenSecuencia'] = float(ov.get('orden_secuencia', 999999))
                 if ov.get('tiempo_manual') is not None: item['Tiempo_Proceso'] = float(ov['tiempo_manual'])
                 # Ahora SÍ respetamos el nivel_manual si el usuario lo forzó en pantalla
                 if ov.get('nivel_manual') is not None and float(ov['nivel_manual']) != 0:
                     item['nivel_planificacion'] = float(ov['nivel_manual'])
                 if ov.get('manual_start'):
                     force_start_times_pass1[p_id] = ov['manual_start']
                     item['is_pinned'] = True
             else:
                 item['OrdenVisual'] = (idx + 1) * 1000.0
             
             item['prioridad_pieza'] = item.get('prioridad_pieza')  # set by services.py
             item['prioridad'] = item['prioridad_pieza']  # backward compat
             # Inject project priority from the already-built proj_priorities map
             item['prioridad_proyecto'] = proj_priorities.get(item.get('ProyectoCode'), 999)
             item['Cantidad'] = item.get('cantidad_final', item.get('Cantidad_Proyecto', 0))
             
             if p_id in virtual_overrides and virtual_overrides[p_id].get('cantidad_producida_manual') is not None:
                 item['Cantidadpp'] = float(virtual_overrides[p_id]['cantidad_producida_manual'])
             else:
                 item['Cantidadpp'] = item.get('cantidad_producida', 0)
                  
        # Jerarquía estricta en Gantt:
        #   1. Prioridad Proyecto   ASC   (número menor = mayor prioridad)
        #   2. Prioridad Artículo   ASC   (número menor = mayor prioridad)
        #   3. Nivel Planificación  DESC  (número mayor = va antes, se usa negativo)
        #   4. Idorden (OP)         ASC   (desempate inteligente cuando el nivel es idéntico)
        #   + desempates de seguridad: secuencia de proceso y orden visual del usuario
        print(f"--- DEBUG ORDENAMIENTO MÁQUINA: {machine_id} ---")
        if machine_id == 'MAC26':
            for t_debug in tasks:
                if isinstance(t_debug, dict):
                    print(f"--- DUMP OP {t_debug.get('Idorden')} (DICT) ---")
                    print(t_debug.keys())
                    print(f"Valores nivel posibles: {t_debug.get('nivel_planificacion')} | {t_debug.get('Nivel_Planificacion')} | {t_debug.get('nivel_manual')} | {t_debug.get('Nivel')}")
                else:
                    print(f"--- DUMP OP {getattr(t_debug, 'Idorden', 'N/A')} (OBJETO) ---")
                    import pprint
                    pprint.pprint(t_debug.__dict__)
                    
        for task_debug in tasks:
            print(f"OP: {get_op_num(task_debug)} - Nivel Extraído: {get_nivel(task_debug)}")
            
        tasks.sort(key=lambda x: (
            int(x.get('prioridad_proyecto') if x.get('prioridad_proyecto') is not None else 999),  # 1. Proyecto Prioridad ASC
            int(x.get('prioridad_pieza')    if x.get('prioridad_pieza')    is not None else 9999), # 2. Artículo Prioridad ASC
            -int(get_nivel(x)),                                                                    # 3. Nivel Planificación DESC
            get_op_num(x),                                                                         # 4. Tie-breaker ID orden (OP) ASC
            x.get('secuencia_proceso', 999),                                                       # desempate: secuencia ERP
            x.get('OrdenSecuencia', 999999),                                                       # desempate: orden manual
            x.get('OrdenVisual', 999999)                                                           # desempate: arrastre visual
        ))
        machine_tasks_map[machine_id] = {'maquina': maquina, 'tasks': tasks}
        
        calculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, 
                                            task_min_start_times=None, task_force_start_times=force_start_times_pass1,
                                            non_working_days=non_working_days, half_day_holidays=half_day_holidays)
        
        for ct in calculated_tasks:
             tid = str(ct.get('Idorden'))
             cend = ct.get('end_date')
             if tid and cend:
                 if tid not in global_task_end_dates or (cend.tzinfo and global_task_end_dates[tid].tzinfo and cend > global_task_end_dates[tid]) or (not cend.tzinfo and not global_task_end_dates[tid].tzinfo and cend > global_task_end_dates[tid]):
                     global_task_end_dates[tid] = cend

    # SECOND PASS (Multi-Pass with Overlap Calculation)
    from .overlap_calculator import calcular_inicio_optimo_sucesor
    final_timeline_map = {}
    for pass_idx in range(5):
        task_info_map = {} 
        sorted_machine_items = sorted(machine_tasks_map.items(), key=lambda x: x[0])
        for machine_id, machine_data in sorted_machine_items:
            maquina = machine_data['maquina']
            tasks = machine_data['tasks']
            min_start_times = {}
            force_start_times = {}
            
            # Build set of task IDs on THIS machine to skip same-machine predecessors.
            # Same-machine chaining is handled by current_time propagation in calculate_timeline.
            # Using stale global_task_end_dates for same-machine preds creates artificial gaps.
            current_machine_task_ids = {str(t.get('Idorden')) for t in tasks}
            
            for t in tasks:
                t_id = str(t.get('Idorden'))
                if t_id in virtual_overrides and virtual_overrides[t_id].get('manual_start'):
                    force_start_times[t_id] = virtual_overrides[t_id]['manual_start']

                if t_id in dependency_map:
                    preds = dependency_map[t_id]
                    ov = virtual_overrides.get(t_id, {})
                    modo_solap = ov.get('modo_solapamiento', 'automatico')
                    overlap_pct = ov.get('porcentaje_solapamiento', 0.0)
                    
                    # Check if rigid relation (A -> B -> C where C needs the material ready of B)
                    is_rigid = any(t_id in succ_preds for succ_preds in dependency_map.values())
                    
                    if is_rigid:
                        # Rule A: rigid relation, no overlap allowed
                        max_e = None
                        for pid in preds:
                            if pid in task_info_map:
                                pinfo = task_info_map[pid]
                                if max_e is None or pinfo['end_date'] > max_e:
                                    max_e = pinfo['end_date']
                            elif pid in global_task_end_dates:
                                if max_e is None or global_task_end_dates[pid] > max_e:
                                    max_e = global_task_end_dates[pid]
                        if max_e:
                            min_start_times[t_id] = max_e
                    elif modo_solap == 'automatico':
                        # Rule B: balance by speed
                        calculated_start_times = []
                        for pid in preds:
                            if pid in task_info_map:
                                pinfo = task_info_map[pid]
                                tasa_pred = pinfo['duration'] / pinfo['cantidad'] if pinfo['cantidad'] > 0 else 0
                                t_duration = float(t.get('Tiempo_Proceso', 0) or 0)
                                t_qty = float(t.get('Cantidad', 1) or 1)
                                tasa_succ = t_duration / t_qty if t_qty > 0 else 0
                                
                                if tasa_pred > tasa_succ:
                                    # Proceso A más lento que B
                                    opt_start = pinfo['end_date'] - timedelta(hours=t_duration)
                                    if opt_start < pinfo['start_date']:
                                        opt_start = pinfo['start_date']
                                    calculated_start_times.append(opt_start)
                                else:
                                    # Proceso A más rápido que B
                                    opt_start = pinfo['start_date'] + timedelta(hours=tasa_pred)
                                    calculated_start_times.append(opt_start)
                            elif pid in global_task_end_dates:
                                calculated_start_times.append(global_task_end_dates[pid])
                        if calculated_start_times:
                            min_start_times[t_id] = max(calculated_start_times)
                    else:  # manual
                        if overlap_pct > 0 and pass_idx > 0:
                            calculated_start_times = []
                            for pid in preds:
                                if pid in task_info_map:
                                    pinfo = task_info_map[pid]
                                    try:
                                        opt, _ = calcular_inicio_optimo_sucesor(
                                            pinfo['start_date'], pinfo['duration'], pinfo['cantidad'],
                                            t.get('Tiempo_Proceso', 0), t.get('Cantidad', 1), overlap_pct
                                        )
                                        calculated_start_times.append(opt if opt > pinfo['start_date'] else pinfo['end_date'])
                                    except: calculated_start_times.append(pinfo['end_date'])
                            if calculated_start_times: min_start_times[t_id] = max(calculated_start_times)
                        else:
                            max_e = None
                            for pid in preds:
                                if pid in global_task_end_dates:
                                    if max_e is None or global_task_end_dates[pid] > max_e: max_e = global_task_end_dates[pid]
                            if max_e: min_start_times[t_id] = max_e

            def get_sort_key(t):
                 tid = str(t.get('Idorden'))
                 ms = min_start_times.get(tid, start_simulation)
                 
                 # Si está pineada, su "tiempo objetivo" es el pin
                 # Si no, es su tiempo de disponibilidad (dependencia)
                 target_start = ms
                 is_pinned = 0
                 if tid in force_start_times:
                     target_start = force_start_times[tid]
                     is_pinned = 1
                 
                 # PRIORIDAD ABSOLUTA e INVIOLABLE — jerarquía en cascada:
                 #   1. Prioridad Proyecto  ASC  → menor número = mayor prioridad.
                 #   2. Prioridad Artículo  ASC  → dentro del proyecto, piezas con menor número primero.
                 #   3. Nivel Planificación DESC → mayor nivel va antes (se usa negativo).
                 #   4. OrdenVisual ASC           → desempate: respeta arrastre manual del usuario.
                 #   5. target_start ASC          → desempate final por disponibilidad (dependencias).
                 proj_code = t.get('ProyectoCode') or ''
                 proj_prio = proj_priorities.get(proj_code, 999)
                 pieza_prio = int(t.get('prioridad_pieza') if t.get('prioridad_pieza') is not None else 9999)
                 return (proj_prio, pieza_prio, -int(get_nivel(t)), get_op_num(t), t.get('OrdenVisual', 999999), target_start)
            
            tasks.sort(key=get_sort_key)
            recalc = calculate_timeline(maquina, tasks, start_date=start_simulation, 
                                      task_min_start_times=min_start_times, task_force_start_times=force_start_times,
                                      non_working_days=non_working_days, half_day_holidays=half_day_holidays)
            
            if machine_id == 'MAC06' and pass_idx == 4:
                 print(f"DEBUG: Final pass for MAC06: {len(recalc)} segments calculated.")

            final_timeline_map[machine_id] = {'machine': maquina, 'tasks': recalc}
            for ct in recalc:
                 tid = str(ct.get('Idorden'))
                 
                 # Inject modo_solapamiento and porcentaje_solapamiento into the calculated tasks for UI
                 ov = virtual_overrides.get(tid, {})
                 modo_solap = ov.get('modo_solapamiento', 'automatico')
                 ct['modo_solapamiento'] = modo_solap
                 
                 if modo_solap == 'automatico':
                     preds = dependency_map.get(tid, [])
                     is_rigid = any(tid in succ_preds for succ_preds in dependency_map.values())
                     if is_rigid:
                         ct['porcentaje_solapamiento'] = 0.0
                     elif preds:
                         calculated_p_pcts = []
                         for pid in preds:
                             if pid in task_info_map:
                                 try:
                                     pinfo = task_info_map[pid]
                                     p_dur = float(pinfo.get('duration', 0) or 0)
                                     if p_dur > 0 and pinfo.get('end_date') and ct.get('start_date'):
                                         overlap_h = (pinfo['end_date'] - ct['start_date']).total_seconds() / 3600.0
                                         if overlap_h > 0:
                                             calculated_p_pcts.append(round(min(100.0, (overlap_h / p_dur) * 100.0), 1))
                                 except Exception as e:
                                     print(f"Error calculating automatic overlap percent: {e}")
                         if calculated_p_pcts:
                             ct['porcentaje_solapamiento'] = max(calculated_p_pcts)
                         else:
                             ct['porcentaje_solapamiento'] = 0.0
                     else:
                         ct['porcentaje_solapamiento'] = 0.0
                 else:
                     ct['porcentaje_solapamiento'] = ov.get('porcentaje_solapamiento', 0.0)

                 if tid not in task_info_map:
                     task_info_map[tid] = {'start_date': ct.get('start_date'), 'end_date': ct.get('end_date'), 'duration': float(ct.get('Tiempo_Proceso', 0) or 0), 'cantidad': float(ct.get('Cantidad', 1) or 1)}
                 else:
                     task_info_map[tid]['end_date'] = ct['end_date']
                 global_task_end_dates[tid] = ct['end_date']

    from .planning_service import get_active_maintenances
    for mid in machine_tasks_map.keys():
        if mid in final_timeline_map:
            row = final_timeline_map[mid]
            m = row['machine']
            row['maintenances'] = get_active_maintenances(m) if hasattr(m, 'id_maquina') and m.id_maquina != 'MAC00' else []
            timeline_data.append(row)

    # --- CRITICAL PATH ---
    project_tasks_final = defaultdict(list)
    for row in timeline_data:
        for t in row['tasks']:
            t['is_critical'] = False
            p = t.get('ProyectoCode')
            if p: project_tasks_final[p].append(t)
    
    for pcode, p_tasks in project_tasks_final.items():
        vts = [t for t in p_tasks if t.get('end_date')]
        if not vts: continue
        
        critical_ids = set()
        curr = max(vts, key=lambda x: x['end_date'])
        tlookup = {str(t['Idorden']): t for t in vts}
        
        while curr:
            cid = str(curr['Idorden'])
            critical_ids.add(cid)
            latest_p = None
            max_p_e = None
            for pid in dependency_map.get(cid, []):
                if pid in tlookup:
                    pe = tlookup[pid]['end_date']
                    if max_p_e is None or pe > max_p_e:
                        max_p_e = pe; latest_p = tlookup[pid]
            if latest_p == curr: break
            curr = latest_p
            
        for t in vts:
            if str(t['Idorden']) in critical_ids:
                t['is_critical'] = True

    # --- GRID & COLUMNS ---
    g_min_h, g_max_h = 24, 0
    has_sch = False
    for row in timeline_data:
        m = row['machine']
        if hasattr(m, 'horarios'):
            for h in m.horarios.all():
                has_sch = True
                g_min_h = min(g_min_h, h.hora_inicio.hour)
                g_max_h = max(g_max_h, h.hora_fin.hour)
        if m.id_maquina != 'MAC00':
            for t in row['tasks']:
                s, e = t.get('start_date'), t.get('end_date')
                if s: g_min_h = min(g_min_h, s.hour); g_max_h = max(g_max_h, s.hour + 1)
                if e: g_max_h = max(g_max_h, e.hour + (1 if e.minute > 0 else 0))
    
    if not has_sch: g_min_h, g_max_h = 7, 18
    
    # Force grid to 22:00 if MAC00 has tasks (Strict Grid)
    for row in timeline_data:
        m = row['machine']
        if (m.id_maquina == 'MAC00' or 'SIN ASIGNAR' in str(m.nombre).upper()) and row['tasks']:
            g_max_h = max(g_max_h, 22)
            g_min_h = min(g_min_h, 7)

    if g_max_h <= g_min_h: g_min_h, g_max_h = 0, 23
    
    calc_max = start_simulation + timedelta(hours=48)
    for row in timeline_data:
        if row['machine'].id_maquina == 'MAC00': continue
        for t in row['tasks']:
            if t['end_date'] and t['end_date'] > calc_max: calc_max = t['end_date']
    
    if calc_max > start_simulation + timedelta(days=30): calc_max = start_simulation + timedelta(days=30)

    show_sa = any(h.dia == 'SA' for row in timeline_data if hasattr(row['machine'], 'horarios') for h in row['machine'].horarios.all())
    task_dates = set(t['start_date'].date() for row in timeline_data for t in row['tasks'] if t.get('start_date'))
    
    valid_dates = []
    p = start_simulation.date()
    for d in range(min((calc_max.date() - p).days + 5, 45)):
        curr = p + timedelta(days=d)
        if curr in task_dates or (0 <= curr.weekday() <= 4) or (curr.weekday() == 5 and show_sa):
            valid_dates.append(curr)

    day_max_hours = {}
    for d in valid_dates:
        day_max_hours[d] = g_max_h
        dtyp = 'LV' if 0 <= d.weekday() <= 4 else ('SA' if d.weekday() == 5 else None)
        if dtyp:
            mh = None
            for row in timeline_data:
                if hasattr(row['machine'], 'horarios'):
                    for h in row['machine'].horarios.all():
                        if h.dia == dtyp: mh = max(mh or 0, h.hora_fin.hour)
            if mh: day_max_hours[d] = mh

    time_columns, date_start_col, offset = [], {}, 0
    for d in valid_dates:
        mx = day_max_hours[d]
        date_start_col[d], offset = offset, offset + (mx - g_min_h)
        for h in range(g_min_h, mx):
            time_columns.append(datetime.combine(d, datetime.min.time()) + timedelta(hours=h))

    # --- ANALYSIS ---
    machine_analysis = []
    for row in timeline_data:
        m, ts = row['machine'], row['tasks']
        av = get_machine_capacity(m, start_simulation, start_simulation + timedelta(days=7), non_working_days, half_day_holidays)
        th = sum(t.get('duration_real', 0) for t in ts if t.get('start_date') and t['start_date'] < start_simulation + timedelta(days=7))
        machine_analysis.append({
            'id': m.id_maquina, 'nombre': m.nombre, 'load_pct': round((th/av*100) if av > 0 else 0, 1),
            'hours': round(th, 1), 'capacity': round(av, 1),
            'tasks': [{
                'id_orden': t['Idorden'],
                'proyecto': t.get('ProyectoCode', 'S/P'),
                'pieza': t.get('Articulo', '-'),
                'proceso': t.get('Denominacion', '-'),
                'nivel': t.get('Nivel_Planificacion', '-'),
                'tiempo': round(t.get('duration_real', 0), 2),
                'start': t['start_date'].strftime('%d/%m %H:%M') if t.get('start_date') else '',
                'end': t['end_date'].strftime('%d/%m %H:%M') if t.get('end_date') else ''
            } for t in ts if t.get('start_date') and t['start_date'] < start_simulation + timedelta(days=7)]
        })

    global_p_vtos = {}
    for t in all_tasks_for_deps:
        pc, vto = t.get('ProyectoCode', 'S/P'), t.get('Vto_Proyecto') or t.get('Vto')
        if vto and (pc not in global_p_vtos or vto > global_p_vtos[pc]): global_p_vtos[pc] = vto

    project_alerts = []
    proj_tasks_map = defaultdict(list)
    for row in timeline_data:
        for t in row['tasks']:
            pc = t.get('ProyectoCode', 'S/P')
            proj_tasks_map[pc].append(t)

    # --- PROJECT PROGRESS CALCULATION (By Time/Hours) ---
    project_time_stats = {}
    project_audit = {}  # Auditing transparency
    
    if all_tasks_raw:
        for t in all_tasks_raw:
            pc = t.get('ProyectoCode', 'S/D')
            if not pc: continue
            
            if pc not in project_time_stats:
                project_time_stats[pc] = {'total': 0.0, 'done': 0.0}
                project_audit[pc] = []
            
            t_unitary = float(t.get('Tiempo', 0.0) or 0.0)
            qty_total = float(t.get('cantidad_final', 0.0) or 0.0)
            qty_done  = float(t.get('cantidad_producida', 0.0) or 0.0)
            
            h_tot = t_unitary * qty_total
            h_done = t_unitary * qty_done
            
            project_time_stats[pc]['total'] += h_tot
            project_time_stats[pc]['done']  += h_done
            
            project_audit[pc].append({
                'Idorden': t.get('Idorden'),
                'Articulo': t.get('Articulo'),
                'Tiempo_Unitario': t_unitary,
                'Cant_Final': qty_total,
                'Cant_Hecha': qty_done,
                'Total_Horas': h_tot,
                'Hecho_Horas': h_done
            })

    # Print audit to console for transparency
    print("--- AUDIT: PROYECTO PROGRESS ---")
    for pc, ops in project_audit.items():
        total_proj = project_time_stats[pc]['total']
        print(f"PROYECTO: {pc} | Suma Total Horas: {total_proj:.4f}h ({len(ops)} OPs)")
        # for o in ops: print(f"  - OP {o['Idorden']}: {o['Total_Horas']:.4f}h")

    for pc, pts in proj_tasks_map.items():
        # 1. Delay Checking
        me, mv = max((t['end_date'] for t in pts if t.get('end_date')), default=None), global_p_vtos.get(pc)
        if me and mv and me.date() > mv.date():
            dd = (me.date() - mv.date()).days
            for t in pts: t['is_delayed'], t['delay_days'] = True, dd
            project_alerts.append({'proyecto': pc, 'max_end': me, 'vto': mv, 'delay_days': dd, 'culprits': [{'orden': t['Idorden'], 'desc': t['Descri'], 'end': t['end_date'].strftime('%d/%m')} for t in pts if t.get('end_date') and t['end_date'].date() > mv.date()][:3]})
        else:
            for t in pts: t['is_delayed'], t['delay_days'] = False, 0

        # 2. Time-based Progress
        stats = project_time_stats.get(pc, {'total': 0.0, 'done': 0.0})
        total_h = stats['total']
        done_h  = stats['done']
        pct = (done_h / total_h * 100) if total_h > 0 else 0.0
        
        for t in pts:
            t['Horas_Totales_Proyecto'] = total_h
            t['Horas_Realizadas_Proyecto'] = done_h
            t['Porcentaje_Avance_Proyecto'] = pct
            t['Project_Audit_Data'] = project_audit.get(pc, []) # Pass audit to frontend

    if active_scenario:
         active_scenario.refresh_from_db(using='default')
         print(f"Luego de procesar Gantt - Proyectos en DB: {active_scenario.proyectos}")

    return {
        'timeline_data': timeline_data, 'maquinas': maquinas, 'start_simulation': start_simulation,
        'time_columns': time_columns, 'valid_dates': valid_dates, 'dependency_map': dependency_map,
        'global_min_h': g_min_h, 'global_max_h': g_max_h, 'ran_calculation': True,
        'active_scenario': active_scenario,
        'analysis': {'machines': machine_analysis, 'project_alerts': project_alerts, 'adaptive_alerts': get_adaptive_capacity_alerts(timeline_data, maquinas)},
        'system_alerts': system_alerts, 'day_max_hours': day_max_hours, 'date_start_col': date_start_col,
        'plan_mode': plan_mode,
        'proyectos_value': raw_proyectos if raw_proyectos else '',
        'id_orden_value': id_orden if id_orden else '',
        'gantt_needs_clear': request.session.pop('gantt_needs_clear', False)
    }
