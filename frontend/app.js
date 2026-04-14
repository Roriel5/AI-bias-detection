/* ═══════════════════════════════════════════════════════════════════════════
   BIAS AUTOPSY — Frontend Application Logic
   Handles: file upload, API calls, charts, animations, state management
   ═══════════════════════════════════════════════════════════════════════════ */

// ── State ─────────────────────────────────────────────────────────────────
const state = {
    file: null,
    columns: [],
    preview: [],
    metrics: null,
    intersectionalMetrics: null,
    explanation: null,
    apiKey: localStorage.getItem('bias_autopsy_api_key') || '',
};

// ── DOM Refs ──────────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
    uploadArea: $('#upload-area'),
    fileInput: $('#file-input'),
    fileInfo: $('#file-info'),
    fileName: $('#file-name'),
    fileSize: $('#file-size'),
    fileRemove: $('#file-remove'),
    previewTable: $('#preview-table'),
    configSection: $('#config-section'),
    truthCol: $('#truth-col'),
    predCol: $('#pred-col'),
    sensitiveCheckboxes: $('#sensitive-checkboxes'),
    runBtn: $('#run-analysis-btn'),
    resultsSection: $('#results-section'),
    resultsDesc: $('#results-desc'),
    metricsContainer: $('#metrics-container'),
    chartsContainer: $('#charts-container'),
    intersectionalContainer: $('#intersectional-container'),
    intersectionalMetrics: $('#intersectional-metrics'),
    intersectionalCharts: $('#intersectional-charts'),
    explanationSection: $('#explanation-section'),
    severityNumber: $('#severity-number'),
    severityFill: $('#severity-fill'),
    impactText: $('#impact-text'),
    rootCauseText: $('#root-cause-text'),
    fixesList: $('#fixes-list'),
    downloadBtn: $('#download-report-btn'),
    apiToggle: $('#api-key-toggle'),
    apiModal: $('#api-modal'),
    apiModalClose: $('#api-modal-close'),
    apiKeyInput: $('#api-key-input'),
    apiKeySave: $('#api-key-save'),
    loadingOverlay: $('#loading-overlay'),
    loadingText: $('#loading-text'),
    toastContainer: $('#toast-container'),
};

// ── Chart.js Global Config ────────────────────────────────────────────────
Chart.defaults.color = '#94a3b8';
Chart.defaults.borderColor = 'rgba(148, 163, 184, 0.08)';
Chart.defaults.font.family = "'Inter', sans-serif";
Chart.defaults.plugins.legend.labels.usePointStyle = true;
Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;

const chartInstances = [];

// ── Utilities ─────────────────────────────────────────────────────────────
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    dom.toastContainer.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

function showLoading(text = 'Analyzing...') {
    dom.loadingText.textContent = text;
    dom.loadingOverlay.hidden = false;
}

function hideLoading() {
    dom.loadingOverlay.hidden = true;
}

function formatBytes(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / 1048576).toFixed(1) + ' MB';
}

function animateNumber(el, target, duration = 1000) {
    const start = performance.now();
    const initial = 0;
    function tick(now) {
        const progress = Math.min((now - start) / duration, 1);
        const eased = 1 - Math.pow(1 - progress, 3);
        const current = initial + (target - initial) * eased;
        el.textContent = current.toFixed(3);
        if (progress < 1) requestAnimationFrame(tick);
    }
    requestAnimationFrame(tick);
}

function getSelectedSensitiveCols() {
    return Array.from(dom.sensitiveCheckboxes.querySelectorAll('input:checked'))
        .map(cb => cb.value);
}

function destroyCharts() {
    chartInstances.forEach(c => c.destroy());
    chartInstances.length = 0;
}

// ── API Key Modal ─────────────────────────────────────────────────────────
dom.apiToggle.addEventListener('click', () => {
    dom.apiModal.hidden = false;
    dom.apiKeyInput.value = state.apiKey;
    dom.apiKeyInput.focus();
});

dom.apiModalClose.addEventListener('click', () => {
    dom.apiModal.hidden = true;
});

dom.apiModal.addEventListener('click', (e) => {
    if (e.target === dom.apiModal) dom.apiModal.hidden = true;
});

dom.apiKeySave.addEventListener('click', () => {
    state.apiKey = dom.apiKeyInput.value.trim();
    localStorage.setItem('bias_autopsy_api_key', state.apiKey);
    dom.apiModal.hidden = true;
    showToast(state.apiKey ? 'API key saved' : 'API key cleared', 'success');
});

