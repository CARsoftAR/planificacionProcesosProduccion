"""
Simula el ordenamiento del Gantt para determinar por qué 47417 va primero.
"""
import os, django
from collections import defaultdict
from datetime import datetime, timedelta
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.utils import timezone
from produccion.models import Scenario, PrioridadManual
from produccion.services import get_planificacion_data

def get_nivel(t):
    try:
        plan_lvl = t.get('Nivel_Planificacion')
        if plan_lvl is not None and float(plan_lvl) != 0:
            return float(plan_lvl)
        erp_lvl = t.get('Nivel')
        if erp_lvl is not None:
            return float(erp_lvl)
        return 0.0
    except:
        return 0.0

# 1. Fetch data
filtros = {'proyectos': ['26-021']}
all_tasks = get_planificacion_data(filtros)
scenario = Scenario.objects.filter(es_principal=True).first()

# 2. Get Overrides
overrides = {str(o.id_orden): o for o in PrioridadManual.objects.filter(scenario=scenario, maquina='MAC08')}

# 3. Simulate Machine Tasks for MAC08
haas_tasks = []
for t in all_tasks:
    oid = str(t.get('Idorden'))
    machine = str(t.get('Idmaquina', '')).strip().upper()
    
    # If it is in HAAS natively OR moved to HAAS
    if 'MAC08' in machine or oid in overrides:
        task_info = dict(t)
        if oid in overrides:
            ov = overrides[oid]
            task_info['OrdenVisual'] = float(ov.prioridad)
            if ov.nivel_manual is not None:
                task_info['Nivel_Planificacion'] = float(ov.nivel_manual)
        else:
            # Default order in Gantt Pass 1
            task_info['OrdenVisual'] = 1000.0 # simplified
        haas_tasks.append(task_info)


# 4. Simulate get_sort_key
start_simulation = timezone.now().replace(hour=7, minute=0, second=0, microsecond=0)

print(f"{'ID':<8} | {'Nivel':<5} | {'NivelPlan':<10} | {'OrdenVis':<10} | {'Sort Key'}")
print("-" * 80)

def get_key(t):
    # Pass 2 sort key: (1, -get_nivel(t), ms, OrdenVisual)
    # ms is min_start_time. Assuming all are today for now.
    ms = start_simulation
    level = get_nivel(t)
    return (1, -level, ms, t.get('OrdenVisual', 999999))

haas_tasks.sort(key=get_key)

for t in haas_tasks:
    oid = t.get('Idorden')
    nivel = t.get('Nivel', 0)
    nivel_p = t.get('Nivel_Planificacion', 'N/A')
    orden_v = t.get('OrdenVisual', 999999)
    key = get_key(t)
    print(f"{oid:<8} | {nivel:<5} | {nivel_p:<10} | {orden_v:<10} | {key}")
