from django.db import models

class Scenario(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Escenario")
    descripcion = models.TextField(blank=True, null=True, verbose_name="Descripción")
    es_principal = models.BooleanField(default=False, verbose_name="Es Plan Oficial")
    proyectos = models.TextField(blank=True, null=True, verbose_name="Proyectos (Comas)")
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        managed = True
        db_table = 'scenario'
        verbose_name = 'Escenario de Planificación'
        verbose_name_plural = 'Escenarios de Planificación'

    def __str__(self):
        return f"{self.nombre} ({'OFICIAL' if self.es_principal else 'BORRADOR'})"
