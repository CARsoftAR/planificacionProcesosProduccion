import os
import django
import sys
from datetime import date

# Setup Django
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import Feriado

def check_holidays():
    target_date = date(2025, 12, 24)
    print(f"Checking Feriado for {target_date}...")
    
    f = Feriado.objects.filter(fecha=target_date).first()
    
    if f:
        print(f"Found: {f.fecha} - Type: {f.tipo_jornada} - Active: {f.activo}")
    else:
        print("No Feriado found for this date.")
        
    # List all feriados
    print("\nAll Feriados:")
    for fer in Feriado.objects.all():
         print(f"{fer.fecha}: {fer.tipo_jornada} ({fer.descripcion})")

if __name__ == "__main__":
    check_holidays()
