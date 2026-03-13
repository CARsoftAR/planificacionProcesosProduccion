import os
import django
import sys
from django.db import connection

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def check_db():
    print("Checking Database State...")
    with connection.cursor() as cursor:
        # Check tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"Tables found: {tables}")
        
        if 'prioridad_manual' in tables:
            cursor.execute("PRAGMA table_info(prioridad_manual);")
            columns = [row[1] for row in cursor.fetchall()]
            print(f"Columns in prioridad_manual: {columns}")
            
        if 'scenario' in tables:
            print("Table 'scenario' exists.")
        else:
            print("Table 'scenario' DOES NOT exist.")

if __name__ == "__main__":
    check_db()
