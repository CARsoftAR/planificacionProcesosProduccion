import os
import django
import json
from django.db import connections

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def diagnostic():
    project_code = '25-063'
    results = {}
    
    with connections['production'].cursor() as cursor:
        # 1. Top 5 tasks with most hours
        project_variations = [project_code, project_code.replace('-', '.'), project_code.replace('.', '-')]
        placeholders_proj = ', '.join(['%s'] * len(project_variations))
        
        sql_ops = f"""
        SELECT T.IdOrden, T.Articulo, T.Descri, T2.Formula as Proyecto
        FROM Tman050 T
        INNER JOIN Tman050 T2 ON T.Mstnmbr = T2.IdOrden
        WHERE T2.Formula IN ({placeholders_proj})
        OR T2.Formula LIKE %s
        """
        cursor.execute(sql_ops, project_variations + [f'%{project_code}%'])
        ops = [row[0] for row in cursor.fetchall()]
        
        if not ops:
            print(f"No OPs found for project {project_code}")
            return

        placeholders = ', '.join(['%s'] * len(ops))
        
        # Query total hours per OP from v_tman
        sql_hours = f"""
        SELECT T4.IdOrden, SUM(T4.Tiempo_minutos)/60.0 as TotalHours, COUNT(DISTINCT T4.IDCONCEPTO) as Personnel
        FROM v_tman T4
        WHERE T4.IdOrden IN ({placeholders})
        GROUP BY T4.IdOrden
        ORDER BY TotalHours DESC
        """
        cursor.execute(sql_hours, ops)
        results['top_tasks'] = []
        for row in cursor.fetchall()[:5]:
             # Get OP details
             cursor.execute("SELECT Articulo, Descri FROM Tman050 WHERE IdOrden = %s", [row[0]])
             details = cursor.fetchone()
             results['top_tasks'].append({
                 'IdOrden': row[0],
                 'Articulo': details[0] if details else '?',
                 'Descri': details[1] if details else '?',
                 'Hours': round(float(row[1]), 2),
                 'Personnel': row[2]
             })

        # 2. Detect open clock-ins or anomalies (> 12h)
        sql_anomalies = f"""
        SELECT T4.IdOrden, T4.CONCEPTO, T4.Tiempo_minutos, T4.FECHA, T4.HORA_D, T4.HORA_H
        FROM v_tman T4
        WHERE T4.IdOrden IN ({placeholders})
        AND T4.Tiempo_minutos > 720
        ORDER BY T4.Tiempo_minutos DESC
        """
        cursor.execute(sql_anomalies, ops)
        results['anomalies'] = [{
            'IdOrden': row[0],
            'Personnel': row[1],
            'Minutes': row[2],
            'Date': str(row[3]),
            'Start': str(row[4]),
            'End': str(row[5])
        } for row in cursor.fetchall()]

        # 3. Density calculation (last 24h)
        # Using FECHA for today comparison
        sql_density = f"""
        SELECT COUNT(DISTINCT T4.IDCONCEPTO) as Personnel, SUM(T4.Tiempo_minutos)/60.0 as HoursToday
        FROM v_tman T4
        WHERE T4.IdOrden IN ({placeholders})
        AND T4.FECHA >= CAST(GETDATE() AS DATE)
        """
        cursor.execute(sql_density, ops)
        row = cursor.fetchone()
        results['density'] = {
            'Personnel': row[0],
            'HoursToday': round(float(row[1] or 0), 2)
        }
        
        # 4. Global project stats
        sql_global = f"""
        SELECT SUM(T4.Tiempo_minutos)/60.0
        FROM v_tman T4
        WHERE T4.IdOrden IN ({placeholders})
        """
        cursor.execute(sql_global, ops)
        results['global_actual_hours'] = round(float(cursor.fetchone()[0] or 0), 2)

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    diagnostic()
