"""
Diagnostic: Compare raw task counts for TM1 and TSUGAMI
to find why our system returns fewer records than the old system.
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.db import connections

def run():
    cursor = connections['production'].cursor()
    
    projects = ['26-002', '26-003', '26-004', '26.002', '26.003', '26.004']
    project_likes = " OR ".join([f"T2.Formula LIKE '%{p}%'" for p in projects])
    
    print("=" * 100)
    print("DIAGNOSTIC: Comparing task counts for TM1 and TSUGAMI")
    print("=" * 100)
    
    # 1. RAW COUNT without any filter
    print("\n--- 1. RAW COUNT per machine (NO state filter, NO DISTINCT, NO T3) ---")
    sql1 = f"""
    SELECT 
        ISNULL(MAC.MAQUINAD, T.Idmaquina) AS Maquina,
        COUNT(*) as Total,
        COUNT(DISTINCT T.IdOrden) as DistinctOrdenes
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE ({project_likes})
      AND (MAC.MAQUINAD LIKE '%TM1%' OR MAC.MAQUINAD LIKE '%TSUGAMI%')
    GROUP BY ISNULL(MAC.MAQUINAD, T.Idmaquina)
    ORDER BY Maquina
    """
    cursor.execute(sql1)
    for r in cursor.fetchall():
        print(f"  Machine: {str(r[0]).strip():30s} | Total: {r[1]:5d} | Distinct IdOrden: {r[2]:5d}")
    
    # 2. With state filter
    print("\n--- 2. WITH STATE FILTER (excluding 3,4,5) ---")
    sql2 = f"""
    SELECT 
        ISNULL(MAC.MAQUINAD, T.Idmaquina) AS Maquina,
        COUNT(*) as Total,
        COUNT(DISTINCT T.IdOrden) as DistinctOrdenes
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE ({project_likes})
      AND T.Idestado NOT IN ('3', '4', '5')
      AND T2.Idestado NOT IN ('3', '4', '5')
      AND (MAC.MAQUINAD LIKE '%TM1%' OR MAC.MAQUINAD LIKE '%TSUGAMI%')
    GROUP BY ISNULL(MAC.MAQUINAD, T.Idmaquina)
    ORDER BY Maquina
    """
    cursor.execute(sql2)
    for r in cursor.fetchall():
        print(f"  Machine: {str(r[0]).strip():30s} | Total: {r[1]:5d} | Distinct IdOrden: {r[2]:5d}")

    # 3. Impact of T3 JOIN
    print("\n--- 3. IMPACT OF TMAN002 (T3) JOIN ---")
    sql3a = f"""
    SELECT ISNULL(MAC.MAQUINAD, T.Idmaquina) AS Maquina, COUNT(*) as Cnt
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE ({project_likes})
      AND (MAC.MAQUINAD LIKE '%TM1%' OR MAC.MAQUINAD LIKE '%TSUGAMI%')
    GROUP BY ISNULL(MAC.MAQUINAD, T.Idmaquina)
    """
    cursor.execute(sql3a)
    rows_without = dict()
    for r in cursor.fetchall():
        rows_without[str(r[0]).strip()] = r[1]
    
    # With T3 and ArticuloP constraint (our system)
    sql3b = f"""
    SELECT ISNULL(MAC.MAQUINAD, T.Idmaquina) AS Maquina, COUNT(*) as Cnt
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN TMAN002 T3 ON T.Articulo = T3.ArticuloH AND T.Formula = T3.Formula AND T2.Articulo = T3.ArticuloP
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE ({project_likes})
      AND (MAC.MAQUINAD LIKE '%TM1%' OR MAC.MAQUINAD LIKE '%TSUGAMI%')
    GROUP BY ISNULL(MAC.MAQUINAD, T.Idmaquina)
    """
    cursor.execute(sql3b)
    rows_with = dict()
    for r in cursor.fetchall():
        rows_with[str(r[0]).strip()] = r[1]
    
    # With T3 WITHOUT ArticuloP constraint (old system?)
    sql3c = f"""
    SELECT ISNULL(MAC.MAQUINAD, T.Idmaquina) AS Maquina, COUNT(*) as Cnt
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN TMAN002 T3 ON T.Articulo = T3.ArticuloH AND T.Formula = T3.Formula
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE ({project_likes})
      AND (MAC.MAQUINAD LIKE '%TM1%' OR MAC.MAQUINAD LIKE '%TSUGAMI%')
    GROUP BY ISNULL(MAC.MAQUINAD, T.Idmaquina)
    """
    cursor.execute(sql3c)
    rows_loose = dict()
    for r in cursor.fetchall():
        rows_loose[str(r[0]).strip()] = r[1]
    
    all_machines = sorted(set(list(rows_without.keys()) + list(rows_with.keys()) + list(rows_loose.keys())))
    print(f"  {'Machine':25s} | {'No T3':8s} | {'T3+ArtP':8s} | {'T3 loose':8s}")
    print(f"  {'-'*60}")
    for m in all_machines:
        print(f"  {m:25s} | {rows_without.get(m, 0):8d} | {rows_with.get(m, 0):8d} | {rows_loose.get(m, 0):8d}")

    # 4. TM1 DETAIL
    print("\n--- 4. TM1 DETAIL: ALL rows (no state filter) ---")
    sql4 = f"""
    SELECT 
        T2.Formula AS Proyecto,
        T.Idorden,
        T.Descri,
        T.Idestado,
        T.Cantidad,
        T.Cantidadpp,
        (T.Cantidad - T.Cantidadpp) AS Pendientes
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE ({project_likes})
      AND MAC.MAQUINAD LIKE '%TM1%'
    ORDER BY T2.Formula, T.Idorden
    """
    cursor.execute(sql4)
    rows = cursor.fetchall()
    print(f"  {'Proyecto':10s} {'IdOrden':10s} {'Descri':40s} {'Estado':6s} {'Cant':8s} {'Prod':8s} {'Pend':8s}")
    print(f"  {'-'*100}")
    for r in rows:
        print(f"  {str(r[0]).strip():10s} {str(r[1]).strip():10s} {str(r[2]).strip()[:40]:40s} {str(r[3]).strip():6s} {str(r[4]):8s} {str(r[5]):8s} {str(r[6]):8s}")
    print(f"  TOTAL: {len(rows)}")

    # 5. TSUGAMI DETAIL
    print("\n--- 5. TSUGAMI DETAIL: ALL rows (no state filter) ---")
    sql5 = f"""
    SELECT 
        T2.Formula AS Proyecto,
        T.Idorden,
        T.Descri,
        T.Idestado,
        T.Cantidad,
        T.Cantidadpp,
        (T.Cantidad - T.Cantidadpp) AS Pendientes
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE ({project_likes})
      AND MAC.MAQUINAD LIKE '%TSUGAMI%'
    ORDER BY T2.Formula, T.Idorden
    """
    cursor.execute(sql5)
    rows = cursor.fetchall()
    print(f"  {'Proyecto':10s} {'IdOrden':10s} {'Descri':40s} {'Estado':6s} {'Cant':8s} {'Prod':8s} {'Pend':8s}")
    print(f"  {'-'*100}")
    for r in rows:
        print(f"  {str(r[0]).strip():10s} {str(r[1]).strip():10s} {str(r[2]).strip()[:40]:40s} {str(r[3]).strip():6s} {str(r[4]):8s} {str(r[5]):8s} {str(r[6]):8s}")
    print(f"  TOTAL: {len(rows)}")

    # 6. TSUGAMI with loose T3 (to see if we get 22)
    print("\n--- 6. TSUGAMI with LOOSE T3 JOIN (old system reproduction?) ---")
    sql6 = f"""
    SELECT 
        T2.Formula AS Proyecto,
        T.Idorden,
        T.Descri,
        T3.Nivel_Planificacion,
        T3.ArticuloP,
        T.Cantidad,
        (T.Cantidad - T.Cantidadpp) AS Pendientes
    FROM Tman050 T
    INNER JOIN tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN TMAN002 T3 ON T.Articulo = T3.ArticuloH AND T.Formula = T3.Formula
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE ({project_likes})
      AND MAC.MAQUINAD LIKE '%TSUGAMI%'
    ORDER BY T2.Formula, T.Idorden, T3.Nivel_Planificacion desc
    """
    cursor.execute(sql6)
    rows = cursor.fetchall()
    print(f"  {'Proyecto':10s} {'IdOrden':10s} {'Descri':40s} {'NivPlan':7s} {'ArticuloP':25s} {'Pend':8s}")
    print(f"  {'-'*110}")
    for r in rows:
        print(f"  {str(r[0]).strip():10s} {str(r[1]).strip():10s} {str(r[2]).strip()[:40]:40s} {str(r[3] or ''):7s} {str(r[4] or '').strip():25s} {str(r[5]):8s}")
    print(f"  TOTAL with loose T3: {len(rows)}")

    # 7. TM1 with loose T3
    print("\n--- 7. TM1 with LOOSE T3 JOIN (old system reproduction?) ---")
    sql7 = f"""
    SELECT 
        T2.Formula AS Proyecto,
        T.Idorden,
        T.Descri,
        T3.Nivel_Planificacion,
        T3.ArticuloP,
        T.Cantidad,
        (T.Cantidad - T.Cantidadpp) AS Pendientes
    FROM Tman050 T
    INNER JOIN tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN TMAN002 T3 ON T.Articulo = T3.ArticuloH AND T.Formula = T3.Formula
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE ({project_likes})
      AND MAC.MAQUINAD LIKE '%TM1%'
    ORDER BY T2.Formula, T.Idorden, T3.Nivel_Planificacion desc
    """
    cursor.execute(sql7)
    rows = cursor.fetchall()
    print(f"  {'Proyecto':10s} {'IdOrden':10s} {'Descri':40s} {'NivPlan':7s} {'ArticuloP':25s} {'Pend':8s}")
    print(f"  {'-'*110}")
    for r in rows:
        print(f"  {str(r[0]).strip():10s} {str(r[1]).strip():10s} {str(r[2]).strip()[:40]:40s} {str(r[3] or ''):7s} {str(r[4] or '').strip():25s} {str(r[5]):8s}")
    print(f"  TOTAL with loose T3: {len(rows)}")

    cursor.close()

if __name__ == '__main__':
    run()
