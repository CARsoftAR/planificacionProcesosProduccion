from django.db import connections

def dictfetchall(cursor):
    """
    Return all rows from a cursor as a dict
    """
    columns = [col[0] for col in cursor.description]
    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]

EXCLUDED_MACHINES = [
    'BANCO MANTENIMIENTO', 'BANCO DE MANTENIMIENTO', 
    'BANCO SOLDADURA 2', 
    'CONTROL', 
    'HORNO',
    'ISAJE DE EMBALAJE', 
    'ISDG 1/2', 'ISDG 1/2"',
    'ISDG 5 1/2', 'ISDG 5 1/2"',
    'PC DISEÑO 1', 'PC DISEÑO 2', 'PC DISEÑO 3',
    'TURRI 190'
]

def get_all_machines():
    """
    Returns a list of all available machines from the database,
    excluding the defined exclusion list.
    """
    placeholders = ', '.join(['%s'] * len(EXCLUDED_MACHINES))
    sql = f"SELECT DISTINCT MAQUINAD FROM Tman010 WHERE MAQUINAD NOT IN ({placeholders}) ORDER BY MAQUINAD"
    
    with connections['production'].cursor() as cursor:
        cursor.execute(sql, EXCLUDED_MACHINES)
        # return list of strings
        return [row[0] for row in cursor.fetchall() if row[0]]

