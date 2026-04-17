import os
import django
import sys

# Add project root to sys.path
sys.path.append(os.getcwd())

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections

def test_query():
    proyecto = "26-028"
    sql = """
    SELECT 
        T.Articulo,
        T.Descri as Denominacion,
        SUM(T.Cantidad) as Solicitado,
        SUM(T.Cantidadpp) as Finalizado,
        MAX(T.Idorden) as IdOrdenMaster
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.Mstnmbr = T2.IdOrden
    WHERE (T2.Formula LIKE %s OR T2.Formula LIKE %s)
    AND T.Descri NOT LIKE %s
    AND T.Descri NOT LIKE %s
    AND T.Descri NOT LIKE %s
    AND T.Descri NOT LIKE %s
    AND T.Descri NOT LIKE %s
    AND T.Descri NOT LIKE %s
    GROUP BY T.Articulo, T.Descri
    ORDER BY T.Descri
    """
    
    try:
        with connections['production'].cursor() as cursor:
            search_val = f"%{proyecto}%"
            params = [
                search_val, search_val,
                'REBABADO%', 'FRESADO%', '%TORNO%', 'PULIDO%', 'CONTROL%', 'ARMADO%'
            ]
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            print(f"Success! Found {len(rows)} rows.")
            for r in rows[:5]:
                print(r)
    except Exception as e:
        print(f"Error executing query: {e}")

if __name__ == "__main__":
    test_query()
