"""
Analisis de la OP 47331 y explicacion de Ruta Critica.
"""
import os
import sys
import django

sys.path.insert(0, r'C:\Sistemas ABBAMAT\planificacionProcesosProductivos')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from datetime import datetime
from produccion.gantt_logic import get_gantt_data

class MockRequest:
    def __init__(self):
        self.GET = {'run': '1', 'fecha_desde': '2026-03-16'}
        self.session = {}
        self.method = 'GET'

request = MockRequest()
data = get_gantt_data(request, force_run=True)

print("=" * 70)
print("ANALISIS DE LA OP 47331")
print("=" * 70)

# Buscar la OP 47331
tarea_47331 = None
for row in data['timeline_data']:
    for task in row['tasks']:
        if task.get('Idorden') == 47331:
            tarea_47331 = task
            tarea_47331['machine_name'] = row['machine'].nombre if hasattr(row['machine'], 'nombre') else str(row['machine'])
            break

if tarea_47331:
    start = tarea_47331.get('start_date')
    end = tarea_47331.get('end_date')
    proyecto = tarea_47331.get('ProyectoCode', '')

    print(f"\nOP 47331:")
    print(f"  Maquina: {tarea_47331.get('machine_name')}")
    print(f"  Proyecto: {proyecto}")
    print(f"  Descripcion: {tarea_47331.get('Descri', '')}")
    print(f"  Inicio: {start}")
    print(f"  Fin: {end}")
    print(f"  Duracion: {tarea_47331.get('duration_real', 0):.2f}h")
    print(f"  Es Ruta Critica: {'SI - HAY QUE PRESTAR ATENCION!' if tarea_47331.get('is_critical') else 'NO'}")

    # Buscar todas las tareas del proyecto
    print(f"\n" + "=" * 70)
    print(f"TODAS LAS TAREAS DEL PROYECTO {proyecto} (ordenadas por inicio):")
    print("=" * 70)

    tareas_proyecto = []
    for row in data['timeline_data']:
        machine = row['machine'].nombre if hasattr(row['machine'], 'nombre') else str(row['machine'])
        for task in row['tasks']:
            if task.get('ProyectoCode') == proyecto and task.get('segment_index', 0) == 0:
                tareas_proyecto.append({
                    'Idorden': task.get('Idorden'),
                    'machine': machine,
                    'start': task.get('start_date'),
                    'end': task.get('end_date'),
                    'is_critical': task.get('is_critical', False),
                })

    tareas_proyecto.sort(key=lambda x: x['start'] if x['start'] else datetime.max)

    print(f"\n{'OP':<8} | {'Maquina':<18} | {'Inicio':>12} | {'Fin':>12} | RC")
    print("-" * 75)
    for t in tareas_proyecto:
        crit = "*** CRITICA ***" if t['is_critical'] else ""
        print(f"{t['Idorden']:<8} | {t['machine']:<18} | {t['start'].strftime('%d/%m %H:%M') if t['start'] else 'N/A':>12} | {t['end'].strftime('%d/%m %H:%M') if t['end'] else 'N/A':>12} | {crit}")

    # Identificar la cadena critica
    print(f"\n" + "=" * 70)
    print("EXPLICACION DE RUTA CRITICA:")
    print("=" * 70)

    criticas = [t for t in tareas_proyecto if t['is_critical']]
    if criticas:
        print(f"\nTareas criticas del proyecto {proyecto}:")
        for t in criticas:
            print(f"  OP {t['Idorden']} en {t['machine']}")
            print(f"    ({t['start'].strftime('%d/%m %H:%M')} - {t['end'].strftime('%d/%m %H:%M')})")

        # Encontrar la tarea que determina el fin del proyecto
        tarea_final = max(tareas_proyecto, key=lambda x: x['end'] if x['end'] else datetime.min)
        print(f"\nTarea que determina el FIN del proyecto:")
        print(f"  OP {tarea_final['Idorden']} en {tarea_final['machine']}")
        print(f"  Termina: {tarea_final['end'].strftime('%d/%m %H:%M')}")

        print(f"\nQue significa?")
        print(f"  - La ruta critica es la cadena de tareas que determina cuando termina el proyecto")
        print(f"  - Si cualquier tarea CRITICA se retrasa, TODO el proyecto se retrasa")
        print(f"  - Las tareas NO criticas tienen 'slack' (margen) y pueden atrasarse un poco sin afectar el proyecto")
    else:
        print(f"\nNo hay tareas criticas en el proyecto {proyecto} segun los datos actuales.")
else:
    print("OP 47331 no encontrada!")
