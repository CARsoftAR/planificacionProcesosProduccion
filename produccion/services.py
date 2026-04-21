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
        T3.Nivel,
        T3.Nivel_Planificacion,
        T3.IDConcepto AS [SECTOR PERSONA],
        Isnull(T3.QConcepto, 1) AS [NIVEL PERSONA],
        Isnull(T.Idmaquina, '') AS Idmaquina,
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
        if isinstance(proyectos_input, str):
            proyectos_list = [p.strip() for p in proyectos_input.split(',') if p.strip()]
        else:
            proyectos_list = proyectos_input

        clauses = []
        for val in proyectos_list:
            val = val.strip()
            
            # User specifically requested searching by Formula for project codes like '25.006'
            # We generate variations to handle '25-006' vs '25.006' mismatch
            vals_to_check = {val}
            vals_to_check.add(val.replace('.', '-'))
            vals_to_check.add(val.replace('-', '.'))

            for v in vals_to_check:
                 clauses.append("T2.Formula LIKE %s")
                 params.append(f"%{v}%")
                 
                 clauses.append("T.Formula LIKE %s")
                 params.append(f"%{v}%")
        
        if clauses:
            where_clauses.append(" AND (" + " OR ".join(clauses) + ")")

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
    final_sql += " ORDER BY MAC.MAQUINAD, T3.Nivel_Planificacion, T3.Nivel, T.IdOrden desc"

    with connections['production'].cursor() as cursor:
        cursor.execute(final_sql, params)
        return dictfetchall(cursor)
