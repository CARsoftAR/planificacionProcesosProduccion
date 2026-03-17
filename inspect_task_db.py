
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario

def inspect_task(id_orden):
    print(f"Inspecting task {id_orden}...")
    overrides = PrioridadManual.objects.filter(id_orden=id_orden)
    print(f"Found {overrides.count()} overrides.")
    for o in overrides:
        print(f"  Scenario: {o.scenario.nombre if o.scenario else 'None'} (ID: {o.scenario_id})")
        print(f"  Machine: {o.maquina}")
        print(f"  Priority: {o.prioridad}")

if __name__ == "__main__":
    inspect_task(47122)
    inspect_task(47123)
    inspect_task(47124)
    inspect_task(47125)
    inspect_task(47126)
