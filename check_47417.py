import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario

s = Scenario.objects.using('default').filter(es_principal=True).first()
p = PrioridadManual.objects.using('default').filter(id_orden=47417, scenario=s).first()

if p:
    print(f"FOUND: ID={p.id_orden}, Machine={p.maquina}, Prio={p.prioridad}, Level={p.nivel_manual}")
else:
    print(f"NOT FOUND: Querying ALL overrides for 47417 in ANY scenario...")
    all_p = PrioridadManual.objects.using('default').filter(id_orden=47417)
    for row in all_p:
        print(f"  - Sc={row.scenario_id}, M={row.maquina}, P={row.prioridad}, L={row.nivel_manual}")
