from django.db import models
from datetime import date, datetime

class VTman(models.Model):
    idorden = models.BigIntegerField(db_column='IDORDEN', primary_key=True)
    idop = models.CharField(db_column='IDOP', max_length=10)
    op_idcliente = models.CharField(db_column='Op_idcliente', max_length=6, blank=True, null=True)
    macropk = models.CharField(db_column='MacroPK', max_length=50, blank=True, null=True)
    ismacro = models.BooleanField(db_column='IsMacro', blank=True, null=True)
    idconcepto = models.CharField(db_column='IDCONCEPTO', max_length=10)
    concepto = models.CharField(db_column='CONCEPTO', max_length=100)
    concepto_vhd = models.DecimalField(db_column='Concepto_vhd', max_digits=19, decimal_places=4, blank=True, null=True)
    concepto_vhi = models.DecimalField(db_column='Concepto_vhi', max_digits=19, decimal_places=4, blank=True, null=True)
    concepto_unidad = models.CharField(db_column='Concepto_unidad', max_length=10, blank=True, null=True)
    hora_d = models.DateTimeField(db_column='HORA_D')
    hora_h = models.DateTimeField(db_column='HORA_H')
    tiempo_cotizado = models.FloatField(db_column='Tiempo_cotizado')
    tiempo_cotizado_individual = models.FloatField(db_column='Tiempo_cotizado_individual')
    tiempo_minutos = models.FloatField(db_column='Tiempo_minutos', blank=True, null=True)
    tiempo_minutos_individual = models.FloatField(db_column='Tiempo_minutos_individual', blank=True, null=True)
    cantidad_producida = models.FloatField(db_column='Cantidad_producida', blank=True, null=True)
    idmaquina = models.CharField(db_column='IDMAQUINA', max_length=10)
    maquinad = models.CharField(db_column='MaquinaD', max_length=200, blank=True, null=True)
    maquina_vhd = models.DecimalField(db_column='Maquina_vhd', max_digits=19, decimal_places=4, blank=True, null=True)
    maquina_vhi = models.DecimalField(db_column='Maquina_vhi', max_digits=19, decimal_places=4, blank=True, null=True)
    maquina_sector = models.CharField(db_column='Maquina_sector', max_length=10, blank=True, null=True)
    maquina_lote = models.CharField(db_column='Maquina_lote', max_length=50, blank=True, null=True)
    maquina_tiempo = models.FloatField(db_column='Maquina_tiempo', blank=True, null=True)
    idoperacion = models.CharField(db_column='IDOPERACION', max_length=10, blank=True, null=True)
    operacion = models.CharField(db_column='OPERACION', max_length=50)
    es_proceso = models.BooleanField(db_column='Es_proceso')
    es_programado = models.BooleanField(db_column='Es_programado')
    es_no_programado = models.BooleanField(db_column='Es_no_programado')
    es_interrupcion = models.BooleanField(db_column='Es_interrupcion')
    hap_row_id = models.BigIntegerField(db_column='HAP_ROW_ID')
    idregistro = models.BigIntegerField(db_column='IDREGISTRO')
    obs = models.CharField(db_column='OBS', max_length=100, blank=True, null=True)
    idorganismo = models.CharField(db_column='IDORGANISMO', max_length=20, blank=True, null=True)
    organismod = models.CharField(db_column='ORGANISMOD', max_length=80, blank=True, null=True)
    valor = models.IntegerField(db_column='Valor')
    articulomop = models.CharField(db_column='Articulomop', max_length=20, blank=True, null=True)
    articulomopd = models.CharField(db_column='Articulomopd', max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'v_tman'


class Tart001(models.Model):
    class Meta:
        managed = False
        db_table = 'Tart001'

class Tcli001(models.Model):
    class Meta:
        managed = False
        db_table = 'Tcli001'

class Tpar021(models.Model):
    class Meta:
        managed = False
        db_table = 'Tpar021'

class Tpar035(models.Model):
    class Meta:
        managed = False
        db_table = 'Tpar035'


class Scenario(models.Model):
    nombre = models.CharField(max_length=100, verbose_name="Nombre del Escenario", default="Plan Oficial")
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


class PrioridadManual(models.Model):
    id_orden = models.BigIntegerField(db_column='IdOrden')
    maquina = models.CharField(max_length=50, blank=True, null=True)
    prioridad = models.FloatField(default=0.0)
    tiempo_manual = models.FloatField(blank=True, null=True, verbose_name='Tiempo Manual')
    nivel_manual = models.IntegerField(blank=True, null=True, verbose_name='Nivel Planificacion Manual')
    porcentaje_solapamiento = models.FloatField(
        blank=True, 
        null=True, 
        default=0.0,
        verbose_name='% Solapamiento',
        help_text='Porcentaje del lote que debe estar completo antes de iniciar siguiente proceso (0-100)'
    )
    fecha_inicio_manual = models.DateTimeField(
        blank=True, 
        null=True, 
        verbose_name='Inicio Manual (Pin)',
        help_text='Fecha forzada manualmente por el usuario (Drag & Drop)'
    )
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='overrides',
        verbose_name='Escenario'
    )

    class Meta:
        managed = True
        db_table = 'prioridad_manual'
        unique_together = ('id_orden', 'maquina', 'scenario') # Unique per task+machine IN A SCENARIO

class MaquinaConfig(models.Model):
    id_maquina = models.CharField(max_length=20, primary_key=True, verbose_name='ID de Maquina')
    nombre = models.CharField(max_length=100, verbose_name='Nombre de Maquina')

    class Meta:
        managed = True
        db_table = 'maquina_config'
        verbose_name = 'Configuracion de Maquina'
        verbose_name_plural = 'Configuraciones de Maquinas'

    def __str__(self):
        return f"{self.nombre} ({self.id_maquina})"

    @property
    def has_lv(self):
        return self.horarios.filter(dia='LV').exists()

    @property
    def has_sa(self):
        return self.horarios.filter(dia='SA').exists()

