"""
Diagnóstico: ¿por qué 26-038 no se guarda en db.sqlite3?
Ejecutar con:  python manage.py shell < diagnostico_26_038.py
O copiar/pegar en python manage.py shell
"""
import os, sys, json, traceback
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
import django
django.setup()

from django.db import connections
from produccion.models import PlannedTask, PrioridadManual, HiddenTask, Scenario

# ============================================================
# CONFIGURACIÓN
# ============================================================
# Usar el escenario 130 como el usuario indicó
try:
    active_scenario = Scenario.objects.using('default').get(id=130)
    print(f"✓ Escenario 130 encontrado: {active_scenario.nombre}")
except Scenario.DoesNotExist:
    print("✗ Escenario 130 no existe. Usando el primer escenario disponible.")
    active_scenario = Scenario.objects.using('default').first()
    print(f"  Usando escenario {active_scenario.id}: {active_scenario.nombre}")

proyectos = ['26-035', '26-037', '26-038']

# ============================================================
# 1. COMPARAR DATOS DEL ERP PARA CADA PROYECTO
# ============================================================
print("\n" + "="*80)
print("1. COMPARACIÓN DE DATOS DEL ERP")
print("="*80)

for proj in proyectos:
    print(f"\n--- Proyecto: {proj} ---")
    v1 = proj
    v2 = proj.replace('-', '.')
    v3 = proj.replace('.', '-')
    codes = list({v1, v2, v3})
    print(f"  Códigos buscados: {codes}")

    with connections['production'].cursor() as cursor:
        # Query 1: OPs por Formula
        where = " OR ".join(["Formula = %s"] * len(codes))
        cursor.execute(f"SELECT Idorden, Articulo, Descri, Idmaquina, Cantidad, Cantidadpp FROM Tman050 WHERE ({where}) AND IsMacro = 0 ORDER BY Idorden", codes)
        ops = cursor.fetchall()
        print(f"  OPs encontradas (IsMacro=0): {len(ops)}")
        for row in ops:
            pend = (row[4] or 0) - (row[5] or 0)
            print(f"    Idorden={row[0]}, Articulo={row[1]}, Proceso={row[2]}, Maquina={repr(row[3])}, Cant={row[4]}, Prod={row[5]}, Pendiente={pend}")

        # Query 2: Artículos (Macro) para este proyecto
        cursor.execute(f"SELECT MacroPK, MAX(Idorden) FROM Tman050 WHERE ({where}) AND IsMacro = 1 GROUP BY MacroPK", codes)
        macros = cursor.fetchall()
        print(f"  Artículos/Macro: {len(macros)}")
        for row in macros:
            print(f"    MacroPK={row[0]}, MAX(Idorden)={row[1]}")

        # Query 3: Datos crudos de las primeras 3 filas
        cursor.execute(f"SELECT TOP 3 * FROM Tman050 WHERE ({where})", codes)
        cols = [c[0] for c in cursor.description]
        print(f"  Columnas Tman050: {cols}")
        for row in cursor.fetchall():
            print(f"    Fila: {dict(zip(cols, row))}")

# ============================================================
# 2. VERIFICAR QUÉ OPs EXISTEN HOY EN db.sqlite3
# ============================================================
print("\n" + "="*80)
print("2. ESTADO ACTUAL EN db.sqlite3 (antes de simular)")
print("="*80)

for proj in proyectos:
    v1 = proj; v2 = proj.replace('-', '.'); v3 = proj.replace('.', '-')
    codes = list({v1, v2, v3})
    pts = PlannedTask.objects.using('default').filter(proyecto_code__in=codes, scenario=active_scenario)
    print(f"  PlannedTask para {proj}: {pts.count()} registros")
    for pt in pts:
        print(f"    id_orden={pt.id_orden}, proyecto_code={pt.proyecto_code}")

# ============================================================
# 3. SIMULAR api_confirm_selected_tasks
# ============================================================
print("\n" + "="*80)
print("3. SIMULACIÓN DEL GUARDADO (PASO 3 de la función)")
print("="*80)

# Simular lo que enviaría el frontend: necesitamos id_ordens de prueba
# Para cada proyecto, tomamos los Idorden que vienen del ERP
id_ordens_por_proyecto = {}

