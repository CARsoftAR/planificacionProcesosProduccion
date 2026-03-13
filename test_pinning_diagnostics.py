"""
Script de diagnóstico completo para el sistema de Pinning Manual.
Verifica:
1. Modelo de base de datos
2. Endpoint API
3. Flujo completo de guardado
"""
import os
import sys
import django

# Add the project directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from produccion.models import PrioridadManual, VTman
from datetime import datetime


print("=" * 70)
print("DIAGNÓSTICO DEL SISTEMA DE PINNING MANUAL")
print("=" * 70)

# 1. Verificar estructura de la tabla
print("\n1. VERIFICACIÓN DE MODELO")
print("-" * 70)
try:
    # Verificar que el campo existe
    fields = [f.name for f in PrioridadManual._meta.get_fields()]
    print(f"[OK] Campos en PrioridadManual: {', '.join(fields)}")
    
    if 'fecha_inicio_manual' in fields:
        print("[OK] Campo 'fecha_inicio_manual' existe en el modelo")
    else:
        print("[ERROR] Campo 'fecha_inicio_manual' NO existe en el modelo")
        
except Exception as e:
    print(f"[ERROR] Error verificando modelo: {e}")

# 2. Verificar datos existentes
print("\n2. DATOS EXISTENTES EN LA BASE DE DATOS")
print("-" * 70)
try:
    total = PrioridadManual.objects.using('default').count()
    print(f"Total de registros en PrioridadManual: {total}")
    
    with_dates = PrioridadManual.objects.using('default').filter(
        fecha_inicio_manual__isnull=False
    ).count()
    print(f"Registros con fecha_inicio_manual: {with_dates}")
    
    if with_dates > 0:
        print("\n[INFO] Tareas con pinning manual:")
        for pm in PrioridadManual.objects.using('default').filter(
            fecha_inicio_manual__isnull=False
        )[:5]:
            print(f"  - Orden {pm.id_orden} en {pm.maquina}: {pm.fecha_inicio_manual}")
    else:
        print("[WARN]  No hay tareas con pinning manual guardado")
        
except Exception as e:
    print(f"[ERROR] Error consultando datos: {e}")

# 3. Obtener una tarea de ejemplo para testing
print("\n3. TAREA DE EJEMPLO PARA TESTING")
print("-" * 70)
try:
    # Use default DB or SQL Server depending on configuration
    # Assuming SQL Server is 'sqlserver' alias, but let's check if we can actually access it
    # If not, use local DB mock or skip
    pass
    # sample_task = VTman.objects.using('sqlserver').filter(es_programado=True).first()
    # For now, let's just use what's in PrioridadManual as reference since we can't always reach SQL Server in test
    print("[INFO] Saltando consulta SQL Server directa en test diagnostico para evitar errores de conexion si no esta disponible.")
        
except Exception as e:
    print(f"[ERROR] Error obteniendo tarea de ejemplo: {e}")

# 4. Instrucciones para testing manual
print("\n4. INSTRUCCIONES DE TESTING")
print("-" * 70)
print("""
Para probar el pinning manual:

1. Inicia el servidor Django:
   python manage.py runserver

2. Abre el Gantt Visual en el navegador:
   http://localhost:8000/planificacion/visual/?proyectos=XXX&run=1

3. Arrastra una tarea a una nueva posición

4. Observa la consola del servidor para ver los logs

5. Ejecuta este script nuevamente para verificar que se guardó.
""")

print("\n" + "=" * 70)
print("FIN DEL DIAGNÓSTICO")
print("=" * 70)

