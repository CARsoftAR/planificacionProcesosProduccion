import os
import sys
import django

# Setup Django environment
sys.path.append(r"c:\Sistemas ABBAMAT\planificacionProcesosProductivos EN DESARROLLO")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "planificacion.settings")
django.setup()

from produccion.models import PrioridadManual

print("--- PrioridadManual OP 48649 ---")
for p in PrioridadManual.objects.using('default').filter(id_orden=48649):
    print(f"Scenario: {p.scenario_id}, Maquina: {p.maquina}, Nivel Manual: {p.nivel_manual}, Prioridad: {p.prioridad}")
