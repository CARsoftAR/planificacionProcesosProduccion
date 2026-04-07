"""
Realiza una limpieza completa de TODOS los overrides con prioridad=1 en TODOS los escenarios hacia MAC08.
Estos son residuos de redistribuciones masivas anteriores.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario

print("Buscando overrides MAC08+prioridad=1 en TODOS los escenarios:")
faulty = PrioridadManual.objects.using('default').filter(maquina='MAC08', prioridad=1.0)
print(f"Total: {faulty.count()}")
for p in faulty:
    s = Scenario.objects.using('default').filter(pk=p.scenario_id).first()
    print(f"  Orden {p.id_orden} | Escenario {p.scenario_id} ({s.nombre if s else '?'})")

if faulty.exists():
    d = faulty.delete()
    print(f"\n✅ Borrados: {d[0]} registros")
else:
    print("\n✅ No hay nada que borrar")