with connections['production'].cursor() as cursor:
    for proj in proyectos:
        v1 = proj; v2 = proj.replace('-', '.'); v3 = proj.replace('.', '-')
        codes = list({v1, v2, v3})
        where = " OR ".join(["Formula = %s"] * len(codes))
        cursor.execute(f"SELECT Idorden FROM Tman050 WHERE ({where}) AND IsMacro = 0 ORDER BY Idorden", codes)
        id_ordens_por_proyecto[proj] = [str(row[0]) for row in cursor.fetchall()]
        print(f"  {proj}: id_ordens = {id_ordens_por_proyecto[proj]}")

print("\n--- Ejecutando update_or_create para cada proyecto ---")

for proj in proyectos:
    print(f"\n>>> Procesando {proj}...")
    id_list = id_ordens_por_proyecto.get(proj, [])
    
    if not id_list:
        print(f"  ✗ Sin OPs para {proj}, se salta")
        # Aún así, registrar proyecto en escenario
        p_list = [p.strip() for p in (active_scenario.proyectos or "").split(",") if p.strip()]
        if proj not in p_list:
            p_list.append(proj)
            active_scenario.proyectos = ",".join(p_list)
            active_scenario.save(using='default')
            print(f"  ✓ Proyecto {proj} registrado en escenario (sin OPs)")
        continue

    # PASO 2: Obtener máquinas del ERP
    op_maquina_map = {}
    with connections['production'].cursor() as cursor:
        placeholders = ', '.join(['%s'] * len(id_list))
        cursor.execute(f"""
            SELECT Idorden, Idmaquina FROM Tman050 WHERE Idorden IN ({placeholders})
        """, id_list)
        for row in cursor.fetchall():
            oid = str(row[0])
            maq = str(row[1]).strip() if row[1] is not None else 'SIN ASIGNAR'
            op_maquina_map[oid] = maq
            print(f"    ERP: OP {oid} → Máquina {repr(maq)}")

    # PASO 3: update_or_create
    for oid in id_list:
        try:
            oid_str = str(oid)
            maquina = op_maquina_map.get(oid_str, 'SIN ASIGNAR')
            
            pt, created_pt = PlannedTask.objects.using('default').update_or_create(
                id_orden=oid,
                scenario=active_scenario,
                defaults={'proyecto_code': proj}
            )
            
            pm, created_pm = PrioridadManual.objects.using('default').update_or_create(
                id_orden=oid,
                scenario=active_scenario,
                maquina=maquina,
                defaults={
                    'nivel_manual': 1,
                    'prioridad': 1.0,
                    'orden_secuencia': 0,
                }
            )
            
            accion_pt = "CREATED" if created_pt else "UPDATED"
            accion_pm = "CREATED" if created_pm else "UPDATED"
            print(f"    ✓ OP {oid}: PlannedTask {accion_pt}, PrioridadManual {accion_pm} → Máq {maquina}")
            
        except Exception as e:
            print(f"    ✗ ERROR en OP {oid}: {e}")
            traceback.print_exc()
            continue

    # Registrar proyecto en escenario
    p_list = [p.strip() for p in (active_scenario.proyectos or "").split(",") if p.strip()]
    if proj not in p_list:
        p_list.append(proj)
        active_scenario.proyectos = ",".join(p_list)
        active_scenario.save(using='default')
        print(f"    ✓ Proyecto {proj} registrado en escenario")

# ============================================================
# 4. VERIFICAR RESULTADOS EN db.sqlite3
# ============================================================
print("\n" + "="*80)
print("4. ESTADO FINAL EN db.sqlite3")
print("="*80)

for proj in proyectos:
    v1 = proj; v2 = proj.replace('-', '.'); v3 = proj.replace('.', '-')
    codes = list({v1, v2, v3})
    pts = PlannedTask.objects.using('default').filter(proyecto_code__in=codes, scenario=active_scenario)
    pms = PrioridadManual.objects.using('default').filter(
        id_orden__in=[pt.id_orden for pt in pts],
        scenario=active_scenario
    ) if pts else PrioridadManual.objects.none()
    
    print(f"\n  {proj}:")
    print(f"    PlannedTask: {pts.count()} registros")
    for pt in pts:
        pm = pms.filter(id_orden=pt.id_orden).first()
        maq = pm.maquina if pm else 'SIN ASIGNAR'
        print(f"      OP {pt.id_orden} → Máq {maq}")
    print(f"    En escenario.proyectos: {proj in (active_scenario.proyectos or '')}")

print("\n" + "="*80)
print("DIAGNÓSTICO COMPLETADO")
print("="*80)
print(f"\nEscenario {active_scenario.id} — proyectos: {active_scenario.proyectos}")
