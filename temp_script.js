
        function openGantt(btn) {
            // UI Feedback
            btn.innerHTML = '<i class="fas fa-spinner fa-spin me-1"></i> Procesando...';
            btn.style.pointerEvents = 'none';

            // Get current Input Value
            const inputProyectos = document.getElementById('proyectos');
            const val = inputProyectos ? inputProyectos.value : '';

            // Construct URL
            const params = new URLSearchParams(window.location.search);
            if (val.trim()) {
                params.set('proyectos', val.trim());
            } else {
                params.delete('proyectos');
            }

            // Evaluar condición de persistencia en memoria del frontend
            try {
                if (sessionStorage.getItem('ganttYaGraficado') === 'true') {
                    params.set('graficar', '1');
                }
            } catch(e) {}

            // Redirect
            window.location.href = "{% url 'planificacion_visual' %}?" + params.toString();
        }

        function openProjectPriorities() {
            const params = new URLSearchParams(window.location.search);
            window.location.href = "{% url 'proyectos_prioridades' %}?" + params.toString();
        }

        function openPlanillasDiarias() {
            const params = new URLSearchParams(window.location.search);
            params.set('run', '1'); // Force run calculation
            window.location.href = "{% url 'planillas_diarias' %}?" + params.toString();
        }

        function updateActiveProjectsPanel() {
            const rows = document.querySelectorAll('.tab-content table tbody tr:not(.hidden-row)');
            const projects = new Set();
            
            rows.forEach(row => {
                const proj = row.getAttribute('data-proyecto');
                if (proj && proj.trim() && proj.trim() !== '-') {
                    projects.add(proj.trim());
                }
            });
            
            const projectArray = Array.from(projects).sort();
            
            const badge = document.getElementById('activeProjectsCountBadge');
            if (badge) {
                badge.textContent = projectArray.length;
                if (projectArray.length > 0) {
                    badge.classList.remove('bg-secondary');
                    badge.classList.add('bg-primary');
                } else {
                    badge.classList.remove('bg-primary');
                    badge.classList.add('bg-secondary');
                }
            }
            
            const listContainer = document.getElementById('activeProjectsList');
            if (listContainer) {
                if (projectArray.length === 0) {
                    listContainer.innerHTML = '<div class="text-center py-4 text-muted small"><i class="fas fa-inbox fa-2x mb-2 opacity-25"></i><br>No hay proyectos activos en plan.</div>';
                } else {
                    let html = '';
                    projectArray.forEach(p => {
                        html += `
                        <div class="list-group-item list-group-item-action d-flex align-items-center justify-content-between py-2 border-bottom-0 border-top" style="cursor: pointer;" onclick="openProductionSelector('${p}')">
                            <div class="d-flex align-items-center">
                                <div class="bg-primary bg-opacity-10 text-primary rounded-circle d-flex align-items-center justify-content-center me-3" style="width: 35px; height: 35px;">
                                    <i class="fas fa-code-branch"></i>
                                </div>
                                <div>
                                    <h6 class="mb-0 fw-bold text-dark" style="font-size: 0.95rem;">${p}</h6>
                                    <small class="text-muted" style="font-size: 0.75rem;">En planificación (Clic para editar)</small>
                                </div>
                            </div>
                            <button class="btn btn-sm btn-outline-danger border-0 p-2" onclick="event.stopPropagation(); deleteProjectPlanning('${p}')" title="Borrar Proyecto">
                                <i class="fas fa-trash-alt"></i>
                            </button>
                        </div>`;
                    });
                    listContainer.innerHTML = html;
                }
            }
        }

        window.deleteProjectPlanning = async function(projectCode) {
            const result = await Swal.fire({
                title: '¿Eliminar proyecto?',
                html: `¿Estás seguro de que deseas eliminar el Proyecto <strong>${projectCode}</strong> y quitar todas sus operaciones de la planificación actual?`,
                icon: 'warning',
                showCancelButton: true,
                confirmButtonText: 'Sí, Eliminar',
                cancelButtonText: 'Cancelar',
                confirmButtonColor: '#ef4444',
                customClass: {
                    popup: 'premium-swal',
                    confirmButton: 'premium-confirm',
                    cancelButton: 'premium-cancel'
                }
            });

            if (!result.isConfirmed) return;

            try {
                const scenarioId = new URLSearchParams(window.location.search).get('scenario_id') || "";
                const response = await fetch('/api/delete_project_planning/', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-CSRFToken': '{{ csrf_token }}'
                    },
                    body: JSON.stringify({
                        proyectos: projectCode,
                        scenario_id: scenarioId
                    })
                });

                if (response.ok) {
                    Swal.fire({
                        title: 'Proyecto Eliminado',
                        text: `El proyecto ${projectCode} ha sido removido de la planificación.`,
                        icon: 'success',
                        timer: 2000,
                        showConfirmButton: false,
                        customClass: { popup: 'premium-swal' }
                    }).then(() => {
                        const params = new URLSearchParams(window.location.search);
                        let currentProjects = params.get('proyectos') || '';
                        let projectsArray = currentProjects.split(',').map(p => p.trim()).filter(p => p && p !== projectCode && p.replace('-', '.') !== projectCode && p.replace('.', '-') !== projectCode);
                        params.set('proyectos', projectsArray.join(','));
                        window.location.href = window.location.pathname + '?' + params.toString();
                    });
                } else {
                    throw new Error("Error al borrar la planificación del proyecto");
                }
            } catch (e) {
                Swal.fire({ title: 'Error', text: e.message, icon: 'error' });
            }
        };

        let currentProjectToSelect = "";
        let selectedOpsByArticle = {}; // { macroPk: [idOrden1, idOrden2, ...] }
        let enabledArticles = {}; // { macroPk: true/false }
        let currentLevel2MacroPk = ""; // Tracker for the active article in detail view

        document.addEventListener('DOMContentLoaded', function() {
            // Activar panel de proyectos inicialmente y observar cambios
            updateActiveProjectsPanel();
            const tabContent = document.getElementById('myTabContent');
            if (tabContent) {
                const observer = new MutationObserver(mutations => {
                    updateActiveProjectsPanel();
                });
                observer.observe(tabContent, { childList: true, subtree: true, attributes: true, attributeFilter: ['class'] });
            }

            // --- SELECTIVE PLANNING FLOW ---
             const planForm = document.getElementById('plan-filter-form');
            if (planForm) {
                planForm.addEventListener('submit', async function(e) {
                    const projectsInput = document.getElementById('proyectos');
                    const projValue = projectsInput ? projectsInput.value.trim() : "";
                    
                    if (!projValue) return; // Si está vacío, sigue el flujo normal (limpiar filtros)

                     if (!projValue.includes(',')) {
                         // SINGLE PROJECT FLOW
                         e.preventDefault();
                         e.stopPropagation();
                         
                         const urlParams = new URLSearchParams(window.location.search);
                         const scenarioId = urlParams.get('scenario_id') || "";
                         
                          try {
                              const checkResp = await fetch(`/api/check_project_planning/?proyecto=${encodeURIComponent(projValue)}&scenario_id=${scenarioId}`);
                              const checkData = await checkResp.json();
                              
                              if (checkData.exists && checkData.action === 'show') {
                                  // Proyecto ya planificado: comportamiento permisivo.
                                  // Redirigimos a la grilla para mostrar el proyecto sin bloqueo.
                                  const params = new URLSearchParams(window.location.search);
                                  params.set('proyectos', projValue);
                                  params.set('run', '1');
                                  projectsInput.value = "";
                                  window.location.href = window.location.pathname + "?" + params.toString();
                                  return;
                              }
                              
                              openProductionSelector(projValue);
                              projectsInput.value = ""; 
                              projectsInput.focus();
                          } catch (err) {
                              console.error("Error checking planning state:", err);
                              openProductionSelector(projValue); 
                              projectsInput.value = "";
                              projectsInput.focus();
                          }
                    } else {
                        // MULTI PROJECT FLOW (Comma separated)
                        e.preventDefault();
                        const params = new URLSearchParams(window.location.search);
                        params.set('proyectos', projValue);
                        params.set('run', '1');
                        
                        projectsInput.value = ""; 
                        window.location.href = window.location.pathname + "?" + params.toString();
                    }
                });
            }

            // Enfocar automáticamente el input de proyectos al cargar la página
            const projectsInput = document.getElementById('proyectos');
            if (projectsInput) projectsInput.focus();

            window.openProductionSelector = async function(projectCode) {
                console.log("Abriendo selector para el proyecto:", projectCode);
                try {
                currentProjectToSelect = projectCode;
                selectedOpsByArticle = {};
                enabledArticles = {};
                document.getElementById('selectorSub').innerText = "Proyecto: " + projectCode;
                
                // Usar el scenarioId de la URL o el definido globalmente (Django template)
                const urlScenarioId = new URLSearchParams(window.location.search).get('scenario_id');
                const activeScenarioId = urlScenarioId || (typeof scenarioId !== 'undefined' ? scenarioId : '');
                
                const dialog = document.getElementById('selectorDialog');
                // Permanent width for stability
                dialog.style.maxWidth = "1600px";
                dialog.style.width = "95%";
                
                // Retrieve or create Modal instance cleanly to prevent multiple backdrops/event duplicates
                const selectorModalEl = document.getElementById('selectorProduccionModal');
                let modalInstance = bootstrap.Modal.getInstance(selectorModalEl);
                if (!modalInstance) {
                    modalInstance = new bootstrap.Modal(selectorModalEl);
                }
                modalInstance.show();
                
                backToArticles();
                
                // Clean close: Stop event propagation to prevent any global/parent listener from redirecting to Gantt
                const handleModalHide = function (e) {
                    e.stopPropagation();
                };
                const handleModalHidden = function (e) {
                    e.stopPropagation();
                    const projectsInput = document.getElementById('proyectos');
                    if (projectsInput) projectsInput.focus();
                };
                
                selectorModalEl.removeEventListener('hide.bs.modal', handleModalHide);
                selectorModalEl.removeEventListener('hidden.bs.modal', handleModalHidden);
                
                selectorModalEl.addEventListener('hide.bs.modal', handleModalHide);
                selectorModalEl.addEventListener('hidden.bs.modal', handleModalHidden, { once: true });
                
                const tbody = document.getElementById('tbodyArticles');
                tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4"><i class="fas fa-sync fa-spin me-2"></i> Cargando artículos...</td></tr>';
                
                try {
                    const response = await fetch(`/api/get_project_articles/?proyecto=${projectCode}&scenario_id=${activeScenarioId}`);
                    const data = await response.json();
                    
                    if (data.planned_state) {
                        selectedOpsByArticle = data.planned_state;
                    }

                    if (data.articles && data.articles.length > 0) {
                        tbody.innerHTML = "";
                        data.articles.forEach(art => {
                            enabledArticles[art.MacroPK] = true;
                            const row = document.createElement('tr');
                            row.id = `row-art-${art.MacroPK.replace(/\s+/g, '-')}`;
                            row.innerHTML = `
                                <td class="ps-4 text-center">
                                    <div class="form-check form-switch form-switch-lg d-inline-block">
                                        <input class="form-check-input shadow-sm article-plan-checkbox" type="checkbox" checked>
                                    </div>
                                </td>
                                <td class="fw-bold text-muted text-center">${art.IdOrdenMaster || '-'}</td>
                                <td class="fw-bold text-primary article-clickable">${art.Articulo}</td>
                                <td class="article-clickable">${art.Denominacion}</td>
                                <td class="text-center">${parseFloat(art.Solicitado || 0).toFixed(0)}</td>
                                <td class="text-center">${parseFloat(art.Finalizado || 0).toFixed(0)}</td>
                                <td class="text-center"><span class="badge bg-secondary rounded-pill process-count" id="count-art-${art.MacroPK.replace(/\s+/g, '-')}">0</span></td>
                                <td class="text-center">
                                    <input type="number" 
                                           class="form-control form-control-sm article-priority-input" 
                                           value="${art.nivel_planificacion || 0}" 
                                           min="1">
                                </td>
                                <td class="pe-4 text-center">
                                    <button class="btn btn-sm btn-link text-primary article-clickable">
                                        <i class="fas fa-chevron-right"></i>
                                    </button>
                                </td>
                            `;

                            // Set data attributes and event listeners programmatically to avoid quote-escaping issues in inline JS/HTML attributes
                            const priorityInput = row.querySelector('.article-priority-input');
                            priorityInput.dataset.macropk = art.MacroPK;

                            const planCheckbox = row.querySelector('.article-plan-checkbox');
                            planCheckbox.addEventListener('change', function() {
                                toggleArticlePlan(art.MacroPK, this.checked);
                            });

                            row.querySelectorAll('.article-clickable').forEach(el => {
                                el.addEventListener('click', function() {
                                    handleArticleClick(art.MacroPK, art.Denominacion, art.Articulo);
                                });
                            });

                            tbody.appendChild(row);
                        });
                        updateAllCounters();
                    } else {
                        tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-muted">No se encontraron artículos para este proyecto.</td></tr>';
                    }
                } catch (e) {
                    tbody.innerHTML = '<tr><td colspan="7" class="text-center py-4 text-danger">Error al cargar artículos.</td></tr>';
                }
                } catch (err) {
                    console.error("Error crítico al abrir el selector:", err);
                }
            };

            window.toggleArticlePlan = function(macroPk, isEnabled) {
                enabledArticles[macroPk] = isEnabled;
                const rowId = `row-art-${macroPk.replace(/\s+/g, '-')}`;
                const row = document.getElementById(rowId);
                if (row) {
                    if (isEnabled) {
                         row.style.opacity = "1";
                         row.classList.remove('bg-light');
                    } else {
                         row.style.opacity = "0.5";
                         row.classList.add('bg-light');
                    }
                }
            };

            window.handleArticleClick = function(macroPk, artName, artCode) {
                if (!enabledArticles[macroPk]) {
                    Swal.fire({
                         title: 'Artículo Desactivado',
                         text: 'Active el switch de "Planificar" para ver los detalles de este artículo.',
                         icon: 'info',
                         timer: 2000,
                         showConfirmButton: false,
                         customClass: { popup: 'premium-swal' }
                    });
                    return;
                }
                showProcesses(macroPk, artName, artCode);
            };

            window.showProcesses = async function(macroPk, artName, artCode) {
                currentLevel2MacroPk = macroPk; // Set global tracker
                
                document.getElementById('level1-articles').style.display = 'none';
                document.getElementById('level2-processes').style.display = 'block';
                document.getElementById('detailArtName').innerText = artName;
                document.getElementById('detailArtCode').innerText = "MacroPK: " + macroPk;
                
                // Button management
                document.getElementById('btnAcceptSelector').style.display = 'block';
                document.getElementById('btnConfirmSelect').style.display = 'none';
                
                const tbody = document.getElementById('tbodyProcesses');
                tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4"><i class="fas fa-sync fa-spin me-2"></i> Cargando procesos...</td></tr>';
                
                try {
                    const urlScenarioId = new URLSearchParams(window.location.search).get('scenario_id');
                    const activeScenarioId = urlScenarioId || (typeof scenarioId !== 'undefined' ? scenarioId : '');
                    const response = await fetch(`/api/get_article_processes/?macro_pk=${macroPk}&scenario_id=${activeScenarioId}`);
                    const data = await response.json();
                    
                    if (data.processes && data.processes.length > 0) {
                        // Ordenar por Nivel de menor a menor (Ascendente) para seguir secuencia ERP
                        data.processes.sort((a, b) => (parseInt(a.Nivel_Planificacion) || 0) - (parseInt(b.Nivel_Planificacion) || 0));
                        
                        tbody.innerHTML = "";
                        
                        // FIXED: Only auto-select processes with real pending quantity (Pendiente > 0)
                        const isFirstTime = !selectedOpsByArticle[macroPk];
                        if (isFirstTime) {
                            selectedOpsByArticle[macroPk] = data.processes
                                .filter(p => parseFloat(p.Pendiente || 0) > 0)
                                .map(p => p.IdOrden.toString());
                        }

                        const previouslySelected = selectedOpsByArticle[macroPk] || [];
                        
                        data.processes.forEach(proc => {
                            const pendiente = parseFloat(proc.Pendiente || 0);
                            const isChecked = previouslySelected.includes(proc.IdOrden.toString());
                            const isCompleted = pendiente <= 0;
                            const row = document.createElement('tr');
                            if (isCompleted) row.style.opacity = '0.5';
                            row.innerHTML = `
                                <td class="ps-4 text-center">
                                    <div class="form-check form-switch form-switch-lg d-inline-block">
                                        <input class="form-check-input shadow-sm process-checkbox" type="checkbox" 
                                               value="${proc.IdOrden}" ${isChecked ? 'checked' : ''}>
                                    </div>
                                </td>
                                <td class="text-center">
                                    <input type="number" class="form-control form-control-sm text-center fw-bold mx-auto process-priority-input" 
                                           style="width: 70px;"
                                           value="${proc.Nivel_Planificacion || 0}">
                                </td>
                                <td class="small">${proc.Proceso}</td>
                                <td class="text-center"><span class="badge bg-light text-dark border">${proc.MaquinaNombre || '-'}</span></td>
                                <td class="text-center">${parseFloat(proc.Cantidad || 0).toFixed(0)}</td>
                                <td class="pe-4 text-center fw-bold ${isCompleted ? 'text-muted' : 'text-danger'}">${pendiente.toFixed(2)}</td>
                            `;

                            // Add change listener to checkbox programmatically to prevent string escaping errors
                            const checkbox = row.querySelector('.process-checkbox');
                            checkbox.addEventListener('change', function() {
                                updateProcessSelection(macroPk, this);
                            });

                            // Add change listener to priority input programmatically to prevent string escaping errors
                            const priorityInput = row.querySelector('.process-priority-input');
                            priorityInput.addEventListener('change', function() {
                                updateProcessPriority(proc.IdOrden, this.value);
                            });

                            tbody.appendChild(row);
                        });
                        
                        // Sync counters for all articles
                        updateAllCounters();
                        // Check if all are selected to sync master checkbox
                        syncMasterCheckbox();
                    } else {
                        tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-muted">No hay procesos abiertos para este artículo.</td></tr>';
                    }
                } catch (e) {
                    tbody.innerHTML = '<tr><td colspan="6" class="text-center py-4 text-danger">Error al cargar procesos.</td></tr>';
                }
            };

            window.backToArticles = function() {
                document.getElementById('level1-articles').style.display = 'block';
                document.getElementById('level2-processes').style.display = 'none';
                
                // Button management
                document.getElementById('btnAcceptSelector').style.display = 'none';
                document.getElementById('btnConfirmSelect').style.display = 'block';
            };

            window.updateProcessSelection = function(macroPk, checkbox) {
                if (!selectedOpsByArticle[macroPk]) selectedOpsByArticle[macroPk] = [];
                const id = checkbox.value.toString();
                if (checkbox.checked) {
                    if (!selectedOpsByArticle[macroPk].includes(id)) {
                        selectedOpsByArticle[macroPk].push(id);
                    }
                } else {
                    selectedOpsByArticle[macroPk] = selectedOpsByArticle[macroPk].filter(x => x !== id);
                }
                updateCounter(macroPk);
                syncMasterCheckbox();
            };

            window.updateCounter = function(macroPk) {
                const badge = document.getElementById(`count-art-${macroPk.replace(/\s+/g, '-')}`);
                if (badge) {
                    const count = selectedOpsByArticle[macroPk] ? selectedOpsByArticle[macroPk].length : 0;
                    badge.innerText = count;
                    if (count > 0) {
                        badge.classList.remove('bg-secondary');
                        badge.classList.add('bg-primary');
                    } else {
                        badge.classList.remove('bg-primary');
                        badge.classList.add('bg-secondary');
                    }
                }
            };

            window.updateProcessPriority = function(idOrden, nivel) {
                console.log("Enviando ID:", idOrden, "Nivel:", nivel);
                const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');
                return fetch('/api/update_manual_nivel/', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        id_orden: idOrden,
                        nivel_manual: nivel,
                        scenario_id: scenarioId
                    })
                })
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        console.error("Error saving priority:", data.error);
                        alert("Error al guardar nivel: " + data.error);
                    } else {
                        console.log("Nivel guardado correctamente en DB SQLite para ID:", idOrden);
                    }
                    return data;
                })
                .catch(err => {
                    console.error("Network error saving priority:", err);
                    alert("Error de red al guardar nivel.");
                });
            };

            window.updateAllCounters = function() {
                for (const mPk in selectedOpsByArticle) {
                    updateCounter(mPk);
                }
            };

            function syncMasterCheckbox() {
                const total = document.querySelectorAll('.process-checkbox').length;
                const checked = document.querySelectorAll('.process-checkbox:checked').length;
                const master = document.getElementById('checkAllProcesses');
                if (master) {
                    master.checked = total > 0 && total === checked;
                }
            }

            window.toggleAllProcesses = function(master) {
                const boxes = document.querySelectorAll('.process-checkbox');
                if (!currentLevel2MacroPk) return;

                if (master.checked) {
                    // Select all
                    selectedOpsByArticle[currentLevel2MacroPk] = Array.from(boxes).map(b => b.value.toString());
                    boxes.forEach(b => b.checked = true);
                } else {
                    // Deselect all
                    selectedOpsByArticle[currentLevel2MacroPk] = [];
                    boxes.forEach(b => b.checked = false);
                }
                updateCounter(currentLevel2MacroPk);
            };

            window.confirmSelection = async function() {
                // Collect all selected OPs but ONLY from ENABLED articles
                let finalSelection = [];
                // Collect priority for ALL articles, regardless of selection
                let piecePriorities = {};
                document.querySelectorAll('.article-priority-input').forEach(input => {
                    const mPk = input.dataset.macropk;
                    if (mPk && enabledArticles[mPk]) {
                        piecePriorities[mPk] = parseInt(input.value) || 1;
                    }
                });

                for (const mPk in selectedOpsByArticle) {
                    if (enabledArticles[mPk]) {
                        finalSelection = finalSelection.concat(selectedOpsByArticle[mPk]);
                    }
                }
                
                if (finalSelection.length === 0) {
                    Swal.fire({
                        title: 'Atención',
                        text: 'No hay procesos seleccionados en los artículos activos.',
                        icon: 'warning',
                        customClass: { popup: 'premium-swal' }
                    });
                    return;
                }

                const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');
                const btn = document.getElementById('btnConfirmSelect');
                const originalHtml = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-spinner fa-spin me-2"></i> Cargando...';
                btn.disabled = true;

                try {
                    const response = await fetch('/api/confirm_selected_tasks/', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': '{{ csrf_token }}'
                        },
                        body: JSON.stringify({
                            id_ordens: finalSelection,
                            piece_priorities: piecePriorities, // macroPk -> priority
                            selected_ops_by_article: selectedOpsByArticle, // to know which OP gets which priority
                            scenario_id: scenarioId,
                            project_code: currentProjectToSelect,
                            force: true
                        })
                    });
                    
                    if (response.ok) {
                        Swal.fire({
                            title: 'Planificación Lista',
                            text: `Se han cargado ${finalSelection.length} procesos correctamente.`,
                            icon: 'success',
                            timer: 2000,
                            showConfirmButton: false,
                            customClass: { popup: 'premium-swal' }
                        }).then(() => {
                             // Hide modal cleanly
                             const modalEl = document.getElementById('selectorProduccionModal');
                             const modalInstance = bootstrap.Modal.getInstance(modalEl);
                             if (modalInstance) {
                                 modalInstance.hide();
                             }
                             
                             const params = new URLSearchParams(window.location.search);
                             const scenarioParam = params.get('scenario_id') || scenarioId;
                             let currentProjects = params.get('proyectos') || '';
                             let projectsArray = currentProjects.split(',').map(p => p.trim()).filter(p => p);
                             if (currentProjectToSelect && !projectsArray.includes(currentProjectToSelect)) {
                                 projectsArray.push(currentProjectToSelect);
                             }
                             
                             params.set('scenario_id', scenarioParam);
                             params.set('proyectos', projectsArray.join(','));
                             
                             // Reload current planning page with updated filters, avoiding Gantt redirection
                             const planUrl = `${window.location.pathname}?${params.toString()}`;
                             window.location.href = planUrl;
                        });
                    } else {
                        throw new Error("Error al confirmar la selección");
                    }
                } catch (e) {
                    Swal.fire({ title: 'Error', text: e.message, icon: 'error' });
                    btn.innerHTML = originalHtml;
                    btn.disabled = false;
                }
            };
            // --- CLEAN / RESET TABLE BUTTON ---
            const btnClean = document.getElementById('btnCleanTable');
            if (btnClean) {
                btnClean.addEventListener('click', async function() {
                    const result = await Swal.fire({
                        title: '¿RESTABLECER planificación?',
                        html: `
                            <div class="text-start mt-3">
                                <div class="d-flex align-items-center mb-2">
                                    <i class="fas fa-trash-alt text-danger me-2"></i>
                                    <span>Se borrarán todos los movimientos manuales.</span>
                                </div>
                                <div class="d-flex align-items-center mb-2">
                                    <i class="fas fa-history text-primary me-2"></i>
                                    <span>Se restaurarán las prioridades originales.</span>
                                </div>
                                <div class="d-flex align-items-center mb-2">
                                    <i class="fas fa-eye text-success me-2"></i>
                                    <span>Reaparecerán tareas ocultas.</span>
                                </div>
                                <hr>
                                <p class="text-muted small mb-0">Esta acción devolverá la planificación al estado original del ERP.</p>
                            </div>
                        `,
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, Restablecer',
                        cancelButtonText: 'Cancelar',
                        confirmButtonColor: '#ef4444',
                        customClass: {
                            popup: 'premium-swal',
                            confirmButton: 'premium-confirm',
                            cancelButton: 'premium-cancel'
                        }
                    });

                    if (!result.isConfirmed) return;
                    
                    // Collect all IDs on the screen (from all tabs)
                    // We can query all rows with data-id attribute
                    const allRows = document.querySelectorAll('tr[data-id]');
                    const ids = Array.from(allRows).map(r => r.dataset.id);
                    
                    try {
                        const proyectosInput = document.getElementById('proyectos');
                        const projVal = proyectosInput ? proyectosInput.value : '';
                        const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');

                        const response = await fetch('/api/reset_planning/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': '{{ csrf_token }}'
                            },
                            body: JSON.stringify({ 
                                ids: ids, 
                                scenario_id: scenarioId,
                                proyectos: projVal
                            })
                        });
                        
                        if (response.ok) {
                            Swal.fire({
                                title: '¡Restablecido!',
                                text: 'La planificación ha vuelto a su estado original.',
                                icon: 'success',
                                timer: 2000,
                                showConfirmButton: false,
                                customClass: { popup: 'premium-swal' }
                            }).then(() => window.location.reload());
                        } else {
                            const data = await response.json();
                            Swal.fire({
                                title: 'Error',
                                text: data.error || "No se pudo restablecer el plan.",
                                icon: 'error',
                                customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                            });
                        }
                    } catch (e) {
                        console.error(e);
                        alert("Error de conexión al restablecer.");
                    }
                });
            }
            // --- Tab Persistence Logic ---
            const activeTabId = localStorage.getItem('activePlanificacionTab');
            if (activeTabId) {
                const tabTrigger = document.getElementById(activeTabId);
                if (tabTrigger) {
                    const tab = new bootstrap.Tab(tabTrigger);
                    tab.show();
                }
            }

            // Save tab state on change
            const tabElsd = document.querySelectorAll('button[data-bs-toggle="tab"]');
            tabElsd.forEach(tabEl => {
                tabEl.addEventListener('shown.bs.tab', event => {
                    localStorage.setItem('activePlanificacionTab', event.target.id);
                });
            });

            // --- Horizontal Scroll with Mouse Wheel ---
            const tabList = document.getElementById('myTab');
            if (tabList) {
                tabList.addEventListener('wheel', (evt) => {
                    evt.preventDefault();
                    tabList.scrollLeft += evt.deltaY;
                });
            }

            // --- Manual Time Edit Logic ---
            // Listener for editable cells
            const editableCells = document.querySelectorAll('.editable-time');
            editableCells.forEach(cell => {
                // Save on Enter key
                cell.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        this.blur(); // Trigger blur to save
                    }
                });

                // Save on leaving the cell
                cell.addEventListener('blur', async function() {
                    const row = this.closest('tr');
                    const idOrden = row.dataset.id;
                    const newValue = this.innerText.trim();
                const maquina = row.dataset.maquina; 
                const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');
                
                // Validate basic number
                    const numVal = parseFloat(newValue.replace(',', '.')); // Handle commas
                    if (isNaN(numVal) || numVal < 0) {
                        alert("Por favor ingrese un número válido.");
                        this.innerText = "0.00"; // Reset or handle error
                        return;
                    }

                    // Visual Feedback
                    this.style.backgroundColor = '#e2e6ea'; // Grey out while saving

                    try {
                        const response = await fetch('/api/update_manual_time/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': '{{ csrf_token }}'
                            },
                            body: JSON.stringify({
                                id_orden: idOrden,
                                tiempo_manual: numVal,
                                maquina: maquina,
                                scenario_id: scenarioId
                            })
                        });

                        if (response.ok) {
                            // Success Feedback
                            this.style.backgroundColor = '#ffeeba'; // Yellow flag
                            this.innerText = numVal.toFixed(2);
                        } else {
                            const data = await response.json();
                            alert("Error al guardar tiempo: " + (data.error || "Desconocido"));
                            // Revert? Hard to revert without knowing original
                            this.style.backgroundColor = '#f8d7da'; // Red error
                        }
                    } catch (e) {
                        console.error(e);
                        alert("Error de conexión al guardar.");
                        this.style.backgroundColor = '#f8d7da';
                    }
                });
            });

            // --- Manual Nivel Edit Logic ---
            const editableNivelCells = document.querySelectorAll('.editable-nivel');
            editableNivelCells.forEach(cell => {
                cell.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        this.blur();
                    }
                });

                cell.addEventListener('blur', async function() {
                    const row = this.closest('tr');
                    const idOrden = row.dataset.id;
                    const newValue = this.innerText.trim();
                    const maquina = row.dataset.maquina; 
                    const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');
                    
                    // Validate basic integer
                    const numVal = parseInt(newValue);
                    if (isNaN(numVal) || numVal < 0) {
                        alert("Por favor ingrese un número entero válido (nivel).");
                        this.innerText = "0"; 
                        return;
                    }

                    this.style.backgroundColor = '#e2e6ea'; 

                    try {
                        const response = await fetch('/api/update_manual_nivel/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': '{{ csrf_token }}'
                            },
                            body: JSON.stringify({
                                id_orden: idOrden,
                                nivel_manual: numVal,
                                maquina: maquina,
                                scenario_id: scenarioId
                            })
                        });

                        if (response.ok) {
                            this.style.backgroundColor = '#ffeeba'; 
                            this.innerText = numVal;
                        } else {
                            const data = await response.json();
                            alert("Error al guardar nivel: " + (data.error || "Desconocido"));
                            this.style.backgroundColor = '#f8d7da'; 
                        }
                    } catch (e) {
                        console.error(e);
                        alert("Error de conexión al guardar.");
                        this.style.backgroundColor = '#f8d7da';
                    }
                });
            });

            // --- Manual Overlap Edit Logic ---
            const editableSolapamientoCells = document.querySelectorAll('.editable-solapamiento');
            editableSolapamientoCells.forEach(cell => {
                cell.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        this.blur();
                    }
                });

                cell.addEventListener('blur', async function() {
                    const row = this.closest('tr');
                    const idOrden = row.dataset.id;
                    const rawValue = this.innerText.replace('%', '').trim();
                    const maquina = row.dataset.maquina; 
                    const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');
                    
                    const numVal = parseFloat(rawValue);
                    if (isNaN(numVal) || numVal < 0 || numVal > 100) {
                        alert("Por favor ingrese un porcentaje válido (0 a 100).");
                        this.innerText = "0%"; 
                        return;
                    }

                    this.style.backgroundColor = '#e2e6ea'; 

                    try {
                        const response = await fetch('/api/update_overlap_percentage/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': '{{ csrf_token }}'
                            },
                            body: JSON.stringify({
                                id_orden: idOrden,
                                porcentaje_solapamiento: numVal,
                                maquina: maquina,
                                scenario_id: scenarioId
                            })
                        });

                        if (response.ok) {
                            this.style.backgroundColor = numVal > 0 ? '#ffeeba' : 'transparent'; 
                            this.innerText = numVal + '%';
                        } else {
                            const data = await response.json();
                            alert("Error al guardar solapamiento: " + (data.error || "Desconocido"));
                            this.style.backgroundColor = '#f8d7da'; 
                        }
                    } catch (e) {
                        console.error(e);
                        alert("Error de conexión al guardar.");
                        this.style.backgroundColor = '#f8d7da';
                    }
                });
            });



            // --- Reordering Logic (Buttons) ---
            async function moveRow(btn, direction) {
                const row = btn.closest('tr');
                const idOrden = row.dataset.id;
                const maquina = row.dataset.maquina;
                // SANITIZE: parse as number to remove any locale comma formatting
                const priority = parseFloat(String(row.dataset.priority).replace(',', '.')) || 0;
                
                let neighbor = null;
                if (direction === 'up') {
                    neighbor = row.previousElementSibling;
                } else {
                    neighbor = row.nextElementSibling;
                }

                if (!neighbor || !neighbor.dataset.id) {
                    console.log("No neighbor to swap with");
                    return; // Can't move
                }

                const neighborId = neighbor.dataset.id;
                const neighborPriority = parseFloat(String(neighbor.dataset.priority).replace(',', '.')) || 0;

                // Call API
                try {
                    const response = await fetch(`/api/move_priority/${idOrden}/${direction}/`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'X-CSRFToken': '{{ csrf_token }}'
                        },
                        body: JSON.stringify({
                            maquina: maquina,
                            priority: priority,
                            neighbor_id: neighborId,
                            neighbor_priority: neighborPriority,
                            scenario_id: new URLSearchParams(window.location.search).get('scenario_id')
                        })
                    });

                    if (response.ok) {
                        // Optimistic Update (No Reload)
                        // 1. Swap Priorities in Dataset
                        row.dataset.priority = neighborPriority.toString();
                        neighbor.dataset.priority = priority.toString();

                        // 2. Swap DOM Elements
                        if (direction === 'up') {
                            row.parentNode.insertBefore(row, neighbor);
                        } else {
                            // Moving down: Insert neighbor before row (effectively swapping)
                            row.parentNode.insertBefore(neighbor, row);
                        }
                    } else {
                        const data = await response.json();
                        alert("Error al mover la fila: " + (data.error || response.statusText));
                    }
                } catch (error) {
                    console.error(error);
                    alert("Error de conexión: " + error.message);
                }
            }

            document.querySelectorAll('.btn-up').forEach(btn => {
                btn.addEventListener('click', () => moveRow(btn, 'up'));
            });

            document.querySelectorAll('.btn-down').forEach(btn => {
                btn.addEventListener('click', () => moveRow(btn, 'down'));
            });

            // --- Delete / Hide Logic ---
            document.querySelectorAll('.btn-delete').forEach(btn => {
                btn.addEventListener('click', async function() {
                    const result = await Swal.fire({
                        title: '¿Ocultar esta OP?',
                        text: 'La tarea se ocultará de la vista actual y del Gantt, pero NO se borrará de la base de datos de SQLSERVER. Es una acción segura.',
                        icon: 'info',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, ocultar',
                        cancelButtonText: 'Cancelar',
                        confirmButtonColor: '#64748b',
                        customClass: {
                            popup: 'premium-swal',
                            confirmButton: 'premium-confirm',
                            cancelButton: 'premium-cancel'
                        }
                    });
                    if (!result.isConfirmed) return;
                    
                    const row = this.closest('tr');
                    const idOrden = row.dataset.id;
                    
                    try {
                        const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');
                        const response = await fetch('/api/hide_task/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': '{{ csrf_token }}'
                            },
                            body: JSON.stringify({ 
                                id_orden: idOrden,
                                scenario_id: scenarioId
                            })
                        });
                        
                        if (response.ok) {
                            row.remove();
                        } else {
                            const data = await response.json();
                            alert('Error al ocultar tarea: ' + (data.error || "Desconocido"));
                        }
                    } catch (e) {
                        console.error(e);
                        alert('Error de conexión');
                    }
                });
            });

            // --- Manual Quantity Produced Logic ---
            const qtyCells = document.querySelectorAll('.editable-cantidad');
            qtyCells.forEach(cell => {
                cell.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault();
                        e.stopPropagation();
                        this.blur();
                    }
                });

                cell.addEventListener('input', function() {
                    const row = this.closest('tr');
                    const total = parseFloat(row.dataset.totalQty) || 0;
                    const unitTime = parseFloat(row.dataset.unitTime) || 0;
                    const valText = this.innerText.trim().replace(',', '.');
                    const val = parseFloat(valText) || 0;
                    
                    // 1. Update Pending Quantity
                    const pendientesCell = row.querySelector('.cant-pendientes');
                    if (pendientesCell) {
                        pendientesCell.innerText = Math.max(0, total - val).toLocaleString('es-AR', {minimumFractionDigits: 0, maximumFractionDigits: 1});
                    }

                    // 2. Update Process Time (Automatic Recalculation)
                    const processTimeCell = row.querySelector('.editable-time');
                    if (processTimeCell) {
                         const newTime = Math.max(0, (total - val) * unitTime);
                         processTimeCell.innerText = newTime.toFixed(2);
                         processTimeCell.style.color = '#0d6efd'; 
                    }
                });

                cell.addEventListener('blur', async function() {
                    const row = this.closest('tr');
                    const idOrden = row.dataset.id;
                    const total = parseFloat(row.dataset.totalQty) || 0;
                    const unitTime = parseFloat(row.dataset.unitTime) || 0;
                    let valText = this.innerText.trim().replace(',', '.');
                    let val = parseFloat(valText) || 0;
                    const maquina = row.dataset.maquina;
                    const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');

                    if (val > total) {
                         Swal.fire({
                             title: 'Validación de Cantidad',
                             text: `La cantidad producida (${val}) no puede ser superior al total (${total}).`,
                             icon: 'warning',
                             customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                         });
                         val = total;
                         this.innerText = val;
                    }
                    if (val < 0) val = 0;

                    this.style.backgroundColor = '#e2e6ea';

                    try {
                        const response = await fetch('/api/update_cantidad_producida/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': '{{ csrf_token }}'
                            },
                            body: JSON.stringify({
                                id_orden: idOrden,
                                cantidad_producida: val,
                                maquina: maquina,
                                scenario_id: scenarioId
                            })
                        });

                        if (response.ok) {
                            this.style.backgroundColor = '#ffeeba'; // Yellow flag
                        } else {
                            const data = await response.json();
                            Swal.fire({ title: 'Error', text: data.error, icon: 'error' });
                        }
                    } catch (e) {
                         console.error(e);
                    }
                });
            });


            // --- Machine Change via Modal Logic ---
            const machineModal = new bootstrap.Modal(document.getElementById('machineSelectorModal'));
            let currentEditingOp = null;
            let currentOriginMachine = null;

            document.querySelectorAll('.open-machine-modal').forEach(btn => {
                btn.addEventListener('click', function() {
                    currentEditingOp = this.dataset.op;
                    currentOriginMachine = this.dataset.currentMachineId;
                    
                    document.getElementById('modal-op-title').innerText = `OP: ${currentEditingOp}`;
                    
                    // Reset search
                    const filterInput = document.getElementById('machineFilterInput');
                    filterInput.value = '';
                    document.querySelectorAll('.machine-item').forEach(item => item.classList.remove('hidden'));
                    
                    machineModal.show();
                });
            });

            // Machine Search Filtering
            document.getElementById('machineFilterInput').addEventListener('input', function() {
                const term = this.value.toLowerCase();
                document.querySelectorAll('.machine-item').forEach(item => {
                    const name = item.querySelector('.fw-bold').innerText.toLowerCase();
                    if (name.includes(term)) {
                        item.classList.remove('hidden');
                    } else {
                        item.classList.add('hidden');
                    }
                });
            });

            document.querySelectorAll('.btn-select-machine-modal').forEach(btn => {
                btn.addEventListener('click', async function() {
                    const targetMachineId = this.dataset.targetId;
                    const targetMachineName = this.dataset.targetName;
                    const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');

                    if (currentOriginMachine === targetMachineId) {
                        machineModal.hide();
                        return;
                    }

                    machineModal.hide();

                    const result = await Swal.fire({
                        title: '¿Cambiar de Máquina?',
                        html: `¿Desea mover la <b>OP ${currentEditingOp}</b> a la máquina <b>${targetMachineName}</b>?`,
                        icon: 'question',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, reasignar',
                        cancelButtonText: 'Cancelar',
                        customClass: {
                            popup: 'premium-swal',
                            confirmButton: 'premium-confirm',
                            cancelButton: 'premium-cancel'
                        }
                    });

                    if (!result.isConfirmed) return;

                    Swal.fire({
                        title: 'Procesando...',
                        text: 'Recalculando tiempos y prioridades...',
                        allowOutsideClick: false,
                        didOpen: () => {
                            Swal.showLoading();
                        },
                        customClass: { popup: 'premium-swal' }
                    });

                    try {
                        const response = await fetch('/api/move_task/', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': '{{ csrf_token }}'
                            },
                            body: JSON.stringify({
                                id_orden: currentEditingOp,
                                target_machine_id: targetMachineId,
                                new_priority: 99999, 
                                modo_solapamiento: 'manual',
                                scenario_id: scenarioId
                            })
                        });

                        if (response.ok) {
                            window.location.reload();
                        } else {
                            const data = await response.json();
                            Swal.fire({ title: 'Error', text: data.error || 'No se pudo mover la tarea.', icon: 'error' });
                        }
                    } catch (err) {
                        console.error(err);
                        Swal.fire({ title: 'Error de Red', text: 'Desconexión con el servidor.', icon: 'error' });
                    }
                });
            });
            
            // --- Drag and Drop Logic (SortableJS for EVERYTHING) ---
            // We use SortableJS to handle the drag. On drop (onEnd), we check if the mouse 
            // is over a Tab Header using elementFromPoint. If so, we treat it as a Move.
            // Otherwise, we treat it as a Reorder.
            
            const tobodies = document.querySelectorAll('tbody');
            tobodies.forEach(tbody => {
                new Sortable(tbody, {
                    animation: 150,
                    forceFallback: true,
                    fallbackOnBody: true,
                    preventOnFilter: false,
                    delay: 100,
                    delayOnTouchOnly: true,
                    ghostClass: 'sortable-ghost',
                    chosenClass: 'sortable-chosen',
                    onEnd: async function (evt) {
                        const itemEl = evt.item; 
                        const idOrden = itemEl.dataset.id;
                        const maquinaOrigin = itemEl.dataset.maquina; // The machine it came from
                        
                        // 1. CHECK FOR DROP ON TAB (Move to Machine)
                        // We need mouse coordinates. Sortable provides a touch/mouse event in originalEvent.
                        const touch = evt.originalEvent.changedTouches ? evt.originalEvent.changedTouches[0] : evt.originalEvent;
                        const x = touch.clientX;
                        const y = touch.clientY;
                        
                        // Hide the helper momentarily so we can see what's under it
                        itemEl.style.display = 'none'; 
                        const elemBelow = document.elementFromPoint(x, y);
                        itemEl.style.display = ''; // Restore
                        
                        const targetTab = elemBelow ? elemBelow.closest('.nav-link') : null;
                        
                        if (targetTab && targetTab.getAttribute('role') === 'tab') {
                            const targetMachine = targetTab.dataset.machine;
                            
                            // Prevent moving to self (tab names match)
                            // The tab text is the machine name.
                            if (targetMachine === maquinaOrigin) {
                                return; // Dropped on self, treat as reorder if index changed, but safer to ignore cross-logic
                            }

                            const result = await Swal.fire({
                                title: '¿Mover Tarea?',
                                html: `¿Confirma que desea mover la <b>OP ${idOrden}</b> a la máquina <b>${targetMachine}</b>?`,
                                icon: 'question',
                                showCancelButton: true,
                                confirmButtonText: 'Sí, mover',
                                cancelButtonText: 'Cancelar',
                                customClass: {
                                    popup: 'premium-swal',
                                    confirmButton: 'premium-confirm',
                                    cancelButton: 'premium-cancel'
                                }
                            });

                            if (!result.isConfirmed) {
                                window.location.reload(); // Revert visual drag
                                return;
                            }
                            
                            // Calculate Priority: End of Target Queue
                            // Find target tab content
                            const contentSelector = targetTab.getAttribute('data-bs-target');
                            const contentDiv = document.querySelector(contentSelector);
                            let newPriority = 1000;
                            
                            if (contentDiv) {
                                const rows = contentDiv.querySelectorAll('tbody tr[data-priority]');
                                if (rows.length > 0) {
                                    const lastRow = rows[rows.length - 1];
                                    const lastPrio = parseFloat(lastRow.dataset.priority) || 0;
                                    newPriority = lastPrio + 1000;
                                }
                            }
                                          // Visual toggle update (Manual) and enable input
                             const rowToggleBtn = itemEl.querySelector('.solapamiento-modo-toggle');
                             if (rowToggleBtn) {
                                 rowToggleBtn.classList.remove('btn-success');
                                 rowToggleBtn.classList.add('btn-warning');
                                 rowToggleBtn.textContent = 'Manual';
                                 const rowPctInput = itemEl.querySelector('.solapamiento-porcentaje-input');
                                 if (rowPctInput) {
                                     rowPctInput.disabled = false;
                                     rowPctInput.style.backgroundColor = '#ffeeba';
                                     rowPctInput.style.color = '';
                                 }
                             }

                             try {
                                console.log('--- DRAG MOVE_TASK ---', {id_orden: idOrden, target_machine_id: targetMachine, new_priority: newPriority});
                                const response = await fetch('/api/move_task/', {
                                    method: 'POST',
                                    headers: {
                                        'Content-Type': 'application/json',
                                        'X-CSRFToken': '{{ csrf_token }}'
                                    },
                                    body: JSON.stringify({
                                        id_orden: idOrden,
                                        target_machine_id: targetMachine,
                                        new_priority: newPriority,
                                        modo_solapamiento: 'manual',
                                        scenario_id: new URLSearchParams(window.location.search).get('scenario_id')
                                    })
                                });
                                
                                if (response.ok) {
                                    window.location.reload();
                                } else {
                                    const data = await response.json();
                                    alert('Error: ' + data.error);
                                    window.location.reload();
                                }
                            } catch (err) {
                                alert('Error de red');
                                window.location.reload();
                            }
                            return; // STOP HERE, DO NOT DO REORDER LOGIC
                        }

                        // 2. NORMAL REORDER LOGIC (Same Machine)
                        // Check if order actually changed
                        if (evt.oldIndex === evt.newIndex) return;

                        // Find neighbors
                        const prev = itemEl.previousElementSibling;
                        const next = itemEl.nextElementSibling;
                        
                        let newPriority = 0;
                        
                        if (prev && next) {
                            const p1 = parseFloat(prev.dataset.priority) || 0;
                            const p2 = parseFloat(next.dataset.priority) || 0;
                            newPriority = (p1 + p2) / 2; 
                        } else if (prev) {
                            const p = parseFloat(prev.dataset.priority) || 0;
                            newPriority = p + 1000;
                        } else if (next) {
                            const p = parseFloat(next.dataset.priority) || 0;
                            newPriority = p / 2; 
                            if (newPriority <= 0) newPriority = 100;
                        } else {
                            return;
                        }

                        console.log(`Reordering ${idOrden} to Priority ${newPriority}`);

                        // Call API to set new priority
                        try {
                            const response = await fetch(`/api/set_priority/${idOrden}/`, {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': '{{ csrf_token }}'
                                },
                                body: JSON.stringify({
                                    maquina: maquinaOrigin,
                                    new_priority: newPriority,
                                    scenario_id: new URLSearchParams(window.location.search).get('scenario_id')
                                })
                            });

                            if (response.ok) {
                                // Optimistic Update
                                itemEl.dataset.priority = newPriority;
                            } else {
                                const data = await response.json();
                                Swal.fire({
                                    title: 'Error',
                                    text: "Error al guardar la nueva posición: " + (data.error || response.statusText),
                                    icon: 'error',
                                    confirmButtonText: 'Cerrar',
                                    customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                                }).then(() => {
                                    window.location.reload();
                                });                            }
                        } catch (e) {
                            console.error(e);
                            Swal.fire({
                                title: 'Error de Conexión',
                                text: "No se pudo guardar la posición: " + e.message,
                                icon: 'error',
                                confirmButtonText: 'Cerrar',
                                customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                            }).then(() => {
                                window.location.reload();
                            });
                        }
                    }
                });
            });

            // Logic for mode selector - decouple scenario when moving to manual
            const planModeSelector = document.getElementById('plan-mode-selector');
            if (planModeSelector) {
                planModeSelector.addEventListener('change', function() {
                    if (this.value === 'manual') {
                        // Clear scenario_id to load Current State when switching to manual
                        const scenSel = document.getElementById('active-scenario-id-input');
                        if (scenSel) scenSel.value = "";
                    }
                    this.form.submit();
                });
            }

            // Reset ERP button
            const btnResetToERP = document.getElementById('btnResetToERP');
            if (btnResetToERP) {
                btnResetToERP.addEventListener('click', async function() {
                    const result = await Swal.fire({
                        title: '¿Restablecer al Plan ERP?',
                        text: "Se borrarán todos los ajustes manuales de este escenario y se volverá a las prioridades originales.",
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, Restablecer',
                        cancelButtonText: 'Cancelar',
                        confirmButtonColor: '#fbbf24',
                        customClass: {
                            popup: 'premium-swal',
                            confirmButton: 'premium-confirm',
                            cancelButton: 'premium-cancel'
                        }
                    });

                    if (result.isConfirmed) {
                        try {
                            const proyectosInput = document.getElementById('proyectos');
                            const projVal = proyectosInput ? proyectosInput.value : '';
                            const scenarioId = document.getElementById('active-scenario-id-input').value;

                            const response = await fetch('/api/reset_planning/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': '{{ csrf_token }}'
                                },
                                body: JSON.stringify({ 
                                    scenario_id: scenarioId,
                                    proyectos: projVal
                                })
                            });
                            
                            if (response.ok) {
                                Swal.fire({
                                    title: '¡Restablecido!',
                                    icon: 'success',
                                    timer: 1500,
                                    showConfirmButton: false,
                                    customClass: { popup: 'premium-swal' }
                                }).then(() => {
                                    // reload with manual mode and NO scenario_id to see current clean state
                                    window.location.href = window.location.pathname + "?plan_mode=manual&proyectos=" + encodeURIComponent(projVal);
                                });
                            }
                        } catch (e) { console.error(e); }
                    }
                });
            }

            // --- CLEAR PLANNING ---
            const btnClearPlanning = document.getElementById('btnClearPlanning');
            if (btnClearPlanning) {
                btnClearPlanning.addEventListener('click', async function() {
                    const result = await Swal.fire({
                        title: '¿Vaciar Planificación?',
                        text: "Se borrarán TODOS los procesos seleccionados y sus ajustes en este escenario.",
                        icon: 'warning',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, Vaciar Todo',
                        cancelButtonText: 'Cancelar',
                        confirmButtonColor: '#dc2626',
                        customClass: {
                            popup: 'premium-swal',
                            confirmButton: 'premium-confirm-danger',
                            cancelButton: 'premium-cancel'
                        }
                    });

                    if (result.isConfirmed) {
                        try {
                            const scenarioIdSelection = document.getElementById('active-scenario-id-input') ? document.getElementById('active-scenario-id-input').value : '';
                            const response = await fetch('/api/clear_all_planning/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': '{{ csrf_token }}'
                                },
                                body: JSON.stringify({ scenario_id: scenarioIdSelection })
                            });
                            
                             if (response.ok) {
                                window.location.reload();
                            } else {
                                Swal.fire({
                                    title: 'Error',
                                    text: 'Hubo un problema al vaciar la planificación.',
                                    icon: 'error',
                                    confirmButtonText: 'Cerrar',
                                    customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                                });
                            }
                        } catch (e) { console.error(e); }
                    }
                });
            }

            // --- SCENARIO MANAGEMENT (NUEVO, GUARDAR, CARGAR) ---
            
            // 1. NUEVO: Start a blank scenario
            const btnNewScenario = document.getElementById('btnNewScenario');
            if (btnNewScenario) {
                btnNewScenario.addEventListener('click', async function() {
                    const result = await Swal.fire({
                        title: '¿Empezar Plan Nuevo?',
                        text: 'Se iniciará un escenario de planificación vacío. Los planes existentes guardados no se modificarán.',
                        icon: 'question',
                        showCancelButton: true,
                        confirmButtonText: 'Sí, empezar nuevo',
                        cancelButtonText: 'Cancelar',
                        customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                    });
                    
                    if (result.isConfirmed) {
                        try {
                            const response = await fetch('/api/scenarios/create/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': '{{ csrf_token }}'
                                },
                                body: JSON.stringify({
                                    nombre: 'Nuevo Plan',
                                    proyectos: ''
                                })
                            });
                            
                            const data = await response.json();
                            if (response.ok) {
                                // Redirect to the new scenario with NO projects in query params
                                window.location.href = `?scenario_id=${data.scenario.id}`;
                            } else {
                                Swal.fire({
                                    title: 'Error',
                                    text: data.error || 'No se pudo crear el escenario nuevo.',
                                    icon: 'error',
                                    customClass: { popup: 'premium-swal' }
                                });
                            }
                        } catch (e) {
                            console.error(e);
                            Swal.fire({
                                title: 'Error',
                                text: 'No se pudo comunicar con el servidor.',
                                icon: 'error',
                                customClass: { popup: 'premium-swal' }
                            });
                        }
                    }
                });
            }

            // 2. GUARDAR: Show save modal & confirm rename/clone
            const saveScenarioModalEl = document.getElementById('saveScenarioModal');
            let saveScenarioModal;
            if (saveScenarioModalEl) {
                saveScenarioModal = new bootstrap.Modal(saveScenarioModalEl);
                
                const btnSaveScenario = document.getElementById('btnSaveScenario');
                if (btnSaveScenario) {
                    btnSaveScenario.addEventListener('click', () => {
                        saveScenarioModal.show();
                    });
                }

                const btnConfirmSave = document.getElementById('btnConfirmSave');
                if (btnConfirmSave) {
                    btnConfirmSave.addEventListener('click', async function() {
                        const nameInput = document.getElementById('newScenarioName');
                        const name = nameInput ? nameInput.value.trim() : '';
                        if (!name) { 
                            return Swal.fire({
                                title: 'Campo Requerido',
                                text: 'Por favor, ingrese un nombre para el escenario.',
                                icon: 'warning',
                                confirmButtonText: 'Aceptar',
                                customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                            });
                        }

                        const activeScenarioId = '{{ active_scenario_id|default:"" }}';
                        const activeScenarioName = '{{ active_scenario.nombre|escapejs }}';
                        const proyectosInput = document.getElementById('proyectos');
                        const proyectosList = proyectosInput ? proyectosInput.value.trim() : '';

                        let secuencias = [];
                        document.querySelectorAll('.tab-content table tbody').forEach(tbody => {
                            // Identificar a qué máquina pertenece esta tabla
                            let defaultRowForMachine = tbody.querySelector('tr[data-maquina]');
                            let currentTabMachineId = defaultRowForMachine ? defaultRowForMachine.getAttribute('data-maquina') : null;

                            let rows = tbody.querySelectorAll('tr:not(.hidden-row)');
                            rows.forEach((row, index) => {
                                let idOrden = row.getAttribute('data-id');
                                // Si la fila se movió a otra tab, toma la ID de la máquina de esa tab
                                let maquina = currentTabMachineId || row.getAttribute('data-maquina');
                                
                                let nivelCell = row.querySelector('.editable-nivel');
                                // Leer el texto real editado por el usuario de forma limpia
                                // .textContent en contenteditable puede traer \n, \r y espacios — los eliminamos todos
                                let rawTexto = nivelCell ? nivelCell.textContent : '0';
                                let textoNivel = rawTexto.replace(/\s+/g, '').replace(/[^\d-]/g, '');
                                let prioridadManual = textoNivel !== '' ? parseInt(textoNivel, 10) : null;
                                
                                console.log(`[GUARDAR] OP ${idOrden} | rawTexto='${rawTexto}' | textoNivel='${textoNivel}' | prioridadManual=${prioridadManual}`);
                                
                                if (idOrden) {
                                    let seq = {
                                        id_orden: idOrden,
                                        maquina: maquina,
                                        orden_secuencia: index
                                    };
                                    // Solo incluir nivel si es un número válido (incluso 0 es válido si el usuario lo puso)
                                    if (prioridadManual !== null && !isNaN(prioridadManual)) {
                                        seq.nivel_planificacion = prioridadManual;
                                        seq.prioridad_manual = prioridadManual;
                                    }
                                    secuencias.push(seq);
                                }
                            });
                        });

                        let payload = {
                            nombre: name,
                            proyectos: proyectosList,
                            secuencias: secuencias
                        };

                        // Word/Excel style flow:
                        // If current name is "Nuevo Plan" or they input the exact same name, update in place.
                        // Otherwise, clone it to a new scenario.
                        if (activeScenarioName === 'Nuevo Plan' || name === activeScenarioName) {
                            payload.id = activeScenarioId;
                            payload.update_id = activeScenarioId;
                        } else {
                            payload.copy_from_id = activeScenarioId;
                        }

                        try {
                            const btn = this;
                            btn.disabled = true;
                            const originalHTML = btn.innerHTML;
                            btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span> Guardando...';

                            const response = await fetch('/api/scenarios/create/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': '{{ csrf_token }}'
                                },
                                body: JSON.stringify(payload)
                            });

                            const data = await response.json();
                            if (response.ok) {
                                saveScenarioModal.hide();
                                Swal.fire({
                                    title: '¡Guardado!',
                                    text: 'El escenario ha sido guardado exitosamente.',
                                    icon: 'success',
                                    timer: 1500,
                                    showConfirmButton: false
                                }).then(() => {
                                    window.location.href = `?scenario_id=${data.scenario.id}&proyectos=${encodeURIComponent(proyectosList)}&plan_mode=manual`;
                                });
                            } else {
                                btn.disabled = false;
                                btn.innerHTML = originalHTML;
                                Swal.fire({
                                    title: 'Error',
                                    text: data.error || "Error al guardar escenario.",
                                    icon: 'error',
                                    customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                                });
                            }
                        } catch (e) {
                            console.error(e);
                            this.disabled = false;
                            this.innerHTML = '<i class="fas fa-check me-2"></i>Confirmar Guardado';
                            Swal.fire({
                                title: 'Error de Red',
                                text: 'No se pudo comunicar con el servidor.',
                                icon: 'error',
                                confirmButtonText: 'Cerrar',
                                customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                            });
                        }
                    });
                }
            }

            // 3. CARGAR: Show load modal & load plan
            const loadScenarioModalEl = document.getElementById('loadScenarioModal');
            let loadScenarioModal;
            if (loadScenarioModalEl) {
                loadScenarioModal = new bootstrap.Modal(loadScenarioModalEl);
                
                const btnLoadScenario = document.getElementById('btnLoadScenario');
                if (btnLoadScenario) {
                    btnLoadScenario.addEventListener('click', () => {
                        loadScenarioModal.show();
                    });
                }

                const btnConfirmLoad = document.getElementById('btnConfirmLoad');
                if (btnConfirmLoad) {
                    btnConfirmLoad.addEventListener('click', function() {
                        const select = document.getElementById('loadScenarioSelect');
                        const selectedId = select ? select.value : '';
                        if (!selectedId) {
                            return Swal.fire({
                                title: 'Selección Requerida',
                                text: 'Por favor, seleccione un plan para cargar.',
                                icon: 'warning',
                                confirmButtonText: 'Aceptar',
                                customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                            });
                        }
                        
                        const selectedOption = select.options[select.selectedIndex];
                        const projects = selectedOption.dataset.proyectos || '';
                        
                        loadScenarioModal.hide();
                        window.location.href = `?scenario_id=${selectedId}&proyectos=${encodeURIComponent(projects)}`;
                    });
                }
            }

            // 4. BORRAR: Open delete modal and load saved scenarios dynamically
            const deleteProjectModalEl = document.getElementById('deleteProjectModal');
            let deleteProjectModal;
            if (deleteProjectModalEl) {
                deleteProjectModal = new bootstrap.Modal(deleteProjectModalEl);
                deleteProjectModalEl.addEventListener('hidden.bs.modal', function() {
                    // Update the select dropdown when closing the modal to ensure sync
                    fetchAndSyncSelect();
                });
            }

            const btnDeleteScenario = document.getElementById('btnDeleteScenario');
            if (btnDeleteScenario && deleteProjectModal) {
                btnDeleteScenario.addEventListener('click', function() {
                    deleteProjectModal.show();
                    loadScenariosList();
                });
            }

            async function fetchAndSyncSelect() {
                try {
                    const response = await fetch('/api/scenarios/list/');
                    if (response.ok) {
                        const data = await response.json();
                        updateLoadScenarioSelect(data.scenarios || []);
                    }
                } catch (e) {
                    console.error('Error syncing scenarios select:', e);
                }
            }

            async function loadScenariosList() {
                const container = document.getElementById('deleteProjectListContainer');
                if (!container) return;

                // Show spinner
                container.innerHTML = `
                    <div class="text-center py-4 text-muted bg-white">
                        <span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span> Cargando escenarios...
                    </div>
                `;

                try {
                    const response = await fetch('/api/scenarios/list/');
                    if (!response.ok) throw new Error('Error al obtener escenarios');
                    
                    const data = await response.json();
                    const scenarios = data.scenarios || [];

                    // Synchronize the load dropdown list
                    updateLoadScenarioSelect(scenarios);

                    if (scenarios.length === 0) {
                        container.innerHTML = `
                            <div class="text-center py-4 text-muted bg-white">
                                <i class="fas fa-info-circle me-1"></i> No hay escenarios guardados.
                            </div>
                        `;
                        return;
                    }

                    container.innerHTML = '';
                    scenarios.forEach(sc => {
                        const item = document.createElement('div');
                        item.className = 'list-group-item d-flex justify-content-between align-items-center bg-white border-0 border-bottom px-3 py-2.5 transition-all';
                        item.style.borderRadius = '8px';
                        item.style.marginBottom = '4px';

                        // Scenario info (Name)
                        const infoDiv = document.createElement('div');
                        infoDiv.className = 'd-flex align-items-center';
                        
                        let iconHTML = `<i class="fas fa-folder fa-md"></i>`;
                        let badgeHTML = '';
                        if (sc.es_principal) {
                            iconHTML = `<i class="fas fa-star fa-md"></i>`;
                            badgeHTML = `<span class="badge bg-secondary ms-2 text-uppercase" style="font-size: 0.65rem;">Oficial</span>`;
                        }
                        
                        infoDiv.innerHTML = `
                            <div class="bg-primary bg-opacity-10 text-primary rounded-3 p-2 me-3 d-flex align-items-center justify-content-center" style="width: 38px; height: 38px;">
                                ${iconHTML}
                            </div>
                            <div>
                                <span class="fw-bold text-dark fs-6">${sc.nombre}</span>
                                ${badgeHTML}
                            </div>
                        `;
                        item.appendChild(infoDiv);

                        // Action button (Delete)
                        if (!sc.es_principal) {
                            const deleteBtn = document.createElement('button');
                            deleteBtn.className = 'btn btn-sm btn-outline-danger rounded-pill px-3 py-1.5 fw-bold d-inline-flex align-items-center gap-1.5 shadow-sm transition-all';
                            deleteBtn.style.borderColor = '#fee2e2';
                            deleteBtn.style.backgroundColor = '#fef2f2';
                            deleteBtn.style.color = '#dc2626';
                            
                            deleteBtn.onmouseover = function() {
                                this.style.backgroundColor = '#fee2e2';
                                this.style.borderColor = '#fca5a5';
                                this.style.color = '#b91c1c';
                            };
                            deleteBtn.onmouseout = function() {
                                this.style.backgroundColor = '#fef2f2';
                                this.style.borderColor = '#fee2e2';
                                this.style.color = '#dc2626';
                            };

                            deleteBtn.title = `Eliminar escenario ${sc.nombre}`;
                            deleteBtn.innerHTML = '<i class="fas fa-trash-alt"></i> Eliminar';
                            
                            deleteBtn.addEventListener('click', async function() {
                                await confirmAndDeleteScenario(sc.id, sc.nombre);
                            });
                            item.appendChild(deleteBtn);
                        } else {
                            // Locked or principal indicator
                            const lockDiv = document.createElement('div');
                            lockDiv.className = 'text-muted small px-3 py-1.5';
                            lockDiv.innerHTML = '<i class="fas fa-lock me-1"></i> No borrable';
                            item.appendChild(lockDiv);
                        }

                        container.appendChild(item);
                    });

                } catch (error) {
                    console.error(error);
                    container.innerHTML = `
                        <div class="text-center py-4 text-danger bg-white">
                            <i class="fas fa-exclamation-triangle me-1"></i> Error al cargar escenarios.
                        </div>
                    `;
                }
            }

            async function confirmAndDeleteScenario(id, name) {
                const result = await Swal.fire({
                    title: '¿Confirmar eliminación?',
                    text: `¿Seguro que deseas eliminar por completo el escenario guardado [${name}]?`,
                    icon: 'warning',
                    showCancelButton: true,
                    confirmButtonText: 'Sí, Eliminar',
                    cancelButtonText: 'Cancelar',
                    confirmButtonColor: '#dc2626',
                    customClass: {
                        popup: 'premium-swal',
                        confirmButton: 'premium-confirm-danger',
                        cancelButton: 'premium-cancel'
                    }
                });

                if (result.isConfirmed) {
                    try {
                        const response = await fetch(`/api/scenarios/${id}/delete/`, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': '{{ csrf_token }}'
                            }
                        });

                        const data = await response.json();
                        if (response.ok && data.status === 'ok') {
                            Swal.fire({
                                title: '¡Eliminado!',
                                text: `El escenario "${name}" ha sido eliminado exitosamente.`,
                                icon: 'success',
                                timer: 1500,
                                showConfirmButton: false
                            });

                            // Reload list in modal (which also updates the select dropdown)
                            await loadScenariosList();

                            // Check if the deleted scenario is currently loaded/active
                            const activeScenarioIdInput = document.getElementById('active-scenario-id-input');
                            const activeScenarioId = activeScenarioIdInput ? activeScenarioIdInput.value : '';
                            if (activeScenarioId && String(activeScenarioId) === String(id)) {
                                // If the active scenario was deleted, reload the main page without the scenario_id param
                                const params = new URLSearchParams(window.location.search);
                                params.delete('scenario_id');
                                window.location.href = window.location.pathname + '?' + params.toString();
                            }
                        } else {
                            Swal.fire({
                                title: 'Error',
                                text: data.error || 'Ocurrió un error al intentar eliminar el escenario.',
                                icon: 'error',
                                confirmButtonText: 'Cerrar',
                                customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                            });
                        }
                    } catch (e) {
                        console.error(e);
                        Swal.fire({
                            title: 'Error de Conexión',
                            text: 'No se pudo comunicar con el servidor para eliminar el escenario.',
                            icon: 'error',
                            confirmButtonText: 'Cerrar',
                            customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                        });
                    }
                }
            }

            function updateLoadScenarioSelect(scenarios) {
                const selectEl = document.getElementById('loadScenarioSelect');
                if (!selectEl) return;
                
                const currentVal = selectEl.value;
                
                selectEl.innerHTML = '<option value="">-- Seleccionar un Plan --</option>';
                
                scenarios.forEach(sc => {
                    const opt = document.createElement('option');
                    opt.value = sc.id;
                    opt.dataset.proyectos = sc.proyectos || '';
                    opt.textContent = sc.nombre;
                    selectEl.appendChild(opt);
                });
                
                if (currentVal && [...selectEl.options].some(o => o.value === currentVal)) {
                    selectEl.value = currentVal;
                }
            }

            function clearUIPlanning() {
                // 1. Clear projects input
                const proyectosInput = document.getElementById('proyectos');
                if (proyectosInput) {
                    proyectosInput.value = '';
                }

                // 2. Reset machine tabs badges and remove .con-carga class
                const tabButtons = document.querySelectorAll('#myTab button.nav-link');
                tabButtons.forEach(btn => {
                    btn.classList.remove('con-carga');
                    const badge = btn.querySelector('.badge');
                    if (badge) {
                        badge.textContent = '0';
                    }
                });

                // 3. Clear table bodies and put them in empty state
                const tableBodies = document.querySelectorAll('#myTabContent table tbody');
                tableBodies.forEach(tbody => {
                    tbody.innerHTML = '<tr><td colspan="16" class="text-center">No hay datos para esta máquina.</td></tr>';
                });

                // 4. Update browser URL to remove proyectos parameter cleanly
                const params = new URLSearchParams(window.location.search);
                params.delete('proyectos');
                const newUrl = window.location.pathname + '?' + params.toString();
                window.history.pushState({ path: newUrl }, '', newUrl);
            }

            // --- Audit Mode Toggle Logic ---
            const btnToggleAudit = document.getElementById('btnToggleAudit');
            if (btnToggleAudit) {
                btnToggleAudit.addEventListener('click', function() {
                    const params = new URLSearchParams(window.location.search);
                    const currentAudit = params.get('audit_mode') === '1';
                    if (currentAudit) {
                        params.delete('audit_mode');
                    } else {
                        params.set('audit_mode', '1');
                    }
                    window.location.href = window.location.pathname + '?' + params.toString();
                });
            }

            // --- Reactivate (Unhide) Task Logic ---
            document.querySelectorAll('.btn-reactivate').forEach(btn => {
                btn.addEventListener('click', async function() {
                    const row = this.closest('tr');
                    const idOrden = row.dataset.id;
                    const scenarioId = new URLSearchParams(window.location.search).get('scenario_id');

                    console.log("Attempting reactivation for ID:", idOrden, "Scenario:", scenarioId);

                    // Instant Visual Feedback
                    row.style.opacity = '0.3';
                    this.disabled = true;

                    try {
                        const response = await fetch("{% url 'reactivar_op' %}", {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                                'X-CSRFToken': '{{ csrf_token }}'
                            },
                            body: JSON.stringify({
                                id_orden: idOrden,
                                scenario_id: scenarioId
                            })
                        });

                        const responseData = await response.json();
                        console.log("Server Response:", responseData);

                        if (response.ok) {
                            // Success: Update UI without Refresh
                            row.classList.remove('hidden-row');
                            row.style.opacity = '1';
                            this.disabled = false;
                            
                            Swal.fire({
                                title: '¡Recuperado!',
                                text: 'La tarea vuelve a estar activa.',
                                icon: 'success',
                                timer: 1000,
                                showConfirmButton: false,
                                customClass: { popup: 'premium-swal' }
                            });
                        } else {
                            console.error("Reactivation Error Status:", response.status, responseData);
                            Swal.fire({
                                title: 'Error',
                                text: `No se pudo recuperar: ${responseData.error || "Error desconocido"} (Status: ${response.status})`,
                                icon: 'error',
                                customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                            });
                            row.style.opacity = '0.5';
                            this.disabled = false;
                        }
                    } catch (e) {
                        console.error("Fetch Exception:", e);
                        Swal.fire({
                            title: 'Error de Red',
                            text: "No se pudo comunicar con el servidor. Revise la consola (F12) para más detalles.",
                            icon: 'error',
                            customClass: { popup: 'premium-swal', confirmButton: 'premium-confirm' }
                        });
                        row.style.opacity = '0.5';
                        this.disabled = false;
                    }
                });
            });
        });
        // Theme Persistence
        function initTheme() {
            const savedTheme = localStorage.getItem('theme') || 'light';
            document.documentElement.setAttribute('data-theme', savedTheme);
            updateThemeIcon(savedTheme);
            
            const btn = document.getElementById('btn-theme-toggle');
            if (btn) {
                btn.addEventListener('click', function() {
                    const currentTheme = document.documentElement.getAttribute('data-theme');
                    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
                    document.documentElement.setAttribute('data-theme', newTheme);
                    localStorage.setItem('theme', newTheme);
                    updateThemeIcon(newTheme);
                });
            }
        }
        
        function updateThemeIcon(theme) {
            const btn = document.getElementById('btn-theme-toggle');
            if (!btn) return;
            const icon = btn.querySelector('i');
            if (theme === 'dark') {
                icon.className = 'fas fa-sun text-warning';
                btn.classList.add('btn-dark');
                btn.classList.remove('btn-outline-secondary');
            } else {
                icon.className = 'fas fa-moon';
                btn.classList.remove('btn-dark');
                btn.classList.add('btn-outline-secondary');
            }
        }

        initTheme();

        // Hard Reset for Projects Input (Strict Requirement)
        document.addEventListener('DOMContentLoaded', function() {
            const projInput = document.getElementById('proyectos');
            if (projInput) {
                projInput.value = '';
                // Ensure autocomplete doesn't re-fill it
                projInput.setAttribute('autocomplete', 'off');
            }
        });
    
