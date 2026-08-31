import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.gantt_logic import get_gantt_data

class FakeRequest:
    GET = {}
    session = {}

req = FakeRequest()
req.GET = {'graficar': '1', 'scenario_id': '150', 'plan_mode': 'manual'}

gantt_data = get_gantt_data(req)

# Encontrar la fila de VM3
mac23_row = None
for row in gantt_data.get('timeline_data', []):
    if row.get('machine_id') == 'MAC23':
        mac23_row = row
        break

if mac23_row:
    print('=== VM3 (MAC23) tasks ===')
    tasks_sorted = sorted(mac23_row.get('tasks', []), key=lambda x: x.get('visual_left', 0))
    prev_end = 0
    for t in tasks_sorted:
        left = t.get('visual_left', 0)
        width = t.get('visual_width', 0)
        end = left + width
        overlap_with_prev = left < prev_end
        print(f"  OP {t.get('Idorden')}: left={left:.1f}px width={width:.1f}px end={end:.1f}px {'<== COLISION!' if overlap_with_prev else ''}")
        print(f"    start={t.get('start_date')}  end={t.get('end_date')}")
        print(f"    solapamiento={t.get('porcentaje_solapamiento')}%")
        prev_end = end
else:
    print('MAC23 not found in timeline_data')
