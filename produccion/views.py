from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from .gantt_logic import get_gantt_data
from .services import get_planificacion_data, get_all_machines
from itertools import groupby
from operator import itemgetter
from .models import PrioridadManual, MaquinaConfig, HorarioMaquina, TaskDependency, HiddenTask
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
from django.contrib import messages
from .planning_service import calculate_timeline
from datetime import datetime, timedelta

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

@csrf_exempt
def reset_planning(request):
    """
    API to clear manual planning (Visual Priorities, Virtual Moves) for a set of Orders.
    Optionally, it can also clear Dependencies and Hidden status.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        ids = body.get('ids', [])
        
        print(f"DEBUG: reset_planning called with {len(ids)} IDs: {ids}")
        
        if not ids:
             return JsonResponse({'status': 'ignored', 'message': 'No IDs provided'})
        
        # 1. Clear Priorities and Virtual Moves
        # This deletes the PrioridadManual record, which holds both the manual priority AND the virtual machine override.
        deleted_prio, _ = PrioridadManual.objects.using('default').filter(id_orden__in=ids).delete()
        print(f"DEBUG: Deleted {deleted_prio} PrioridadManual entries (Resets Moves & Priorities)")
        
        # 2. Clear Dependencies (Manual ones)
        deleted_dep_pred, _ = TaskDependency.objects.using('default').filter(predecessor_id__in=ids).delete()
        deleted_dep_succ, _ = TaskDependency.objects.using('default').filter(successor_id__in=ids).delete()
        print(f"DEBUG: Deleted dependencies Pred: {deleted_dep_pred}, Succ: {deleted_dep_succ}")
        
        # 3. Clear HIDDEN Status
        # The user specifically requested that filtering should "clean everything".
        # If they are resetting the plan, un-hiding hidden tasks is likely desired to get a fresh start.
        deleted_hidden, _ = HiddenTask.objects.using('default').filter(id_orden__in=ids).delete()
        print(f"DEBUG: Un-hid {deleted_hidden} tasks")
        
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
        
        if not id_orden:
             return JsonResponse({'error': 'Missing ID'}, status=400)
             
        HiddenTask.objects.using('default').create(id_orden=id_orden)
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def update_manual_time(request):
    """
    API to update the manual process time for a task.
    Updates or creates a PrioridadManual entry.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get('id_orden')
        tiempo_manual = body.get('tiempo_manual')
        maquina = body.get('maquina') # Optional implies current, but better to have it
        
        if not id_orden or tiempo_manual is None:
             return JsonResponse({'error': 'Missing parameters'}, status=400)
             
        time_val = float(tiempo_manual)
        
        # We need to find if there is an existing entry for this order
        # If so, update it. If not, create it.
        # Note: If not exists, what is the default Priority and Machine?
        # We should use the provided machine, and default priority 9999 or attempt to keep current.
        
        obj, created = PrioridadManual.objects.using('default').get_or_create(
            id_orden=id_orden,
            defaults={
                'maquina': maquina or 'SIN ASIGNAR',
                'prioridad': 9999, # Default low priority if new
                'tiempo_manual': time_val
            }
        )
        
        if not created:
            obj.tiempo_manual = time_val
            # If machine was provided and differs, should we update it? NO, only time edit.
            # But if the record existed on another machine (unlikely if unique per order), we just update time.
            obj.save()
            
        print(f"DEBUG: Updated manual time for {id_orden} to {time_val}")
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        print(f"ERROR update_manual_time: {e}")
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
def update_manual_nivel(request):
    """
    API to update the manual planning level (Nivel Planificacion) for a task.
    Updates or creates a PrioridadManual entry.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get('id_orden')
        nivel_manual = body.get('nivel_manual')
        maquina = body.get('maquina') 
        
        if not id_orden or nivel_manual is None:
             return JsonResponse({'error': 'Missing parameters'}, status=400)
             
        nivel_val = int(nivel_manual)
        
        obj, created = PrioridadManual.objects.using('default').get_or_create(
            id_orden=id_orden,
            defaults={
                'maquina': maquina or 'SIN ASIGNAR',
                'prioridad': 9999,
                'nivel_manual': nivel_val
            }
        )
        
        if not created:
            obj.nivel_manual = nivel_val
            obj.save()
            
        print(f"DEBUG: Updated manual nivel for {id_orden} to {nivel_val}")
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        print(f"ERROR update_manual_nivel: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def update_overlap_percentage(request):
    """
    API to update the overlap percentage for a task.
    Updates or creates a PrioridadManual entry.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get('id_orden')
        porcentaje_solapamiento = body.get('porcentaje_solapamiento')
        maquina = body.get('maquina')
        
        if not id_orden or porcentaje_solapamiento is None:
            return JsonResponse({'error': 'Missing parameters'}, status=400)
        
        # Validate percentage (0-100)
        porcentaje_val = float(porcentaje_solapamiento)
        if porcentaje_val < 0 or porcentaje_val > 100:
            return JsonResponse({'error': 'Percentage must be between 0 and 100'}, status=400)
        
        obj, created = PrioridadManual.objects.using('default').get_or_create(
            id_orden=id_orden,
            defaults={
                'maquina': maquina or 'SIN ASIGNAR',
                'prioridad': 9999,
                'porcentaje_solapamiento': porcentaje_val
            }
        )
        
        if not created:
            obj.porcentaje_solapamiento = porcentaje_val
            obj.save()
        
        print(f"✅ Updated overlap percentage for task {id_orden} to {porcentaje_val}%")
        
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
    Use ?format=json to get raw JSON data.
    """
    # Extract query parameters for filtering
    filtros = {}
    
    # Example: ?id_orden=123
    id_orden = request.GET.get('id_orden')
    if id_orden:
        filtros['id_orden'] = id_orden

    # Example: ?proyectos=1,2,3
    proyectos = request.GET.get('proyectos')
    if proyectos:
        filtros['proyectos'] = proyectos.split(',')

    try:
        # --- Local Machine Config Logic (Fetch FIRST to filter query) ---
        # User requested: "solo pone las maquinas que tens en la base de datos local, y el where lo agregas"
        local_machines = MaquinaConfig.objects.using('default').all()
        using_local_config = local_machines.exists()
        
        if using_local_config:
            # Map Code -> Name
            machine_map = {m.id_maquina.strip(): m.nombre for m in local_machines}
            # The tabs are the configured names
            all_machines_list = [m.nombre for m in local_machines]
            # Add to filters to optimize query
            filtros['machine_ids'] = list(machine_map.keys())
        else:
            # Fallback to ERP distinct names
            all_machines_list = get_all_machines()
            machine_map = {}

        # Optimization: Only fetch data if filters are active
        # Don't count machine_ids as an active user filter, we need user intent (project/id)
        search_active = bool(filtros.get('proyectos') or filtros.get('id_orden'))
        
        if search_active:
            data = get_planificacion_data(filtros)
        else:
            data = []
        
        # --- FILTER HIDDEN TASKS ---
        hidden_ids = set(HiddenTask.objects.using('default').values_list('id_orden', flat=True))
        if hidden_ids:
            data = [d for d in data if d.get('Idorden') not in hidden_ids]

        
        # Determine response format
        if request.GET.get('format') == 'json':
             return JsonResponse({'data': data}, safe=False)
        
        # Fetch Local Priorities
        prioridades_db = PrioridadManual.objects.using('default').all()
        
        # Create maps for OVERRIDES
        # Since we enforce one-assignment-per-order in move_task, we can map by ID directly.
        # id_orden -> {maquina, prioridad, tiempo_manual}
        virtual_overrides = { 
            p.id_orden: {
                'maquina': p.maquina, 
                'prioridad': p.prioridad,
                'tiempo_manual': p.tiempo_manual,
                'nivel_manual': p.nivel_manual
            } 
            for p in prioridades_db 
        }

        # 1. Calculate extra fields, assign Priority, and Normalize Machine Name
        # We start with a BASELINE PROIRITY based on the initial SQL sort order (Index).
        # This prevents "unmoved" items (Priority 0) from being jumped over by a moved item (Priority 1500).
        for idx, item in enumerate(data):
            # Update Machine Name based on Local Config if active
            native_code = str(item.get('Idmaquina', '')).strip()
            
                # A. Determine NATIVE Machine Name
            if using_local_config:
                if native_code in machine_map:
                    current_machine = machine_map[native_code]
                else:
                    current_machine = 'SIN ASIGNAR'
            else:
                current_machine = item.get('MAQUINAD', 'SIN ASIGNAR')
            
            # B. Check for VIRTUAL OVERRIDE (Moved Task)
            t_id = item.get('Idorden')
            
            # Robust Lookup Logic
            override = None
            if t_id in virtual_overrides:
                override = virtual_overrides[t_id]
            else:
                try:
                    t_id_int = int(t_id)
                    if t_id_int in virtual_overrides:
                        override = virtual_overrides[t_id_int]
                except (ValueError, TypeError):
                    pass

            if override:
                target_machine = override['maquina'] # This is usually the ID (e.g. 'STI' or '10')
                priority_val = override['prioridad']
                time_manual = override.get('tiempo_manual')
                
                # FIX: Map ID to Name if using local config
                if using_local_config:
                    target_code = str(target_machine).strip()
                    if target_code in machine_map:
                        target_machine = machine_map[target_code]
                
                # Apply Machine & Priority Override
                current_machine = target_machine
                item['OrdenVisual'] = float(priority_val)
                
                # Apply Time Override
                if time_manual is not None:
                     item['Tiempo_Proceso'] = float(time_manual)
                     item['CalculadoManual'] = True # Flag for UI

                # Apply Nivel Override
                if override.get('nivel_manual') is not None:
                     item['Nivel_Planificacion'] = override['nivel_manual']
                     item['NivelManualFlag'] = True
            else:
                # Default Priority logic if not moved/overridden
                default_prio = (idx + 1) * 1000.0
                item['OrdenVisual'] = default_prio
                item['CalculadoManual'] = False # Ensure flag is false if not overridden
            
            # Final Assignment to Item
            item['MAQUINAD'] = current_machine

            # Cantidades (Already calculated in SQL in lowercase for driver compatibility)
            item['Cantidad'] = item.get('cantidad_final') or 0
            item['Cantidadpp'] = item.get('cantidad_producida') or 0
            item['CantidadesPendientes'] = item.get('cantidad_pendiente') or 0

        # 2. Initialize Grouping
        grouped_data = {m: [] for m in all_machines_list}
        if 'SIN ASIGNAR' not in grouped_data:
             grouped_data['SIN ASIGNAR'] = []

        # Populate with data
        for item in data:
            m_name = item.get('MAQUINAD', 'SIN ASIGNAR')
            if m_name in grouped_data:
                grouped_data[m_name].append(item)
            else:
                # If using local config, strictly IGNORE machines not in the list (or put in SIN ASIGNAR if you want)
                # But user asked for Strict filtering. The SQL query filtered by ID, so data shouldn't have other IDs.
                # However, if 'maquina_map' mapped it, it should be fine.
                if using_local_config:
                     # If it's SIN ASIGNAR, add it? Or ignore?
                     # Let's add to SIN ASIGNAR if it falls through, but not create new tabs.
                     if 'SIN ASIGNAR' in grouped_data:
                         grouped_data['SIN ASIGNAR'].append(item)
                else:
                    # Legacy behavior for ERP mode
                    if m_name == 'SIN ASIGNAR':
                        grouped_data['SIN ASIGNAR'].append(item)
                    else:
                        grouped_data.setdefault(m_name, []).append(item)
                        if m_name not in all_machines_list:
                            all_machines_list.append(m_name)
        
        # Sort items within each machine
        for m_name in grouped_data:
            machine_items = grouped_data[m_name]
            machine_items.sort(key=lambda x: x.get('OrdenVisual', 9999))
            
            # Re-assign discrete OrdenVisual
            for idx, m_item in enumerate(machine_items):
                m_item['OrdenVisual'] = (idx + 1) * 1000

        # Sort machines list just in case
        if using_local_config:
            # Keep the order from DB or sort Alphabetically? 
            # Let's sort alphabetically for now, or maybe MaquinaConfig should have 'orden'?
            # For now, simplistic sort.
            processed_machines = sorted(all_machines_list)
        else:
            processed_machines = sorted(all_machines_list)

        if 'SIN ASIGNAR' in processed_machines:
             # Ensure SIN ASIGNAR is at the end?
             processed_machines.remove('SIN ASIGNAR')
             processed_machines.append('SIN ASIGNAR')
        
        # FINAL FILTER: REMOVED per user request ("no las ocultes")
        # We keep all machines visible to allow moving tasks to them.
        # if search_active:
        #      processed_machines = [m for m in processed_machines if grouped_data.get(m)]

        return render(request, 'produccion/planificacion.html', {
            'grouped_data': grouped_data, 
            'machines': processed_machines,
            'search_active': search_active
        })
    except Exception as e:
        if request.GET.get('format') == 'json':
            return JsonResponse({'error': str(e)}, status=500)
        return render(request, 'produccion/planificacion.html', {'grouped_data': {}, 'machines': [], 'error': str(e)})


@csrf_exempt
def move_priority(request, id_orden, direction):
    """
    API to move an order up or down in the local priority list.
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        maquina = body.get('maquina')
        # Fix: Use float to avoid ValueError on fractional strings (1500.5)
        current_priority = float(body.get('priority', 0)) 
    except Exception as e:
        return JsonResponse({'error': f'Invalid body: {e}'}, status=400)

    # Simple approach: Swap priority values with the adjacent item.
    # But since we mix DB priorities and ERP priorities, this is tricky.
    # Strategy:
    # 1. We need the list of ALL items for this machine to know who is adjacent.
    #    This is expensive to fetch again.
    #
    # Better Strategy for "Visual Only" with no complex backend state:
    # When user clicks "Up", frontend sends the ID of the item to move AND the ID of the item above it.
    # We just swap their priority values in the DB.
    # If they don't have a value in DB, we create one.
    
    # Let's implement specific swap logic
    # Expecting: { 'neighbor_id': 123, 'neighbor_priority': 100 }
    
    neighbor_id = body.get('neighbor_id')
    neighbor_priority = body.get('neighbor_priority') # Value of neighbor
    
    if neighbor_id is None:
        return JsonResponse({'status': 'ignored', 'message': 'No neighbor'})

    try:
        # Get or Create objects for both
        
        # Target Item
        obj_target, created_t = PrioridadManual.objects.using('default').get_or_create(
            id_orden=id_orden, maquina=maquina,
            defaults={'prioridad': current_priority}
        )
        # If it existed but priority was different from what UI sees (e.g. ERP default), update it?
        # No, we assume UI sends correct current state or we accept current DB state.
        # If newly created, it took 'current_priority'.
        
        # Neighbor Item
        obj_neighbor, created_n = PrioridadManual.objects.using('default').get_or_create(
            id_orden=neighbor_id, maquina=maquina,
            defaults={'prioridad': neighbor_priority}
        )
        
        # Logic fix: Trust the frontend values for the swap.
        # The frontend has the "Logical" visual order (1000, 2000, 3000...)
        # We simply enforce that:
        # Target gets Neighbor's Priority
        # Neighbor gets Target's Priority
        
        obj_target.prioridad = neighbor_priority
        obj_neighbor.prioridad = current_priority
        
        obj_target.save(using='default')
        obj_neighbor.save(using='default')
        
        return JsonResponse({'status': 'ok'})
    except Exception as e:
        return JsonResponse({'error': f'DB Error: {str(e)}'}, status=500)


