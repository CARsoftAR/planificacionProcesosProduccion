import os
import sys
import django
from datetime import datetime

# Setup Django environment
sys.path.append(r"c:\Sistemas ABBAMAT\planificacionProcesosProductivos EN DESARROLLO")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "planificacion.settings")
django.setup()

from datetime import datetime, timedelta

# Mock tasks
tarea_predecesora = {
    'Idorden': '100',
    'ProyectoCode': 'PROY1',
    'Tiempo_Proceso': 6.0,
    '_maq': 'MAC1',
    '_mid': 'MAC1',
    'prioridad': 1000
}

tarea_dependiente = {
    'Idorden': '101',
    'ProyectoCode': 'PROY1',
    'Tiempo_Proceso': 4.0,
    '_maq': 'MAC2',
    '_mid': 'MAC2',
    'prioridad': 2000,
    'porcentaje_solapamiento': 50.0,
    'modo_solapamiento': 'manual'
}

from produccion.gantt_logic import get_gantt_data

all_tasks = [tarea_predecesora, tarea_dependiente]

virtual_overrides = {
    '101': {
        'maquina': 'MAC2',
        'porcentaje_solapamiento': 50.0,
        'modo_solapamiento': 'manual'
    }
}

class MockScenario:
    id = 1
    start_time = datetime(2026, 8, 27, 8, 0, 0)
    hora_inicio = datetime.now().time()

scenario = MockScenario()
gantt_data = get_gantt_data(all_tasks, scenario=scenario, plan_mode='manual', virtual_overrides=virtual_overrides)

mac1_tasks = gantt_data['tasks_by_machine']['MAC1']
mac2_tasks = gantt_data['tasks_by_machine']['MAC2']
print(f"Predecesora: Start {mac1_tasks[0]['start_date']} End {mac1_tasks[0]['end_date']}")
print(f"Dependiente: Start {mac2_tasks[0]['start_date']} End {mac2_tasks[0]['end_date']}")
