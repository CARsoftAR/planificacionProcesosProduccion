import os
import django
import json
from django.db import connections

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def diagnostic():
    project_code = '25.063'
    results = {}
    
    with connections['production'].cursor() as cursor:
        sql = """
        SELECT T.IdOrden, T.Articulo, T.Descri, T.Cantidad, T.Cantidadpp, T3.Tiempo, T3.Cantidad as BOM_Qty
        FROM Tman050 T
        INNER JOIN Tman050 T2 ON T.Mstnmbr = T2.IdOrden
        LEFT JOIN TMAN002 T3 ON T.Articulo = T3.ArticuloH AND T.Formula = T3.Formula
        WHERE T2.Formula LIKE '%25.063%' OR T2.Formula LIKE '%25-063%'
        """
        cursor.execute(sql)
        rows = cursor.fetchall()
        
        results['op_counts'] = []
        for row in rows:
            qty_final = float(row[3] or row[6] or 0)
            qty_done = float(row[4] or 0)
            t_unitary = float(row[5] or 0)
            
            h_tot = t_unitary * qty_final
            h_done = t_unitary * qty_done
            
            results['op_counts'].append({
                'IdOrden': row[0],
                'Descri': row[2],
                'QtyFinal': qty_final,
                'QtyDone': qty_done,
                'EstTotalH': round(h_tot, 2),
                'EstDoneH': round(h_done, 2),
                'OverProduced': qty_done > qty_final
            })

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    diagnostic()
