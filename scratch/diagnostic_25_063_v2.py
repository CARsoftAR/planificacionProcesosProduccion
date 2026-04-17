import os
import django
import json
from django.db import connections

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def get_op_details(cursor, op_id):
    sql = """
    SELECT T.Articulo, T.Descri, T.Lote, T3.Tiempo, T3.Cantidad, T.Cantidad, T.Cantidadpp
    FROM Tman050 T
    LEFT JOIN TMAN002 T3 ON T.Articulo = T3.ArticuloH AND T.Formula = T3.Formula
    WHERE T.IdOrden = %s
    """
    cursor.execute(sql, [op_id])
    row = cursor.fetchone()
    if row:
        return {
            'Articulo': row[0],
            'Descri': row[1],
            'Lote': row[2],
            'TiempoUnitario': float(row[3] or 0),
            'BOM_Qty': float(row[4] or 0),
            'OP_Qty': float(row[5] or 0),
            'Produced_Qty': float(row[6] or 0)
        }
    return {}

def diagnostic():
    project_code = '25.063'
    results = {}
    
    with connections['production'].cursor() as cursor:
        # Find all OPs for project 25.063
        sql_ops = """
        SELECT T.IdOrden
        FROM Tman050 T
        INNER JOIN Tman050 T2 ON T.Mstnmbr = T2.IdOrden
        WHERE T2.Formula LIKE '%25.063%' OR T2.Formula LIKE '%25-063%'
        """
        cursor.execute(sql_ops)
        ops = [row[0] for row in cursor.fetchall()]
        
        if not ops:
            print("Project not found.")
            return

        # 1. Inspect OP 46025 specifically (the one with most hours)
        results['target_op'] = get_op_details(cursor, 46025)
        
        # 2. Check time logs for 46025
        sql_logs = """
        SELECT FECHA, HORA_D, HORA_H, Tiempo_minutos, CONCEPTO, IDREGISTRO
        FROM v_tman
        WHERE IdOrden = 46025
        ORDER BY Tiempo_minutos DESC
        """
        cursor.execute(sql_logs)
        logs = cursor.fetchall()
        
        results['anomalies_46025'] = []
        for row in logs[:10]:
            results['anomalies_46025'].append({
                'Fecha': str(row[0]),
                'Hora_D': str(row[1]),
                'Hora_H': str(row[2]),
                'Minutes': row[3],
                'Concepto': row[4],
                'IDRegistro': row[5]
            })

        # 3. Last 24h calculation
        sql_24h = """
        SELECT CONCEPTO, SUM(Tiempo_minutos)/60.0 as TotalH
        FROM v_tman
        WHERE (Formula LIKE '%25.063%' OR Formula LIKE '%25-063%')
        AND FECHA >= CAST(GETDATE() AS DATE)
        GROUP BY CONCEPTO
        """
        cursor.execute(sql_24h)
        results['density_24h'] = {row[0]: round(float(row[1]), 2) for row in cursor.fetchall()}

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    diagnostic()
