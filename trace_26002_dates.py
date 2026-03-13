import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

from django.db import connections
from collections import defaultdict

def inspect_26002():
    sql = """
    SELECT 
        T2.Formula as Proyecto,
        T.Idorden,
        T.Vto as VtoTarea,
        T2.Vto as VtoProj,
        T.Descri
    FROM Tman050 T
    INNER JOIN Tman050 T2 ON T.MSTNMBR = T2.IdOrden
    WHERE T2.Formula LIKE '%26%002%' OR T.Formula LIKE '%26%002%'
    """
    with connections['production'].cursor() as cursor:
        cursor.execute(sql)
        columns = [col[0] for col in cursor.description]
        rows = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        proj_data = defaultdict(lambda: {'vtos': set(), 'tasks': 0})
        
        for row in rows:
            p = row['Proyecto']
            proj_data[p]['vtos'].add(row['VtoProj'])
            proj_data[p]['tasks'] += 1
            
        print("Detailed breakdown by Formula string:")
        for p, data in proj_data.items():
            print(f"String: '{p}' | Tasks: {data['tasks']} | VtoProj values: {data['vtos']}")

if __name__ == "__main__":
    inspect_26002()