// Update API key button appearance based on saved key
function updateApiKeyUI() {
    const label = dom.apiToggle.querySelector('.key-label');
    if (state.apiKey) {
        label.textContent = 'Key Set ✓';
        dom.apiToggle.style.borderColor = 'rgba(6, 214, 160, 0.3)';
    } else {
        label.textContent = 'API Key';
        dom.apiToggle.style.borderColor = '';
    }
}
updateApiKeyUI();

// ── File Upload ───────────────────────────────────────────────────────────
function handleFile(file) {
    if (!file || !file.name.endsWith('.csv')) {
        showToast('Please upload a CSV file', 'error');
        return;
    }
    if (file.size > 50 * 1024 * 1024) {
        showToast('File too large (max 50 MB)', 'error');
        return;
    }

    state.file = file;
    dom.fileName.textContent = file.name;
    dom.fileSize.textContent = formatBytes(file.size);

    // Parse CSV locally for preview and column names
    const reader = new FileReader();
    reader.onload = (e) => {
        const text = e.target.result;
        const lines = text.split('\n').filter(l => l.trim());
        const headers = lines[0].split(',').map(h => h.trim());
        state.columns = headers;

        // Build preview
        const previewRows = lines.slice(1, 6);
        state.preview = previewRows.map(row => {
            const vals = row.split(',');
            const obj = {};
            headers.forEach((h, i) => obj[h] = vals[i]?.trim() || '');
            return obj;
        });

        renderPreview();
        renderColumnConfig();

        dom.uploadArea.hidden = true;
        dom.fileInfo.hidden = false;
        revealSection(dom.configSection);

        // Scroll to config
        dom.configSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    };
    reader.readAsText(file);
}

// Drag & drop
dom.uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    dom.uploadArea.classList.add('drag-over');
});
dom.uploadArea.addEventListener('dragleave', () => {
    dom.uploadArea.classList.remove('drag-over');
});
dom.uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    dom.uploadArea.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    handleFile(file);
});
dom.uploadArea.addEventListener('click', () => dom.fileInput.click());
dom.fileInput.addEventListener('change', () => {
    if (dom.fileInput.files[0]) handleFile(dom.fileInput.files[0]);
});

// Remove file
dom.fileRemove.addEventListener('click', () => {
    state.file = null;
    state.columns = [];
    state.preview = [];
    dom.fileInput.value = '';
    dom.uploadArea.hidden = false;
    dom.fileInfo.hidden = true;
    dom.configSection.hidden = true;
    dom.resultsSection.hidden = true;
    dom.explanationSection.hidden = true;
    destroyCharts();
});

function renderPreview() {
    const headers = state.columns;
    const rows = state.preview;
    let html = '<thead><tr>';
    headers.forEach(h => html += `<th>${h}</th>`);
    html += '</tr></thead><tbody>';
    rows.forEach(row => {
        html += '<tr>';
        headers.forEach(h => html += `<td>${row[h] || ''}</td>`);
        html += '</tr>';
    });
    html += '</tbody>';
    dom.previewTable.innerHTML = html;
}

function renderColumnConfig() {
    const cols = state.columns;

    // Populate selects
    [dom.truthCol, dom.predCol].forEach(sel => {
        sel.innerHTML = cols.map(c => `<option value="${c}">${c}</option>`).join('');
    });

    // Sensitive attribute chips
    dom.sensitiveCheckboxes.innerHTML = cols.map(c => `
        <label class="checkbox-chip" data-col="${c}">
            <input type="checkbox" value="${c}">
            ${c}
        </label>
    `).join('');

    // Chip click behavior
    dom.sensitiveCheckboxes.querySelectorAll('.checkbox-chip').forEach(chip => {
        chip.addEventListener('click', (e) => {
            if (e.target.tagName === 'INPUT') {
                chip.classList.toggle('selected', e.target.checked);
            } else {
                const cb = chip.querySelector('input');
                cb.checked = !cb.checked;
                chip.classList.toggle('selected', cb.checked);
            }
            updateRunButton();
        });
    });

    updateRunButton();
}

function updateRunButton() {
    const selected = getSelectedSensitiveCols();
    dom.runBtn.disabled = selected.length === 0;
}

// ── Run Analysis ──────────────────────────────────────────────────────────
dom.runBtn.addEventListener('click', runAnalysis);

