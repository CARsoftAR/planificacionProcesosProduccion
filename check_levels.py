"""
Verifica los niveles y prioridades de las tareas en HAAS.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import Scenario, PrioridadManual
from produccion.services import get_planificacion_data

# Project filter from the screenshot
filtros = {'proyectos': ['26-021', '25-072']}
all_tasks = get_planificacion_data(filtros)

# Machines of interest
machines = ['MAC08', 'MAC38'] # Haas and Tsugami

print(f"{'ID':<8} | {'Maquina':<15} | {'Nivel':<6} | {'Nivel_Plan':<10} | {'Prioridad':<10} | {'Descri'}")
print("-" * 80)

for t in all_tasks:
    mid = str(t.get('Idmaquina', '')).strip().upper()
    mnand = str(t.get('MAQUINAD', '')).strip().upper()
    
    if 'MAC08' in mid or 'HAAS' in mnand or 'MAC38' in mid or 'TSUGAMI' in mnand:
        oid = str(t.get('Idorden'))
        nivel = t.get('Nivel', 0)
        nivel_p = t.get('Nivel_Planificacion', 0)
        
        # Check if it has override
        ov = PrioridadManual.objects.filter(id_orden=oid, maquina='MAC08').first()
        ov_str = f"P={ov.prioridad} L={ov.nivel_manual}" if ov else "No OV"
        
        print(f"{oid:<8} | {mnand[:15]:<15} | {nivel:<6} | {nivel_p:<10} | {ov_str:<10} | {t.get('Descri', '')[:30]}")
