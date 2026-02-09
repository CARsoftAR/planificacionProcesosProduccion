"""
Script para crear feriados de Argentina 2026 en el sistema.
Ejecutar con: python manage.py shell < create_holidays_2026.py
"""

from produccion.models import Feriado
from datetime import date

# Feriados de Argentina 2026
feriados_2026 = [
    # Enero
    {'fecha': date(2026, 1, 1), 'descripcion': 'Año Nuevo'},
    
    # Febrero - Carnaval
    {'fecha': date(2026, 2, 16), 'descripcion': 'Carnaval'},
    {'fecha': date(2026, 2, 17), 'descripcion': 'Carnaval'},
    
    # Marzo
    {'fecha': date(2026, 3, 24), 'descripcion': 'Día Nacional de la Memoria por la Verdad y la Justicia'},
    
    # Abril
    {'fecha': date(2026, 4, 2), 'descripcion': 'Día del Veterano y de los Caídos en la Guerra de Malvinas'},
    {'fecha': date(2026, 4, 3), 'descripcion': 'Viernes Santo'},
    
    # Mayo
    {'fecha': date(2026, 5, 1), 'descripcion': 'Día del Trabajador'},
    {'fecha': date(2026, 5, 25), 'descripcion': 'Día de la Revolución de Mayo'},
    
    # Junio
    {'fecha': date(2026, 6, 17), 'descripcion': 'Paso a la Inmortalidad del General Martín Miguel de Güemes'},
    {'fecha': date(2026, 6, 20), 'descripcion': 'Paso a la Inmortalidad del General Manuel Belgrano'},
    
    # Julio
    {'fecha': date(2026, 7, 9), 'descripcion': 'Día de la Independencia'},
    
    # Agosto
    {'fecha': date(2026, 8, 17), 'descripcion': 'Paso a la Inmortalidad del General José de San Martín'},
    
    # Octubre
    {'fecha': date(2026, 10, 12), 'descripcion': 'Día del Respeto a la Diversidad Cultural'},
    
    # Noviembre
    {'fecha': date(2026, 11, 20), 'descripcion': 'Día de la Soberanía Nacional'},
    
    # Diciembre
    {'fecha': date(2026, 12, 8), 'descripcion': 'Día de la Inmaculada Concepción de María'},
    {'fecha': date(2026, 12, 25), 'descripcion': 'Navidad'},
]

print("Creando feriados de Argentina 2026...")
print("=" * 60)

created_count = 0
updated_count = 0

# Crear feriados
for feriado_data in feriados_2026:
    feriado, created = Feriado.objects.using('default').get_or_create(
        fecha=feriado_data['fecha'],
        defaults={
            'descripcion': feriado_data['descripcion'],
            'tipo_jornada': 'NO',  # Por defecto no se trabaja
            'activo': True
        }
    )
    
    if created:
        created_count += 1
        print(f"✓ Creado: {feriado.fecha.strftime('%d/%m/%Y')} - {feriado.descripcion}")
    else:
        # Actualizar si ya existe
        feriado.descripcion = feriado_data['descripcion']
        feriado.tipo_jornada = 'NO'
        feriado.activo = True
        feriado.save(using='default')
        updated_count += 1
        print(f"↻ Actualizado: {feriado.fecha.strftime('%d/%m/%Y')} - {feriado.descripcion}")

print("=" * 60)
print(f"\nResumen:")
print(f"  - Feriados creados: {created_count}")
print(f"  - Feriados actualizados: {updated_count}")
print(f"  - Total feriados 2026: {Feriado.objects.using('default').filter(fecha__year=2026).count()}")
print(f"  - Total en base de datos: {Feriado.objects.using('default').count()}")
print("=" * 60)

print("\n¡Feriados de Argentina 2026 cargados exitosamente!")
