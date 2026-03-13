import os

FUNCTIONS_CODE = '''

@csrf_exempt
def create_scenario(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        data = json.loads(request.body)
        nombre = data.get('nombre')
        descripcion = data.get('descripcion', '')
        es_principal = data.get('es_principal', False)
        proyectos = data.get('proyectos', '')
        copy_from_id = data.get('copy_from_id')
        scenario_id = data.get('id')  # If editing
        
        with transaction.atomic(using='default'):
            if es_principal:
                Scenario.objects.using('default').filter(es_principal=True).update(es_principal=False)
                
            if scenario_id:
                # Update existing
                scenario = Scenario.objects.using('default').get(pk=scenario_id)
                scenario.nombre = nombre
                scenario.descripcion = descripcion
                scenario.es_principal = es_principal
                if proyectos:
                    scenario.proyectos = proyectos
                scenario.save(using='default')
                return JsonResponse({'status': 'ok', 'scenario': {'id': scenario.id, 'nombre': scenario.nombre}})
                
            else:
                # Create NEW scenario
                if not nombre:
                    return JsonResponse({'error': 'Nombre es requerido'}, status=400)
                    
                new_scenario = Scenario.objects.using('default').create(
                    nombre=nombre, descripcion=descripcion, es_principal=es_principal, proyectos=proyectos
                )
                
                # Clone overrides if requested
                if copy_from_id:
                    source = Scenario.objects.using('default').get(pk=copy_from_id)
                    overrides = PrioridadManual.objects.using('default').filter(scenario=source)
                    new_overrides = []
                    for o in overrides:
                        new_overrides.append(PrioridadManual(
                            id_orden=o.id_orden, maquina=o.maquina, prioridad=o.prioridad,
                            tiempo_manual=o.tiempo_manual, nivel_manual=o.nivel_manual,
                            porcentaje_solapamiento=o.porcentaje_solapamiento,
                            fecha_inicio_manual=o.fecha_inicio_manual, scenario=new_scenario
                        ))
                    PrioridadManual.objects.using('default').bulk_create(new_overrides)
                    
                    # Clone Prioridades de Proyecto
                    p_priorities = ProyectoPrioridad.objects.using('default').filter(scenario=source)
                    new_p_priorities = []
                    for p in p_priorities:
                        new_p_priorities.append(ProyectoPrioridad(
                            scenario=new_scenario, proyecto=p.proyecto, prioridad=p.prioridad
                        ))
                    ProyectoPrioridad.objects.using('default').bulk_create(new_p_priorities)
                
                return JsonResponse({
                    'status': 'ok',
                    'scenario': {'id': new_scenario.id, 'nombre': new_scenario.nombre}
                })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def delete_scenario(request, scenario_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        scenario = get_object_or_404(Scenario, pk=scenario_id)
        
        if scenario.es_principal:
            return JsonResponse({'error': 'No se puede eliminar el Plan Oficial'}, status=400)
            
        scenario.delete()
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def publish_scenario(request, scenario_id):
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        with transaction.atomic():
            # Set all to False
            Scenario.objects.using('default').update(es_principal=False)
            
            # Set target to True
            target = Scenario.objects.using('default').get(pk=scenario_id)
            target.es_principal = True
            target.save(using='default')
            
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


def estadisticas_produccion(request):
    """
    Dashboard for system-wide statistics and machine occupancy.
    """
    from .gantt_logic import get_gantt_data
    # Force run of shared logic to get statistics
    # Note: Using default behavior (next 7 days lookahead)
    data = get_gantt_data(request, force_run=True)
    
    analysis = data.get('analysis', {})
    machines = analysis.get('machines', [])
    
    # Filter out machines with 0 capacity to avoid division by zero
    total_capacity = sum(m['capacity'] for m in machines)
    total_hours = sum(m['hours'] for m in machines)
    avg_load = (total_hours / total_capacity * 100) if total_capacity > 0 else 0
    
    # Metrics
    collapsed_machines = [m for m in machines if m['load_pct'] >= 100]
    high_load_machines = [m for m in machines if 70 <= m['load_pct'] < 100]
    healthy_machines = [m for m in machines if m['load_pct'] < 50]
    
    # Recent Alerts
    project_alerts = analysis.get('project_alerts', [])
    
    context = {
        'analysis': analysis,
        'machines': machines,
        'total_capacity': round(total_capacity, 1),
        'total_hours': round(total_hours, 1),
        'avg_load': round(avg_load, 1),
        'collapsed_count': len(collapsed_machines),
        'high_load_count': len(high_load_machines),
        'healthy_count': len(healthy_machines),
        'collapsed_machines': collapsed_machines,
        'healthy_machines': healthy_machines,
        'project_alerts': project_alerts,
        'active_scenario': data.get('active_scenario'),
        'today': datetime.now(),
    }
    
    return render(request, 'produccion/estadisticas.html', context)


def proyectos_prioridades(request):
    scenario_id = request.GET.get('scenario_id')
    active_scenario = None
    if scenario_id:
        try:
            active_scenario = Scenario.objects.using('default').get(pk=scenario_id)
        except:
            pass
    if not active_scenario:
        active_scenario = Scenario.objects.using('default').filter(es_principal=True).first()
        
    proyectos_str = active_scenario.proyectos if active_scenario and active_scenario.proyectos else request.session.get('last_proyectos', '')
    
    proyectos_list = [p.strip() for p in proyectos_str.split(',') if p.strip()] if proyectos_str else []
    
    prioridades_db = {}
    if active_scenario:
        prioridades_db = {p.proyecto: p.prioridad for p in ProyectoPrioridad.objects.using('default').filter(scenario=active_scenario)}
        
    proyectos_data = []
    # Assign priorities based on what is in DB or assign incremental default
    for p in proyectos_list:
        prio = prioridades_db.get(p, 999) # Default priority for unranked
        proyectos_data.append({'proyecto': p, 'prioridad': prio})
        
    # Correct unassigned priorities to be incremental starting from last max
    max_prio = max([d['prioridad'] for d in proyectos_data if d['prioridad'] != 999] + [0])
    for item in proyectos_data:
        if item['prioridad'] == 999:
            max_prio += 1
            item['prioridad'] = max_prio

    proyectos_data.sort(key=lambda x: x['prioridad'])
    
    return render(request, 'produccion/proyectos_prioridades.html', {
        'proyectos_data': proyectos_data,
        'active_scenario': active_scenario,
        'all_scenarios': Scenario.objects.using('default').all().order_by('-fecha_creacion'),
        'has_projects': len(proyectos_data) > 0
    })

@csrf_exempt
def update_proyecto_prioridad(request):
    """
    API endpoint to update the priority of multiple projects for the active scenario.
    Expects a JSON body with a list of updates:
    {
        "scenario_id": 1,
        "updates": [
            {"proyecto": "25-001", "prioridad": 1},
            {"proyecto": "23-145", "prioridad": 2}
        ]
    }
    """
    if request.method != 'POST':
         return JsonResponse({'error': 'Method not allowed'}, status=405)
         
    try:
        data = json.loads(request.body)
        scenario_id = data.get('scenario_id')
        updates = data.get('updates', [])
        
        scenario = None
        if scenario_id:
             scenario = Scenario.objects.using('default').filter(pk=scenario_id).first()
        else:
             scenario = Scenario.objects.using('default').filter(es_principal=True).first()
             
        if not scenario:
             return JsonResponse({'error': 'No active scenario found'}, status=400)
             
        with transaction.atomic(using='default'):
             for update in updates:
                  proyecto = update.get('proyecto')
                  prioridad = update.get('prioridad')
                  
                  if proyecto and prioridad is not None:
                       # Update or create priority
                       ProyectoPrioridad.objects.using('default').update_or_create(
                            scenario=scenario,
                            proyecto=proyecto,
                            defaults={'prioridad': int(prioridad)}
                       )
                       
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': str(e)}, status=500)


def planillas_diarias(request):
    """
    Generates a daily production sheet per machine based on Gantt calculation.
    """
    from .gantt_logic import get_gantt_data
    from collections import defaultdict
    import datetime
    
    # 1. Get timeline data by forcing a run
    gantt_res = get_gantt_data(request, force_run=True)
    timeline_data = gantt_res.get('timeline_data', [])
    valid_dates = gantt_res.get('valid_dates', [])
    
    daily_plan = {}
    
    for machine_row in timeline_data:
        machine = machine_row['machine']
        m_id = str(machine.id_maquina)
        
        # Don't create sheets for "SIN ASIGNAR" unless there are tasks
        if m_id == 'MAC00' and not machine_row['tasks']:
            continue
            
        daily_plan[m_id] = {
            'machine_id': m_id,
            'machine_name': machine.nombre,
            'dates': {}
        }
        
        # Initialize dates dictionary
        for v_date in valid_dates[:15]: # Up to 3 weeks
             daily_plan[m_id]['dates'][v_date.isoformat()] = []
             
        for segment in machine_row['tasks']:
            start = segment.get('start_date')
            if not start: continue
            
            d_str = start.date().isoformat()
            
            if d_str not in daily_plan[m_id]['dates']:
                  continue
            
            # Formatos
            cant_total = float(segment.get('Cantidad') or 0.0)
            cant_prod = float(segment.get('Cantidadpp') or 0.0)
            qty_pend = float(segment.get('CantidadesPendientes') or (cant_total - cant_prod))
            if qty_pend < 0: qty_pend = 0.0
            
            total_duration = float(segment.get('Tiempo_Proceso') or 0.001)
            if total_duration <= 0: total_duration = 0.001
            
            segment_duration = float(segment.get('duration_real') or 0.0)
            
            # Use segment_duration / total_duration to find the fraction of qty to produce today
            segment_qty = round(qty_pend * (segment_duration / total_duration), 2)
            
            if segment_qty > 0 or segment_duration > 0:
                daily_plan[m_id]['dates'][d_str].append({
                    'orden': segment.get('Idorden'),
                    'proyecto': segment.get('ProyectoCode'),
                    'denominacion': segment.get('Denominacion'),
                    'descripcion': segment.get('Descri'),
                    'cantidad_dia': segment_qty,
                    'tiempo_dia': round(segment_duration, 2),
                    'start_time': start.strftime('%H:%M'),
                    'end_time': segment.get('end_date').strftime('%H:%M') if segment.get('end_date') else ''
                })
                
    # Sort dates inside each machine
    for m_id, m_data in daily_plan.items():
        for d in m_data['dates']:
            m_data['dates'][d].sort(key=lambda x: x['start_time'])
            
        # Clean empty dates to not print blank pages
        m_data['has_active_dates'] = any(len(tasks) > 0 for tasks in m_data['dates'].values())
        
    daily_plan_list = [v for k, v in daily_plan.items() if v.get('has_active_dates')]
    
    # Spanish nicely formatted dates
    DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    nice_target_dates = []
    # Maximum 10 working days
    for d in valid_dates[:10]:
         nice_target_dates.append((d.isoformat(), f"{DAYS_ES[d.weekday()]} {d.strftime('%d/%m')}"))
    
    context = {
        'daily_plan': daily_plan_list,
        'target_dates': nice_target_dates,
        'active_scenario': gantt_res.get('active_scenario')
    }
    
    return render(request, 'produccion/planillas_diarias.html', context)

'''

with open(r"c:\Sistemas ABBAMAT\planificacionProcesosProductivos\produccion\views.py", "a", encoding="utf-8") as f:
    f.write(FUNCTIONS_CODE)
print("Done appending functions")
