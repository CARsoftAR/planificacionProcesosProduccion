"""
Elimina el override incorrecto de 47496 del Escenario 1 (Plan Oficial).
También muestra el estado completo de todos los escenarios.
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario

# Show all scenarios
print("Todos los Escenarios:")
for s in Scenario.objects.all():
    count = PrioridadManual.objects.filter(scenario=s).count()
    print(f"  ID={s.id}: '{s.nombre}' | es_principal={s.es_principal} | overrides={count}")

# Delete the spurious 47496 override in Escenario 1
deleted = PrioridadManual.objects.using('default').filter(
    scenario_id=1,
    id_orden='47496'
).delete()
print(f"\nBorrado override 47496 en Escenario 1: {deleted[0]} registros")

# Also delete any prioridad=1 overrides in Escenario 1 pointing to MAC08  
faulty_s1 = PrioridadManual.objects.using('default').filter(
    scenario_id=1,
    maquina='MAC08',
    prioridad=1.0
)
print(f"\nOtros overrides en Escenario 1 con MAC08+prioridad=1: {faulty_s1.count()}")
if faulty_s1.exists():
    for p in faulty_s1:
        print(f"  Orden {p.id_orden}")
    deleted2 = faulty_s1.delete()
    print(f"  Borrados: {deleted2[0]}")

print("\n✅ Limpieza completada.")
