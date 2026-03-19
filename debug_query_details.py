import os
import django
import sys
import json
from django.db import connections

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data
from produccion.models import MaquinaConfig

def debug_query(proyectos):
    local_machines = MaquinaConfig.objects.using('default').all()
    m_ids = [m.id_maquina.strip() for m in local_machines]
    
    filtros = {
        'proyectos': proyectos,
        'machine_ids': m_ids
    }
    
    data = get_planificacion_data(filtros)
    print(f"Registros encontrados: {len(data)}")
    for d in data:
        print(f"OP: {d['Idorden']} | Proyecto: {d['ProyectoCode']} | MaquinaID: {d['Idmaquina']} | MaquinaD: {d['MAQUINAD']}")

if __name__ == "__main__":
    debug_query(['25-074', '25-032'])
