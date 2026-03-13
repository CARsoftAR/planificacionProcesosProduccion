
import os
import django
import sys

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import Scenario, PrioridadManual

def init_scenarios():
    print("Iniciando Migracion de Escenarios...")
    
    # 1. Check/Create Default Scenario
    try:
        official, created = Scenario.objects.get_or_create(
            es_principal=True,
            defaults={'nombre': 'Plan Oficial', 'descripcion': 'Plan de produccion principal'}
        )
        
        if created:
            print(f"[OK] Creado escenario por defecto: {official}")
        else:
            print(f"[INFO] Escenario oficial ya existe: {official}")
            
        # 2. Link orphaned PrioridadManuals (scenario IS NULL) to official
        orphans = PrioridadManual.objects.filter(scenario__isnull=True)
        count = orphans.count()
        
        if count > 0:
            print(f"[WARN] Encontrados {count} overrides huerfanos. Vinculando a Plan Oficial...")
            orphans.update(scenario=official)
            print("[OK] Vinculacion completada.")
        else:
            print("[OK] No hay overrides huerfanos.")
            
        # List all scenarios
        print("\nEscenarios Disponibles:")
        for s in Scenario.objects.all():
            count = PrioridadManual.objects.filter(scenario=s).count()
            print(f" - [{s.id}] {s.nombre} ({'OFICIAL' if s.es_principal else 'DRAFT'}) -> {count} overrides")
            
    except Exception as e:
        print(f"[ERROR] {e}")

if __name__ == "__main__":
    init_scenarios()
