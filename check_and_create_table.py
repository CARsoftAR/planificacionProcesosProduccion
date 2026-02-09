from django.core.management import call_command
from django.db import connection

# Verificar si la tabla existe
with connection.cursor() as cursor:
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='feriado'
    """)
    result = cursor.fetchone()
    
    if result:
        print("✓ La tabla 'feriado' YA existe")
    else:
        print("✗ La tabla 'feriado' NO existe")
        print("\nCreando tabla manualmente...")
        
        # Crear la tabla manualmente
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS feriado (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha DATE NOT NULL UNIQUE,
                descripcion VARCHAR(200) NOT NULL,
                se_planifica BOOLEAN NOT NULL DEFAULT 0,
                activo BOOLEAN NOT NULL DEFAULT 1,
                fecha_creacion DATETIME NOT NULL,
                fecha_modificacion DATETIME NOT NULL
            )
        """)
        print("✓ Tabla 'feriado' creada exitosamente")

# Verificar nuevamente
with connection.cursor() as cursor:
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='feriado'")
    result = cursor.fetchone()
    
    if result:
        print("\n✓ Verificación: La tabla 'feriado' existe correctamente")
        
        # Mostrar estructura
        cursor.execute("PRAGMA table_info(feriado)")
        columns = cursor.fetchall()
        print("\nEstructura de la tabla:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
    else:
        print("\n✗ Error: La tabla aún no existe")
