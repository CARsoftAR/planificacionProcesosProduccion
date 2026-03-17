
import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, MaquinaConfig

def cleanup():
    # 1. Map Names to IDs
    machines = MaquinaConfig.objects.all()
    name_to_id = {m.nombre: m.id_maquina for m in machines}
    print(f"Machine map: {name_to_id}")

    # 2. Harmonize Names to IDs in all records
    all_overrides = PrioridadManual.objects.all()
    print(f"Total overrides: {all_overrides.count()}")
    
    updated = 0
    for o in all_overrides:
        if o.maquina in name_to_id:
            new_id = name_to_id[o.maquina]
            if o.maquina != new_id:
                print(f"  Updating {o.id}: {o.maquina} -> {new_id}")
                o.maquina = new_id
                o.save()
                updated += 1
    print(f"Updated {updated} records to use IDs.")

    # 3. Remove duplicates
    all_overrides = PrioridadManual.objects.all().order_by('id') # Oldest first
    seen = {} # (op, machine, scenario) -> id
    to_delete = []
    
    for o in all_overrides:
        key = (o.id_orden, o.maquina, o.scenario_id)
        if key in seen:
            # Current one is newer (higher ID), so delete the OLD one if the new one is "better" 
            # or just delete the old one to keep the latest.
            to_delete.append(seen[key])
            seen[key] = o.id
        else:
            seen[key] = o.id
            
    if to_delete:
        print(f"Deleting {len(to_delete)} duplicate older records...")
        PrioridadManual.objects.filter(id__in=to_delete).delete()
    else:
        print("No duplicates found.")

if __name__ == "__main__":
    cleanup()