@csrf_exempt
def move_task(request):
    """
    API to move a task to a different machine and/or update its priority order.
    Updates:
    1. Machine Assignment in Tman050 (if changed)
    2. Visual Priority in PrioridadManual
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        body = json.loads(request.body)
        id_orden = body.get('id_orden')
        target_machine_id = body.get('target_machine_id')
        new_priority = body.get('new_priority')
        
        if not id_orden or not target_machine_id or new_priority is None:
             return JsonResponse({'error': 'Missing parameters'}, status=400)
             
        new_priority = float(new_priority)
        
        # 1. Update Machine in Tman050
        # Tman050 might have composite key, filter by idorden
        # We assume one record per order for scheduling purposes or update all
        # 1. Update Machine in Tman050 - REMOVED AS PER USER RESTRICTION (READ ONLY)
        # We will handle machine moves virtually using PrioridadManual.
        # The Tman050.idmaquina field in SQL Server remains unchanged.
        # The view 'planificacion_visual' must respect the 'maquina' field in PrioridadManual as the override.

        # 2. Update Priority in PrioridadManual
        # We use the target machine ID for the scope of priority and assignment
        target_machine_id = str(target_machine_id).strip()
        print(f"DEBUG: move_task - Request to move ID {id_orden} to Machine '{target_machine_id}' with Prio {new_priority}")
        
        # LOGIC: A task should only have ONE 'active' virtual assignment/priority override.
        # If we just create a new one, we might leave an old one if the unique_together is (id_orden, maquina).
        # Strategy: Wipe previous override for this order, set new one. But PRESERVE Manual Time.
        
        with transaction.atomic():
            # Check for existing manual data before deleting
            existing_data = {
                'tiempo_manual': None,
                'fecha_inicio_manual': None,
                'nivel_manual': None,
                'porcentaje_solapamiento': 0.0
            }
            
            old_entries = PrioridadManual.objects.using('default').filter(id_orden=id_orden)
            if old_entries.exists():
                prev = old_entries.first()
                existing_data['tiempo_manual'] = prev.tiempo_manual
                existing_data['fecha_inicio_manual'] = prev.fecha_inicio_manual
                existing_data['nivel_manual'] = prev.nivel_manual
                existing_data['porcentaje_solapamiento'] = prev.porcentaje_solapamiento
            
            # 1. Delete ALL old manual priorities for this task (on any machine)
            deleted_count, _ = old_entries.delete()
            print(f"DEBUG: move_task - Deleted {deleted_count} old entries for {id_orden}")
            
            # 2. Create the NEW assignment trying to preserve manual time and pinning
            obj = PrioridadManual.objects.using('default').create(
                id_orden=id_orden, 
                maquina=target_machine_id,
                prioridad=new_priority,
                tiempo_manual=existing_data['tiempo_manual'],
                fecha_inicio_manual=existing_data['fecha_inicio_manual'],
                nivel_manual=existing_data['nivel_manual'],
                porcentaje_solapamiento=existing_data['porcentaje_solapamiento']
            )
            print(f"DEBUG: move_task - Created new assignment. ID: {obj.id_orden} Machine: {obj.maquina} Prio: {obj.prioridad}")
        
        return JsonResponse({'status': 'ok'})
            
    except Exception as e:
        print(f"ERROR move_task: {e}")
        return JsonResponse({'error': str(e)}, status=500)

@csrf_exempt
def set_priority(request, id_orden):
    """
    API to set a specific priority AND/OR manual start date for an order.
    Used for Drag and Drop (pinning).
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    print(f"🔍 DEBUG set_priority ID: {id_orden}")
    print(f"🔍 DEBUG set_priority body: {request.body}")
    try:
        body = json.loads(request.body)
        maquina = body.get('maquina')
        new_priority = body.get('new_priority')
        manual_start_str = body.get('manual_start')
        
        print(f"🔍 Parsed - Machine: {maquina}, Priority: {new_priority}, Manual Start: {manual_start_str}")
        
        # Validation
        if new_priority is None and manual_start_str is None:
             return JsonResponse({'error': 'Missing new_priority or manual_start'}, status=400)
             
        if new_priority is not None:
            new_priority = float(new_priority)
            
        manual_start_dt = None
        if manual_start_str:
            try:
                from django.utils import timezone as django_tz
                
                # Robust Date Parsing: Try ISO, Space-sep, and others
                manual_start_str = str(manual_start_str).strip()
                if 'T' in manual_start_str:
                    # ISO Format (assume already has timezone info)
                    manual_start_dt = datetime.fromisoformat(manual_start_str.replace('Z', '+00:00'))
                else:
                    # SQL / Human Format (NO timezone info - assume LOCAL time)
                    # Truncate milliseconds if present
                    if '.' in manual_start_str:
                        manual_start_str = manual_start_str.split('.')[0]
                    
                    # Parse as naive datetime
                    naive_dt = datetime.strptime(manual_start_str, '%Y-%m-%d %H:%M:%S')
                    
                    # Convert to timezone-aware datetime using Django's utility
                    # This automatically uses the configured TIME_ZONE from settings.py
                    manual_start_dt = django_tz.make_aware(naive_dt)
                    
                print(f"✅ Parsed manual_start_dt: {manual_start_dt} (TZ: {manual_start_dt.tzinfo})")
            except ValueError as ve:
                print(f"❌ ERROR parsing date '{manual_start_str}': {ve}")
                return JsonResponse({'error': f'Invalid date format: {manual_start_str}. Expecting YYYY-MM-DD HH:MM:SS'}, status=400)

    except Exception as e:
        print(f"❌ ERROR set_priority body parsing: {e}")
        return JsonResponse({'error': f'Invalid body: {e}'}, status=400)

    try:
        print(f"🔍 Cleaning old entries for order {id_orden} and applying NEW machine {maquina}")
        
        # 1. Preserve existing manual data from ANY previous entry
        existing_manual_data = {
            'tiempo_manual': None,
            'nivel_manual': None,
            'porcentaje_solapamiento': 0.0,
            'fecha_inicio_manual': None
        }
        
        previous_entries = PrioridadManual.objects.using('default').filter(id_orden=id_orden)
        if previous_entries.exists():
            prev = previous_entries.first()
            existing_manual_data['tiempo_manual'] = prev.tiempo_manual
            existing_manual_data['nivel_manual'] = prev.nivel_manual
            existing_manual_data['porcentaje_solapamiento'] = prev.porcentaje_solapamiento
            existing_manual_data['fecha_inicio_manual'] = prev.fecha_inicio_manual
            print(f"   (Preserving manual data: {existing_manual_data})")

        # 2. Delete ALL previous assignments
        deleted_count = previous_entries.delete()[0]
        
        # 3. Create NEW assignment
        # Ensure maquina is stripped
        safe_maquina = str(maquina).strip() if maquina else 'SIN ASIGNAR'
        
        # Determine final Date to save
        # If manual_start_str was provided (even if valid parsed object is None? No, only if parsed), use it.
        # Logic: If manual_start_dt is NOT None, use it.
        # If manual_start_dt IS None:
        #    Did the request EXPLICITLY ask for None/Null? (Hard to know with .get())
        #    Assume: If not provided, PRESERVE existing.
        #    Issue: How to unpin? We'll assume unpin requires specific action or clear.
        
        final_start_date = manual_start_dt if manual_start_dt is not None else existing_manual_data['fecha_inicio_manual']
        
        obj = PrioridadManual.objects.using('default').create(
            id_orden=id_orden,
            maquina=safe_maquina, 
            prioridad=new_priority if new_priority is not None else 0.0,
            fecha_inicio_manual=final_start_date,
            
            # Restore preserved data
            tiempo_manual=existing_manual_data['tiempo_manual'],
            nivel_manual=existing_manual_data['nivel_manual'],
            porcentaje_solapamiento=existing_manual_data['porcentaje_solapamiento']
        )
        
        print(f"✅ Successfully saved PrioridadManual for order {id_orden} on {safe_maquina}")
        
        return JsonResponse({
            'status': 'ok',
            'saved_date': str(manual_start_dt) if manual_start_dt else None,
            'saved_priority': new_priority,
            'saved_machine': safe_maquina
        })
    except Exception as e:
        print(f"❌ ERROR set_priority DB: {e}")
        import traceback
        traceback.print_exc()
        return JsonResponse({'error': f'DB Error: {str(e)}'}, status=500)
    