async function runAnalysis() {
    const truthCol = dom.truthCol.value;
    const predCol = dom.predCol.value;
    const sensitiveCols = getSelectedSensitiveCols();

    if (!sensitiveCols.length) {
        showToast('Select at least one sensitive attribute', 'warning');
        return;
    }
    if (truthCol === predCol) {
        showToast('Ground truth and prediction columns must be different', 'error');
        return;
    }
    if (sensitiveCols.includes(truthCol) || sensitiveCols.includes(predCol)) {
        showToast('Sensitive attributes cannot be the same as truth/prediction columns', 'error');
        return;
    }

    showLoading('Computing fairness metrics...');
    destroyCharts();

    try {
        // 1. Run main analysis
        const formData = new FormData();
        formData.append('file', state.file);
        formData.append('truth_col', truthCol);
        formData.append('pred_col', predCol);
        formData.append('sensitive_cols', sensitiveCols.join(','));

        const res = await fetch('/api/analyze', { method: 'POST', body: formData });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || 'Analysis failed');
        }
        const data = await res.json();
        state.metrics = data.metrics;

        // 2. Run intersectional analysis if 2+ attributes
        if (sensitiveCols.length >= 2) {
            showLoading('Running intersectional analysis...');
            const formData2 = new FormData();
            formData2.append('file', state.file);
            formData2.append('truth_col', truthCol);
            formData2.append('pred_col', predCol);
            formData2.append('sensitive_cols', sensitiveCols.join(','));

            const res2 = await fetch('/api/analyze-intersectional', { method: 'POST', body: formData2 });
            if (res2.ok) {
                const data2 = await res2.json();
                state.intersectionalMetrics = data2.metrics;
            }
        } else {
            state.intersectionalMetrics = null;
        }

        renderResults(data.rows);

        // 3. Get LLM explanation if API key is set
        if (state.apiKey) {
            showLoading('Generating AI explanation...');
            try {
                const explainRes = await fetch('/api/explain', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        metrics: state.metrics,
                        sensitive_cols: sensitiveCols,
                        api_key: state.apiKey
                    })
                });
                if (explainRes.ok) {
                    const explainData = await explainRes.json();
                    state.explanation = explainData.explanation;
                    renderExplanation();
                }
            } catch (e) {
                console.error('Explanation error:', e);
                showToast('Could not generate AI explanation', 'warning');
            }
        } else {
            dom.explanationSection.hidden = true;
            showToast('Add a Gemini API key to get AI explanations', 'warning');
        }

        hideLoading();
        dom.resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });

    } catch (err) {
        hideLoading();
        showToast(err.message, 'error');
        console.error(err);
    }
}

// ── Render Results ────────────────────────────────────────────────────────
function renderResults(totalRows) {
    revealSection(dom.resultsSection);
    dom.resultsDesc.textContent = `Analyzed ${totalRows.toLocaleString()} rows across ${Object.keys(state.metrics).length} sensitive attribute(s)`;

    dom.metricsContainer.innerHTML = '';
    dom.chartsContainer.innerHTML = '';

    for (const [attr, data] of Object.entries(state.metrics)) {
        renderAttributeMetrics(attr, data, dom.metricsContainer, dom.chartsContainer);
    }

    // Intersectional
    if (state.intersectionalMetrics && Object.keys(state.intersectionalMetrics).length > 0) {
        revealSection(dom.intersectionalContainer);
        dom.intersectionalMetrics.innerHTML = '';
        dom.intersectionalCharts.innerHTML = '';

        for (const [attr, data] of Object.entries(state.intersectionalMetrics)) {
            if (data.error) {
                dom.intersectionalMetrics.innerHTML += `
                    <div class="glass-card" style="padding: var(--space-lg); margin-bottom: var(--space-md);">
                        <p style="color: var(--text-tertiary);">⚠️ ${attr}: ${data.error}</p>
                    </div>`;
                continue;
            }
            renderAttributeMetrics(attr, data, dom.intersectionalMetrics, dom.intersectionalCharts, true);
        }
    } else {
        dom.intersectionalContainer.hidden = true;
    }
}

