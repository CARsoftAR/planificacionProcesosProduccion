import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

# Project 26-021
data = get_planificacion_data({'articulos_p': ['26-021']})

for d in data:
    proyecto = d.get('ProyectoCode', 'S/P')
    maquina_d = d.get('MAQUINAD', 'SIN ASIGNAR')
    maquina_id = d.get('Idmaquina', '')
    proceso = d.get('Descri', '-')
    print(f"{proyecto:<10} | ID:{maquina_id:<8} | D:{maquina_d:<20} | {proceso}")
