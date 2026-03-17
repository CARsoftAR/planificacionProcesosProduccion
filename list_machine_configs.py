
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import MaquinaConfig

def list_configs():
    print("Listing MaquinaConfig...")
    configs = MaquinaConfig.objects.all().order_by('id_maquina')
    for c in configs:
        print(f"  ID: {c.id_maquina} | Name: {c.nombre}")

if __name__ == "__main__":
    list_configs()