function renderAttributeMetrics(attr, data, metricsParent, chartsParent, isIntersectional = false) {
    const dp = data.demographic_parity_difference;
    const eo = data.equalized_odds_difference;
    const di = data.disparate_impact_ratio;

    // Severity
    let severity, severityClass;
    if (Math.abs(dp) > 0.15) {
        severity = 'High Bias'; severityClass = 'severity-high';
    } else if (Math.abs(dp) > 0.05) {
        severity = 'Moderate Bias'; severityClass = 'severity-moderate';
    } else {
        severity = 'Low Bias'; severityClass = 'severity-low';
    }

    // Metric color classes
    const dpClass = dp < 0.05 ? 'good' : dp < 0.15 ? 'moderate' : 'bad';
    const eoClass = eo < 0.05 ? 'good' : eo < 0.15 ? 'moderate' : 'bad';
    const diClass = di > 0.8 ? 'good' : di > 0.6 ? 'moderate' : 'bad';

    const blockId = `attr-${attr.replace(/[^a-zA-Z0-9]/g, '_')}`;
    const breakdownId = `breakdown-${blockId}`;

    // Metrics block
    const block = document.createElement('div');
    block.className = 'attr-block';
    block.innerHTML = `
        <div class="attr-header">
            <div>
                <h3 class="attr-name">⚖️ ${attr}</h3>
                ${data.warning ? `<p style="color: var(--color-warning); font-size: 0.8rem; margin-top: 4px;">⚠️ ${data.warning}</p>` : ''}
            </div>
            <span class="severity-badge ${severityClass}">${severity}</span>
        </div>

        <div class="metrics-row">
            <div class="metric-card glass-card">
                <div class="metric-value ${dpClass}" data-value="${dp}">${dp.toFixed(3)}</div>
                <div class="metric-label">Demographic Parity Diff</div>
                <div class="metric-indicator">
                    <div class="metric-indicator-fill" style="width: ${Math.min(dp * 500, 100)}%; background: ${dpClass === 'good' ? 'var(--color-success)' : dpClass === 'moderate' ? 'var(--color-warning)' : 'var(--color-danger)'}"></div>
                </div>
            </div>
            <div class="metric-card glass-card">
                <div class="metric-value ${eoClass}" data-value="${eo}">${eo.toFixed(3)}</div>
                <div class="metric-label">Equalized Odds Diff</div>
                <div class="metric-indicator">
                    <div class="metric-indicator-fill" style="width: ${Math.min(eo * 500, 100)}%; background: ${eoClass === 'good' ? 'var(--color-success)' : eoClass === 'moderate' ? 'var(--color-warning)' : 'var(--color-danger)'}"></div>
                </div>
            </div>
            <div class="metric-card glass-card">
                <div class="metric-value ${diClass}" data-value="${di}">${di.toFixed(3)}</div>
                <div class="metric-label">Disparate Impact Ratio</div>
                <div class="metric-indicator">
                    <div class="metric-indicator-fill" style="width: ${Math.min(di * 100, 100)}%; background: ${diClass === 'good' ? 'var(--color-success)' : diClass === 'moderate' ? 'var(--color-warning)' : 'var(--color-danger)'}"></div>
                </div>
            </div>
        </div>

        <button class="group-toggle" data-target="${breakdownId}">
            <span>Group-level breakdown</span>
            <span class="arrow">▼</span>
        </button>
        <div class="group-breakdown" id="${breakdownId}">
            <div class="table-wrapper" style="margin-top: var(--space-md);">
                <table class="preview-table">
                    <thead>
                        <tr>
                            <th>Group</th>
                            <th>Count</th>
                            <th>Positive Rate</th>
                            <th>TPR</th>
                            <th>FPR</th>
                            <th>Accuracy</th>
                            <th>Precision</th>
                        </tr>
                    </thead>
                    <tbody>
                        ${(data.group_breakdown || []).map(g => `
                            <tr>
                                <td><strong>${g.group}</strong></td>
                                <td>${g.n.toLocaleString()}</td>
                                <td>${g.positive_rate.toFixed(4)}</td>
                                <td>${g.true_positive_rate.toFixed(4)}</td>
                                <td>${g.false_positive_rate.toFixed(4)}</td>
                                <td>${g.accuracy.toFixed(4)}</td>
                                <td>${g.precision.toFixed(4)}</td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        </div>
    `;
    metricsParent.appendChild(block);

    // Toggle breakdown
    block.querySelector('.group-toggle').addEventListener('click', function () {
        this.classList.toggle('open');
        document.getElementById(this.dataset.target).classList.toggle('open');
    });

    // Animate metric values
    block.querySelectorAll('.metric-value').forEach(el => {
        animateNumber(el, parseFloat(el.dataset.value));
    });

    // ── Charts ────────────────────────────────────────────────────────────
    const groups = (data.group_breakdown || []).map(g => g.group);
    const rates = (data.group_breakdown || []).map(g => g.positive_rate);
    const tprs = (data.group_breakdown || []).map(g => g.true_positive_rate);
    const fprs = (data.group_breakdown || []).map(g => g.false_positive_rate);
    const accuracies = (data.group_breakdown || []).map(g => g.accuracy);

    if (groups.length > 0 && groups.length <= 30) {
        // Bar chart — positive rates
        const barCard = document.createElement('div');
        barCard.className = 'chart-card glass-card';
        barCard.innerHTML = `<h4>Selection Rate by Group — ${attr}</h4><div class="chart-wrapper"><canvas></canvas></div>`;
        chartsParent.appendChild(barCard);

        const barCtx = barCard.querySelector('canvas').getContext('2d');
        const barColors = rates.map(r => {
            const maxRate = Math.max(...rates);
            const minRate = Math.min(...rates);
            if (maxRate - minRate < 0.05) return 'rgba(6, 214, 160, 0.7)';
            return r === Math.max(...rates) ? 'rgba(124, 58, 237, 0.7)' : (r === Math.min(...rates) ? 'rgba(239, 68, 68, 0.7)' : 'rgba(56, 189, 248, 0.7)');
        });

        chartInstances.push(new Chart(barCtx, {
            type: 'bar',
            data: {
                labels: groups,
                datasets: [{
                    label: 'Positive Prediction Rate',
                    data: rates,
                    backgroundColor: barColors,
                    borderRadius: 6,
                    borderSkipped: false,
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        backgroundColor: 'rgba(15, 20, 40, 0.9)',
                        borderColor: 'rgba(124, 58, 237, 0.3)',
                        borderWidth: 1,
                        cornerRadius: 8,
                        padding: 12,
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        max: 1,
                        grid: { color: 'rgba(148, 163, 184, 0.06)' },
                        ticks: { callback: v => (v * 100).toFixed(0) + '%' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { maxRotation: 45 }
                    }
                },
                animation: { duration: 1200, easing: 'easeOutQuart' }
            }
        }));

        // Radar chart — fairness overview (only for non-intersectional with reasonable groups)
        if (!isIntersectional && groups.length <= 10) {
            const radarCard = document.createElement('div');
            radarCard.className = 'chart-card glass-card';
            radarCard.innerHTML = `<h4>Group Performance Radar — ${attr}</h4><div class="chart-wrapper"><canvas></canvas></div>`;
            chartsParent.appendChild(radarCard);

            const radarCtx = radarCard.querySelector('canvas').getContext('2d');
            const radarColors = [
                'rgba(124, 58, 237, 0.6)',
                'rgba(6, 214, 160, 0.6)',
                'rgba(239, 68, 68, 0.6)',
                'rgba(56, 189, 248, 0.6)',
                'rgba(251, 191, 36, 0.6)',
                'rgba(168, 85, 247, 0.6)',
                'rgba(34, 211, 238, 0.6)',
                'rgba(244, 114, 182, 0.6)',
                'rgba(163, 230, 53, 0.6)',
                'rgba(251, 146, 60, 0.6)',
            ];

            const radarDatasets = groups.map((g, i) => {
                const gData = data.group_breakdown[i];
                return {
                    label: g,
                    data: [gData.positive_rate, gData.true_positive_rate, gData.false_positive_rate, gData.accuracy, gData.precision],
                    backgroundColor: radarColors[i % radarColors.length].replace('0.6', '0.1'),
                    borderColor: radarColors[i % radarColors.length],
                    borderWidth: 2,
                    pointRadius: 3,
                    pointBackgroundColor: radarColors[i % radarColors.length],
                };
            });

            chartInstances.push(new Chart(radarCtx, {
                type: 'radar',
                data: {
                    labels: ['Selection Rate', 'TPR', 'FPR', 'Accuracy', 'Precision'],
                    datasets: radarDatasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: true,
                    scales: {
                        r: {
                            beginAtZero: true,
                            max: 1,
                            grid: { color: 'rgba(148, 163, 184, 0.08)' },
                            angleLines: { color: 'rgba(148, 163, 184, 0.08)' },
                            pointLabels: { font: { size: 11 } },
                            ticks: { display: false, stepSize: 0.2 }
                        }
                    },
                    plugins: {
                        legend: { position: 'bottom', labels: { padding: 16 } },
                        tooltip: {
                            backgroundColor: 'rgba(15, 20, 40, 0.9)',
                            borderColor: 'rgba(124, 58, 237, 0.3)',
                            borderWidth: 1,
                            cornerRadius: 8,
                        }
                    },
                    animation: { duration: 1400, easing: 'easeOutQuart' }
                }
            }));
        }
    }
}

// ── Render Explanation ────────────────────────────────────────────────────
function renderExplanation() {
    if (!state.explanation) return;

    revealSection(dom.explanationSection);

    const exp = state.explanation;
    const score = exp.severity_score || 0;

    // Severity ring
    dom.severityNumber.textContent = score;
    const circumference = 2 * Math.PI * 54; // r=54
    const offset = circumference - (score / 10) * circumference;
    dom.severityFill.style.strokeDashoffset = offset;

    // Color by severity
    let ringColor;
    if (score >= 7) ringColor = 'var(--color-danger)';
    else if (score >= 4) ringColor = 'var(--color-warning)';
    else ringColor = 'var(--color-success)';
    dom.severityFill.style.stroke = ringColor;
    dom.severityNumber.style.color = ringColor;

    // Impact & root cause
    dom.impactText.textContent = exp.impact || 'No impact analysis available.';
    dom.rootCauseText.textContent = exp.root_cause || 'No root cause analysis available.';

    // Fixes
    dom.fixesList.innerHTML = '';
    (exp.fixes || []).forEach((fix, i) => {
        const effort = (fix.effort || 'unknown').toLowerCase();
        const effortClass = effort === 'low' ? 'effort-low' : effort === 'medium' ? 'effort-medium' : 'effort-high';

        const card = document.createElement('div');
        card.className = 'fix-card glass-card';
        card.innerHTML = `
            <div class="fix-number">${i + 1}</div>
            <div class="fix-content">
                <div class="fix-header">
                    <span class="fix-desc">${fix.description || fix}</span>
                    <span class="effort-badge ${effortClass}">${effort}</span>
                </div>
                ${fix.impact ? `<p class="fix-impact">Expected: ${fix.impact}</p>` : ''}
            </div>
        `;
        dom.fixesList.appendChild(card);
    });

    // Scroll
    setTimeout(() => {
        dom.explanationSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }, 300);
}

// ── Download Report ───────────────────────────────────────────────────────
dom.downloadBtn.addEventListener('click', async () => {
    if (!state.metrics || !state.explanation) {
        showToast('Run analysis with an API key first to generate a report', 'warning');
        return;
    }

    showLoading('Generating PDF report...');

    try {
        const sensitiveCols = getSelectedSensitiveCols();
        const res = await fetch('/api/report', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                metrics: state.metrics,
                explanation: state.explanation,
                sensitive_cols: sensitiveCols
            })
        });

        if (!res.ok) throw new Error('Report generation failed');

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'bias_report_card.pdf';
        a.click();
        URL.revokeObjectURL(url);

        hideLoading();
        showToast('Report downloaded!', 'success');
    } catch (err) {
        hideLoading();
        showToast(err.message, 'error');
    }
});

// ── Smooth Scroll for Nav Links ───────────────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(link => {
    link.addEventListener('click', (e) => {
        e.preventDefault();
        const target = document.querySelector(link.getAttribute('href'));
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
});

// ── Intersection Observer for Fade-in ─────────────────────────────────────
const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
        if (entry.isIntersecting) {
            entry.target.style.opacity = '1';
            entry.target.style.transform = 'translateY(0)';
        }
    });
}, { threshold: 0.05, rootMargin: '0px 0px -30px 0px' });

// Only observe sections that are visible on initial load (not hidden)
document.querySelectorAll('.section:not([hidden])').forEach(section => {
    section.style.opacity = '0';
    section.style.transform = 'translateY(30px)';
    section.style.transition = 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)';
    observer.observe(section);
});

// Make hero always visible
document.querySelector('.hero').style.opacity = '1';
document.querySelector('.hero').style.transform = 'translateY(0)';

// Helper to reveal a hidden section with animation
function revealSection(sectionEl) {
    if (!sectionEl) return;
    sectionEl.style.opacity = '0';
    sectionEl.style.transform = 'translateY(30px)';
    sectionEl.style.transition = 'opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1)';
    sectionEl.hidden = false;
    // Force reflow then animate
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            sectionEl.style.opacity = '1';
            sectionEl.style.transform = 'translateY(0)';
        });
    });
}
