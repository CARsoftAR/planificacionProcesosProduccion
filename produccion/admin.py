from django.contrib import admin
from .models import MaquinaConfig, MantenimientoMaquina, Feriado

@admin.register(MaquinaConfig)
class MaquinaConfigAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'id_maquina')

@admin.register(MantenimientoMaquina)
class MantenimientoMaquinaAdmin(admin.ModelAdmin):
    list_display = ('maquina', 'motivo', 'fecha_inicio', 'fecha_fin', 'estado')
    list_filter = ('estado', 'maquina')
    
@admin.register(Feriado)
class FeriadoAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'descripcion', 'tipo_jornada', 'activo')