@csrf_exempt
@require_POST
def set_manual_time(request):
    """
    Sets a manual 'Tiempo Proceso' for a specific task.
    Creates or updates PrioridadManual entry.
    """
    try:
        data = json.loads(request.body)
        id_orden = data.get('id_orden')
        tiempo_manual = data.get('tiempo_manual')
        maquina_actual = data.get('maquina') # Current machine to ensure we don't move it accidentally or lose it

        if id_orden is None or tiempo_manual is None:
            return JsonResponse({'error': 'Faltan parametros (id_orden, tiempo_manual)'}, status=400)

        id_orden = int(id_orden)
        tiempo_manual = float(tiempo_manual)
        maquina_str = str(maquina_actual).strip() if maquina_actual else ''

        with transaction.atomic():
            # Try to get existing entry to preserve other fields (priority, machine)
            # Or create new one.
            # Strategy: valid PrioridadManual entry usually exists if dragged.
            # If not, we create one. But we need to know the 'machine'. 
            # If it's pure SQL data, we don't have PrioridadManual.
            # If we create new PM, we must set 'maquina' correct so it doesn't disappear from the view 
            # (since view checks PM.maquina for location).
            
            entry = PrioridadManual.objects.using('default').filter(id_orden=id_orden).first()
            if entry:
                entry.tiempo_manual = tiempo_manual
                entry.save()
            else:
                # Create new. 
                # IMPORTANT: If we create an entry, the planner thinks it's a "Manual Override".
                # If we don't set 'maquina', it might default to '' and disappear from table if table filters by maquina.
                # So we MUST save the current machine code.
                if not maquina_str:
                     # This is risky? If Frontend sends valid machine, we use it.
                     pass 
                
                PrioridadManual.objects.using('default').create(
                    id_orden=id_orden,
                    maquina=maquina_str,
                    prioridad= 99999999, # Default to end if new? Or 0?
                    # Ideally we should keep original priority logic but here we are forcing an entry.
                    # PlanificacionList logic: if PM exists, uses PM.maquina.
                    # If PM priority is 0, it sorts 0.
                    # Let's try to preserve relative order? Hard without context.
                    # Putting it at the end (high number) avoids disruption? Or 0?
                    # Ideally, PrioridadManual should optionally ONLY override time.
                    # But the model structure (one row) ties them.
                    tiempo_manual=tiempo_manual
                )
        
        return JsonResponse({'message': 'Tiempo actualizado.'})
    except Exception as e:
        print(f"Error set_manual_time: {e}")
        return JsonResponse({'error': str(e)}, status=500)


