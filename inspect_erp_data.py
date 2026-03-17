
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.services import get_planificacion_data

def inspect_erp(id_orden):
    print(f"Inspecting ERP data for task {id_orden}...")
    data = get_planificacion_data({'id_orden': id_orden})
    if not data:
        print("  Not found in ERP view.")
        return
    item = data[0]
    print(f"  Idmaquina: {item.get('Idmaquina')}")
    print(f"  MAQUINAD: {item.get('MAQUINAD')}")

if __name__ == "__main__":
    inspect_erp(47122)
    inspect_erp(47123)
    inspect_erp(47124)
    inspect_erp(47125)
    inspect_erp(47126)
