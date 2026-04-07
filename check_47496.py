"""
Busca TODOS los overrides de 47496 en TODOS los escenarios.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario

print("Todos los overrides para 47496 en todos los escenarios:")
for p in PrioridadManual.objects.using('default').filter(id_orden='47496'):
    s = Scenario.objects.using('default').filter(pk=p.scenario_id).first()
    print(f"  Escenario {p.scenario_id} ({s.nombre if s else '?'}): maquina={p.maquina}, prio={p.prioridad}, inicio_manual={p.fecha_inicio_manual}")

print("\nTodos los overrides que van hacia MAC08 en todos los escenarios:")
for p in PrioridadManual.objects.using('default').filter(maquina='MAC08'):
    s = Scenario.objects.using('default').filter(pk=p.scenario_id).first()
    print(f"  Orden {p.id_orden} | Escenario {p.scenario_id} ({s.nombre if s else '?'}): prio={p.prioridad}, inicio_manual={p.fecha_inicio_manual}")

print("\nEscenario activo en sesión sería el principal:")
s = Scenario.objects.using('default').filter(es_principal=True).first()
print(f"  ID={s.id}, Nombre={s.nombre}")