# --- Machine Configuration Views ---

from django.db import transaction

from django.core.paginator import Paginator

def maquina_config_list(request):
    """
    List all locally configured machines and their schedules.
    """
    # Order by ID to ensure consistent pagination
    maquinas_list = MaquinaConfig.objects.using('default').prefetch_related('horarios').all().order_by('id_maquina')
    
    paginator = Paginator(maquinas_list, 5) # 5 items per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Pass page_obj as 'maquinas' (it acts as an iterable like the queryset)
    # But we also need it for pagination controls
    return render(request, 'produccion/maquina_config_list.html', {'maquinas': page_obj})

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
    print("\n" + "=" * 70)
    print("🔢 OPCIÓN B: Dependencias Automáticas por Nivel (Mayor a Menor)")
    print("=" * 70)

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


    print(f"\n  ✅ Created {len(dependency_map)} automatic dependencies based on Nivel (Desc)")
    print("=" * 70 + "\n")
        
    # Global map to track end dates of ALL tasks across ALL machines
    global_task_end_dates = {}
    
    # Store machine data for second pass
    machine_tasks_map = {}  # machine_id -> {'maquina': obj, 'tasks': [...]}

    # ========================================================================
    # FIRST PASS: Calculate ALL tasks to build global_task_end_dates
    # ========================================================================
    print("=" * 60)
    print("DEPENDENCY RESOLUTION: FIRST PASS (Building end dates map)")
    print("=" * 60)
    
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
                 
        # Sort tasks by Visual Priority
        tasks.sort(key=lambda x: x.get('OrdenVisual', 999999))
        
        # Re-normalize priorities
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
    print("\n" + "=" * 60)
    print("DEPENDENCY RESOLUTION: SECOND PASS (Applying dependencies - Multi-Pass)")
    print("=" * 60)
    
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
    for machine_id in machine_tasks_map.keys(): # Use original keys ordering
        if machine_id in final_timeline_map:
            timeline_data.append(final_timeline_map[machine_id])
    
    # FILTER: REMOVED per user request ("no las ocultes")
    # We keep empty rows to allow Drag and Drop to empty machines
    # timeline_data = [row for row in timeline_data if row['tasks']]

    print("=" * 60)
    print(f"DEPENDENCY RESOLUTION COMPLETE")
    print(f"Total tasks processed: {len(global_task_end_dates)}")
    print("=" * 60 + "\n")
        
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

    # 5. Pre-calculate Task Positions (Pixels)
    COL_WIDTH = 40
    
    for row in timeline_data:
        for t in row['tasks']:
            t_start = t['start_date']
            t_duration = t['duration_real'] # hours
            
            if not t_start:
                continue

            # Calculate CSS Left
            # Find visual index of the day
            t_date = t_start.date()
            
            # If start date is not in valid_dates (e.g. started on a Sunday? Should not happen with calc_timeline logic)
            # We fallback to nearest previous or 0
            # But calc_timeline skips non-working.
            
            day_visual_idx = date_to_visual_index.get(t_date)
            
            if day_visual_idx is None:
                # Fallback: find nearest valid date?
                # For now 0
                day_visual_idx = 0
            
            # Include minutes in hour_diff
            hour_diff = (t_start.hour - global_min_h) + (t_start.minute / 60.0)
            
            # Safety checks
            if hour_diff < 0: hour_diff = 0
            
            col_index = (day_visual_idx * slots_per_day) + hour_diff
            
            t['visual_left'] = col_index * COL_WIDTH
            t['visual_width'] = t_duration * COL_WIDTH

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
from openpyxl.styles import PatternFill, Border, Side, Alignment, Font, Color
from openpyxl.utils import get_column_letter
from datetime import timedelta

