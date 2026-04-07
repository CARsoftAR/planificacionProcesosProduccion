"""
Limpia overrides incorrectos de MAC08 creados por redistribuciones anteriores con prioridad=1 o con fecha_inicio_manual.
Deja solo los overrides manuales que el usuario puso deliberadamente (los de prioridad != 1 y sin fecha_inicio_manual).
"""
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario

scenario = Scenario.objects.using('default').filter(es_principal=True).first()
print(f"Escenario: {scenario.nombre}")

# Find all MAC08 overrides
all_mac08 = PrioridadManual.objects.using('default').filter(scenario=scenario, maquina='MAC08')
print(f"\nTotal overrides MAC08: {all_mac08.count()}")

# Classify them
to_delete = []
to_keep = []

for p in all_mac08:
    # Delete if: prioridad=1 (mass redistribution), or prioridad >= 99000 (previous auto-redistribution), or has fecha_inicio_manual (wrong pin)
    is_mass = float(p.prioridad or 0) == 1.0
    is_auto = float(p.prioridad or 0) >= 99000
    has_pin = p.fecha_inicio_manual is not None

    if is_mass or is_auto or has_pin:
        to_delete.append(p.id_orden)
        reason = []
        if is_mass: reason.append('prioridad=1')
        if is_auto: reason.append(f'prioridad={p.prioridad}>=99000')
        if has_pin: reason.append(f'fecha_inicio={p.fecha_inicio_manual}')
        print(f"  BORRAR {p.id_orden}: {', '.join(reason)}")
    else:
        to_keep.append(p.id_orden)

print(f"\nA borrar: {len(to_delete)}")
print(f"A conservar: {len(to_keep)} → {to_keep}")

if to_delete:
    deleted = PrioridadManual.objects.using('default').filter(
        scenario=scenario,
        maquina='MAC08',
        id_orden__in=to_delete
    ).delete()
    print(f"\n✅ Borrados: {deleted[0]} registros")
else:
    print("\n✅ No hay nada que borrar")
