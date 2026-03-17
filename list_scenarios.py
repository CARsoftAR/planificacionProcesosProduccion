
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import Scenario

def list_scenarios():
    print("Listing Scenarios...")
    scenarios = Scenario.objects.all()
    for s in scenarios:
        print(f"  ID: {s.id} | Name: {s.nombre} | Principal: {s.es_principal}")

if __name__ == "__main__":
    list_scenarios()