def export_planificacion_excel_OLD(request):
    """
    Generate a Visual Gantt Chart in Excel.
    """
    # 1. Setup Simulation (Same as Visual View)
    maquinas = MaquinaConfig.objects.using('default').prefetch_related('horarios').all().order_by('id_maquina')
    
    fecha_desde = request.GET.get('fecha_desde')
    if fecha_desde:
        try:
            start_simulation = datetime.strptime(fecha_desde, '%Y-%m-%d')
        except ValueError:
            start_simulation = datetime.now()
    else:
        start_simulation = datetime.now()
    
    start_simulation = start_simulation.replace(hour=7, minute=0, second=0, microsecond=0)

    # --- Virtual Moves Logic ---
    virtual_moves = {}
    virtual_priorities = {}
    all_manuals = PrioridadManual.objects.using('default').all()
    for pm in all_manuals:
        virtual_moves[pm.id_orden] = pm.maquina 
        virtual_priorities[pm.id_orden] = pm.prioridad

    tasks_moved_in_map = {}
    for oid, mid in virtual_moves.items():
        if mid not in tasks_moved_in_map:
             tasks_moved_in_map[mid] = []
        tasks_moved_in_map[mid].append(oid)

    # 2. CALCULATION PHASE
    # We must run the simulation for ALL machines to determine the Full Date Range and valid Grid.
    
    # --- AUTOMATIC DEPENDENCY PREPARATION (Same as Visual View) ---
    # BUILD AUTOMATIC DEPENDENCIES based on NumeroOperacion
    all_tasks_for_deps = get_planificacion_data({})
    
    from collections import defaultdict
    orders_map = defaultdict(list)
    
    for task in all_tasks_for_deps:
        mstnmbr = task.get('Mstnmbr')
        if mstnmbr:
            orders_map[mstnmbr].append(task)
    
    dependency_map = {}
    
    for mstnmbr, tasks_in_order in orders_map.items():
        tasks_sorted = sorted(tasks_in_order, key=lambda x: x.get('NumeroOperacion', 0))
        
        for i in range(1, len(tasks_sorted)):
            predecessor = tasks_sorted[i-1]
            successor = tasks_sorted[i]
            
            pred_id = predecessor.get('Idorden')
            succ_id = successor.get('Idorden')
            pred_num = predecessor.get('NumeroOperacion', 0)
            succ_num = successor.get('NumeroOperacion', 0)
            
            if pred_id and succ_id and pred_num < succ_num:
                if succ_id not in dependency_map:
                    dependency_map[succ_id] = []
                dependency_map[succ_id].append(pred_id)
    
    global_task_end_dates = {}
    machine_tasks_map = {}
    
    # FIRST PASS: Build end_dates map
    for maquina in maquinas:
        machine_id = maquina.id_maquina
        
        # Filters (Reuse Logic)
        filtros = request.GET.copy()
        machine_filter = {'machine_ids': [machine_id]}
        if request.GET.get('proyectos'):
             raw_proyectos = request.GET.get('proyectos')
             machine_filter['proyectos'] = [p.strip() for p in raw_proyectos.split(',') if p.strip()]

        native_tasks = get_planificacion_data(machine_filter) 
        
        # Logic: Move Out
        active_tasks = []
        for t in native_tasks:
            try: oid = int(t.get('Idorden', 0))
            except: oid = 0
            
            if oid in virtual_moves:
                target_machine = virtual_moves[oid]
                if str(target_machine).strip() == str(machine_id).strip():
                    active_tasks.append(t)
            else:
                 active_tasks.append(t)
        
        # Logic: Move In
        moved_in_ids = tasks_moved_in_map.get(machine_id, [])
        if moved_in_ids:
            inbound_filter = {}
            if request.GET.get('proyectos'): inbound_filter['proyectos'] = machine_filter['proyectos']
            inbound_filter['id_orden_in'] = moved_in_ids
            
            extra_tasks = get_planificacion_data(inbound_filter)
            existing_ids = set(t['Idorden'] for t in active_tasks)
            for t in extra_tasks:
                if t['Idorden'] not in existing_ids: active_tasks.append(t)
        
        # Sort
        tasks = active_tasks
        for idx, item in enumerate(tasks):
             default_prio = (idx + 1) * 1000.0
             p_id = item['Idorden']
             if p_id in virtual_priorities: item['OrdenVisual'] = float(virtual_priorities[p_id])
             else: item['OrdenVisual'] = default_prio
        tasks.sort(key=lambda x: x.get('OrdenVisual', 999999))
        for idx, item in enumerate(tasks): item['OrdenVisual'] = (idx + 1) * 1000

        # Store for second pass
        machine_tasks_map[machine_id] = {'maquina': maquina, 'tasks': tasks}
        
        # FIRST PASS: Calculate without dependencies
        calculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, task_min_start_times=None)
        
        # Build end_dates map
        for ct in calculated_tasks:
            ct_id = ct.get('Idorden')
            ct_end = ct.get('end_date')
            if ct_id and ct_end:
                if ct_id not in global_task_end_dates or ct_end > global_task_end_dates[ct_id]:
                    global_task_end_dates[ct_id] = ct_end
    
    # SECOND PASS: Recalculate with dependencies
    tasks_with_dependencies = set(dependency_map.keys())
    
    # Initialize variables for second pass
    processed_data = []
    global_max_date = start_simulation + timedelta(hours=48)
    
    for machine_id, machine_data in machine_tasks_map.items():
        maquina = machine_data['maquina']
        tasks = machine_data['tasks']
        
        machine_has_dependencies = any(t.get('Idorden') in tasks_with_dependencies for t in tasks)
        
        if not machine_has_dependencies:
            calculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, task_min_start_times=None)
        else:
            min_start_times = {}
            for t in tasks:
                t_id = t.get('Idorden')
                if t_id in dependency_map:
                    preds = dependency_map[t_id]
                    max_pred_end = None
                    for pid in preds:
                        if pid in global_task_end_dates:
                            end_date = global_task_end_dates[pid]
                            if max_pred_end is None or end_date > max_pred_end:
                                max_pred_end = end_date
                    if max_pred_end:
                        min_start_times[t_id] = max_pred_end
            
            calculated_tasks = calculate_timeline(maquina, tasks, start_date=start_simulation, task_min_start_times=min_start_times)
        
        processed_data.append({
            'machine': maquina,
            'tasks': calculated_tasks
        })
        
        # Update Global Bounds
        for t in calculated_tasks:
            if t['end_date'] and t['end_date'] > global_max_date:
                global_max_date = t['end_date']
    
    # Set global min date
    global_min_date = start_simulation

    # 3. BUILD TIME GRID (Columns)
    # We want columns ONLY for working hours found in the machine configurations?
    # Or simplified: 07:00 to 22:00 for every day from min to max.
    # Let's check the global schedule limits again.
    
    grid_min_h = 24
    grid_max_h = 0
    has_schedules = False
    for m in maquinas:
        for h in m.horarios.all():
            has_schedules = True
            if h.hora_inicio.hour < grid_min_h: grid_min_h = h.hora_inicio.hour
            if h.hora_fin.hour > grid_max_h: grid_max_h = h.hora_fin.hour
            
    if not has_schedules:
        grid_min_h = 7
        grid_max_h = 18
    elif grid_max_h <= grid_min_h: # Wrap around or error
        grid_max_h = 23
        grid_min_h = 0
        
    # Generate map: Datetime (Round to Hour) -> Column Index (1-based for Excel)
    # Excel Cols: A=Machine. Time starts at B (2).
    
    time_cols_map = {} # datetime(Y,M,D,H,0,0) -> col_index
    grid_headers = [] # List of datetimes for header generation
    
    current_pointer = global_min_date.replace(hour=grid_min_h, minute=0, second=0, microsecond=0)
    # Adjust valid range slightly buffer
    end_pointer = global_max_date + timedelta(days=1)
    
    col_counter = 2 # Start at Column B
    
    while current_pointer <= end_pointer:
        # Is this hour valid?
        # Check day of week + hour range
        wd = current_pointer.weekday()
        # Simplified Check: Just check Hour Range (User usually wants Mon-Fri + Sat?)
        # Let's rely on hour range for simplicity of grid, visual view does same.
        
        if grid_min_h <= current_pointer.hour < grid_max_h:
            # Add to grid
            # But skip Sundays? Visual view filters days.
            # Visual View Logic: Mon-Fri=Always, Sat=IfConfigured.
            # Let's blindly include all days for safety or check 'SA'.
            # Assuming Mon-Fri (0-4) + Sat (5) if needed.
            # Let's include Mon-Sat to be safe.
            if wd != 6: # Skip Sunday
                time_cols_map[current_pointer] = col_counter
                grid_headers.append(current_pointer)
                col_counter += 1
                
        current_pointer += timedelta(hours=1)
        
    # verify we have columns
    if not grid_headers:
        return HttpResponse("No valid time range calculated.")

    # 4. EXCEL GENERATION
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Gantt Visual"
    
    # --- STYLES ---
    # Colors from user image approximation
    FILL_HEADER_MACHINE = PatternFill("solid", fgColor="C6E0B4") # Light Green
    FILL_HEADER_DAY     = PatternFill("solid", fgColor="4472C4") # Blue
    FILL_MACHINE_ROW    = PatternFill("solid", fgColor="D99795") # Salmon/Reddish
    
    FONT_BOLD_WHITE = Font(bold=True, color="FFFFFF")
    FONT_BOLD_BLACK = Font(bold=True, color="000000")
    
    BORDER_THIN = Border(left=Side(style='thin', color="CCCCCC"), 
                         right=Side(style='thin', color="CCCCCC"), 
                         top=Side(style='thin', color="CCCCCC"), 
                         bottom=Side(style='thin', color="CCCCCC"))
                         
    BORDER_DOTTED_VERT = Border(left=Side(style='dotted', color="BBBBBB"), 
                                right=Side(style='dotted', color="BBBBBB"), 
                                top=Side(style='thin', color="EEEEEE"), 
                                bottom=Side(style='thin', color="EEEEEE"))

    ALIGN_CENTER = Alignment(horizontal='center', vertical='center')
    ALIGN_WRAP   = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # Task Colors (Pastel Palette)
    colors = ['FFB6C1', 'ADD8E6', '90EE90', 'FFD700', 'E6E6FA', 'FFAB91', '80DEEA', 'C5E1A5']
    
    # --- HEADER CONSTRUCTION ---
    
    # 1. "MAQUINA" Label (Merged A2:A3 usually, or just A2 if we want to align with Day Header)
    # User image shows MAQUINA header spanning Row 2 and 3? Or just Row 2?
    # Let's merge A2:A3 to cover Day and Hour rows for the label.
    ws.merge_cells("A2:A3")
    c_maquina = ws["A2"]
    c_maquina.value = "MAQUINA"
    c_maquina.fill = FILL_HEADER_MACHINE
    c_maquina.font = FONT_BOLD_BLACK
    c_maquina.alignment = ALIGN_CENTER
    c_maquina.border = BORDER_THIN
    # Apply style to A3 too?
    ws["A3"].border = BORDER_THIN

    # 2. Day Headers (Row 2) & Hour Headers (Row 3)
    
    # Setup standard column widths for time
    for col_idx in time_cols_map.values():
        ws.column_dimensions[get_column_letter(col_idx)].width = 3.5

    # Group headers by Day
    current_day = None
    start_merge = -1
    
    for i, dt in enumerate(grid_headers):
        col_idx = i + 2
        
        # HOUR HEADER (Row 3)
        c_hour = ws.cell(row=3, column=col_idx)
        c_hour.value = dt.hour
        c_hour.alignment = ALIGN_CENTER
        c_hour.border = BORDER_THIN # Keep hours with solid thin border for readability
        c_hour.font = Font(size=8)
        
        # DAY HEADER LOGIC
        day_str = dt.strftime('%a, %d-%b')
        if day_str != current_day:
            # Close previous merge
            if current_day is not None:
                ws.merge_cells(start_row=2, start_column=start_merge, end_row=2, end_column=col_idx-1)
                c_day = ws.cell(row=2, column=start_merge)
                c_day.value = current_day
                c_day.alignment = ALIGN_CENTER
                c_day.fill = FILL_HEADER_DAY
                c_day.font = FONT_BOLD_WHITE
                c_day.border = BORDER_THIN
            
            current_day = day_str
            start_merge = col_idx
            
    # Close last day
    if current_day is not None and start_merge != -1:
        ws.merge_cells(start_row=2, start_column=start_merge, end_row=2, end_column=col_counter-1)
        c_day = ws.cell(row=2, column=start_merge)
        c_day.value = current_day
        c_day.alignment = ALIGN_CENTER
        c_day.fill = FILL_HEADER_DAY
        c_day.font = FONT_BOLD_WHITE
        c_day.border = BORDER_THIN

    # Fix Column A width
    ws.column_dimensions['A'].width = 25
    
    # --- RENDER DATA ---
    current_row = 4
    
    for p_data in processed_data:
        maquina = p_data['machine']
        tasks = p_data['tasks']
        
        # 1. Machine Name (Column A)
        c_name = ws.cell(row=current_row, column=1)
        c_name.value = maquina.nombre
        c_name.alignment = ALIGN_CENTER
        c_name.font = FONT_BOLD_BLACK
        c_name.fill = FILL_MACHINE_ROW
        c_name.border = BORDER_THIN
        
        ws.row_dimensions[current_row].height = 45
        
        # 2. Prepare Grid Background (Dashed vertical lines for empty slots)
        # We process all valid columns for this row to set the default grid style
        for col_idx in time_cols_map.values():
            c_bg = ws.cell(row=current_row, column=col_idx)
            c_bg.border = BORDER_DOTTED_VERT
            
        # Track occupied columns
        occupied_cols = set()
        
        # 3. Render Tasks
        for i, t in enumerate(tasks):
            t_start = t['start_date']
            t_end = t['end_date']
            
            if not t_start or not t_end: continue
            
            t_start_h = t_start.replace(minute=0, second=0, microsecond=0)
            start_col = time_cols_map.get(t_start_h)
            
            if not start_col: continue 
                
            duration_h = int(t['duration_real'])
            if duration_h < 1: duration_h = 1
            
            sorted_keys = sorted(time_cols_map.keys())
            try:
                start_idx_in_keys = sorted_keys.index(t_start_h)
                end_idx_in_keys = min(start_idx_in_keys + duration_h - 1, len(sorted_keys)-1)
                end_time_key = sorted_keys[end_idx_in_keys]
                end_col = time_cols_map[end_time_key]
            except ValueError:
                continue

            if end_col < start_col: end_col = start_col
            
            # Check Collision
            is_collision = False
            for c_idx in range(start_col, end_col + 1):
                if c_idx in occupied_cols:
                    is_collision = True
                    break
            
            # Prepare Text uses Project Code and OP ID
            line1 = f"{t.get('ProyectoCode', '')} ({t.get('Idorden')})"
            line2 = t.get('Descripcion', '')[:20]
            task_text = f"{line1}\n{line2}"

            if is_collision:
                # Append to existing
                cell = ws.cell(row=current_row, column=start_col)
                if cell.value:
                    existing = str(cell.value)
                    if task_text not in existing: # Avoid EXACT dupes
                         cell.value = existing + "\n" + task_text
                else:
                    cell.value = task_text
            else:
                # Mark occupied
                for c_idx in range(start_col, end_col + 1):
                    occupied_cols.add(c_idx)
                
                # Merge
                if end_col > start_col:
                    ws.merge_cells(start_row=current_row, start_column=start_col, end_row=current_row, end_column=end_col)
                
                cell = ws.cell(row=current_row, column=start_col)
                cell.value = task_text
                
                # Task Style (Solid fill, thin border overrides dotted)
                color_idx = i % len(colors)
                cell.fill = PatternFill("solid", fgColor=colors[color_idx])
                cell.alignment = ALIGN_WRAP
                cell.font = Font(size=8, bold=False)
                cell.border = BORDER_THIN
            
        current_row += 1

    # Output
    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=PlanificacionVisual_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    wb.save(response)
    return response


