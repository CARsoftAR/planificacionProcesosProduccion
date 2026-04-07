import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()
from produccion.services import get_planificacion_data
from produccion.models import HiddenTask

project_list = ['26-021', '25-072']
raw_data = get_planificacion_data({'proyectos': project_list})
hidden_ids = set(HiddenTask.objects.using('default').values_list('id_orden', flat=True))

print("DEBUG TSUGAMI (MAC38) TASKS:")
for item in raw_data:
    id_maquina = str(item.get('Idmaquina', '')).strip()
    if id_maquina == 'MAC38':
        id_orden = str(item.get('Idorden'))
        h_status = "!! HIDDEN !!" if id_orden in hidden_ids else ""
        print(f"- {id_orden}: {item.get('Articulo')} | {item.get('Descri')} {h_status}")

print("\nDEBUG HAAS (MAC08) TASKS:")
for item in raw_data:
    id_maquina = str(item.get('Idmaquina', '')).strip()
    if id_maquina == 'MAC08':
        id_orden = str(item.get('Idorden'))
        h_status = "!! HIDDEN !!" if id_orden in hidden_ids else ""
        print(f"- {id_orden}: {item.get('Articulo')} | {item.get('Descri')} {h_status}")

print("\nDEBUG BANCO TRABAJO 1 (MAC06) TASKS:")
for item in raw_data:
    id_maquina = str(item.get('Idmaquina', '')).strip()
    if id_maquina == 'MAC06':
        id_orden = str(item.get('Idorden'))
        h_status = "!! HIDDEN !!" if id_orden in hidden_ids else ""
        print(f"- {id_orden}: {item.get('Articulo')} | {item.get('Descri')} {h_status}")
