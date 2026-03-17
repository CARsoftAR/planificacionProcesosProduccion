
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario

def check_op(op_id):
    overrides = PrioridadManual.objects.filter(id_orden=op_id)
    print(f"Overrides for OP {op_id}: {overrides.count()}")
    for o in overrides:
        print(f"  ID: {o.id} | Machine: '{o.maquina}' | Priority: {o.prioridad} | Scenario: {o.scenario.nombre if o.scenario else 'None'}")

if __name__ == "__main__":
    check_op(47487)
    # Also check nearby OPs in the screenshot
    check_op(46136) # Position 1 in Image 2
    check_op(46135) # Position 2 in Image 2
    check_op(47553) # Position 3 in Image 2