# --- Feriados Views ---

from .models import Feriado
from .forms import FeriadoForm
from django.db.models import Q

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

    # 5. Pre-calculate Task Positions (Pixels) for HTML View
    COL_WIDTH = 40
    
    # Map Date -> Column Index Start (Visual Day Index)
    # e.g. Mon=0, Tue=1, (Sat skip), Mon=2...
    date_to_visual_index = { d: i for i, d in enumerate(valid_dates) }
    slots_per_day = global_max_h - global_min_h
    
    for row in timeline_data:
        for t in row['tasks']:
            t_start = t['start_date']
            t_duration = t['duration_real'] # hours
            
            if not t_start:
                continue

            # Calculate CSS Left
            t_date = t_start.date()
            day_visual_idx = date_to_visual_index.get(t_date)
            
            if day_visual_idx is None:
                day_visual_idx = 0
            
            # Include minutes in hour_diff
            hour_diff = (t_start.hour - global_min_h) + (t_start.minute / 60.0)
            if hour_diff < 0: hour_diff = 0
            
            # Convert to float explicit to avoid type errors
            hour_diff = float(hour_diff)
            
            col_index = (day_visual_idx * slots_per_day) + hour_diff
            
            t['visual_left'] = col_index * COL_WIDTH
            t['visual_width'] = t_duration * COL_WIDTH

    # Build dependencies list for JSON
    dependencies_list = []
    for succ_id, pred_ids in dependency_map.items():
        for pred_id in pred_ids:
            dependencies_list.append({'pred': pred_id, 'succ': succ_id})

    context = {
        'timeline_data': timeline_data,
        'time_columns': time_columns,
        'start_date': start_simulation, 
        'dependencies_json': json.dumps(dependencies_list),
        'today': start_simulation,
        'total_width': len(time_columns) * 40 if time_columns else 15*40
    }
    return render(request, 'produccion/planificacion_visual.html', context)


