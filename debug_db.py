import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual

def test_db():
    print("--- VERIFICANDO TABLA LOCAL ---")
    try:
        count = PrioridadManual.objects.using('default').count()
        print(f"   -> EXITO: Tabla 'prioridad_manual' existe. Filas: {count}")
    except Exception as e:
        print(f"   !!! ERROR: La tabla no existe o no es accesible: {e}")


if __name__ == "__main__":
    test_db()