def get_planificacion_data(filtros=None, exclude_completed=True):
    """
    Ejecuta la consulta principal de planificación con filtros dinámicos.
    
    Args:
        filtros (dict, optional): Diccionario de condiciones. Ejemplo:
            {
                'fecha_desde': '2025-01-01',
                'id_sector': 'SEC01',
                'articulos_p': ['P...', 'P...']
            }
    """
    # Determine if we should limit results
    # If specific filters are applied (like project or ID), we want ALL matching records.
    # If no specific filters, we return TOP 5000 to avoid overloading but ensure all machines are seen.
    has_filters = any(v for k,v in filtros.items() if v)
    top_clause = "" if has_filters else "TOP 5000"

    # Base de la consulta proporcionada por el usuario
    base_sql = f"""
    SELECT DISTINCT {top_clause}
        T.Formula,
        T2.Formula AS ProyectoCode,
        T.Mstnmbr,
        T2.Descri AS Denominacion,
        T.Idorden,
        T.Articulo,
        T.Descri,
        T.Vto,
        T2.Vto AS Vto_Proyecto,
        T.Idprioridad,
        Oe.Descripcion AS Estadod,
        T.Lote,
        ISNULL((SELECT MAX(SUB.Nivel_Planificacion) FROM TMAN002 SUB WHERE LTRIM(RTRIM(SUB.ArticuloH)) = LTRIM(RTRIM(T.Articulo)) AND LTRIM(RTRIM(SUB.Formula)) = LTRIM(RTRIM(T.Formula))), 0) AS Nivel_Planificacion,
        T3.IDConcepto AS [SECTOR PERSONA],
        Isnull(T3.QConcepto, 1) AS [NIVEL PERSONA],
        Isnull(T.Idmaquina, '') AS Idmaquina,
        T3.IdMaquina AS IdmaquinaCompatible,
        0 AS NumeroOperacion,
        MAC.MAQUINAD,
        SEC.SECTORD,
        Isnull(T3.QMaquina, 1) AS [NIVEL MAQUINA],
        Cast(
            CASE WHEN T3.Cantidad <> 0 AND T.idorganismo NOT IN ( '1', '2', '3' ) THEN
                Isnull((
                    CASE WHEN T3.DENSIDAD <> 0 THEN
                        T3.TIEMPO / T3.cantidad 
                    ELSE 
                        T3.TIEMPO 
                    END
                ) , 0)
            ELSE
                0
            END 
        AS FLOAT) AS Tiempo,
        Cast(
            CASE WHEN T.Cantidadpp <> 0 THEN
                Isnull((
                    SELECT
                        Sum(T4.Tiempo_minutos) / 60 / T.Cantidadpp
                    FROM
                        v_tman T4
                    WHERE
                        T.Sucursal = T4.Sucursal AND
                        T.IdOrden = T4.IdOrden
                ) , 0)
            ELSE 
                0
            END 
        AS FLOAT) AS Tiempo_Logrado,
        Isnull((
            SELECT
                Sum(T4.Tiempo_minutos) / 60
            FROM
                v_tman T4
            WHERE
                T.Sucursal = T4.Sucursal AND
                T.IdOrden = T4.IdOrden
        ) , 0) AS Total_Horas_Fichadas,
        Isnull(Q.Cantidad_Final, 0) AS cantidad_final,
        (Isnull(Q.Cantidad_Final, 0) - Isnull(T.Cantidadpp, 0)) AS cantidad_pendiente,
        T.Lote,
        T3.Cantidad AS Cantidad_BOM,
        T2.Cantidad AS Cantidad_Proyecto,
        Isnull(T.Cantidadpp, 0) AS cantidad_producida,
        Cast(
            CASE WHEN (Isnull(Q.Cantidad_Final, 0) - Isnull(T.Cantidadpp, 0)) > 0 THEN
                (CASE WHEN T3.Cantidad <> 0 AND T.idorganismo NOT IN ( '1', '2', '3' ) THEN
                    Isnull((
                        CASE WHEN T3.DENSIDAD <> 0 THEN
                            T3.TIEMPO / T3.cantidad 
                        ELSE 
                            T3.TIEMPO 
                        END
                    ) , 0)
                ELSE
                    0
                END) * (Isnull(Q.Cantidad_Final, 0) - Isnull(T.Cantidadpp, 0))
            ELSE
                0
            END
        AS FLOAT) AS Tiempo_Proceso

    FROM Tman050 T
    INNER JOIN tman050 T2 ON 
        T.MSTNMBR = T2.IdOrden

    LEFT JOIN TMAN002 T3 ON 
        T.Articulo = T3.ArticuloH AND 
        T.Formula = T3.Formula AND 
        T2.Articulo = T3.ArticuloP

    CROSS APPLY (
        SELECT MAX(v) AS Cantidad_Final
        FROM (VALUES (Isnull(T.Cantidad, 0)), (Isnull(T3.Cantidad, 0)), (Isnull(T.Lote, 0))) AS Value(v)
    ) Q

    LEFT JOIN Tman006 SEC ON 
        T.Idsector = SEC.Idsector

    LEFT JOIN Tman007 Oe ON 
        T.Idestado = Oe.Idestado

    LEFT JOIN Tman010 MAC ON 
        T3.IdMaquina = MAC.Idmaquina

    WHERE 1=1
    """

    # --- NEW: Fetch Manual Priority Overrides from SQLite ---
    from .models import PrioridadManual, Scenario
    active_scenario = None
    if filtros and filtros.get('scenario_id'):
        try:
            active_scenario = Scenario.objects.using('default').get(id=filtros['scenario_id'])
        except Scenario.DoesNotExist:
            pass
    
    if not active_scenario:
        # Fallback to current official scenario
        active_scenario = Scenario.objects.using('default').filter(es_principal=True).first()

    # Construcción Dinámica del WHERE
    params = []
    where_clauses = []

    # Ejemplo    # Si 'id_orden' está en los filtros
    if 'id_orden' in filtros and filtros['id_orden']:
        where_clauses.append(" AND T.IdOrden = %s")
        params.append(filtros['id_orden'])
        
    # NEW: Support for list of IDs (Virtual Moves)
    if 'id_orden_in' in filtros and filtros['id_orden_in']:
        ids = filtros['id_orden_in']
        placeholders = ', '.join(['%s'] * len(ids))
        where_clauses.append(f" AND T.IdOrden IN ({placeholders})")
        params.extend(ids)
    
    # Filtro básico mencionado en el ejemplo original para filtrar 'P'
    # SUBSTRING(T.Articulo,1,1) = 'P' (Ya estaba en el where original, lo incluimos si es fijo o lo parametrizamos)
    # Lo dejaremos fijo o configurable. Asumamos que siempre va:
    # where_clauses.append(" AND SUBSTRING(T.Articulo,1,1) = 'P'") 

    # Si hay una lista de proyectos/ordenes especificas
    # Si hay una lista de proyectos/ordenes especificas
    if 'proyectos' in filtros and filtros['proyectos']:
        proyectos_input = filtros['proyectos']
        # Desempaquetar string o listas anidadas con comas
        proyectos_list = []
        if isinstance(proyectos_input, str):
            proyectos_list = [p.strip() for p in proyectos_input.split(',') if p.strip()]
        else:
            for p in proyectos_input:
                proyectos_list.extend([x.strip() for x in str(p).split(',') if x.strip()])

        if proyectos_list:
            vals_to_check = set()
            for val in proyectos_list:
                if val:
                    vals_to_check.add(val)
                    # User specifically requested searching by Formula for project codes like '25.006'
                    vals_to_check.add(val.replace('.', '-'))
                    vals_to_check.add(val.replace('-', '.'))
            
            if vals_to_check:
                # Use strict IN clause as requested by the user
                placeholders = ', '.join(['%s'] * len(vals_to_check))
                where_clauses.append(f" AND (LTRIM(RTRIM(T2.Formula)) IN ({placeholders}) OR LTRIM(RTRIM(T.Formula)) IN ({placeholders}))")
                # Add params twice (one for T2.Formula, one for T.Formula)
                params.extend(list(vals_to_check))
                params.extend(list(vals_to_check))

    if 'machine_ids' in filtros and filtros['machine_ids']:
        # machine_ids matches T3.IdMaquina (Engineering BOM assignment)
        m_ids = filtros['machine_ids']
        placeholders_m = ', '.join(['%s'] * len(m_ids))
        where_clauses.append(f" AND (T3.IdMaquina IN ({placeholders_m}) OR T3.IdMaquina IS NULL OR T3.IdMaquina = '')")
        params.extend(m_ids)
    else:
        # Filter out excluded machines
        placeholders = ', '.join(['%s'] * len(EXCLUDED_MACHINES))
        
        if EXCLUDED_MACHINES:
             where_clauses.append(f" AND MAC.MAQUINAD NOT IN ({placeholders})")
             params.extend(EXCLUDED_MACHINES)

    # Filtros de fecha, etc...
    if exclude_completed:
        # '3'=COMPLETA, '4'=ANULADO, '5'=CERRADA
        where_clauses.append(" AND T.Idestado NOT IN ('3', '4', '5')")
        where_clauses.append(" AND T2.Idestado NOT IN ('3', '4', '5')")
        # Ensure we only pull tasks that have pending pieces (avoid finished saldo)
        where_clauses.append(" AND (Isnull(Q.Cantidad_Final, 0) - Isnull(T.Cantidadpp, 0)) > 0")
    
    # Unir todo
    final_sql = base_sql + "".join(where_clauses)
    
    # Ordenamiento (Jerarquía solicitada: Maquina, Nivel Planificacion ASC)
    final_sql += " ORDER BY MAC.MAQUINAD, Nivel_Planificacion, T.Idorden desc"

    with connections['production'].cursor() as cursor:
        cursor.execute(final_sql, params)
        results = dictfetchall(cursor)
        
    # --- MERGE: Overlay Manual Levels and Auto-Sequence ---
    op_to_nivel = {}
    if results and active_scenario:
        op_ids = [r['Idorden'] for r in results]
        # Collect all Master OP IDs to ensure we query their priorities too
        mst_ids = []
        for r in results:
            mst = r.get('Mstnmbr')
            if mst:
                try:
                    mst_ids.append(int(float(mst)))
                except:
                    pass
        query_ids = list(set(op_ids + mst_ids))
        
        p_manual_db = PrioridadManual.objects.using('default').filter(
            scenario=active_scenario,
            id_orden__in=query_ids
        ).values('id_orden', 'nivel_manual')
        op_to_nivel = {p['id_orden']: p['nivel_manual'] for p in p_manual_db if p['nivel_manual'] is not None}

    # DEDUPLICAR / FILTRAR RESULTADOS (Asignación Única por Idorden)
    if results:
        from collections import defaultdict
        by_id = defaultdict(list)
        for r in results:
            by_id[r['Idorden']].append(r)
            
        pm_machines = {}
        if active_scenario:
            pm_list = PrioridadManual.objects.using('default').filter(
                scenario=active_scenario
            ).values('id_orden', 'maquina')
            for p in pm_list:
                if p['maquina']:
                    try:
                        oid_clean = int(float(p['id_orden']))
                    except:
                        oid_clean = p['id_orden']
                    pm_machines[oid_clean] = p['maquina'].strip().upper()

        deduped_results = []
        for oid, rows in by_id.items():
            try:
                oid_clean = int(float(oid))
            except:
                oid_clean = oid
                
            override_m = pm_machines.get(oid_clean)
            selected_row = None
            
            if override_m:
                # Buscar fila que coincida con la máquina del override manual
                for r in rows:
                    comp_m = str(r.get('IdmaquinaCompatible') or '').strip().upper()
                    if comp_m == override_m:
                        selected_row = r
                        break
                if not selected_row:
                    selected_row = rows[0].copy()
                    selected_row['IdmaquinaCompatible'] = override_m
            else:
                # Sin override: buscar la fila que coincida con la máquina asignada en el ERP
                erp_m = str(rows[0].get('Idmaquina') or '').strip().upper()
                if erp_m and erp_m not in ['', 'SIN ASIGNAR']:
                    for r in rows:
                        comp_m = str(r.get('IdmaquinaCompatible') or '').strip().upper()
                        if comp_m == erp_m:
                            selected_row = r
                            break
                
                if not selected_row:
                    selected_row = rows[0]
                    if not erp_m:
                        selected_row['Idmaquina'] = ''
                        selected_row['MAQUINAD'] = 'SIN ASIGNAR'
                        
            deduped_results.append(selected_row)
        results = deduped_results
        
    if results:
        # Agrupamos por código de proyecto y MSTNMBR (artículo/pieza madre) para secuenciar
        from collections import defaultdict
        groups = defaultdict(list)
        for r in results:
            proj = r.get('ProyectoCode', '')
            mst = r.get('Mstnmbr') or 0
            groups[(proj, mst)].append(r)
            
        for (proj, mst), group in groups.items():
            # Ordenamos las operaciones por Idorden (secuencia de hoja de ruta natural del ERP)
            group.sort(key=lambda x: int(x.get('Idorden') or 0))
            for i, r in enumerate(group):
                oid = r.get('Idorden')
                
                # 1. Secuencia correlativa de procesos
                r['secuencia_proceso'] = i + 1
                
                # 2. Prioridad de pieza (nivel_manual en SQLite)
                try:
                    clean_oid = int(float(oid))
                except:
                    clean_oid = oid
                
                prio = op_to_nivel.get(clean_oid)
                # Si no tiene prioridad manual a nivel de esta OP, buscamos si la tiene en la OP Master (mst)
                if prio is None and mst:
                    try:
                        clean_mst = int(float(mst))
                    except:
                        clean_mst = mst
                    prio = op_to_nivel.get(clean_mst)
                
                r['prioridad_pieza'] = int(prio) if prio is not None else None
                
                # Nivel_Planificacion: usar SIEMPRE el valor nativo del ERP (columna NIVEL de TMAN002).
                # NO sobreescribir con índices calculados (i+1) ni con valores inventados.
                # El valor ya viene correcto desde la subconsulta SQL (línea 71 de la query).
                # Solo lo normalizamos a int para garantizar tipos consistentes.
                erp_nivel = r.get('Nivel_Planificacion')
                r['Nivel_Planificacion'] = int(erp_nivel) if erp_nivel is not None else 0

    return results
