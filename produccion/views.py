from django.shortcuts import render, get_object_or_404, redirect
from django.db import transaction, connections
from django.http import JsonResponse, HttpResponse
from .gantt_logic import get_gantt_data
from .services import get_planificacion_data, get_all_machines
from itertools import groupby
from operator import itemgetter
from .models import (
    PrioridadManual, MaquinaConfig, HorarioMaquina, 
    TaskDependency, HiddenTask, Scenario, ProyectoPrioridad
)
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from django.contrib import messages
from .planning_service import calculate_timeline
from datetime import datetime, timedelta
import openpyxl
from openpyxl.styles import PatternFill, Border, Side, Alignment, Font
from openpyxl.utils import get_column_letter
from openpyxl.comments import Comment
from openpyxl.worksheet.datavalidation import DataValidation

...

@csrf_exempt
def link_tasks(request):
    """
    API to create a dependency: Successor depends on Predecessor.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        pred_id = body.get('predecessor_id')
        succ_id = body.get('successor_id')
        
        if not pred_id or not succ_id:
            return JsonResponse({'error': 'Missing IDs'}, status=400)
            
        TaskDependency.objects.using('default').get_or_create(
            predecessor_id=pred_id,
            successor_id=succ_id
        )
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def unlink_tasks(request):
    """
    API to remove a dependency.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
        
    try:
        body = json.loads(request.body)
        pred_id = body.get('predecessor_id')
        succ_id = body.get('successor_id')
        
        TaskDependency.objects.using('default').filter(
            predecessor_id=pred_id,
            successor_id=succ_id
        ).delete()
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

def get_active_scenario(request, scenario_id=None):
    """
    Helper to resolve the active scenario from URL, session, or POST body.
    """
    url_scenario_id = request.GET.get('scenario_id')
    
    # If explicitly empty in URL, it means the user selected "Current State"
    if url_scenario_id == "":
        request.session['last_scenario_id'] = None
        scenario_id = None
    elif url_scenario_id:
        scenario_id = url_scenario_id
    
    # Check if we are switching to manual mode without a scenario in URL
    plan_mode = request.GET.get('plan_mode')
    if plan_mode == 'manual' and url_scenario_id is None:
        # If the user goes to manual but doesn't specify a scenario, 
        # assume they want to "leave" the current simulation scenario and see the Official state.
        request.session['last_scenario_id'] = None
        scenario_id = None

    if not scenario_id and request.method == 'POST':
        try:
            body = json.loads(request.body)
            scenario_id = body.get('scenario_id')
        except:
            pass
            
    if not scenario_id:
        scenario_id = request.session.get('last_scenario_id')
        
    active_scenario = None
    if scenario_id and str(scenario_id).isdigit():
        active_scenario = Scenario.objects.using('default').filter(id=scenario_id).first()
        
    if not active_scenario:
        # Fallback to Principal (Official)
        active_scenario = Scenario.objects.using('default').filter(es_principal=True).first()
        
    if active_scenario:
        request.session['last_scenario_id'] = str(active_scenario.id)
    else:
        request.session['last_scenario_id'] = None
        
    return active_scenario