class HorarioMaquina(models.Model):
    DIA_CHOICES = [
        ('LV', 'Lunes a Viernes'),
        ('SA', 'Sabado'),
        ('DO', 'Domingo'),
    ]
    
    maquina = models.ForeignKey(MaquinaConfig, related_name='horarios', on_delete=models.CASCADE)
    dia = models.CharField(max_length=2, choices=DIA_CHOICES, verbose_name='Dia')
    hora_inicio = models.TimeField(verbose_name='Hora Inicio')
    hora_fin = models.TimeField(verbose_name='Hora Fin')

    class Meta:
        managed = True
        db_table = 'horario_maquina'
        unique_together = ('maquina', 'dia')
        verbose_name = 'Horario de Maquina'
        verbose_name_plural = 'Horarios de Maquinas'


class MantenimientoMaquina(models.Model):
    maquina = models.ForeignKey(MaquinaConfig, related_name='mantenimientos', on_delete=models.CASCADE, verbose_name='Máquina')
    motivo = models.CharField(max_length=200, verbose_name='Motivo (Ej: Reparación, Preventivo)')
    fecha_inicio = models.DateTimeField(verbose_name='Fecha y Hora de Inicio')
    fecha_fin = models.DateTimeField(verbose_name='Fecha y Hora de Fin Estimada')
    estado = models.CharField(
        max_length=20,
        choices=[('PROGRAMADO', 'Programado'), ('EN_CURSO', 'En Curso'), ('FINALIZADO', 'Finalizado')],
        default='PROGRAMADO',
        verbose_name='Estado'
    )
    notas = models.TextField(blank=True, null=True, verbose_name='Notas de Mantenimiento')
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'mantenimiento_maquina'
        ordering = ['-fecha_inicio']
        verbose_name = 'Mantenimiento de Máquina'
        verbose_name_plural = 'Mantenimientos de Máquinas'

    def __str__(self):
        return f"{self.maquina.nombre} - {self.motivo} ({self.estado})"

    @property
    def is_active(self):
        now = datetime.now()
        # Si tiene timezone, deberíamos usar timezone.now(), pero para consistencia usamos lo actual
        # Asumiendo fechas naive local
        return self.fecha_inicio <= now <= self.fecha_fin and self.estado != 'FINALIZADO'


class Feriado(models.Model):
    TIPO_JORNADA_CHOICES = [
        ('NO', 'No se trabaja'),
        ('MEDIO', 'Medio dia'),
        ('SI', 'Se trabaja'),
    ]
    
    fecha = models.DateField(verbose_name='Fecha', unique=True)
    descripcion = models.CharField(max_length=200, verbose_name='Descripcion')
    tipo_jornada = models.CharField(
        max_length=5,
        choices=TIPO_JORNADA_CHOICES,
        default='NO',
        verbose_name='Tipo de Jornada',
        help_text='Indica si se trabaja, medio dia o no se trabaja'
    )
    activo = models.BooleanField(
        default=True,
        verbose_name='Activo',
        help_text='Feriados inactivos no se consideran en la planificacion'
    )
    fecha_creacion = models.DateTimeField(auto_now_add=True, verbose_name='Fecha de Creacion')
    fecha_modificacion = models.DateTimeField(auto_now=True, verbose_name='Ultima Modificacion')

    class Meta:
        managed = True
        db_table = 'feriado'
        ordering = ['fecha']
        verbose_name = 'Feriado'
        verbose_name_plural = 'Feriados'

    def __str__(self):
        tipo_display = self.get_tipo_jornada_display()
        return f"{self.fecha.strftime('%d/%m/%Y')} - {self.descripcion} ({tipo_display})"

    @property
    def es_pasado(self):
        return self.fecha < date.today()

    @property
    def es_futuro(self):
        return self.fecha > date.today()
    
    @property
    def se_planifica(self):
        return self.tipo_jornada in ['SI', 'MEDIO']

class TaskDependency(models.Model):
    predecessor_id = models.BigIntegerField(db_column='PredecessorId', verbose_name='Tarea Predecesora')
    successor_id = models.BigIntegerField(db_column='SuccessorId', verbose_name='Tarea Sucesora')
    
    class Meta:
        managed = True
        db_table = 'task_dependency'
        unique_together = ('predecessor_id', 'successor_id')
        verbose_name = 'Dependencia de Tarea'
        verbose_name_plural = 'Dependencias de Tareas'

class HiddenTask(models.Model):
    id_orden = models.BigIntegerField(db_column='IdOrden', primary_key=True, verbose_name='ID de Orden')
    fecha_oculto = models.DateTimeField(auto_now_add=True)

    class Meta:
        managed = True
        db_table = 'hidden_task'
        verbose_name = 'Tarea Oculta'
        verbose_name_plural = 'Tareas Ocultas'

class ProyectoPrioridad(models.Model):
    proyecto = models.CharField(max_length=50, verbose_name="Proyecto (Formula)")
    prioridad = models.IntegerField(default=999, verbose_name="Prioridad")
    scenario = models.ForeignKey(
        Scenario,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='proyecto_prioridades',
        verbose_name='Escenario'
    )

    class Meta:
        managed = True
        db_table = 'proyecto_prioridad'
        unique_together = ('proyecto', 'scenario')
        verbose_name = 'Prioridad de Proyecto'
        verbose_name_plural = 'Prioridades de Proyectos'

    def __str__(self):
        return f"{self.proyecto} (Prioridad {self.prioridad})"

