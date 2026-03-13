
import os
import django
import sys
from django.db import connection

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'planificacion.settings')
django.setup()

def fix_db():
    print("Fixing Database State...")
    with connection.cursor() as cursor:
        # 1. Create Scenario Table
        print("Creating 'scenario' table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "scenario" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
                "nombre" varchar(100) NOT NULL, 
                "descripcion" text NULL, 
                "es_principal" bool NOT NULL, 
                "fecha_creacion" datetime NOT NULL
            );
        ''')
        print("Table created.")

        print("Creating 'proyecto_prioridad' table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS "proyecto_prioridad" (
                "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT, 
                "proyecto" varchar(50) NOT NULL, 
                "prioridad" integer NOT NULL, 
                "scenario_id" integer NULL REFERENCES "scenario" ("id") DEFERRABLE INITIALLY DEFERRED,
                UNIQUE ("proyecto", "scenario_id")
            );
        ''')
        print("Table proyecto_prioridad created.")

if __name__ == "__main__":
    fix_db()
