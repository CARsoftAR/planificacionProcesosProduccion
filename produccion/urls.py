from django.urls import path
from . import views

urlpatterns = [
    path('api/planificacion/', views.planificacion_list, name='planificacion_list'),
    path('api/move_priority/<int:id_orden>/<str:direction>/', views.move_priority, name='move_priority'),
    path('api/set_priority/<int:id_orden>/', views.set_priority, name='set_priority'),
    
    # Machine Configuration
    path('config/maquinas/', views.maquina_config_list, name='maquina_config_list'),
    path('config/maquinas/crear/', views.maquina_config_create_update, name='maquina_config_create'),
    path('config/maquinas/<pk>/editar/', views.maquina_config_create_update, name='maquina_config_update'),
    path('config/maquinas/<pk>/borrar/', views.maquina_config_delete, name='maquina_config_delete'),
    path('config/maquinas/<maquina_id>/horario/crear/', views.horario_maquina_create, name='horario_maquina_create'),
    path('config/horario/<pk>/borrar/', views.horario_maquina_delete, name='horario_maquina_delete'),

    # Feriados
    path('feriados/', views.feriado_list, name='feriado_list'),
    path('feriados/crear/', views.feriado_create, name='feriado_create'),
    path('feriados/<int:pk>/editar/', views.feriado_update, name='feriado_update'),
    path('feriados/<int:pk>/eliminar/', views.feriado_delete, name='feriado_delete'),
    path('api/feriados/<int:pk>/toggle-planifica/', views.feriado_toggle_planifica, name='feriado_toggle_planifica'),
    path('api/feriados/<int:pk>/toggle-activo/', views.feriado_toggle_activo, name='feriado_toggle_activo'),
    path('api/feriados/<int:pk>/update-jornada/', views.feriado_update_jornada, name='feriado_update_jornada'),

    # Navigation
    path('planificacion/', views.planificacion_list, name='planificacion_view'),
    path('planificacion/visual/', views.planificacion_visual, name='planificacion_visual'),
    path('proyectos/prioridades/', views.proyectos_prioridades, name='proyectos_prioridades'),
    path('planillas_diarias/', views.planillas_diarias, name='planillas_diarias'),
    path('api/proyectos/update_prioridad/', views.update_proyecto_prioridad, name='update_proyecto_prioridad'),
    path('api/move_task/', views.move_task, name='move_task'),
    path('api/update_manual_time/', views.update_manual_time, name='update_manual_time'),
    path('api/update_manual_nivel/', views.update_manual_nivel, name='update_manual_nivel'),
    path('api/update_overlap_percentage/', views.update_overlap_percentage, name='update_overlap_percentage'),
    path('api/link_tasks/', views.link_tasks, name='link_tasks'),
    path('api/unlink_tasks/', views.unlink_tasks, name='unlink_tasks'),
    path('api/export_excel/', views.export_planificacion_excel, name='export_planificacion_excel'),
    path('api/hide_task/', views.hide_task, name='hide_task'),
    path('api/reset_planning/', views.reset_planning, name='reset_planning'),
    
    # Scenario Management
    path('api/scenarios/create/', views.create_scenario, name='create_scenario'),
    path('api/scenarios/<int:scenario_id>/delete/', views.delete_scenario, name='delete_scenario'),
    path('api/scenarios/<int:scenario_id>/publish/', views.publish_scenario, name='publish_scenario'),
    
    # Statistics
    path('estadisticas/', views.estadisticas_produccion, name='estadisticas_produccion'),

    path('', views.main_menu, name='home'),
]
