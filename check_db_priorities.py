
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario

def check_priorities():
    scenarios = Scenario.objects.all()
    print(f"Total scenarios: {scenarios.count()}")
    for s in scenarios:
        overrides = PrioridadManual.objects.filter(scenario=s).order_by('prioridad')
        print(f"\nScenario: {s.nombre} (ID: {s.id}) - {overrides.count()} overrides")
        for o in overrides[:20]:
            print(f"  OP: {o.id_orden} | Machine: {o.maquina} | Priority: {o.prioridad}")

if __name__ == "__main__":
    check_priorities()