@csrf_exempt
def reset_planning(request):
    """
    API to clear manual planning (Visual Priorities, Virtual Moves) for a set of Orders.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        ids = body.get('ids', [])
        active_scenario = get_active_scenario(request)

        print(f"DEBUG: reset_planning called for Scenario: {active_scenario.nombre} (ID: {active_scenario.id}) with {len(ids)} IDs")
        
        # If no IDs on screen, try to find them by project filter
        proyectos = body.get('proyectos')
        if not ids and proyectos:
             if isinstance(proyectos, str):
                  proj_list = [p.strip() for p in proyectos.split(',') if p.strip()]
             else:
                  proj_list = proyectos
             
             if proj_list:
                  # Use the same data fetching logic to find all OPs for these projects
                  from .services import get_planificacion_data
                  erp_data = get_planificacion_data({'proyectos': proj_list})
                  ids = [int(d['Idorden']) for d in erp_data if d.get('Idorden')]
                  print(f"DEBUG: reset_planning - Expanded to {len(ids)} tasks via Project lookup: {proj_list}")

        if not ids:
             return JsonResponse({'status': 'ignored', 'message': 'No IDs provided and no projects found to reset'})
        
        # 1. Clear Priorities and Virtual Moves FOR THIS SCENARIO ONLY
        deleted_prio, _ = PrioridadManual.objects.using('default').filter(id_orden__in=ids, scenario=active_scenario).delete()
        
        # 2. Clear Dependencies (Manual ones)
        # These are currently global
        deleted_dep_pred, _ = TaskDependency.objects.using('default').filter(predecessor_id__in=ids).delete()
        deleted_dep_succ, _ = TaskDependency.objects.using('default').filter(successor_id__in=ids).delete()
        
        # 3. Clear HIDDEN Status FOR THIS SCENARIO ONLY
        deleted_hidden, _ = HiddenTask.objects.using('default').filter(id_orden__in=ids, scenario=active_scenario).delete()
        
        return JsonResponse({'status': 'ok', 'message': f'Reset {len(ids)} tasks'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def hide_task(request):
    """
    API to hide a task from the list (virtual delete).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get('id_orden')
        active_scenario = get_active_scenario(request)
        
        if not id_orden:
             return JsonResponse({'error': 'Missing ID'}, status=400)
             
        HiddenTask.objects.using('default').update_or_create(
            id_orden=id_orden, 
            scenario=active_scenario
        )
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def reactivar_op(request):
    """
    API to restore a hidden task (remove from hidden_task table).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get('id_orden')
        # We can extract scenario_id directly to avoid redundant calls
        scenario_id = body.get('scenario_id')
        active_scenario = get_active_scenario(request, scenario_id=scenario_id)
        
        if not id_orden:
             return JsonResponse({'error': 'Missing ID'}, status=400)
             
        # Normalize ID
        try:
            id_orden_clean = int(float(id_orden))
        except:
            id_orden_clean = id_orden

        deleted_count, _ = HiddenTask.objects.using('default').filter(
            id_orden=id_orden_clean, 
            scenario=active_scenario
        ).delete()
        
        return JsonResponse({'status': 'ok', 'active': True, 'deleted_count': deleted_count})
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def update_manual_time(request):
    """
    API to update the manual process time for a task.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get('id_orden')
        tiempo_manual = body.get('tiempo_manual')
        maquina = body.get('maquina') or 'SIN ASIGNAR'
        active_scenario = get_active_scenario(request)
        
        if not id_orden or tiempo_manual is None:
             return JsonResponse({'error': 'Missing parameters'}, status=400)
             
        time_val = float(tiempo_manual)
        
        # We need to maintain the same machine for the override to be found correctly later
        obj, created = PrioridadManual.objects.using('default').get_or_create(
            id_orden=id_orden,
            scenario=active_scenario,
            maquina=maquina
        )
        obj.tiempo_manual = time_val
        obj.save(using='default')
            
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        print(f"ERROR update_manual_time: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def update_manual_nivel(request):
    """
    API to update the manual planning level (Nivel Planificacion) for a task.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get('id_orden')
        nivel_manual = body.get('nivel_manual')
        maquina = body.get('maquina') or 'SIN ASIGNAR'
        active_scenario = get_active_scenario(request)
        
        if not id_orden or nivel_manual is None:
             return JsonResponse({'error': 'Missing parameters'}, status=400)
             
        nivel_val = int(nivel_manual)
        
        obj, created = PrioridadManual.objects.using('default').get_or_create(
            id_orden=id_orden,
            scenario=active_scenario,
            maquina=maquina
        )
        obj.nivel_manual = nivel_val
        obj.save(using='default')
            
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        print(f"ERROR update_manual_nivel: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def update_overlap_percentage(request):
    """
    API to update the overlap percentage for a task.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get('id_orden')
        porcentaje_solapamiento = body.get('porcentaje_solapamiento')
        maquina = body.get('maquina') or 'SIN ASIGNAR'
        active_scenario = get_active_scenario(request)
        
        if not id_orden or porcentaje_solapamiento is None:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
            
        porcentaje_val = float(porcentaje_solapamiento)
        if porcentaje_val < 0 or porcentaje_val > 100:
            return JsonResponse({'error': 'Percentage must be between 0 and 100'}, status=400)
        
        obj, created = PrioridadManual.objects.using('default').get_or_create(
            id_orden=id_orden,
            scenario=active_scenario,
            maquina=maquina
        )
        obj.porcentaje_solapamiento = porcentaje_val
        obj.save(using='default')
        
        return JsonResponse({
            'status': 'ok',
            'id_orden': id_orden,
            'porcentaje_solapamiento': porcentaje_val
        })
    except Exception as e:
        print(f"❌ ERROR update_overlap_percentage: {e}")
        return JsonResponse({'error': str(e)}, status=500)



from .planning_service import calculate_timeline
from datetime import datetime, timedelta
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import json


def main_menu(request):
    return render(request, 'produccion/menu.html')

def planificacion_list(request):
    """
    View to retrieve planning data and render it in a table.
    """
    # Canonical URL Redirect: Ensure scenario_id is always in URL for consistency
    if 'scenario_id' not in request.GET:
        active_scenario = get_active_scenario(request)
        params = request.GET.copy()
        params['scenario_id'] = active_scenario.id
        return redirect(f"{request.path}?{params.urlencode()}")

    active_scenario = get_active_scenario(request)

    # Filter Persistence: Session + GET
    id_orden = request.GET.get('id_orden')
    if id_orden is not None:
        request.session['last_id_orden_filter'] = id_orden
    elif 'id_orden' not in request.GET:
        id_orden = request.session.get('last_id_orden_filter')

    proyectos = request.GET.get('proyectos')
    if proyectos is not None:
        request.session['last_proyectos_filter'] = proyectos
    elif 'proyectos' not in request.GET:
        proyectos = request.session.get('last_proyectos_filter')

    # FALLBACK: If no projects in URL or Session, use the Scenario's defaults
    if not proyectos and active_scenario and active_scenario.proyectos:
        proyectos = active_scenario.proyectos

    # Build filtros for the SQL query
    filtros = {}
    if id_orden:
        filtros['id_orden'] = id_orden
    if proyectos:
        filtros['proyectos'] = [p.strip() for p in proyectos.split(',') if p.strip()]


    try:
        # --- Local Machine Config Logic ---
        local_machines = MaquinaConfig.objects.using('default').all()
        using_local_config = local_machines.exists()
        
        if using_local_config:
            # Map: { ID: Name }
            machine_map = {m.id_maquina.strip(): m.nombre for m in local_machines}
            # List of objects for the template
            all_machines_list = [{'id': m.id_maquina.strip(), 'nombre': m.nombre} for m in local_machines]
            filtros['machine_ids'] = list(machine_map.keys())
        else:
            names = get_all_machines()
            # If no local config, Name IS the ID
            all_machines_list = [{'id': n, 'nombre': n} for n in names]
            machine_map = {n: n for n in names}

        # Optimization: Only fetch data if filters are active
        # Don't count machine_ids as an active user filter, we need user intent (project/id)
        search_active = bool(filtros.get('proyectos') or filtros.get('id_orden'))
        
        if search_active:
            data = get_planificacion_data(filtros)
        else:
            data = []
        
        # --- CANONICAL MACHINE HARMONIZATION ---
        # Build maps to translate between Name and ID for overrides
        name_to_id = {m.nombre.strip().upper(): m.id_maquina.strip() for m in local_machines}
        id_to_name = {m.id_maquina.strip(): m.nombre.strip() for m in local_machines}
        
        # Determine plan mode
        plan_mode = request.GET.get('plan_mode')
        if plan_mode:
            request.session['last_plan_mode'] = plan_mode
        else:
            plan_mode = request.session.get('last_plan_mode', 'original')

        # --- FILTER HIDDEN TASKS FOR THIS SCENARIO ---
        # If we are in 'audit_mode', we include hidden tasks but mark them.
        audit_mode = request.GET.get('audit_mode') == '1'
        hidden_ids = set()
        if plan_mode != 'original':
            hidden_ids = set(HiddenTask.objects.using('default').filter(scenario=active_scenario).values_list('id_orden', flat=True))
            
            if audit_mode:
                # In audit mode, we keep them but flag them
                for item in data:
                    if item.get('Idorden') in hidden_ids:
                        item['is_hidden'] = True
            else:
                # Normal mode: filter them out
                if hidden_ids:
                    data = [d for d in data if d.get('Idorden') not in hidden_ids]

        
        # Determine response format
        if request.GET.get('format') == 'json':
             return JsonResponse({'data': data}, safe=False)




        # Fetch Local Priorities filtered by Scenario
        virtual_overrides = {}
        id_to_any_override = {}
        if plan_mode == 'manual':
            if active_scenario:
                prioridades_db = PrioridadManual.objects.using('default').filter(scenario=active_scenario)
                print(f"DEBUG: planificacion_list - Loading {prioridades_db.count()} overrides for Scenario {active_scenario.nombre}")
                               # Map for OVERRIDES: (id_orden, maquina_id) -> data
                # We harvest ALL manual attributes to ensure consistency
                virtual_overrides = {}
                id_to_any_override = {}
                
                for p in prioridades_db:
                    oid = int(p.id_orden)
                    mid = str(p.maquina).strip()
                    node = {
                        'maquina': mid, 
                        'prioridad': p.prioridad,
                        'tiempo_manual': p.tiempo_manual,
                        'nivel_manual': p.nivel_manual,
                        'porcentaje_solapamiento': p.porcentaje_solapamiento,
                        'fecha_inicio_manual': p.fecha_inicio_manual
                    }
                    virtual_overrides[(oid, mid)] = node
                    id_to_any_override[oid] = mid
                
                id_to_override = id_to_any_override
            else:
                print("[WARN] No Active Scenario found in manual mode.")
        else:
            print("[INFO] AUTOMATIC MODE: Ignoring manual overrides in machine table.")

        # 1. Calculate extra fields, assign Priority, and Normalize Machine Name
        # We start with a BASELINE PROIRITY based on the initial SQL sort order (Index).
        # This prevents "unmoved" items (Priority 0) from being jumped over by a moved item (Priority 1500).
        for idx, item in enumerate(data):
            # Normalizar ID de orden para que coincida con overrides
            try:
                t_id_val = int(float(item.get('Idorden')))
                item['Idorden'] = t_id_val # Actualizar en el item
            except:
                t_id_val = 0

            # Update Machine Name based on Local Config if active
            native_code = str(item.get('Idmaquina', '')).strip()
            
            # A. Determine NATIVE Machine Name & ID
            if using_local_config:
                # HARMONIZATION: Translate ERP code to our Canonical ID
                # erp_code could be "MAC18" OR "VF2" depending on ERP version
                erp_code = str(item.get('Idmaquina', '')).strip()
                canonical_id = erp_code
                
                # Check if erp_code is actually a Name in our config
                if erp_code.upper() in name_to_id:
                    canonical_id = name_to_id[erp_code.upper()]
                
                current_machine_id = canonical_id
                current_machine_name = id_to_name.get(canonical_id, erp_code)
            else:
                current_machine_id = item.get('MAQUINAD', 'SIN ASIGNAR')
                current_machine_name = current_machine_id
            
            # B. Check for VIRTUAL OVERRIDE (Moved Task)
            t_id_val = int(item.get('Idorden'))
            override_node = None
            
            # Use Canonical ID for lookup
            m_lookup = str(current_machine_id).strip()
            
            keys_to_try = [(t_id_val, m_lookup)]
            
            for k in keys_to_try:
                if k in virtual_overrides:
                    override_node = virtual_overrides[k]
                    break
            
            if not override_node:
                # Cross-machine lookup (Moved items)
                if t_id_val in id_to_any_override:
                    target_m_id = id_to_any_override[t_id_val]
                    override_node = virtual_overrides.get((t_id_val, target_m_id))

            if override_node:
                target_machine_id = str(override_node['maquina']).strip()
                priority_val = override_node['prioridad']
                
                # Update current state
                current_machine_id = target_machine_id
                # Use name_to_id/id_to_name for robust naming
                current_machine_name = id_to_name.get(target_machine_id, target_machine_id)

                item['OrdenVisual'] = float(priority_val)
                item['ManualPriorityFlag'] = True
                
                # Apply Overrides
                if override_node.get('tiempo_manual') is not None:
                     item['Tiempo_Proceso'] = float(override_node['tiempo_manual'])
                     item['CalculadoManual'] = True 
                else:
                     item['CalculadoManual'] = False

                if override_node.get('nivel_manual') is not None:
                     item['Nivel_Planificacion'] = override_node['nivel_manual']
                     item['NivelManualFlag'] = True
                else:
                     item['NivelManualFlag'] = False
                     
                if override_node.get('porcentaje_solapamiento') is not None:
                     item['porcentaje_solapamiento'] = override_node['porcentaje_solapamiento']
            else:
                # Default Logic: Base it on SQL Position but spread it out
                # We will re-number these per-machine later for better UI consistency
                item['OrdenVisual'] = None # Flag for default
                item['ManualPriorityFlag'] = False
                item['CalculadoManual'] = False
                item['NivelManualFlag'] = False
            
            # Final Assignment to Item
            item['MAQUINAD'] = current_machine_name
            item['MAQUINA_ID'] = current_machine_id

            # Cantidades
            item['Cantidad'] = item.get('cantidad_final') or 0
            item['Cantidadpp'] = item.get('cantidad_producida') or 0
            item['CantidadesPendientes'] = item.get('cantidad_pendiente') or 0


        # 2. Initialize Grouping using MACHINE NAMES
        grouped_data = {m['nombre']: [] for m in all_machines_list}
        if 'SIN ASIGNAR' not in grouped_data:
             grouped_data['SIN ASIGNAR'] = []        # Populate with data
        for item in data:
            m_name = item.get('MAQUINAD', 'SIN ASIGNAR')
            if m_name in grouped_data:
                grouped_data[m_name].append(item)
            else:
                if using_local_config:
                     if 'SIN ASIGNAR' in grouped_data:
                          grouped_data['SIN ASIGNAR'].append(item)
                else:
                    grouped_data.setdefault(m_name, []).append(item)
                    if m_name not in all_machines_list:
                        all_machines_list.append(m_name)
        
        # Sort items within each machine and re-assign visual IDs
        for m_name in grouped_data:
            machine_items = grouped_data[m_name]
            
            # 1. Fill defaults for items without manual priority
            # We use their original SQL index to maintain the ERP order among non-moved items
            for idx, m_item in enumerate(machine_items):
                if m_item['OrdenVisual'] is None:
                    # We use a large offset to ensure they are usually after small manual priorities (unless manually set high)
                    # But actually, SQL order is better. 
                    # Let's use a per-machine index to keep priorities clean.
                    m_item['OrdenVisual'] = (idx + 1) * 5000.0 # Wide spacing for default

            # 2. Sort by the finalized OrdenVisual
            machine_items.sort(key=lambda x: x.get('OrdenVisual', 999999.0))
            
            # 3. Re-assign discrete OrdenVisual (1000, 2000, 3000...) for the template/UI
            # This provides the clean baseline for the next Drag event.
            for idx, m_item in enumerate(machine_items):
                val = (idx + 1) * 1000
                m_item['OrdenVisual'] = float(val)
                m_item['Idprioridad'] = int(val)

        # FINAL FILTER: REMOVED per user request ("no las ocultes")
        # We keep all machines visible to allow moving tasks to them.
        processed_machines = []
        for m in all_machines_list:
             processed_machines.append({'id': m['id'], 'nombre': m['nombre']})
        
        # Sort by name
        processed_machines.sort(key=lambda x: x['nombre'])

        if any(m['nombre'] == 'SIN ASIGNAR' for m in processed_machines):
             # Ensure SIN ASIGNAR is at the end
             sin_a = [m for m in processed_machines if m['nombre'] == 'SIN ASIGNAR'][0]
             processed_machines.remove(sin_a)
             processed_machines.append(sin_a)
        elif 'SIN ASIGNAR' in grouped_data:
             processed_machines.append({'id': 'SIN ASIGNAR', 'nombre': 'SIN ASIGNAR'})
        
        # FINAL FILTER: REMOVED per user request ("no las ocultes")
        # We keep all machines visible to allow moving tasks to them.
        # if search_active:
        #      processed_machines = [m for m in processed_machines if grouped_data.get(m)]

        return render(request, 'produccion/planificacion.html', {
            'grouped_data': grouped_data, 
            'machines': processed_machines,
            'search_active': search_active,
            'proyectos_value': proyectos if proyectos else '',
            'id_orden_value': id_orden if id_orden else '',
            'all_scenarios': Scenario.objects.using('default').all() if 'Scenario' in globals() else [],
            'active_scenario_id': active_scenario.id if active_scenario else None,
            'audit_mode': audit_mode
        })
    except Exception as e:
        if request.GET.get('format') == 'json':
            return JsonResponse({'error': str(e)}, status=500)
        return render(request, 'produccion/planificacion.html', {'grouped_data': {}, 'machines': [], 'error': str(e)})


@csrf_exempt
@csrf_exempt
def move_priority(request, id_orden, direction):
    """
    API to move an order up or down in the local priority list.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        maquina_raw = body.get('maquina')
        current_priority = float(body.get('priority', 0)) 
        neighbor_id = body.get('neighbor_id')
        neighbor_priority = body.get('neighbor_priority') 
        active_scenario = get_active_scenario(request)
        
        if neighbor_id is None:
            return JsonResponse({'status': 'ignored', 'message': 'No neighbor'})

        # Harmonize machine key
        from .models import MaquinaConfig
        m_conf = MaquinaConfig.objects.filter(nombre=maquina_raw).first()
        maquina_id = m_conf.id_maquina if m_conf else maquina_raw

        # Target Item (Delete old name-based if moving to ID-based)
        if m_conf and maquina_raw != maquina_id:
             PrioridadManual.objects.filter(id_orden=id_orden, maquina=maquina_raw, scenario=active_scenario).delete()
             PrioridadManual.objects.filter(id_orden=neighbor_id, maquina=maquina_raw, scenario=active_scenario).delete()

        obj_target, _ = PrioridadManual.objects.using("default").update_or_create(
            id_orden=id_orden, maquina=maquina_id, scenario=active_scenario,
            defaults={"prioridad": neighbor_priority}
        )
        
        obj_neighbor, _ = PrioridadManual.objects.using("default").update_or_create(
            id_orden=neighbor_id, maquina=maquina_id, scenario=active_scenario,
            defaults={"prioridad": current_priority}
        )
        
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"error": f"DB Error: {str(e)}"}, status=500)

@csrf_exempt
def move_task(request):
    """
    API to move a task to a different machine and/or update its priority order.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get("id_orden")
        target_machine_raw = body.get("target_machine_id")
        new_priority = body.get("new_priority")
        active_scenario = get_active_scenario(request)
        
        if not id_orden or not target_machine_raw or new_priority is None:
             return JsonResponse({"error": "Missing parameters"}, status=400)
             
        new_priority = float(new_priority)
        
        # Harmonize machine
        from .models import MaquinaConfig
        print(f"DEBUG: move_task - ID: {id_orden}, TargetRaw: {target_machine_raw}, Prio: {new_priority}")
        m_conf = MaquinaConfig.objects.using("default").filter(nombre=target_machine_raw).first()
        target_machine_id = m_conf.id_maquina if m_conf else target_machine_raw
        print(f"DEBUG: move_task - Resolved Machine ID: {target_machine_id}")


        from django.db import transaction
        with transaction.atomic(using="default"):
            # Normalizar ID (SQL vs Django)
            try:
                id_orden_clean = int(float(id_orden))
            except:
                id_orden_clean = id_orden

            # Fetch existing to preserve attributes
            old_entry = PrioridadManual.objects.using("default").filter(id_orden=id_orden_clean, scenario=active_scenario).first()
            
            existing_data = {
                "tiempo_manual": old_entry.tiempo_manual if old_entry else None,
                "fecha_inicio_manual": old_entry.fecha_inicio_manual if old_entry else None,
                "nivel_manual": old_entry.nivel_manual if old_entry else None,
                "porcentaje_solapamiento": old_entry.porcentaje_solapamiento if old_entry else 0.0
            }
            
            # Clean up all assignments for this OP in this scenario
            PrioridadManual.objects.using("default").filter(id_orden=id_orden_clean, scenario=active_scenario).delete()
            
            PrioridadManual.objects.using("default").create(
                id_orden=id_orden_clean,
                maquina=target_machine_id,
                prioridad=new_priority,
                scenario=active_scenario,
                **existing_data
            )
            
            # CRITICAL UX: Force manual mode in session so the user SEES the change
            request.session['last_plan_mode'] = 'manual'
            
        return JsonResponse({"status": "ok"})
    except Exception as e:
        return JsonResponse({"error": f"DB Error: {str(e)}"}, status=500)

@csrf_exempt
def set_priority(request, id_orden):
    """
    API to set a specific priority AND/OR manual start date for an order.
    Used for Drag and Drop (pinning/manual sequencing).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        maquina = body.get('maquina')
        new_priority = body.get('new_priority')
        manual_start_str = body.get('manual_start')
        active_scenario = get_active_scenario(request)
        
        # Validation
        if new_priority is None and manual_start_str is None:
             return JsonResponse({'error': 'Missing new_priority or manual_start'}, status=400)
             
        if new_priority is not None:
            new_priority = float(new_priority)
            
        manual_start_dt = None
        if manual_start_str:
            try:
                from django.utils import timezone as django_tz
                # Robust Date Parsing
                manual_start_str = str(manual_start_str).strip()
                if 'T' in manual_start_str:
                    manual_start_dt = datetime.fromisoformat(manual_start_str.replace('Z', '+00:00'))
                    if manual_start_dt.tzinfo is None:
                        manual_start_dt = django_tz.make_aware(manual_start_dt)
                else:
                    if '.' in manual_start_str:
                        manual_start_str = manual_start_str.split('.')[0]
                    naive_dt = datetime.strptime(manual_start_str, '%Y-%m-%d %H:%M:%S')
                    manual_start_dt = django_tz.make_aware(naive_dt)
            except Exception as ve:
                print(f"ERROR parsing date in set_priority: {ve}")
                return JsonResponse({'error': f'Invalid date format: {manual_start_str}'}, status=400)

        # Harmonize machine
        from .models import MaquinaConfig
        print(f"DEBUG: set_priority - ID: {id_orden}, TargetRaw: {maquina}, Prio: {new_priority}, Scenario: {active_scenario.id if active_scenario else 'None'}")
        m_conf = MaquinaConfig.objects.using('default').filter(nombre=maquina).first()
        maquina_id = m_conf.id_maquina if m_conf else maquina
        print(f"DEBUG: set_priority - Resolved Machine ID: {maquina_id}")


        from django.db import transaction
        with transaction.atomic(using='default'):
            # Normalizar ID para asegurar match con DB (SQL vs Django types)
            try:
                id_orden_clean = int(float(id_orden))
            except:
                id_orden_clean = id_orden
                
            # Fetch existing to preserve ALL other manual overrides
            old_entry = PrioridadManual.objects.using('default').filter(id_orden=id_orden_clean, scenario=active_scenario).first()
            
            # Default values if no entry exists
            existing_data = {
                'tiempo_manual': old_entry.tiempo_manual if old_entry else None,
                'nivel_manual': old_entry.nivel_manual if old_entry else None,
                'porcentaje_solapamiento': old_entry.porcentaje_solapamiento if old_entry else 0.0,
                'fecha_inicio_manual': old_entry.fecha_inicio_manual if old_entry else None,
                'prioridad': old_entry.prioridad if old_entry else (new_priority if new_priority is not None else 0.0)
            }
            
            # Clean up before re-creating
            PrioridadManual.objects.using('default').filter(id_orden=id_orden_clean, scenario=active_scenario).delete()
            
            final_start_date = manual_start_dt if manual_start_dt is not None else existing_data['fecha_inicio_manual']
            final_priority = new_priority if new_priority is not None else existing_data['prioridad']
            
            PrioridadManual.objects.using('default').create(
                id_orden=id_orden_clean,
                maquina=maquina_id, 
                prioridad=final_priority,
                fecha_inicio_manual=final_start_date,
                scenario=active_scenario,
                tiempo_manual=existing_data['tiempo_manual'],
                nivel_manual=existing_data['nivel_manual'],
                porcentaje_solapamiento=existing_data['porcentaje_solapamiento']
            )

            # CRITICAL UX: Force manual mode in session so the user SEES the change
            request.session['last_plan_mode'] = 'manual'
            
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        print(f"❌ ERROR set_priority DB: {e}")
        return JsonResponse({'error': f'DB Error: {str(e)}'}, status=500)
    




# --- Machine Configuration Views ---

from django.db import transaction

from django.core.paginator import Paginator

def maquina_config_list(request):
    """
    List all locally configured machines and their schedules + Equivalencies.
    """
    from .models import MaquinaEquivalencia
    
    # Order by ID to ensure consistent pagination
    maquinas_list = MaquinaConfig.objects.using('default').prefetch_related('horarios').all().order_by('id_maquina')
    all_maquinas = MaquinaConfig.objects.using('default').all().order_by('id_maquina')
    
    paginator = Paginator(maquinas_list, 10) # Increased to 10
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Equivalencies for the management section
    equivalencias = MaquinaEquivalencia.objects.using('default').select_related('maquina_origen', 'maquina_destino').all()
    
    return render(request, 'produccion/maquina_config_list.html', {
        'maquinas': page_obj,
        'all_maquinas': all_maquinas,
        'equivalencias': equivalencias
    })

@csrf_exempt
def maquina_equivalencia_save(request):
    """
    Save or delete a machine equivalency.
    """
    from .models import MaquinaEquivalencia, MaquinaConfig
    from django.shortcuts import redirect
    from django.contrib import messages
    
    if request.method == 'POST':
        action = request.POST.get('action', 'save')
        
        if action == 'delete':
            eq_id = request.POST.get('id')
            MaquinaEquivalencia.objects.using('default').filter(pk=eq_id).delete()
            messages.success(request, "Equivalencia eliminada correctamente.")
        else:
            origen_id = request.POST.get('origen')
            destino_id = request.POST.get('destino')
            eficiencia = float(request.POST.get('eficiencia', 1.0))
            
            if origen_id == destino_id:
                messages.error(request, "La máquina origen y destino no pueden ser la misma.")
            else:
                origen = MaquinaConfig.objects.using('default').get(id_maquina=origen_id)
                destino = MaquinaConfig.objects.using('default').get(id_maquina=destino_id)
                
                MaquinaEquivalencia.objects.using('default').update_or_create(
                    maquina_origen=origen,
                    maquina_destino=destino,
                    defaults={'factor_eficiencia': eficiencia}
                )
                messages.success(request, f"Equivalencia {origen_id} -> {destino_id} guardada.")
                
    return redirect('maquina_config_list')

def planificacion_visual_OLD(request):
    """
    Visual Gantt Chart View.
    """
    # 1. Get Local Machines
    maquinas = MaquinaConfig.objects.using('default').prefetch_related('horarios').all().order_by('id_maquina')
    
    # 2. Get Data and Calculate Timeline
    timeline_data = [] 
    
    # 2. Prepare Start Date for Simulation
    # Parse fecha_desde if provided, otherwise use today
    fecha_desde = request.GET.get('fecha_desde')
    if fecha_desde:
        try:
            start_simulation = datetime.strptime(fecha_desde, '%Y-%m-%d')
        except ValueError:
            start_simulation = datetime.now()
    else:
        start_simulation = datetime.now()
    
    # IMPORTANT: Start from beginning of workday (7:00 AM), not current time
    # This ensures tasks are scheduled from the start of the day
    start_simulation = start_simulation.replace(hour=7, minute=0, second=0, microsecond=0)
    
    # 3. Check for Local Manual Priorities/Group Assignments & Time Overrides
    # Using PrioridadManual table to override positions and machines locally (Virtual Moves)
    # Map: id_orden -> { 'maquina': machine_id, 'prioridad': val, 'tiempo_manual': val }
    virtual_overrides = {}
    
    manual_entries = PrioridadManual.objects.using('default').all()
    for entry in manual_entries:
        # If there are duplicates for id_orden (shouldn't be with new logic, but historically maybe), take latest?
        # New logic ensures unique id_orden in PrioridadManual roughly (by deleting old).
        virtual_overrides[entry.id_orden] = {
            'maquina': entry.maquina,
            'prioridad': entry.prioridad,
            'tiempo_manual': entry.tiempo_manual,
            'nivel_manual': entry.nivel_manual,
            'manual_start': entry.fecha_inicio_manual # New field for Pinning
        }

    # Create a set of IDs that are moved TO a machine locally
    # machine_id -> list of order_ids
    tasks_moved_in_map = {}
    for oid, override_data in virtual_overrides.items():
        mid = override_data['maquina']
        if mid not in tasks_moved_in_map:
             tasks_moved_in_map[mid] = []
        tasks_moved_in_map[mid].append(oid)
    
    # --- HIDDEN TASKS ---
    # Fetch list of hidden task IDs to exclude them from the Gantt
    hidden_ids = set(HiddenTask.objects.using('default').values_list('id_orden', flat=True))

    # EXECUTION MODE CHECK
    # User requested: "Cuando presione VER GANTT, solo ingrese... pero si procesar nada."
    # "EJECUTAR Gantt" button adds &run=1
    run_calculation = request.GET.get('run') == '1'

    if not run_calculation:
        # Return empty structure with machines but no tasks
        for maquina in maquinas:
            timeline_data.append({
                'machine': maquina,
                'tasks': []
            })
        
        # Skip all the complex logic below
        context = {
            'timeline_data': timeline_data,
            'today': start_simulation,
            'time_columns': range(7, 22), # Default columns for grid
            'total_width': 15 * 40,
            'dependencies_json': '[]',
        }
        return render(request, 'produccion/planificacion_visual.html', context)

    # --- AUTOMATIC DEPENDENCY PREPARATION (OPTION B: By Nivel Decreasing) ---
#    print("\n" + "=" * 70)
#    print("🔢 OPCIÓN B: Dependencias Automáticas por Nivel (Mayor a Menor)")
#    print("=" * 70)

    # 1. Fetch relevant tasks to build the map (Scope to Current Project filter)
    deps_filter = {}
    if request.GET.get('proyectos'):
         raw_proyectos = request.GET.get('proyectos')
         deps_filter['proyectos'] = [p.strip() for p in raw_proyectos.split(',') if p.strip()]
    if request.GET.get('id_orden'):
        deps_filter['id_orden'] = request.GET.get('id_orden')
    
    # If no filter used, fallback to empty (all/defaults)
    all_tasks_for_deps = get_planificacion_data(deps_filter) 
    
    # DEBUG: Trace specific IDs
    debug_ids = [46762, 46759]
    for t in all_tasks_for_deps:
        if t.get('Idorden') in debug_ids:
             print(f"DEBUG TRACE {t.get('Idorden')}: Mstnmbr={t.get('Mstnmbr')}, Nivel={t.get('Nivel_Planificacion')}") 

    # Debug: Check if specific tasks are in virtual_overrides
    for task_id in [46543, 46542]:
        if task_id in virtual_overrides:
            print(f"DEBUG: Task {task_id} found in virtual_overrides: {virtual_overrides[task_id]}")
        else:
            print(f"DEBUG: Task {task_id} NOT found in virtual_overrides")
    
    # --- Apply Overrides to Dependency Candidates ---
    for task in all_tasks_for_deps:
        p_id = task.get('Idorden')
        ov_data = None
        # Robust Lookup
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
             # Debug: Show when manual nivel is applied
             if p_id in [46543, 46542]:
                 print(f"DEBUG OVERRIDE: Applied nivel_manual={ov_data['nivel_manual']} to task {p_id}")
             
    # Debug: Check Sample
    # print(f"DEBUG: Checking Mstnmbr/Nivel for deps. Count: {len(all_tasks_for_deps)}") 

    # 2. Group by Formula/ProyectoCode (NOT by Mstnmbr)
    # This ensures dependencies are created only between tasks of the same project
    from collections import defaultdict
    orders_map = defaultdict(list)
    
    for task in all_tasks_for_deps:
        formula = task.get('ProyectoCode')  # Changed from Mstnmbr to ProyectoCode
        # Only group if Formula exists
        if formula:
            orders_map[formula].append(task)

    dependency_map = {}
    dependencies_list_for_json = []

    for formula, tasks_in_order in orders_map.items():
        # Debug: Show all tasks and niveles for projects 25-100 and 25-098
        if formula in ['25-100', '25-098']:
            print(f"\n  DEBUG: Formula {formula} has {len(tasks_in_order)} tasks:")
            for t in tasks_in_order:
                nivel_p = t.get('Nivel_Planificacion')
                nivel = t.get('Nivel')
                print(f"    - Task {t.get('Idorden')}: Nivel_Planificacion={nivel_p}, Nivel={nivel} ({t.get('MAQUINAD')})")
        
        # Helper to get Nivel safely
        def get_nivel(t):
            try:
                # Use ONLY Nivel_Planificacion (not Nivel)
                val = t.get('Nivel_Planificacion')
                
                if val is None: 
                    return 0
                return float(val)
            except (ValueError, TypeError):
                return 0


        # Sort by Nivel DESCENDING (Highest Nivel = First Operation)
        tasks_sorted = sorted(tasks_in_order, key=get_nivel, reverse=True)
        
        # FILTER OUT tasks that are "SIN ASIGNAR" (not assigned to any machine)
        # We only want to create dependencies between tasks that are actually scheduled
        tasks_assigned = [t for t in tasks_sorted if t.get('MAQUINAD') and t.get('MAQUINAD') != 'SIN ASIGNAR']
        
        if formula in ['25-100', '25-098']:
            print(f"\n  DEBUG: After filtering SIN ASIGNAR, {len(tasks_assigned)} tasks remain:")
            for t in tasks_assigned:
                print(f"    - Task {t.get('Idorden')}: Nivel {get_nivel(t)} ({t.get('MAQUINAD')})")
        
        # Group tasks by nivel (only assigned tasks)
        nivel_groups = {}
        for task in tasks_assigned:
            nivel = get_nivel(task)
            if nivel not in nivel_groups:
                nivel_groups[nivel] = []
            nivel_groups[nivel].append(task)
        
        # Get sorted list of unique niveles (descending)
        sorted_niveles = sorted(nivel_groups.keys(), reverse=True)
        
        # Create dependencies: each nivel depends on the immediately higher nivel
        for i in range(len(sorted_niveles) - 1):
            higher_nivel = sorted_niveles[i]
            lower_nivel = sorted_niveles[i + 1]
            
            # All tasks in lower_nivel depend on ALL tasks in higher_nivel
            for successor in nivel_groups[lower_nivel]:
                succ_id = successor.get('Idorden')
                if not succ_id:
                    continue
                
                for predecessor in nivel_groups[higher_nivel]:
                    pred_id = predecessor.get('Idorden')
                    if not pred_id or pred_id == succ_id:
                        continue
                    
                    if succ_id not in dependency_map:
                        dependency_map[succ_id] = []
                    
                    # Avoid duplicates
                    if pred_id not in dependency_map[succ_id]:
                        dependency_map[succ_id].append(pred_id)
                        
                        dependencies_list_for_json.append({
                            'pred': pred_id,
                            'succ': succ_id
                        })
                        
                        # Debug logging for our specific tasks
                        if pred_id in [46762, 46759] or succ_id in [46762, 46759]:
                            print(f"  [DEPENDENCY CREATED] {pred_id} (Nivel {higher_nivel}) -> {succ_id} (Nivel {lower_nivel})")


#    print(f"\n  ✅ Created {len(dependency_map)} automatic dependencies based on Nivel (Desc)")
#    print("=" * 70 + "\n")
        
    # Global map to track end dates of ALL tasks across ALL machines
    global_task_end_dates = {}
    
    # Store machine data for second pass
    machine_tasks_map = {}  # machine_id -> {'maquina': obj, 'tasks': [...]}

    # ========================================================================
    # FIRST PASS: Calculate ALL tasks to build global_task_end_dates
    # ========================================================================
#    print("=" * 60)
#    print("DEPENDENCY RESOLUTION: FIRST PASS (Building end dates map)")
#    print("=" * 60)
    
    for maquina in maquinas:
        machine_id = maquina.id_maquina
        
        # 1. Fetch "Native" Tasks from SQL (Tasks physically assigned to this machine)
        # --------------------------------------------------------------------------------
        filtros = request.GET.copy()
        
        machine_filter = {'machine_ids': [machine_id]}
        
        if request.GET.get('proyectos'):
             raw_proyectos = request.GET.get('proyectos')
             machine_filter['proyectos'] = [p.strip() for p in raw_proyectos.split(',') if p.strip()]

        native_tasks = get_planificacion_data(machine_filter) 
        
        # 2. Filter OUT tasks that were virtually moved AWAY
        # --------------------------------------------------------------------------------
        active_tasks = []
        
        # Prepare current machine identifiers
        current_machine_code = str(machine_id).strip()
        current_machine_name = str(maquina.nombre).strip()

        for t in native_tasks:
            try:
                oid = int(t.get('Idorden', 0))
            except (ValueError, TypeError):
                oid = 0
            
            # Check Virtual Map
            if oid in virtual_overrides:
                override_data = virtual_overrides[oid]
                target_machine = str(override_data['maquina']).strip()
                
                # Check if the target machine matches THIS machine (either by Code or Name)
                # If it matches, we keep it (it was 'moved' here, or stayed here).
                # If it doesn't match, it was moved AWAY.
                if target_machine == current_machine_code or target_machine == current_machine_name:
                    # Is it hidden?
                    if oid not in hidden_ids:
                        active_tasks.append(t)
            else:
                 # No virtual move. Keep it unless hidden.
                 if oid not in hidden_ids:
                     active_tasks.append(t)
                 
        # 3. Add tasks that were virtually moved IN (from other machines)
        # --------------------------------------------------------------------------------
        # keys in tasks_moved_in_map could be Codes OR Names. Check both.
        moved_in_ids = []
        if current_machine_code in tasks_moved_in_map:
            moved_in_ids.extend(tasks_moved_in_map[current_machine_code])
        if current_machine_name in tasks_moved_in_map:
             # Avoid duplicates if Code == Name or overlap
             new_ids = tasks_moved_in_map[current_machine_name]
             moved_in_ids.extend([i for i in new_ids if i not in moved_in_ids])
        
        if moved_in_ids:
            inbound_filter = {}
            if request.GET.get('proyectos'):
                 inbound_filter['proyectos'] = machine_filter['proyectos']
            
            inbound_filter['id_orden_in'] = moved_in_ids
            
            extra_tasks = get_planificacion_data(inbound_filter)
            
            # Merge unique tasks (avoid duplicates if native query somehow caught them)
            existing_ids = set(t['Idorden'] for t in active_tasks)
            for t in extra_tasks:
                t_id = t['Idorden']
                if t_id not in existing_ids and t_id not in hidden_ids:
                    active_tasks.append(t)

        
        # Deduplicate tasks by Idorden just in case
        unique_tasks_map = {}
        for t in active_tasks:
            # Use string key for robust deduplication
            tid = str(t.get('Idorden'))
            if tid not in unique_tasks_map:
                unique_tasks_map[tid] = t
        
        tasks = list(unique_tasks_map.values())
        
        # --- Apply Visual Priority Sorting AND Manual Time Override ---
        for idx, item in enumerate(tasks):
             # Default Priority (preserve SQL order)
             default_prio = (idx + 1) * 1000.0
             
             p_id = item['Idorden']
             
             # Robust Lookup: Try raw, then int, then str
             override_found = False
             ov_data = None
             
             if p_id in virtual_overrides:
                 ov_data = virtual_overrides[p_id]
                 override_found = True
             else:
                 try:
                     p_id_int = int(p_id)
                     if p_id_int in virtual_overrides:
                         ov_data = virtual_overrides[p_id_int]
                         override_found = True
                 except (ValueError, TypeError):
                     pass
             
             if override_found and ov_data:
                 item['OrdenVisual'] = float(ov_data['prioridad'])
                 
                 # Apply Time Override
                 if ov_data.get('tiempo_manual') is not None:
                     item['Tiempo_Proceso'] = float(ov_data['tiempo_manual'])
                     item['CalculadoManual'] = True

                 # Apply Nivel Override
                 if ov_data.get('nivel_manual') is not None:
                     item['Nivel_Planificacion'] = ov_data['nivel_manual']
             else:
                 item['OrdenVisual'] = default_prio
                 
        # Group by Project, then sort by Nivel DESC, then by Visual Priority
        # This ensures the manufacturing sequence is respected as requested.
        tasks.sort(key=lambda x: (
            x.get('ProyectoCode') or '', 
            -int(x.get('Nivel_Planificacion', 0) or 0), 
            x.get('OrdenVisual', 999999)
        ))
        
        # Re-normalize priorities within the final resulting order
        for idx, item in enumerate(tasks):
            item['OrdenVisual'] = (idx + 1) * 1000
        
        # Store for second pass
        machine_tasks_map[machine_id] = {
            'maquina': maquina,
            'tasks': tasks
        }
        
        # FIRST PASS: Calculate WITHOUT dependency constraints
        # This builds the initial end_dates map
        calculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, task_min_start_times=None)
        
        # Update Global End Dates with FIRST PASS results
        for ct in calculated_tasks:
             ct_id = ct.get('Idorden')
             ct_end = ct.get('end_date')
             if ct_id and ct_end:
                 if ct_id not in global_task_end_dates or ct_end > global_task_end_dates[ct_id]:
                     global_task_end_dates[ct_id] = ct_end
                     
                     # Debug logging for our specific tasks
                     if ct_id in [46762, 46759]:
                         print(f"  [END DATE RECORDED] Task {ct_id} ends at {ct_end}")
        
        print(f"  Machine {machine_id}: Calculated {len(calculated_tasks)} tasks")

    # ========================================================================
    # SECOND PASS: Recalculate ONLY tasks with dependencies (MULTI-PASS)
    # ========================================================================
#    print("\n" + "=" * 60)
#    print("DEPENDENCY RESOLUTION: SECOND PASS (Applying dependencies - Multi-Pass)")
#    print("=" * 60)
    
    # Identify which tasks have dependencies
    tasks_with_dependencies = set(dependency_map.keys())
    
    # We will store the FINAL result for each machine here
    final_timeline_map = {} 

    # We run this loop multiple times to propagate dependency changes across machines.
    # e.g. Machine A changes -> affects Machine B -> affects Machine A's later tasks.
    NUM_PASSES = 3
    
    for pass_idx in range(NUM_PASSES):
        print(f"\n--- Resolution Pass {pass_idx + 1}/{NUM_PASSES} ---")
        changes_detected = False # We could optimize to stop if no changes, but fixed passes is safer/simpler
        
        for machine_id, machine_data in machine_tasks_map.items():
            maquina = machine_data['maquina']
            tasks = machine_data['tasks']
            
            # Check if ANY task in this machine has dependencies OR if we just want to update strictly
            # Actually, even if *this* machine has no dependencies, its tasks might be NEEDED by others.
            # So if we are in Pass 1, we might rely on Pass 0 (Simulated).
            # But 'calculate_timeline' is deterministic if inputs (min_start_times) don't change.
            
            min_start_times = {}
            has_deps_here = False
            
            for t in tasks:
                t_id = t.get('Idorden')
                if t_id in dependency_map:
                    has_deps_here = True
                    preds = dependency_map[t_id]
                    max_pred_end = None
                    
                    for pid in preds:
                        if pid in global_task_end_dates:
                            end_date = global_task_end_dates[pid]
                            if max_pred_end is None or end_date > max_pred_end:
                                max_pred_end = end_date
                    
                    if max_pred_end:
                        min_start_times[t_id] = max_pred_end
                        
                        # Debug logging for our specific tasks
                        if t_id in [46762, 46759]:
                            print(f"  [DEPENDENCY APPLIED] Task {t_id} must start after {max_pred_end} (from predecessors: {preds})")
            
            # Optimization: If no dependencies here, and we already calculated in Pass 0 (First Pass), 
            # we technically don't need to re-run unless we want to be super safe. 
            # But First Pass didn't use `min_start_times`. So YES, we must run at least once if there are deps.
            # If Pass > 0 and no input changes... but let's just run it. It's fast.
            
            recalculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, task_min_start_times=min_start_times)
            
            # SAVE RESULT
            final_timeline_map[machine_id] = {
                'machine': maquina,
                'tasks': recalculated_tasks
            }
            
            # CRITICAL: Update Global End Dates LIVE for next machines/next pass
            for ct in recalculated_tasks:
                 ct_id = ct.get('Idorden')
                 ct_end = ct.get('end_date')
                 if ct_id and ct_end:
                     global_task_end_dates[ct_id] = ct_end
            
            print(f"  Machine {machine_id}: Recalculated {len(recalculated_tasks)} tasks")

    # Build final list
    # Ensure preservation of order if possible (not strictly required since we group by machine)
    from .planning_service import get_active_maintenances
    for machine_id in machine_tasks_map.keys(): # Use original keys ordering
        if machine_id in final_timeline_map:
            row = final_timeline_map[machine_id]
            m = row['machine']
            if hasattr(m, 'id_maquina') and m.id_maquina != 'MAC00':
                row['maintenances'] = get_active_maintenances(m)
            else:
                row['maintenances'] = []
            timeline_data.append(row)
    
    # FILTER: REMOVED per user request ("no las ocultes")
    # We keep empty rows to allow Drag and Drop to empty machines
    # timeline_data = [row for row in timeline_data if row['tasks']]

#    print("=" * 60)
#    print(f"DEPENDENCY RESOLUTION COMPLETE")
#    print(f"Total tasks processed: {len(global_task_end_dates)}")
#    print("=" * 60 + "\n")
        
    # 3. Determine Visual Bounds (Min/Max working hours)
    global_min_h = 24
    global_max_h = 0
    has_schedules = False
    
    for m in maquinas:
        for h in m.horarios.all():
            has_schedules = True
            if h.hora_inicio.hour < global_min_h:
                global_min_h = h.hora_inicio.hour
            if h.hora_fin.hour > global_max_h:
                global_max_h = h.hora_fin.hour
    
    if not has_schedules:
        global_min_h = 7
        global_max_h = 18
    else:
        # Buffer ensures we see the closing hour block?
        # If max is 22, range(7, 22) stops at 21:59. Correct.
        pass
        
    if global_max_h <= global_min_h:
        global_max_h = 23
        global_min_h = 0

    # 4. Generate Time Columns (Filtering non-working hours)
    # Align start to the min_hour of the start day
    min_date = start_simulation.replace(hour=global_min_h, minute=0, second=0, microsecond=0)
    
    # Calculate Max Date from tasks
    calc_max_date = min_date + timedelta(hours=48)
    for row in timeline_data:
        for t in row['tasks']:
            if t['end_date'] and t['end_date'] > calc_max_date:
                calc_max_date = t['end_date']
    
    # Determine which days are "Working Days" to display
    # Iterate from min_date to calc_max_date
    # Rules: 
    # - Always include Mon-Fri (LV)
    # - Include Sat (SA) ONLY if at least one machine has simple schedule 'SA' or we default to showing it?
    #   Let's check if any machine has 'SA' in its schedules.
    show_saturdays = False
    for m in maquinas:
        for h in m.horarios.all():
            if h.dia == 'SA':
                show_saturdays = True
                break
        if show_saturdays: break
        
    # Strict list of valid dates for columns
    valid_dates = []
    day_pointer = min_date.date()
    end_date_limit = calc_max_date.date()
    day_count = (end_date_limit - day_pointer).days + 5 # Buffer
    
    for d in range(day_count):
        current_day = day_pointer + timedelta(days=d)
        wd = current_day.weekday() # 0=Mon, 6=Sun
        
        is_working_day = False
        if 0 <= wd <= 4: # Mon-Fri
            is_working_day = True
        elif wd == 5 and show_saturdays: # Sat
            is_working_day = True
            
        if is_working_day:
            valid_dates.append(current_day)
            
    # Map Date -> Column Index Start (Visual Day Index)
    # e.g. Mon=0, Tue=1, (Sat skip), Mon=2...
    date_to_visual_index = { d: i for i, d in enumerate(valid_dates) }

    # Generate Columns
    time_columns = []
    slots_per_day = global_max_h - global_min_h
    
    for d in valid_dates:
        for h in range(global_min_h, global_max_h):
             dt = datetime.combine(d, datetime.min.time()) + timedelta(hours=h)
             time_columns.append(dt)

    # =========================================================
    # 5. POSICIONAMIENTO DEFINITIVO - ANTI-SOLAPAMIENTO
    # Regla: visual_left[n] = max(time_pos[n], cursor[n-1] + GAP)
    # MIN_WIDTH = 100px universal — ninguna card puede ser menor.
    # =========================================================
    COL_WIDTH  = 40    # px por hora
    MIN_WIDTH  = 100   # px mínimo de card (cubre badge "40D ATRASO" + padding)
    SAFETY_GAP = 6     # px de aire entre cards
    
    def _time_to_px(dt_obj):
        day_idx = date_to_visual_index.get(dt_obj.date(), 0)
        h_diff  = (dt_obj.hour - global_min_h) + (dt_obj.minute / 60.0)
        if h_diff < 0: h_diff = 0
        return ((day_idx * slots_per_day) + h_diff) * COL_WIDTH

    for row in timeline_data:

        # Paso 1 — lista unificada (tareas + mantenimientos) con ancho_total_elemento
        events = []
        for t in row['tasks']:
            if not t.get('start_date'):
                continue
            raw_left        = _time_to_px(t['start_date'])
            duration_px     = t['duration_real'] * COL_WIDTH
            # ancho_total_elemento: mínimo 100px siempre
            ancho_total     = max(MIN_WIDTH, duration_px)
            events.append({'obj': t, 'raw_left': raw_left, 'ancho': ancho_total, 'is_maint': False})

        for m in row.get('maintenances', []):
            raw_left    = _time_to_px(m['start'])
            maint_px    = (m['end'] - m['start']).total_seconds() / 3600.0 * COL_WIDTH
            ancho_total = max(MIN_WIDTH, maint_px)
            events.append({'obj': m, 'raw_left': raw_left, 'ancho': ancho_total, 'is_maint': True})

        # Paso 2 — ordenar por tiempo real
        events.sort(key=lambda e: e['raw_left'])

        # Paso 3 — push acumulativo
        # cursor  = borde derecho del último elemento YA posicionado
        cursor = -9999.0
        for ev in events:
            # REGLA CENTRAL: left[n] = max(time_pos, fin_anterior + gap)
            final_left = max(ev['raw_left'], cursor + SAFETY_GAP)
            ev['obj']['visual_left']  = round(final_left, 2)
            ev['obj']['visual_width'] = round(ev['ancho'],  2)
            cursor = final_left + ev['ancho']
            # Diagnóstico en consola
            oid  = ev['obj'].get('Idorden', 'MAINT')
            is_d = ev['obj'].get('is_delayed', False)
            print(f"  [POS] OP={oid} delayed={is_d} left={final_left:.0f} width={ev['ancho']:.0f} cursor={cursor:.0f}")



    # Build dependencies list for JSON (for visualization)
    dependencies_list = []
    for succ_id, pred_ids in dependency_map.items():
        for pred_id in pred_ids:
            dependencies_list.append({'pred': pred_id, 'succ': succ_id})
    
    context = {
        'timeline_data': timeline_data,
        'time_columns': time_columns,
        'start_date': min_date,
        'dependencies_json': json.dumps(dependencies_list),
    }
    return render(request, 'produccion/planificacion_visual.html', context)

def maquina_config_create_update(request, pk=None):
    """
    Create or Update a machine.
    """
    maquina = None
    if pk:
        maquina = get_object_or_404(MaquinaConfig.objects.using('default'), pk=pk)
    
    if request.method == 'POST':
        id_maquina = request.POST.get('id_maquina')
        nombre = request.POST.get('nombre')
        
        if not id_maquina or not nombre:
            messages.error(request, "Todos los campos son obligatorios")
            return redirect('maquina_config_list')
            
        try:
            if maquina:
                 # Update
                 new_id = id_maquina # From POST
                 
                 if new_id != maquina.pk:
                     # ID Changed: Rename Logic
                     if MaquinaConfig.objects.using('default').filter(pk=new_id).exists():
                         messages.error(request, f"El ID '{new_id}' ya existe. No se puede renombrar.")
                         return render(request, 'produccion/maquina_config_form.html', {'maquina': maquina})
                     
                     # 1. Create New
                     new_maquina = MaquinaConfig.objects.using('default').create(id_maquina=new_id, nombre=nombre)
                     
                     # 2. Move Related Horarios
                     for horario in maquina.horarios.all():
                         horario.maquina = new_maquina
                         horario.save(using='default')
                         
                     # 3. Delete Old
                     maquina.delete(using='default')
                     messages.success(request, f"MÃ¡quina renombrada a '{new_id}' y actualizada correctamente")
                 else:
                     # Standard Update
                     maquina.nombre = nombre
                     maquina.save(using='default')
                     messages.success(request, "MÃ¡quina actualizada correctamente")
            else:
                 # Create
                 if MaquinaConfig.objects.using('default').filter(pk=id_maquina).exists():
                     messages.error(request, "El ID de mÃ¡quina ya existe")
                     return redirect('maquina_config_list')
                     
                 MaquinaConfig.objects.using('default').create(id_maquina=id_maquina, nombre=nombre)
                 messages.success(request, "MÃ¡quina creada correctamente")
                 
            return redirect('maquina_config_list')
        except Exception as e:
            messages.error(request, f"Error: {e}")
    
    return render(request, 'produccion/maquina_config_form.html', {'maquina': maquina})

def maquina_config_delete(request, pk):
    if request.method == 'POST':
        maquina = get_object_or_404(MaquinaConfig.objects.using('default'), pk=pk)
        maquina.delete(using='default')
        messages.success(request, "MÃ¡quina eliminada")
    return redirect('maquina_config_list')

def horario_maquina_create(request, maquina_id):
    if request.method == 'POST':
        maquina = get_object_or_404(MaquinaConfig.objects.using('default'), pk=maquina_id)
        dia = request.POST.get('dia')
        hora_inicio = request.POST.get('hora_inicio')
        hora_fin = request.POST.get('hora_fin')
        
        try:
            HorarioMaquina.objects.using('default').create(
                maquina=maquina,
                dia=dia,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin
            )
            messages.success(request, "Horario agregado")
        except Exception as e:
            messages.error(request, f"Error al agregar horario: {e}")
            
    return redirect('maquina_config_list')

def horario_maquina_delete(request, pk):
    if request.method == 'POST':
        horario = get_object_or_404(HorarioMaquina.objects.using('default'), pk=pk)
        horario.delete(using='default')
        messages.success(request, "Horario eliminado")
    return redirect('maquina_config_list')

import openpyxl
from openpyxl.styles import PatternFill, Border, Side, Alignment, Font, Color, NamedStyle
from openpyxl.utils import get_column_letter
from datetime import timedelta



# --- Feriados Views ---

from .models import Feriado
from .forms import FeriadoForm, MantenimientoMaquinaForm
from django.db.models import Q
from .models import MantenimientoMaquina

# ==========================================
# GESTIÓN DE MANTENIMIENTOS
# ==========================================

def mantenimiento_list(request):
    mantenimientos = MantenimientoMaquina.objects.using('default').all().order_by('-fecha_inicio')
    
    # Optional filtering
    maq_id = request.GET.get('maquina')
    if maq_id:
        mantenimientos = mantenimientos.filter(maquina_id=maq_id)
        
    estado = request.GET.get('estado')
    if estado:
        mantenimientos = mantenimientos.filter(estado=estado)
        
    context = {
        'mantenimientos': mantenimientos,
        'maquinas': MaquinaConfig.objects.using('default').all(),
        'selected_maq': maq_id,
        'selected_estado': estado
    }
    return render(request, 'produccion/mantenimiento_list.html', context)

def mantenimiento_create_update(request, pk=None):
    if pk:
        mantenimiento = get_object_or_404(MantenimientoMaquina.objects.using('default'), pk=pk)
        title = "Editar Mantenimiento"
    else:
        mantenimiento = None
        title = "Programar Mantenimiento"
        
    if request.method == 'POST':
        form = MantenimientoMaquinaForm(request.POST, instance=mantenimiento)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.save(using='default')
            messages.success(request, f'Mantenimiento {"actualizado" if pk else "programado"} exitosamente.')
            return redirect('mantenimiento_list')
    else:
        form = MantenimientoMaquinaForm(instance=mantenimiento)
        
    context = {
        'form': form,
        'title': title,
        'is_edit': bool(pk)
    }
    return render(request, 'produccion/mantenimiento_form.html', context)

def mantenimiento_delete(request, pk):
    mantenimiento = get_object_or_404(MantenimientoMaquina.objects.using('default'), pk=pk)
    if request.method == 'POST':
        mantenimiento.delete()
        messages.success(request, 'Mantenimiento eliminado correctamente.')
        return redirect('mantenimiento_list')
    return render(request, 'produccion/mantenimiento_confirm_delete.html', {'mantenimiento': mantenimiento})


# ==========================================
# GESTIÓN DE FERIADOS
# ==========================================

def feriado_list(request):
    """
    Lista todos los feriados con filtros opcionales y paginación.
    """
    from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
    
    # Filtros
    year_filter = request.GET.get('year')
    
    feriados = Feriado.objects.filter(activo=True)
    
    # Filtro por año
    selected_year = None
    if year_filter:
        try:
            selected_year = int(year_filter)
            feriados = feriados.filter(fecha__year=selected_year)
        except ValueError:
            pass
    
    # Obtener años disponibles para el filtro
    years = Feriado.objects.dates('fecha', 'year', order='DESC')
    available_years = [d.year for d in years]
    
    # Paginación
    paginator = Paginator(feriados, 8)  # 8 feriados por página
    page = request.GET.get('page')
    
    try:
        feriados_page = paginator.page(page)
    except PageNotAnInteger:
        # Si page no es un entero, mostrar la primera página
        feriados_page = paginator.page(1)
    except EmptyPage:
        # Si page está fuera de rango, mostrar la última página
        feriados_page = paginator.page(paginator.num_pages)
    
    context = {
        'feriados': feriados_page,
        'available_years': available_years,
        'selected_year': selected_year,
    }
    
    return render(request, 'produccion/feriado_list.html', context)


def feriado_create(request):
    """
    Crear un nuevo feriado desde el formulario simplificado.
    """
    if request.method == 'POST':
        # Obtener datos del formulario simplificado
        fecha = request.POST.get('fecha')
        descripcion = request.POST.get('descripcion')
        
        if not fecha or not descripcion:
            messages.error(request, 'Por favor complete todos los campos.')
            return redirect('feriado_list')
        
        try:
            # Verificar que no exista otro feriado en la misma fecha
            if Feriado.objects.filter(fecha=fecha).exists():
                messages.error(request, f'Ya existe un feriado registrado para la fecha {fecha}')
                return redirect('feriado_list')
            
            # Crear el feriado con valores por defecto
            feriado = Feriado.objects.create(
                fecha=fecha,
                descripcion=descripcion,
                tipo_jornada='NO',  # Por defecto no se trabaja
                activo=True
            )
            messages.success(request, f'Feriado "{feriado.descripcion}" creado exitosamente.')
            return redirect('feriado_list')
        except Exception as e:
            messages.error(request, f'Error al crear el feriado: {str(e)}')
            return redirect('feriado_list')
    else:
        form = FeriadoForm()
    
    return render(request, 'produccion/feriado_form.html', {
        'form': form,
        'title': 'Crear Nuevo Feriado',
        'button_text': 'Crear Feriado'
    })


def feriado_update(request, pk):
    """
    Editar un feriado existente.
    """
    feriado = get_object_or_404(Feriado, pk=pk)
    
    if request.method == 'POST':
        form = FeriadoForm(request.POST, instance=feriado)
        if form.is_valid():
            feriado = form.save()
            messages.success(request, f'Feriado "{feriado.descripcion}" actualizado exitosamente.')
            return redirect('feriado_list')
        else:
            messages.error(request, 'Por favor corrija los errores en el formulario.')
    else:
        form = FeriadoForm(instance=feriado)
    
    return render(request, 'produccion/feriado_form.html', {
        'form': form,
        'feriado': feriado,
        'title': f'Editar Feriado: {feriado.descripcion}',
        'button_text': 'Guardar Cambios'
    })


def feriado_delete(request, pk):
    """
    Eliminar un feriado.
    """
    feriado = get_object_or_404(Feriado, pk=pk)
    
    if request.method == 'POST':
        descripcion = feriado.descripcion
        feriado.delete()
        messages.success(request, f'Feriado "{descripcion}" eliminado exitosamente.')
        return redirect('feriado_list')
    
    return render(request, 'produccion/feriado_confirm_delete.html', {
        'feriado': feriado
    })


@csrf_exempt
def feriado_toggle_planifica(request, pk):
    """
    API para cambiar rÃ¡pidamente el estado de planificaciÃ³n de un feriado.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        feriado = get_object_or_404(Feriado, pk=pk)
        feriado.se_planifica = not feriado.se_planifica
        feriado.save()
        
        return JsonResponse({
            'status': 'ok',
            'se_planifica': feriado.se_planifica,
            'message': f'Feriado {"se trabajarÃ¡" if feriado.se_planifica else "no se trabajarÃ¡"}'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def feriado_toggle_activo(request, pk):
    """
    API para activar/desactivar un feriado.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        feriado = get_object_or_404(Feriado, pk=pk)
        feriado.activo = not feriado.activo
        feriado.save()
        
        return JsonResponse({
            'status': 'ok',
            'activo': feriado.activo,
            'message': f'Feriado {"activado" if feriado.activo else "desactivado"}'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def feriado_update_jornada(request, pk):
    """
    API para actualizar el tipo de jornada de un feriado.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        import json
        feriado = get_object_or_404(Feriado, pk=pk)
        
        # Obtener el nuevo tipo de jornada del body
        data = json.loads(request.body)
        nuevo_tipo = data.get('tipo_jornada', 'NO')
        
        # Validar que el tipo sea válido
        if nuevo_tipo not in ['NO', 'MEDIO', 'SI']:
            return JsonResponse({'error': 'Tipo de jornada inválido'}, status=400)
        
        # Actualizar el feriado
        feriado.tipo_jornada = nuevo_tipo
        feriado.save()
        
        return JsonResponse({
            'status': 'ok',
            'tipo_jornada': feriado.tipo_jornada,
            'message': f'Tipo de jornada actualizado a {feriado.get_tipo_jornada_display()}'
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# =========================================================================
# NEW SHARED LOGIC IMPLEMENTATION
# =========================================================================

def planificacion_visual(request):
    """
    Visual Gantt Chart View.
    Uses shared logic from gantt_logic.py
    """
    # Use shared logic
    data = get_gantt_data(request)
    
    # Extract data for context
    timeline_data = data['timeline_data']
    time_columns = data['time_columns']
    valid_dates = data['valid_dates']
    start_simulation = data['start_simulation']
    dependency_map = data['dependency_map']
    global_min_h = data['global_min_h']
    global_max_h = data['global_max_h']
    day_max_hours = data.get('day_max_hours', {})
    date_start_col = data.get('date_start_col', {})

    # =========================================================
    # 5. POSICIONAMIENTO DINÁMICO (ANTI-SOLAPAMIENTO)
    # Regla: visual_left = max(posición_por_tiempo, fin_anterior + 6px)
    # Para OPs con atraso, garantizamos un ancho visual de 100px.
    # =========================================================
    COL_WIDTH = 40
    DAY_GAP = 10
    
    # Mapa de fechas a índice visual
    date_to_day_idx = {d: i for i, d in enumerate(valid_dates)}
    
    for row in timeline_data:
        # --- Paso 1: Recolectar todos los elementos de la fila (ordenados por tiempo) ---
        elements = []
        for t in row['tasks']:
            t_start = t.get('start_date')
            if not t_start: continue
            
            day_idx = date_to_day_idx.get(t_start.date(), 0)
            day_col_start = date_start_col.get(t_start.date(), 0)
            hour_diff = float((t_start.hour - global_min_h) + (t_start.minute / 60.0))
            if hour_diff < 0: hour_diff = 0
            
            time_left = (day_col_start + hour_diff) * COL_WIDTH + (day_idx * DAY_GAP)
            duration_px = t.get('duration_real', 0) * COL_WIDTH
            elements.append({'obj': t, 'time_left': time_left, 'duration_px': duration_px, 'is_maint': False})

        for m in row.get('maintenances', []):
            m_s = m.get('start')
            if not m_s: continue
            m_dur_px = (m['end'] - m['start']).total_seconds() / 3600.0 * COL_WIDTH
            day_idx = date_to_day_idx.get(m_s.date(), 0)
            day_col_start = date_start_col.get(m_s.date(), 0)
            hour_diff = float((m_s.hour - global_min_h) + (m_s.minute / 60.0))
            if hour_diff < 0: hour_diff = 0
            time_left = (day_col_start + hour_diff) * COL_WIDTH + (day_idx * DAY_GAP)
            elements.append({'obj': m, 'time_left': time_left, 'duration_px': m_dur_px, 'is_maint': True})

        # Ordenar por tiempo de inicio real
        elements.sort(key=lambda x: x['time_left'])

        # --- Paso 2: Posicionamiento Temporal Estricto con Escalonamiento de Badges ---
        cursor_card_end = -9999.0
        cursor_badge_end = -9999.0
        stagger_level = 0 # 0=normal, 1=alto
        
        for el in elements:
            obj = el['obj']
            # Normalización robusta del ID para el frontend
            try:
                obj['Idorden'] = str(int(float(obj.get('Idorden', 0))))
            except:
                obj['Idorden'] = str(obj.get('Idorden', ''))

            # 1. Ancho NATURAL (mínimo 24px para ser accionable)
            natural_w = max(24, el['duration_px']) 
            
            # 2. El inicio (left) solo se empuja si las CARDS físicas colisionan (overlap real)
            final_left = max(el['time_left'], cursor_card_end + 3)
            
            obj['visual_left']  = round(final_left, 2)
            obj['visual_width'] = round(natural_w, 2)
            
            # 3. Lógica de Escalonamiento de Badges (Staggering)
            has_badge = obj.get('is_delayed') and obj.get('segment_index', 0) == 0
            if has_badge:
                if final_left < (cursor_badge_end + 5):
                     stagger_level = (stagger_level + 1) % 2
                else:
                     stagger_level = 0
                
                obj['badge_stagger'] = stagger_level
                cursor_badge_end = final_left + 95
            
            # El cursor de tiempo solo avanza con la tarjeta física
            cursor_card_end = final_left + natural_w


    # Build time columns with gap info
    time_columns_data = []
    last_date = None
    total_gaps = 0
    for dt in time_columns:
        curr_date = dt.date()
        is_day_start = (curr_date != last_date)
        if is_day_start and last_date is not None:
            total_gaps += 1
        
        time_columns_data.append({
            'datetime': dt,
            'is_day_start': is_day_start
        })
        last_date = curr_date

    # Build dependencies list for JSON
    # To handle hidden tasks, we need to find the "first visible predecessor" for each visible task
    dependencies_list = []
    visible_tids = {str(t['Idorden']) for row in timeline_data for t in row['tasks']}
    
    def get_visible_preds(tid, visited=None):
        if visited is None: visited = set()
        if tid in visited: return []
        visited.add(tid)
        
        preds = dependency_map.get(tid, [])
        v_preds = []
        for pid in preds:
            s_pid = str(pid)
            # Try cleaning for match
            try: clean_p = str(int(float(s_pid)))
            except: clean_p = s_pid
            
            if clean_p in visible_tids:
                v_preds.append(clean_p)
            else:
                # Recursively look for visible predecessors of this hidden task
                v_preds.extend(get_visible_preds(s_pid, visited))
        return v_preds

    for succ_id in visible_tids:
        v_preds = get_visible_preds(succ_id)
        for pred_id in set(v_preds): # Deduplicate
            dependencies_list.append({'pred': pred_id, 'succ': succ_id})
    
    print(f"DEBUG: [Dependencies] Grafo reconstruido (saltando ocultos): {len(dependencies_list)} vínculos encontrados.")
    
    print(f"DEBUG: [Dependencies] Grafo generado: {len(dependencies_list)} vínculos encontrados.")

    # Fetch all scenarios for selector (used in template)
    from .models import Scenario
    all_scenarios = Scenario.objects.using('default').all().order_by('-es_principal', 'nombre')

    # Calculate actual total width in pixels
    calculated_total_width = (len(time_columns) * COL_WIDTH) + (total_gaps * DAY_GAP)

    context = {
        'timeline_data': timeline_data,
        'time_columns': time_columns_data, # Use the new data structure
        'start_date': start_simulation,
        'dependencies_json': json.dumps(dependencies_list),
        'today': start_simulation,
        'total_width': calculated_total_width,
        'system_alerts': data.get('system_alerts', []),
        'analysis': data.get('analysis', {'machines': [], 'project_alerts': []}),
        'all_scenarios': all_scenarios,
        'active_scenario': data.get('active_scenario', None),
        'plan_mode': data.get('plan_mode', 'manual'),
    }


    # DEBUG: Log results for redistribution checking
    adaptive_alerts_count = len(data.get('analysis', {}).get('adaptive_alerts', []))
    print(f"DEBUG: [View] Fallas encontradas en adaptive_alerts: {adaptive_alerts_count}")

    return render(request, 'produccion/planificacion_visual.html', context)


def export_planificacion_excel(request):
    try:
        # 1. Obtener Datos
        data = get_gantt_data(request, force_run=True)
        timeline_data = data['timeline_data']
        time_columns = data['time_columns']
        global_min_h = data['global_min_h']
        global_max_h = data['global_max_h']
        active_scenario = data.get('active_scenario')
        
        if not time_columns:
             return HttpResponse("No hay datos calculados. Ejecute la planificacion visual primero.")

        # 2. GENERACION EXCEL
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Gantt Visual"
        ws.sheet_view.showGridLines = False 

        COLS_PER_HOUR = 6 
        hours_per_day = (global_max_h - global_min_h)
        unique_dates = []
        for dt in time_columns:
            if dt.date() not in unique_dates:
                unique_dates.append(dt.date())
        date_to_index = {d: i for i, d in enumerate(unique_dates)}
        
        # --- ESTILOS CORPORATIVOS ---
        CORP_DARK      = "27323E" # Carbon Slate
        CORP_BLUE      = "0078D4" # Microsoft Blue
        CORP_RED       = "E81123" # Microsoft Red
        CORP_BORDER    = "D2D2D2" # Light Grey
        ALIGN_CENTER   = Alignment(horizontal='center', vertical='center', wrap_text=True)
        BORDER_THIN    = Border(left=Side(style='thin', color="CCCCCC"), right=Side(style='thin', color="CCCCCC"), top=Side(style='thin', color="CCCCCC"), bottom=Side(style='thin', color="CCCCCC"))
        
        # --- IDENTIFICACION DE PROYECTOS ---
        all_projs = set()
        for r in timeline_data:
            for t in r['tasks']:
                if t.get('ProyectoCode'): all_projs.add(t['ProyectoCode'])
        
        # Paleta Curada y Utilidades de Color
        PALETTE = ["0078D4", "107C10", "D83B01", "5C2D91", "008272", "A4262C", "004E8C", "498205"]
        def get_corp_color(v):
            idx = sum(ord(c) for c in str(v)) % len(PALETTE)
            return PALETTE[idx]

        def tint_color(hex_color, factor=0.85):
            """Genera una versión clara (tintada) de un color hex."""
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            tr = int((1 - 0.15) * 255 + 0.15 * r)
            tg = int((1 - 0.15) * 255 + 0.15 * g)
            tb = int((1 - 0.15) * 255 + 0.15 * b)
            return f"{tr:02X}{tg:02X}{tb:02X}"

        def darken_color(hex_color, factor=0.7):
            """Genera una versión más oscura de un color hex."""
            hex_color = hex_color.lstrip('#')
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            dr = int(r * factor); dg = int(g * factor); db = int(b * factor)
            return f"{dr:02X}{dg:02X}{db:02X}"

        proyecto_color_map = {p: get_corp_color(p) for p in all_projs}

        # Helper para bordes precisos en rangos combinados
        def set_border(ws, start_row, end_row, start_col, end_col, border):
            for r in range(start_row, end_row + 1):
                for c in range(start_col, end_col + 1):
                    ws.cell(row=r, column=c).border = border

        from openpyxl.cell.cell import MergedCell

        # =========================================================
        # ESTÁNDAR CÁPSULA ENVOLVENTE (REGLA DE ORO: VALOR -> MERGE -> ESTILO)
        # =========================================================
        def draw_floating_card(ws, label_row, task_row, start_col, end_col, color_hex, proj, op, is_critical=False, is_delayed=False, delay_days=0, is_continuation=False):
            # 1. DETERMINAR VALORES Y COLORES
            task_text = f"PROJECT {proj}\nOP {op}" if proj != "---" else "..."
            if is_delayed and delay_days > 0:
                label_text = f"[ {delay_days}D ATRASO ]"
                label_color = "EF4444"
            elif is_critical:
                label_text = "[ RUTA CRÍTICA ]"
                label_color = "F97316"
            else:
                label_text = f"PROJECT {proj}"
                label_color = "1E3A8A"

            # Colores del proyecto
            proj_rgb = color_hex.upper()
            bg_tint = tint_color(proj_rgb) # Fondo suave del color del proyecto

            # 2. DEFINICIÓN DE BORDES (Perímetro Envolvente)
            side_identity = Side(style='thick', color=proj_rgb)
            side_outline  = Side(style='thin', color=proj_rgb)
            
            # 3. RENDERIZADO CELDA POR CELDA (Seguro para border/fill, NO para value)
            for c in range(start_col, end_col + 1):
                # Cuerpo de Tarea
                cell_t = ws.cell(row=task_row, column=c)
                cell_t.fill = PatternFill("solid", fgColor=bg_tint)
                
                # Construir borde dinámico según posición
                l = side_identity if c == start_col else None
                r = side_outline if c == end_col else None
                cell_t.border = Border(left=l, right=r, top=side_outline, bottom=side_outline)
                
                if c == start_col:
                    if not isinstance(cell_t, MergedCell):
                        cell_t.value = task_text
                    cell_t.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                    cell_t.font = Font(name='Segoe UI', bold=True, size=8, color="1E293B")

                # Sticker Superior
                cell_l = ws.cell(row=label_row, column=c)
                cell_l.fill = PatternFill("solid", fgColor=label_color)
                cell_l.border = Border(left=side_outline if c == start_col else None, 
                                       right=side_outline if c == end_col else None, 
                                       top=side_outline, bottom=side_outline)
                
                if c == start_col:
                    if not isinstance(cell_l, MergedCell):
                        cell_l.value = label_text
                    cell_l.font = Font(name='Segoe UI', bold=True, size=7, color="FFFFFF")
                    cell_l.alignment = Alignment(horizontal='center', vertical='center')

            # 4. MERGE FINAL (Para asegurar coherencia en Excel)
            if end_col > start_col:
                try: ws.merge_cells(start_row=task_row, start_column=start_col, end_row=task_row, end_column=end_col)
                except: pass
                try: ws.merge_cells(start_row=label_row, start_column=start_col, end_row=label_row, end_column=end_col)
                except: pass

        # --- CONFIGURACIÓN DE PÁGINA Y ENCABEZADOS (Fidelity Style) ---
        ws.sheet_view.showGridLines = False
        grid_width = (len(time_columns) * COLS_PER_HOUR)
        
        from openpyxl.cell.rich_text import CellRichText, TextBlock
        from openpyxl.cell.text import InlineFont
        from openpyxl.styles import Color

        # --- CABECERA PREMIUM (Rows 1-2) ---
        header_bg = PatternFill("solid", fgColor="F8FAFC")
        for r in range(1, 4):
            for c in range(1, 2 + grid_width):
                ws.cell(row=r, column=c).fill = header_bg

        ws.row_dimensions[1].height = 30
        ws.row_dimensions[2].height = 20
        
        # TÍTULO: VALOR -> MERGE
        c_title = ws.cell(row=1, column=1)
        font_black = InlineFont(); font_black.rFont = 'Segoe UI'; font_black.b = True; font_black.sz = 16.0; font_black.color = Color(rgb="0F172A")
        font_blue = InlineFont(); font_blue.rFont = 'Segoe UI'; font_blue.b = True; font_blue.sz = 16.0; font_blue.color = Color(rgb="2563EB")
        c_title.value = CellRichText([TextBlock(font_black, "Planificación "), TextBlock(font_blue, "Visual")])
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=15)
        c_title.alignment = Alignment(horizontal='left', vertical='center', indent=1)

        # SUBTÍTULO: VALOR -> MERGE
        c_sub = ws.cell(row=2, column=1)
        c_sub.value = "Control de línea ABBAMAT"
        ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=15)
        c_sub.font = Font(name='Segoe UI', size=9, color="64748B")
        c_sub.alignment = Alignment(horizontal='left', vertical='top', indent=1)

        ws.column_dimensions['A'].width = 25

        # Render Timeline (Días en fila 3, Horas en fila 4)
        # El header premium ocupa filas 1-2 y NO colisiona con el timeline
        # porque el timeline empieza en columna 2+
        current_day, start_m = None, -1
        header_fill = PatternFill("solid", fgColor="F1F5F9")
        header_border = Border(
            left=Side(style='thin', color="E2E8F0"), right=Side(style='thin', color="E2E8F0"),
            top=Side(style='thin', color="E2E8F0"), bottom=Side(style='thin', color="E2E8F0")
        )
        ROW_DAY = 3   # Fila de encabezados de día
        ROW_HOUR = 4  # Fila de encabezados de hora
        DATA_START = 5  # Primera fila de datos

        # Encabezado MÁQUINA en A3:A4
        c_maq = ws.cell(row=ROW_DAY, column=1)
        if not isinstance(c_maq, MergedCell):
            c_maq.value = "MÁQUINA"
        ws.merge_cells(start_row=ROW_DAY, start_column=1, end_row=ROW_HOUR, end_column=1)
        c_maq.fill = PatternFill("solid", fgColor="F8F9FA")
        c_maq.font = Font(name='Segoe UI', bold=True, size=10, color="64748B")
        c_maq.alignment = Alignment(horizontal='center', vertical='center')
        c_maq.border = Border(bottom=Side(style='thin', color="E2E8F0"), right=Side(style='thin', color="E2E8F0"), top=Side(style='thin', color="E2E8F0"))

        for h_idx, hour in enumerate(time_columns):
            h_col = 2 + (h_idx * COLS_PER_HOUR)

            # HORAS — REGLA DE ORO: valor -> merge -> estilo
            c_h = ws.cell(row=ROW_HOUR, column=h_col)
            if not isinstance(c_h, MergedCell):
                c_h.value = hour.strftime("%H")
            ws.merge_cells(start_row=ROW_HOUR, start_column=h_col, end_row=ROW_HOUR, end_column=h_col + COLS_PER_HOUR - 1)
            c_h.alignment = Alignment(horizontal='center', vertical='center')
            c_h.fill = header_fill
            c_h.border = header_border
            c_h.font = Font(name='Segoe UI', size=8, color="64748B")

            # DÍAS — REGLA DE ORO: valor -> merge -> estilo
            d_str = hour.strftime("%d %b - %a").upper()
            if d_str != current_day:
                if current_day:
                    c_d = ws.cell(row=ROW_DAY, column=start_m)
                    if not isinstance(c_d, MergedCell):
                        c_d.value = current_day
                    ws.merge_cells(start_row=ROW_DAY, start_column=start_m, end_row=ROW_DAY, end_column=h_col - 1)
                    c_d.fill = header_fill
                    c_d.font = Font(name='Segoe UI', bold=True, size=8, color="2563EB")
                    c_d.alignment = Alignment(horizontal='left', vertical='center', indent=1)
                    c_d.border = header_border
                current_day, start_m = d_str, h_col

        if current_day:
            c_d = ws.cell(row=ROW_DAY, column=start_m)
            if not isinstance(c_d, MergedCell):
                c_d.value = current_day
            ws.merge_cells(start_row=ROW_DAY, start_column=start_m, end_row=ROW_DAY, end_column=1 + grid_width)
            c_d.fill = header_fill
            c_d.font = Font(name='Segoe UI', bold=True, size=8, color="2563EB")
            c_d.alignment = Alignment(horizontal='left', vertical='center', indent=1)
            c_d.border = header_border

        ws.column_dimensions['A'].width = 30
        from openpyxl.utils import get_column_letter
        for c in range(2, 2 + grid_width):
            ws.column_dimensions[get_column_letter(c)].width = 2.5
        
        # --- RENDER DE DATOS (desde DATA_START) ---
        current_row = DATA_START
        for row_data in timeline_data:
            maquina = row_data['machine']
            tasks = row_data['tasks']
            if maquina.nombre.upper() == 'SIN ASIGNAR' and not tasks: continue
            
            l_row, t_row = current_row, current_row + 1
            ws.row_dimensions[l_row].height = 11 # 50% altura para etiquetas
            ws.row_dimensions[t_row].height = 38 # Altura para cards
            
            # Sidebar Maquina — REGLA DE ORO: valor -> merge -> estilo
            c_n = ws.cell(row=l_row, column=1)
            if not isinstance(c_n, MergedCell):
                c_n.value = maquina.nombre.upper()
            ws.merge_cells(start_row=l_row, start_column=1, end_row=t_row, end_column=1)
            c_n.alignment = Alignment(horizontal='center', vertical='center')
            c_n.font = Font(name='Segoe UI', bold=True, size=9, color="1E293B")
            c_n.fill = PatternFill("solid", fgColor="F8F9FA")
            c_n.border = Border(bottom=Side(style='thin', color="E2E8F0"), right=Side(style='thin', color="E2E8F0"))
            
            for t in tasks:
                start_date = t.get('start_date')
                if not start_date: continue
                day_idx = date_to_index.get(start_date.date())
                if day_idx is None: continue
                
                h_off = start_date.hour - global_min_h
                m_off = start_date.minute / 10.0
                s_col = int(2 + (day_idx * hours_per_day * COLS_PER_HOUR) + (h_off * COLS_PER_HOUR) + m_off)
                e_col = int(s_col + (t.get('duration_real', 0) * COLS_PER_HOUR))
                
                if s_col < 2: s_col = 2
                if e_col > 2 + grid_width: e_col = 2 + grid_width
                
                if s_col < e_col:
                    draw_floating_card(ws, l_row, t_row, s_col, e_col - 1, 
                                       proyecto_color_map.get(t.get('ProyectoCode'), '0078D4'), 
                                       t.get('ProyectoCode', 'S/P'), t.get('Idorden', ''),
                                       is_critical=t.get('is_critical', False), 
                                       is_delayed=t.get('is_delayed', False), 
                                       delay_days=t.get('delay_days', 0),
                                       is_continuation=t.get('segment_index', 0) > 0)
            current_row += 2

        ws.freeze_panes = f'B{DATA_START}'
        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = f'attachment; filename=Gantt_Produccion.xlsx'
        wb.save(response)
        return response

    except Exception as global_err:
        import traceback
        print(traceback.format_exc())
        return HttpResponse(f"Error critico en Exportacion Excel: {str(global_err)}", status=500)



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
        scenario_id = data.get('id') or data.get('update_id')
        
        with transaction.atomic(using='default'):
            if es_principal:
                Scenario.objects.using('default').filter(es_principal=True).update(es_principal=False)
                
            if scenario_id:
                # Update existing
                scenario = Scenario.objects.using('default').get(pk=scenario_id)
                if nombre:
                    scenario.nombre = nombre
                if descripcion:
                    scenario.descripcion = descripcion
                scenario.es_principal = es_principal
                scenario.proyectos = proyectos
                scenario.save(using='default')
                
                # If we are "overwriting" (copying data from another scenario)
                if copy_from_id and str(copy_from_id) != str(scenario_id):
                    # Clean target scenario first
                    PrioridadManual.objects.using('default').filter(scenario=scenario).delete()
                    ProyectoPrioridad.objects.using('default').filter(scenario=scenario).delete()
                    HiddenTask.objects.using('default').filter(scenario=scenario).delete()
                    
                    # Clone from source
                    source = Scenario.objects.using('default').get(pk=copy_from_id)
                    
                    # Clone Overrides
                    overrides = PrioridadManual.objects.using('default').filter(scenario=source)
                    new_overrides = [
                        PrioridadManual(
                            id_orden=o.id_orden, maquina=o.maquina, prioridad=o.prioridad,
                            tiempo_manual=o.tiempo_manual, nivel_manual=o.nivel_manual,
                            porcentaje_solapamiento=o.porcentaje_solapamiento,
                            fecha_inicio_manual=o.fecha_inicio_manual,
                            scenario=scenario
                        ) for o in overrides
                    ]
                    PrioridadManual.objects.using('default').bulk_create(new_overrides)

                    # Clone Hidden Tasks
                    hidden = HiddenTask.objects.using('default').filter(scenario=source)
                    new_hidden = [
                        HiddenTask(id_orden=h.id_orden, scenario=scenario)
                        for h in hidden
                    ]
                    HiddenTask.objects.using('default').bulk_create(new_hidden)
                    
                    # Clone Project Priorities
                    proj_prios = ProyectoPrioridad.objects.using('default').filter(scenario=source)
                    new_proj_prios = [
                        ProyectoPrioridad(proyecto=p.proyecto, prioridad=p.prioridad, scenario=scenario)
                        for p in proj_prios
                    ]
                    ProyectoPrioridad.objects.using('default').bulk_create(new_proj_prios)

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
        
    # Session Persistence for Proyectos
    proyectos_str = request.GET.get('proyectos')
    if proyectos_str is not None:
        request.session['last_proyectos_filter'] = proyectos_str
    elif 'proyectos' not in request.GET:
        proyectos_str = request.session.get('last_proyectos_filter')

    if not proyectos_str and active_scenario and active_scenario.proyectos:
        proyectos_str = active_scenario.proyectos
    
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
                       
        return JsonResponse({'status': 'ok'})
        
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
    today = datetime.now().date()
    week_monday = today - timedelta(days=today.weekday())
    
    # 1. Get timeline data. 
    # Force simulation to start from Monday so we see the whole week's plan
    if not request.GET.get('fecha_desde'):
        # Create a mutable copy of GET to add the parameter
        mutable_get = request.GET.copy()
        mutable_get['fecha_desde'] = week_monday.isoformat()
        request.GET = mutable_get

    gantt_res = get_gantt_data(request, force_run=True)
    timeline_data = gantt_res.get('timeline_data', [])
    all_valid_dates = gantt_res.get('valid_dates', [])
    
    # --- FILTER: Only current week, Monday to Friday ---
    today = datetime.now().date()
    # Monday of current week (weekday(): Mon=0, Sun=6)
    week_monday = today - timedelta(days=today.weekday())
    week_friday = week_monday + timedelta(days=4)
    
    # Keep only working days (Mon-Fri) within the current week
    valid_dates = [
        d for d in all_valid_dates
        if d.weekday() < 5 and week_monday <= d <= week_friday
    ]
    
    # If no dates available for current week, fallback to all working dates (next 5 days Mon-Fri)
    if not valid_dates:
        valid_dates = [d for d in all_valid_dates if d.weekday() < 5][:5]
        # Recalculate boundaries for fallback
        if valid_dates:
            week_monday = valid_dates[0] - timedelta(days=valid_dates[0].weekday())
            week_friday = week_monday + timedelta(days=4)
        else:
            week_monday = today - timedelta(days=today.weekday())
            week_friday = week_monday + timedelta(days=4)
    
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
        
        # Initialize dates dictionary - only for current week dates
        for v_date in valid_dates:
             daily_plan[m_id]['dates'][v_date.isoformat()] = []
             
        # Group segments by Task ID to distribute quantity discretely across days
        task_segments = []
        for segment in machine_row['tasks']:
            start = segment.get('start_date')
            if not start: continue
            task_segments.append(segment)
            
        # Map to track distributed quantity for each task in this machine
        # (A task might have multiple segments if it's interrupted by a non-working period)
        processed_qty_map = defaultdict(float) # idorden -> total distributed so far
        
        # We need another pass or a stateful approach. 
        # But since we are inside machine_row, we can do it row by row.
        
        # To ensure total quantity is preserved, we first count segments per task
        segments_per_task = defaultdict(int)
        for seg in task_segments:
            tid = str(seg.get('Idorden'))
            segments_per_task[tid] += 1
            
        current_segment_index = defaultdict(int)
        processed_qty_map = defaultdict(float) # idorden -> total distributed so far
        
        for segment in task_segments:
            start = segment.get('start_date')
            d_str = start.date().isoformat()
            
            if d_str not in daily_plan[m_id]['dates']:
                continue
            
            t_id = str(segment.get('Idorden'))
            
            # Unified Quantity: uses the lowercase aliases from services.py SQL
            # cantidad_final = MAX(T.Cantidad, T3.Cantidad, T.Lote) - the true lot size
            cant_total = float(segment.get('cantidad_final') or segment.get('Cantidad_Final') or 0.0)
            cant_prod = float(segment.get('cantidad_producida') or segment.get('Cantidadpp') or 0.0)
            
            # Pending = Total - Already Produced
            qty_pend = cant_total - cant_prod
            if qty_pend < 0: qty_pend = 0.0
            
            total_duration = float(segment.get('Tiempo_Proceso') or 0.001)
            if total_duration <= 0: total_duration = 0.001
            
            segment_duration = float(segment.get('duration_real') or 0.0)
            
            # Tracking segment count to handle the last segment correctly
            current_segment_index[t_id] += 1
            is_last_segment = current_segment_index[t_id] == segments_per_task[t_id]
            
            if is_last_segment:
                # Take all remaining quantity for this task to reach the exact total
                segment_qty = qty_pend - processed_qty_map[t_id]
            else:
                # Proportional distribution but forced to 0.5 steps (1, 2, 5, etc or 0.5)
                # Mathematical rounding to nearest 0.5
                raw_qty = qty_pend * (segment_duration / total_duration)
                segment_qty = round(raw_qty * 2.0) / 2.0
                
                # Check for exceeding total
                if processed_qty_map[t_id] + segment_qty > qty_pend:
                    segment_qty = qty_pend - processed_qty_map[t_id]
            
            # Ensure it never goes negative due to weird floating point subtractions
            if segment_qty < 0: segment_qty = 0.0
            
            processed_qty_map[t_id] += segment_qty
            
            # Standard Time Unit per piece
            std_t = float(segment.get('Tiempo') or 0.0)
            
            # Total Standard Time for this day's quantity
            # User requirement: Horas Totales = Tiempo STD * Cantidad
            # NO USAR segment_duration para el campo 'Horas Totales' de la planilla
            total_std_time = std_t * segment_qty

            if segment_qty > 0 or segment_duration > 0:
                # Format Horas Totales (Standard Total) - Redondear a lo más cercano para evitar desvíos decimales
                h_tot = int(total_std_time)
                m_tot = int(round((total_std_time - h_tot) * 60))
                if m_tot >= 60:
                    h_tot += 1
                    m_tot = 0
                tiempo_dia_hm = f"{h_tot}:{m_tot:02d}h"

                # Standard Time Unit (Formatted for display)
                h_standard = int(std_t)
                m_standard = int(round((std_t - h_standard) * 60))
                if m_standard >= 60:
                    h_standard += 1
                    m_standard = 0
                tiempo_standard_hm = f"{h_standard}:{m_standard:02d}h"


                daily_plan[m_id]['dates'][d_str].append({
                    'orden': t_id,
                    'proyecto': segment.get('ProyectoCode'),
                    'denominacion': segment.get('Denominacion'),
                    'descripcion': segment.get('Descri'),
                    'tiempo_standard': tiempo_standard_hm, 
                    'cantidad_dia': segment_qty,
                    'tiempo_dia': tiempo_dia_hm,
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
    
    # Spanish nicely formatted dates - FORCE FULL WEEK Lunes-Viernes
    DAYS_ES = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    nice_target_dates = []
    
    curr = week_monday
    while curr <= week_friday:
        if curr.weekday() < 5: # Only Mon-Fri
            nice_target_dates.append((curr.isoformat(), f"{DAYS_ES[curr.weekday()]} {curr.strftime('%d/%m')}"))
        curr += timedelta(days=1)
    
    context = {
        'daily_plan': daily_plan_list,
        'target_dates': nice_target_dates,
        'active_scenario': gantt_res.get('active_scenario')
    }
    
    return render(request, 'produccion/planillas_diarias.html', context)

def ai_planning_suggest_api(request):
    """
    API endpoint que devuelve sugerencias de IA para la planificación de producción.
    """
    from .ai_planning_service import get_ai_planning_suggestion
    
    if not request.GET.get('run') == '1':
        return JsonResponse({'error': 'Debe ejecutar la planificación primero (Re-Calcular) para tener datos de contexto.'}, status=400)
        
    try:
        suggestions = get_ai_planning_suggestion(request)
        return JsonResponse(suggestions)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
@require_POST
def apply_ai_suggestions(request):
    """
    API endpoint que aplica las sugerencias de la IA a la base de datos de prioridades.
    """
    try:
        body = json.loads(request.body)
        suggestions = body.get('suggestions', [])
        active_scenario = get_active_scenario(request)

        from .models import PrioridadManual, VTman
        
        for s in suggestions:
            id_orden = s.get('id_orden')
            nueva_prio = s.get('nueva_prioridad')
            nueva_maquina = s.get('nueva_maquina_id')

            if id_orden is None or nueva_prio is None:
                continue

            # Buscar si ya existe una prioridad manual para esta orden en este escenario
            existing = PrioridadManual.objects.filter(id_orden=id_orden, scenario=active_scenario).first()
            
            # Determinar la máquina: usamos la nueva si viene de la IA, o la actual si ya tenía override, o la del ERP
            maquina_final = nueva_maquina
            if maquina_final is None and existing:
                maquina_final = existing.maquina
            
            if maquina_final is None:
                vt = VTman.objects.using('production').filter(idorden=id_orden).first()
                if vt:
                    maquina_final = vt.idmaquina
            
                # SIEMPRE borramos CUALQUIER registro previo de esta OP en este escenario
                # para evitar duplicados en diferentes máquinas que causen inconsistencias en el Gantt
                PrioridadManual.objects.using("default").filter(id_orden=id_orden, scenario=active_scenario).delete()

                # Creamos el nuevo registro con la máquina final (IA o ERP o Override previo)
                PrioridadManual.objects.using("default").create(
                    id_orden=id_orden,
                    maquina=maquina_final,
                    scenario=active_scenario,
                    prioridad=float(nueva_prio)
                )


        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def redistribute_tasks(request):
    """
    API endpoint para redistribuir SOLO las tareas que se solapan con la falla
    de la máquina hacia otra máquina compatible.
    """
    from django.http import JsonResponse
    from .models import PrioridadManual, Scenario, MaquinaEquivalencia, HiddenTask
    from .services import get_planificacion_data
    from django.utils import timezone
    from django.db.models import Max

    try:
        from_machine_id = request.GET.get('from')
        to_machine_id = request.GET.get('to')
        proyectos_p = request.GET.get('proyectos')
        scenario_id = request.GET.get('scenario_id')

        if not from_machine_id or not to_machine_id:
            return JsonResponse({'success': False, 'error': 'Parámetros incompletos'}, status=400)

        # 1. Resolver Escenario
        scenario = Scenario.objects.using('default').filter(pk=scenario_id).first() if scenario_id else None
        if not scenario:
            scenario = Scenario.objects.using('default').filter(es_principal=True).first()
        if not scenario:
            return JsonResponse({'success': False, 'error': 'No hay escenario activo'}, status=400)

        # 2. Buscar Factor de Eficiencia por Equivalencia
        equivalencia = MaquinaEquivalencia.objects.using('default').filter(
            maquina_origen_id=from_machine_id,
            maquina_destino_id=to_machine_id
        ).first()
        factor = equivalencia.factor_eficiencia if equivalencia else 1.0

        # 3. Obtener Tareas del Origen (usando el Gantt actual para ver qué está realmente allí)
        print(f"DEBUG: [Redistribute] From: {from_machine_id}, To: {to_machine_id}, Proyectos: {proyectos_p}")
        
        from .gantt_logic import get_gantt_data
        from datetime import timedelta
        
        class MockRequest:
            def __init__(self, projects, s_id):
                self.GET = {
                    'run': '1',
                    'proyectos': projects or '',
                    'scenario_id': str(s_id) if s_id else '',
                    'plan_mode': 'manual'
                }
                self.session = {}
        
        mock_req = MockRequest(proyectos_p, scenario.id)
        gantt_data = get_gantt_data(mock_req, force_run=True)
        
        # Obtener rango de la falla para filtrar (Solo Inicio)
        from .models import MantenimientoMaquina, MaquinaConfig
        now = timezone.now()
        failure = MantenimientoMaquina.objects.using('default').filter(
            maquina_id=from_machine_id,
            estado__in=['FALLA', 'EN_CURSO', 'PROGRAMADO'],
            fecha_fin__gte=now
        ).order_by('fecha_inicio').first()
        
        # Si no hay falla activa, el filtro de inicio es hoy (Redistribución por carga)
        f_start = failure.fecha_inicio if failure else now
        
        if failure:
            print(f"DEBUG: [Redistribute] Queue Start: {f_start}")

        affected_tasks = []
        from_m_upper = str(from_machine_id).strip().upper()
        
        all_machine_tasks = []

        for row in gantt_data.get('timeline_data', []):
            m_id = str(row['machine'].id_maquina).strip().upper()
            if m_id == from_m_upper:
                for t in row.get('tasks', []):
                    all_machine_tasks.append(str(t.get('Idorden')))
                    
                    task_start = t.get('start_date')
                    if task_start:
                        # Ensure comparison in same timezone reference
                        if timezone.is_naive(task_start): task_start = timezone.make_aware(task_start)
                        
                        # NUEVA LOGICA: Cola de Producción
                        # Cualquier tarea que empiece DESPUÉS de que inicie la falla (Bloqueo Total)
                        if task_start >= f_start:
                            affected_tasks.append(t)
        
        print(f"DEBUG: [Redistribute] Total Tasks on {from_machine_id}: {len(all_machine_tasks)}")
        print(f"DEBUG: [Redistribute] Affected in Queue: {len(affected_tasks)}")

        if not affected_tasks:
            return JsonResponse({
                'success': False, 
                'error': 'No se encontraron tareas afectadas por la falla en este horario.'
            }, status=200) # Use 200 so UI can show the message instead of alert box crash

        # 4. Agrupar por Proyecto para mantener cohesión
        # Ordenamos primero por ProyectoCode para el agrupamiento
        affected_tasks.sort(key=lambda x: (x.get('ProyectoCode', 'ZZZ'), x.get('OrdenVisual', 0)))

        # 5. Calcular Punto de Inserción (Max Prioridad + 100)
        max_prio = PrioridadManual.objects.using('default').filter(
            scenario=scenario, maquina=to_machine_id
        ).aggregate(Max('prioridad'))['prioridad__max'] or 1000000.0
        
        next_prio = max_prio + 100.0

        # 6. Ejecutar Movimiento
        moved_count = 0
        from django.db import transaction
        with transaction.atomic(using='default'):
            for task in affected_tasks:
                task_id = task.get('Idorden')
                # Tiempo original de pieza (Tiempo_Proceso / Cantidad Pendiente)
                # O mejor: El sistema ya calculó el `Tiempo_Proceso` en el Gantt original
                original_total_time = float(task.get('Tiempo_Proceso', 0) or 0)
                if original_total_time <= 0: continue
                
                # RE-CALCULAR TIEMPO POR EFICIENCIA
                new_total_time = original_total_time * factor
                
                # Borrar asignación previa en este escenario
                PrioridadManual.objects.using('default').filter(id_orden=task_id, scenario=scenario).delete()
                
                # Crear nueva asignación
                PrioridadManual.objects.using('default').create(
                    id_orden=task_id,
                    scenario=scenario,
                    maquina=to_machine_id,
                    prioridad=next_prio,
                    tiempo_manual=new_total_time, # Sobrescribir tiempo por equivalencia
                    porcentaje_solapamiento=task.get('porcentaje_solapamiento', 0.0),
                    nivel_manual=None # Limpiar niveles antiguos para usar solo prioridad
                )
                
                next_prio += 100.0 # Siguiente paso
                moved_count += 1

        return JsonResponse({
            'success': True,
            'moved_count': moved_count,
            'message': f'Se redistribuyeron {moved_count} tareas de {from_machine_id} a {to_machine_id} aplicando un factor de eficiencia x{factor}.'
        })


    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({'success': False, 'error': str(e)}, status=500)

