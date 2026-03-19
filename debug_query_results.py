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
    print(f"--- DEPURA QUERY PARA: {proyectos} ---")
    
    local_machines = MaquinaConfig.objects.using('default').all()
    m_ids = [m.id_maquina.strip() for m in local_machines]
    print(f"Machine IDs in config: {m_ids}")
    
    filtros = {
        'proyectos': proyectos,
        'machine_ids': m_ids
    }
    
    data = get_planificacion_data(filtros)
    print(f"Registros encontrados con machine filter: {len(data)}")
    
    if len(data) == 0:
        print("Buscando SIN machine filter...")
        filtros_no_m = {'proyectos': proyectos}
        data_no_m = get_planificacion_data(filtros_no_m)
        print(f"Registros encontrados SIN machine filter: {len(data_no_m)}")
        if len(data_no_m) > 0:
            print("Ejemplos de maquinas encontradas en ERP para estos proyectos:")
            unique_mq = set(d.get('Idmaquina') for d in data_no_m)
            print(f"  IDs de maquina en ERP: {unique_mq}")
            unique_mq_d = set(d.get('MAQUINAD') for d in data_no_m)
            print(f"  Nombres de maquina en ERP: {unique_mq_d}")

if __name__ == "__main__":
    debug_query(['25-074', '25-032'])
