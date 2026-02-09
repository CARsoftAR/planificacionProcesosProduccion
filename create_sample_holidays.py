"""
Script para crear feriados de ejemplo en el sistema.
Ejecutar con: python manage.py shell < create_sample_holidays.py
"""

from produccion.models import Feriado
from datetime import date

# Feriados de Argentina 2025
feriados_2025 = [
    # Enero
    {'fecha': date(2025, 1, 1), 'descripcion': 'Año Nuevo', 'se_planifica': False},
    
    # Febrero
    {'fecha': date(2025, 2, 24), 'descripcion': 'Carnaval', 'se_planifica': False},
    {'fecha': date(2025, 2, 25), 'descripcion': 'Carnaval', 'se_planifica': False},
    
    # Marzo
    {'fecha': date(2025, 3, 24), 'descripcion': 'Día Nacional de la Memoria por la Verdad y la Justicia', 'se_planifica': False},
    
    # Abril
    {'fecha': date(2025, 4, 2), 'descripcion': 'Día del Veterano y de los Caídos en la Guerra de Malvinas', 'se_planifica': False},
    {'fecha': date(2025, 4, 18), 'descripcion': 'Viernes Santo', 'se_planifica': False},
    
    # Mayo
    {'fecha': date(2025, 5, 1), 'descripcion': 'Día del Trabajador', 'se_planifica': False},
    {'fecha': date(2025, 5, 25), 'descripcion': 'Día de la Revolución de Mayo', 'se_planifica': False},
    
    # Junio
    {'fecha': date(2025, 6, 16), 'descripcion': 'Paso a la Inmortalidad del General Martín Miguel de Güemes', 'se_planifica': False},
    {'fecha': date(2025, 6, 20), 'descripcion': 'Paso a la Inmortalidad del General Manuel Belgrano', 'se_planifica': False},
    
    # Julio
    {'fecha': date(2025, 7, 9), 'descripcion': 'Día de la Independencia', 'se_planifica': False},
    
    # Agosto
    {'fecha': date(2025, 8, 17), 'descripcion': 'Paso a la Inmortalidad del General José de San Martín', 'se_planifica': False},
    
    # Octubre
    {'fecha': date(2025, 10, 12), 'descripcion': 'Día del Respeto a la Diversidad Cultural', 'se_planifica': False},
    
    # Noviembre
    {'fecha': date(2025, 11, 24), 'descripcion': 'Día de la Soberanía Nacional', 'se_planifica': False},
    
    # Diciembre
    {'fecha': date(2025, 12, 8), 'descripcion': 'Día de la Inmaculada Concepción de María', 'se_planifica': False},
    {'fecha': date(2025, 12, 25), 'descripcion': 'Navidad', 'se_planifica': False},
]

# Ejemplo de feriados que SÍ se trabajan (días especiales de producción)
feriados_laborables = [
    {'fecha': date(2025, 12, 24), 'descripcion': 'Nochebuena (Medio día)', 'se_planifica': True},
    {'fecha': date(2025, 12, 31), 'descripcion': 'Fin de Año (Medio día)', 'se_planifica': True},
]

print("Creando feriados de ejemplo...")

created_count = 0
updated_count = 0
skipped_count = 0

# Crear feriados no laborables
for feriado_data in feriados_2025:
    feriado, created = Feriado.objects.using('default').get_or_create(
        fecha=feriado_data['fecha'],
        defaults={
            'descripcion': feriado_data['descripcion'],
            'se_planifica': feriado_data['se_planifica'],
            'activo': True
        }
    )
    
    if created:
        created_count += 1
        print(f"✓ Creado: {feriado}")
    else:
        # Actualizar si ya existe
        feriado.descripcion = feriado_data['descripcion']
        feriado.se_planifica = feriado_data['se_planifica']
        feriado.activo = True
        feriado.save(using='default')
        updated_count += 1
        print(f"↻ Actualizado: {feriado}")

# Crear feriados laborables
for feriado_data in feriados_laborables:
    feriado, created = Feriado.objects.using('default').get_or_create(
        fecha=feriado_data['fecha'],
        defaults={
            'descripcion': feriado_data['descripcion'],
            'se_planifica': feriado_data['se_planifica'],
            'activo': True
        }
    )
    
    if created:
        created_count += 1
        print(f"✓ Creado (laborable): {feriado}")
    else:
        feriado.descripcion = feriado_data['descripcion']
        feriado.se_planifica = feriado_data['se_planifica']
        feriado.activo = True
        feriado.save(using='default')
        updated_count += 1
        print(f"↻ Actualizado (laborable): {feriado}")

print(f"\n{'='*60}")
print(f"Resumen:")
print(f"  - Feriados creados: {created_count}")
print(f"  - Feriados actualizados: {updated_count}")
print(f"  - Total en base de datos: {Feriado.objects.using('default').count()}")
print(f"  - Feriados que NO se trabajan: {Feriado.objects.using('default').filter(se_planifica=False).count()}")
print(f"  - Feriados que SÍ se trabajan: {Feriado.objects.using('default').filter(se_planifica=True).count()}")
print(f"{'='*60}\n")

print("¡Feriados de ejemplo creados exitosamente!")
