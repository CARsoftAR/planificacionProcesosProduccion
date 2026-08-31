import os, django, datetime
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()
from produccion.gantt_logic import _build_gantt_timeline
from produccion.models import MaquinaConfig, Scenario

m = MaquinaConfig.objects.using('default').first()
# Two tasks on the same machine!
task1 = {
    'Idorden': '101',
    'ProyectoCode': 'PROJ-TEST',
    '_maq': m,
    'MAQUINAD': m.nombre,
    'Tiempo_Proceso': 10,
    'prioridad_pieza': 1,
    'nivel_planificacion': 10,
    'is_pinned': False,
    'porcentaje_solapamiento': 0,
    'modo_solapamiento': 'manual'
}
task2 = {
    'Idorden': '102',
    'ProyectoCode': 'PROJ-TEST',
    '_maq': m,
    'MAQUINAD': m.nombre,
    'Tiempo_Proceso': 10,
    'prioridad_pieza': 2,
    'nivel_planificacion': 10,
    'is_pinned': False,
    'porcentaje_solapamiento': 50, # 50% overlap!
    'modo_solapamiento': 'manual'
}

valid_dates = [datetime.datetime.now().date() + datetime.timedelta(days=i) for i in range(10)]
date_start_col = {d: i*24 for i, d in enumerate(valid_dates)}
start_simulation = datetime.datetime.now()

timeline = _build_gantt_timeline([task1, task2], 'manual', valid_dates, date_start_col, {}, start_simulation, None, None)

for row in timeline:
    for t in row['tasks']:
        print(f"Task {t.get('Idorden')} -> Start: {t.get('start_date')}, End: {t.get('end_date')}")

