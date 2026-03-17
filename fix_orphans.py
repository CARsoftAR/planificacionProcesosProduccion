
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, Scenario

def fix_orphans():
    principal = Scenario.objects.filter(es_principal=True).first()
    if not principal:
        print("No principal scenario found!")
        return
    
    orphans = PrioridadManual.objects.filter(scenario__isnull=True)
    count = orphans.count()
    if count > 0:
        print(f"Fixing {count} orphan overrides. Setting them to Scenario: {principal.nombre} (ID: {principal.id})")
        orphans.update(scenario=principal)
        print("Done.")
    else:
        print("No orpans found.")

if __name__ == "__main__":
    fix_orphans()