def export_planificacion_excel(request):
    """
    Generate a Visual Gantt Chart in Excel.
    Uses shared logic from gantt_logic.py to equate with Visual View.
    """
    # 1. Get Data (Force run to ensure we get tasks)
    data = get_gantt_data(request, force_run=True)
    
    timeline_data = data['timeline_data']
    time_columns = data['time_columns']
    global_min_h = data['global_min_h']
    global_max_h = data['global_max_h']
    start_simulation = data['start_simulation']
    
    if not time_columns:
         return HttpResponse("No hay datos calculados para exportar. Ejecute la planificación visual primero.")

    # 2. EXCEL GENERATION
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Gantt Visual"
    
    # --- STYLES ---
    FILL_HEADER_MACHINE = PatternFill("solid", fgColor="4472C4") # Blue header
    FILL_HEADER_DAY     = PatternFill("solid", fgColor="4472C4") # Blue
    FILL_MACHINE_ROW    = PatternFill("solid", fgColor="000000") # BLACK for machine names
    
    FONT_BOLD_WHITE = Font(bold=True, color="FFFFFF")
    FONT_BOLD_BLACK = Font(bold=True, color="000000")
    
    # Thin borders for headers
    BORDER_THIN = Border(
        left=Side(style='thin', color="CCCCCC"), 
        right=Side(style='thin', color="CCCCCC"), 
        top=Side(style='thin', color="CCCCCC"), 
        bottom=Side(style='thin', color="CCCCCC")
    )
    
    # Thin borders for task cards (clean, subtle - almost invisible)
    BORDER_TASK_CARD = Border(
        left=Side(style='thin', color="CCCCCC"), 
        right=Side(style='thin', color="CCCCCC"), 
        top=Side(style='thin', color="CCCCCC"), 
        bottom=Side(style='thin', color="CCCCCC")
    )
                         
    BORDER_DOTTED_VERT = Border(
        left=Side(style='hair', color="E0E0E0"), 
        right=Side(style='hair', color="E0E0E0"), 
        top=Side(style='hair', color="E0E0E0"), 
        bottom=Side(style='hair', color="E0E0E0")
    )

    ALIGN_CENTER = Alignment(horizontal='center', vertical='center')
    ALIGN_WRAP   = Alignment(horizontal='center', vertical='center', wrap_text=True)
    
    # Task Colors - Assign by ProyectoCode using Hash Algorithm (Same as Visual View)
    def string_to_rgb_hex(value):
        """Replicates the Visual View color generation logic"""
        if not value: return "0D6EFD"
        hash_val = 0
        for char in str(value):
            hash_val = ord(char) + ((hash_val << 5) - hash_val)
        
        hue = abs(hash_val) % 360
        saturation = 70 + (abs(hash_val >> 8) % 30)
        lightness = 40 + (abs(hash_val >> 16) % 15)
        
        h, s, l = hue/360.0, saturation/100.0, lightness/100.0
        
        def hue_to_rgb(p, q, t):
            if t < 0: t += 1
            if t > 1: t -= 1
            if t < 1/6: return p + (q - p) * 6 * t
            if t < 1/2: return q
            if t < 2/3: return p + (q - p) * (2/3 - t) * 6
            return p
            
        if s == 0: r = g = b = l
        else:
            q = l * (1 + s) if l < 0.5 else l + s - l * s
            p = 2 * l - q
            r = hue_to_rgb(p, q, h + 1/3)
            g = hue_to_rgb(p, q, h)
            b = hue_to_rgb(p, q, h - 1/3)
            
        return f"{int(r*255):02X}{int(g*255):02X}{int(b*255):02X}"

    # Build a map of ProyectoCode -> Color
    # First, collect all unique ProyectoCodes from all tasks
    all_proyecto_codes = set()
    for row_data in timeline_data:
        for t in row_data['tasks']:
            proyecto_code = t.get('ProyectoCode', '')
            if proyecto_code:
                all_proyecto_codes.add(proyecto_code)
    
    # Assign colors dynamically
    proyecto_color_map = {}
    for p_code in all_proyecto_codes:
        proyecto_color_map[p_code] = string_to_rgb_hex(p_code)
    
    default_color = "0D6EFD"
    
    # --- HEADER CONSTRUCTION ---
    
    # "MAQUINA" Label
    ws.merge_cells("A2:A3")
    c_maquina = ws["A2"]
    c_maquina.value = "MAQUINA"
    c_maquina.fill = FILL_HEADER_MACHINE
    c_maquina.font = FONT_BOLD_BLACK
    c_maquina.alignment = ALIGN_CENTER
    c_maquina.border = BORDER_THIN
    ws["A3"].border = BORDER_THIN

    # Map time_columns to Excel Columns (Start at B=2)
    # time_columns is a list of datetimes (hourly)
    
    # We need to assume the LIST is contiguous hours, skipping nights/weekends as defined.
    # The get_gantt_data returns a specific list of *valid* hours.
    # So we can just map index -> Excel Col
    
    time_cols_map = {} 
    
    # Headers
    current_day = None
    start_merge = -1
    
    for i, dt in enumerate(time_columns):
        col_idx = i + 2
        time_cols_map[dt] = col_idx
        
        ws.column_dimensions[get_column_letter(col_idx)].width = 3.5
        
        # HOUR HEADER (Row 3)
        c_hour = ws.cell(row=3, column=col_idx)
        c_hour.value = dt.hour
        c_hour.alignment = ALIGN_CENTER
        c_hour.border = BORDER_THIN
        c_hour.font = Font(size=8)
        
        # DAY HEADER LOGIC
        day_str = dt.strftime('%a, %d-%b')
        if day_str != current_day:
            if current_day is not None:
                ws.merge_cells(start_row=2, start_column=start_merge, end_row=2, end_column=col_idx-1)
                c_day = ws.cell(row=2, column=start_merge)
                c_day.value = current_day
                c_day.alignment = ALIGN_CENTER
                c_day.fill = FILL_HEADER_DAY
                c_day.font = FONT_BOLD_WHITE
                c_day.border = BORDER_THIN
            
            current_day = day_str
            start_merge = col_idx
            
    # Close last day
    if current_day is not None and start_merge != -1:
        last_col = 2 + len(time_columns) - 1
        ws.merge_cells(start_row=2, start_column=start_merge, end_row=2, end_column=last_col)
        c_day = ws.cell(row=2, column=start_merge)
        c_day.value = current_day
        c_day.alignment = ALIGN_CENTER
        c_day.fill = FILL_HEADER_DAY
        c_day.font = FONT_BOLD_WHITE
        c_day.border = BORDER_THIN

    ws.column_dimensions['A'].width = 25
    
    # --- RENDER DATA ---
    current_row = 4
    
    for row_data in timeline_data:
        maquina = row_data['machine']
        tasks = row_data['tasks']
        
        # Machine Name
        c_name = ws.cell(row=current_row, column=1)
        c_name.value = maquina.nombre
        c_name.alignment = ALIGN_CENTER
        c_name.font = FONT_BOLD_WHITE  # White text on black background
        c_name.fill = FILL_MACHINE_ROW
        c_name.border = BORDER_THIN
        
        ws.row_dimensions[current_row].height = 45
        
        # Grid Background
        for col_idx in time_cols_map.values():
            c_bg = ws.cell(row=current_row, column=col_idx)
            c_bg.border = BORDER_DOTTED_VERT
            
        occupied_cols = set()
        
        for i, t in enumerate(tasks):
            t_start = t['start_date']
            t_duration = t['duration_real']
            
            if not t_start: continue
            
            # --- ROBUST MATHEMATICAL POSITIONING (Same as Scheduler JS/CSS) ---
            t_start_h = t_start.replace(minute=0, second=0, microsecond=0)
            
            # 1. Find the starting column for this DATE
            # We need a map of { Date -> Base Column Index }
            # Since we iterate time_columns, we can build this map or just calculate it from valid_dates.
            # But let's use the time_cols_map we already somewhat have, or better:
            # Reconstruct the logic: Col = Base(Date) + (Hour - MinH)
            
            t_date = t_start.date()
            
            # Find the *first* column that matches this date to get the Base Index
            # (Optimization: Build this map once outside the loop for speed)
            if 'date_base_col_map' not in locals():
                date_base_col_map = {}
                for idx, col_dt in enumerate(time_columns):
                    d_key = col_dt.date()
                    if d_key not in date_base_col_map:
                        date_base_col_map[d_key] = idx
                        
            if t_date not in date_base_col_map:
                # Date not in valid dates (pinned way out?)
                # Try fallback: matching nearest date? Or just Skip.
                continue
                
            base_col_idx = date_base_col_map[t_date]
            
            # 2. Add Hour Offset
            # hour_diff = (t_hour - global_min_h)
            # Check for TZ issues: use naive hour
            t_h = t_start.hour
            if t_start.tzinfo:
                # If aware, ensure we compare apples to apples?
                # Actually .hour on a local-aware datetime is usually correct relative to the day.
                pass

            hour_offset = t_h - global_min_h
            
            # Handle implicit clipping if task starts before min_h (e.g. 05:00 when min is 07:00)
            if hour_offset < 0:
                 # It starts before the visual grid of the day.
                 # Does it extend INTO the grid?
                 duration_full = t_duration
                 if (hour_offset + duration_full) > 0:
                     # Yes, it spans into the visible area.
                     # Clip start to 0
                     hour_offset = 0
                 else:
                     # Totally before
                     continue

            # 3. Calculate Start Index in the list
            start_l_idx = base_col_idx + hour_offset
            
            # 4. Calculate End Index
            # Duration is in hours
            duration_h = int(t_duration)
            if duration_h < 1: duration_h = 1
            
            end_l_idx = min(start_l_idx + duration_h - 1, len(time_columns) - 1)
            
            if end_l_idx < start_l_idx:
                continue
            
            start_col = 2 + int(start_l_idx)
            end_col = 2 + int(end_l_idx)
            
            # Check Collision
            is_collision = False
            for c_idx in range(start_col, end_col + 1):
                if c_idx in occupied_cols:
                    is_collision = True
                    break
            
            # Text
            line1 = f"{t.get('ProyectoCode', '')} ({t.get('Idorden')})"
            line2 = t.get('Descripcion', '')[:20]
            task_text = f"{line1}\n{line2}"

            if is_collision:
                cell = ws.cell(row=current_row, column=start_col)
                # FIX: Check if cell is 'MergedCell' (read-only)
                # In openpyxl, MergedCell doesn't support value assignment.
                # Only the top-left cell of a merge range is real.
                from openpyxl.cell.cell import MergedCell
                if isinstance(cell, MergedCell):
                    # Find the top-left cell of the merge range this cell belongs to?
                    # Too complex for quick fix. If it's merged, we skip overwriting or log it.
                    # Or better: We just don't write to it if it's not a normal cell.
                    pass 
                else:
                    if cell.value:
                        existing = str(cell.value)
                        if task_text not in existing:
                             cell.value = existing + "\n" + task_text
                    else:
                        cell.value = task_text
            else:
                for c_idx in range(start_col, end_col + 1):
                    occupied_cols.add(c_idx)
                
                if end_col > start_col:
                    ws.merge_cells(start_row=current_row, start_column=start_col, end_row=current_row, end_column=end_col)
                
                # Get color based on ProyectoCode
                proyecto_code = t.get('ProyectoCode', '')
                task_color = proyecto_color_map.get(proyecto_code, default_color)
                
                # Define Sides
                side_thick_color = Side(style='thick', color=task_color)
                side_thin_grey = Side(style='thin', color="CCCCCC")
                
                # Apply styles to ALL cells in the range
                for c_idx in range(start_col, end_col + 1):
                    cell_sub = ws.cell(row=current_row, column=c_idx)
                    
                    # Logic for Merged Cells Borders:
                    # Left Border: Only on the first cell
                    # Right Border: Only on the last cell
                    
                    if c_idx == start_col:
                        b_left = side_thick_color
                    else:
                        b_left = side_thin_grey 
                        
                    if c_idx == end_col:
                        b_right = side_thick_color
                    else:
                        b_right = side_thin_grey
                        
                    cell_sub.border = Border(
                        left=b_left,
                        right=b_right,
                        top=side_thin_grey,
                        bottom=side_thin_grey
                    )
                    
                    cell_sub.fill = PatternFill("solid", fgColor="FFFFFF")

                    if c_idx == start_col:
                        cell_sub.value = task_text
                        cell_sub.alignment = ALIGN_WRAP
                        cell_sub.font = Font(size=8, bold=True, color="000000")
            
        current_row += 1

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename=PlanificacionVisual_{datetime.now().strftime("%Y%m%d_%H%M")}.xlsx'
    wb.save(response)
    return response



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
            
            if segment_qty > 0 or segment_duration > 0:
                h_tot = int(segment_duration)
                m_tot = int(round((segment_duration - h_tot) * 60))
                if m_tot >= 60:
                    h_tot += 1
                    m_tot = 0
                tiempo_dia_hm = f"{h_tot}:{m_tot:02d}h"

                # Standard Time Unit
                std_t = float(segment.get('Tiempo') or 0.0)
                h_std = int(std_t)
                m_std = int(round((std_t - h_std) * 60))
                if m_std >= 60:
                    h_std += 1
                    m_std = 0
                tiempo_standard_hm = f"{h_std}:{m_std:02d}h"

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

