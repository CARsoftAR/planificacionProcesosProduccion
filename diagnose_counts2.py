"""
Verify: Does the old system show duplicates due to searching multiple projects
that match the same records multiple times?
"""
import os, sys, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.db import connections

def run():
    cursor = connections['production'].cursor()
    
    # Check: What projects do these tasks belong to?
    print("=" * 80)
    print("VERIFY: Do tasks 46798-46801, 47056-47064 belong to multiple projects?")
    print("=" * 80)
    
    # Check the parent record for these tasks
    print("\n--- 1. Parent records for TM1 tasks (46798, 46799) ---")
    sql1 = """
    SELECT T.IdOrden, T.MSTNMBR, T.Formula, T.Articulo, T.Descri, T.Idmaquina,
           T2.IdOrden AS ParentIdOrden, T2.Formula AS ParentFormula, T2.Articulo AS ParentArticulo
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    WHERE T.IdOrden IN ('46798', '46799')
    """
    cursor.execute(sql1)
    for r in cursor.fetchall():
        print(f"  IdOrden: {str(r[0]).strip():8s} MSTNMBR: {str(r[1]).strip():8s} Formula: {str(r[2]).strip():15s} Art: {str(r[3]).strip():20s}")
        print(f"    -> Parent IdOrden: {str(r[6]).strip():8s} ParentFormula: {str(r[7]).strip():15s} ParentArt: {str(r[8]).strip():20s}")
    
    # Check: Does the old system's search match each project separately?
    print("\n--- 2. How many times does each task appear with different project filters? ---")
    projects = ['26-002', '26-003', '26-004']
    for p in projects:
        sql2 = f"""
        SELECT COUNT(*) as Cnt
        FROM Tman050 T
        INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
        LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
        WHERE T2.Formula LIKE '%{p}%'
          AND MAC.MAQUINAD LIKE '%TSUGAMI%'
        """
        cursor.execute(sql2)
        cnt = cursor.fetchone()[0]
        print(f"  Project {p} -> TSUGAMI tasks: {cnt}")
    
    print("\n--- 3. Check: Does the old system have overlapping project formulas? ---")
    sql3 = """
    SELECT DISTINCT T2.Formula
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE (T2.Formula LIKE '%26-002%' OR T2.Formula LIKE '%26-003%' OR T2.Formula LIKE '%26-004%'
           OR T2.Formula LIKE '%26.002%' OR T2.Formula LIKE '%26.003%' OR T2.Formula LIKE '%26.004%')
      AND (MAC.MAQUINAD LIKE '%TSUGAMI%')
    """
    cursor.execute(sql3)
    rows = cursor.fetchall()
    print(f"  Distinct project codes matching these filters:")
    for r in rows:
        print(f"    -> '{str(r[0]).strip()}'")
    
    # The old system might include 26-013 too (contains '26-0')
    print("\n--- 4. CHECK: Broad match - what if old system uses LIKE '%26%' ? ---")
    sql4 = """
    SELECT ISNULL(MAC.MAQUINAD, T.Idmaquina) AS Maquina, T2.Formula, COUNT(*) as Cnt
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE T2.Formula LIKE '%26%'
      AND T.Idestado NOT IN ('3', '4', '5')
      AND T2.Idestado NOT IN ('3', '4', '5')
      AND (MAC.MAQUINAD LIKE '%TM1%' OR MAC.MAQUINAD LIKE '%TSUGAMI%')
    GROUP BY ISNULL(MAC.MAQUINAD, T.Idmaquina), T2.Formula
    ORDER BY Maquina, T2.Formula
    """
    cursor.execute(sql4)
    rows = cursor.fetchall()
    for r in rows:
        print(f"  Machine: {str(r[0]).strip():25s} | Project: {str(r[1]).strip():15s} | Count: {r[2]}")

    # 5. Check ALL projects that have tasks in TSUGAMI (broader view)
    print("\n--- 5. ALL projects with tasks in TSUGAMI (any Formula containing '26') ---")
    sql5 = """
    SELECT T2.Formula, T.IdOrden, T.Descri, T.Cantidad, T.Cantidadpp, (T.Cantidad - T.Cantidadpp) AS Pend
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE T2.Formula LIKE '%26%'
      AND MAC.MAQUINAD LIKE '%TSUGAMI%'
    ORDER BY T2.Formula, T.IdOrden
    """
    cursor.execute(sql5)
    rows = cursor.fetchall()
    print(f"  {'Proyecto':15s} {'IdOrden':10s} {'Descri':45s} {'Cant':8s} {'Prod':8s} {'Pend':8s}")
    print(f"  {'-'*100}")
    for r in rows:
        print(f"  {str(r[0]).strip():15s} {str(r[1]).strip():10s} {str(r[2]).strip()[:45]:45s} {str(r[3]):8s} {str(r[4]):8s} {str(r[5]):8s}")
    print(f"  TOTAL: {len(rows)}")

    # 6. Same for TM1
    print("\n--- 6. ALL projects with tasks in TM1 (any Formula containing '26') ---")
    sql6 = """
    SELECT T2.Formula, T.IdOrden, T.Descri, T.Cantidad, T.Cantidadpp, (T.Cantidad - T.Cantidadpp) AS Pend
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE T2.Formula LIKE '%26%'
      AND MAC.MAQUINAD LIKE '%TM1%'
    ORDER BY T2.Formula, T.IdOrden
    """
    cursor.execute(sql6)
    rows = cursor.fetchall()
    print(f"  {'Proyecto':15s} {'IdOrden':10s} {'Descri':45s} {'Cant':8s} {'Prod':8s} {'Pend':8s}")
    print(f"  {'-'*100}")
    for r in rows:
        print(f"  {str(r[0]).strip():15s} {str(r[1]).strip():10s} {str(r[2]).strip()[:45]:45s} {str(r[3]):8s} {str(r[4]):8s} {str(r[5]):8s}")
    print(f"  TOTAL: {len(rows)}")

    # 7. Check: Does 26-013 exist and also match?
    print("\n--- 7. Any project '26-013' in TSUGAMI? ---")
    sql7 = """
    SELECT T2.Formula, T.IdOrden, T.Descri
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    LEFT JOIN Tman010 MAC ON T.Idmaquina = MAC.Idmaquina
    WHERE (T2.Formula LIKE '%26-013%' OR T2.Formula LIKE '%26.013%')
      AND MAC.MAQUINAD LIKE '%TSUGAMI%'
    ORDER BY T.IdOrden
    """
    cursor.execute(sql7)
    rows = cursor.fetchall()
    if rows:
        for r in rows:
            print(f"  Project: {str(r[0]).strip():15s} IdOrden: {str(r[1]).strip():10s} Desc: {str(r[2]).strip()}")
    else:
        print("  No 26-013 tasks in TSUGAMI")
    
    print(f"\n  TOTAL 26-013 in TSUGAMI: {len(rows)}")

    cursor.close()

if __name__ == '__main__':
    run()
