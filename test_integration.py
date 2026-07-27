import os
import django
import json

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.test import Client
from produccion.models import Scenario, PrioridadManual, PlannedTask

def test_integration():
    client = Client()
    
    # 1. Obtener o crear un escenario
    scenario = Scenario.objects.using('default').first()
    if not scenario:
        print("No se encontraron escenarios, el test no puede ejecutarse.")
        return
        
    print(f"--- TEST DE INTEGRACIÓN: GRABAR ESCENARIO ---")
    print(f"Escenario: {scenario.nombre} (ID: {scenario.id})")
    
    # Obtener un par de tareas de PrioridadManual
    tareas = list(PrioridadManual.objects.using('default').filter(scenario=scenario)[:3])
    if len(tareas) < 2:
        print("No hay suficientes tareas manuales para probar. Test abortado.")
        return
        
    maquina = tareas[0].maquina
    print(f"Máquina a probar: {maquina}")
    print(f"Orden antes de guardar:")
    for t in tareas:
        print(f"  OP: {t.id_orden} | Seq: {t.orden_secuencia} | Prio: {t.prioridad}")
        
    # Invertir el orden (simular drag & drop)
    secuencias = []
    for idx, t in enumerate(reversed(tareas)):
        secuencias.append({
            'id_orden': t.id_orden,
            'maquina': maquina,
            'orden_secuencia': idx
        })
        
    print("\nPayload secuencias simulando reordenamiento manual:")
    print(json.dumps(secuencias, indent=2))
    
    payload = {
        'nombre': scenario.nombre,
        'id': scenario.id,
        'update_id': scenario.id,
        'secuencias': secuencias,
        'plan_mode': 'manual'
    }
    
    print("\nEnviando POST a /api/scenarios/create/ ...")
    response = client.post('/api/scenarios/create/', data=json.dumps(payload), content_type='application/json')
    
    print(f"Respuesta HTTP: {response.status_code}")
    print(f"Body: {response.content.decode('utf-8')}")
    
    # 3. Auditoría de datos post-guardado
    print("\n--- AUDITORÍA POST-GUARDADO ---")
    tareas_post = PrioridadManual.objects.using('default').filter(scenario=scenario, id_orden__in=[t.id_orden for t in tareas]).order_by('orden_secuencia')
    
    def mock_obtener_clave(op, mode):
        orden_visual = float(op.get('OrdenVisual', 1000.0))
        return (0, orden_visual, op.get('Idorden'))
        
    for t in tareas_post:
        op = {
            'Idorden': t.id_orden,
            'OrdenVisual': t.prioridad, 
            'OrdenSecuencia': t.orden_secuencia
        }
        clave = mock_obtener_clave(op, mode='manual')
        print(f"OP: {t.id_orden} | DB_Seq: {t.orden_secuencia} | DB_Prio (OrdenVisual): {t.prioridad} -> Clave de ordenamiento: {clave}")

if __name__ == '__main__':
    test_integration()
