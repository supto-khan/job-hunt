const state = {
    jobs: [],
    stats: {},
    sources: [],
    filters: { source: '', status: '', min_score: 0, search: '', location: '', tech: '', bd_friendly: '' },
    offset: 0,
    limit: 50,
    collecting: false,
};

// ── API ──
async function api(path, opts = {}) {
    const resp = await fetch(`/api${path}`, opts);
    return resp.json();
}

async function loadJobs() {
    const f = state.filters;
    const params = new URLSearchParams();
    if (f.source) params.set('source', f.source);
    if (f.status) params.set('status', f.status);
    if (f.min_score) params.set('min_score', f.min_score);
    if (f.search) params.set('search', f.search);
    if (f.location) params.set('location', f.location);
    if (f.tech) params.set('tech', f.tech);
    if (f.bd_friendly) params.set('bd_friendly', f.bd_friendly);
    params.set('limit', state.limit);
    params.set('offset', state.offset);

    document.getElementById('job-list').innerHTML = `
        <div class="loading"><div class="spinner"></div> Loading jobs...</div>`;

    const data = await api(`/jobs?${params}`);
    state.jobs = data.jobs;
    renderJobs();
}

async function loadStats() {
    state.stats = await api('/stats');
    renderStats();
}

async function loadSources() {
    const data = await api('/sources');
    state.sources = data.sources;
    renderSourceFilter();
}

async function collectJobs() {
    if (state.collecting) return;
    state.collecting = true;
    const btn = document.getElementById('btn-collect');
    btn.disabled = true;
    btn.textContent = 'Collecting...';

    const estimateSec = await estimateCollectionTime();
    const startMs = Date.now();
    showCollectLoader(estimateSec);
    const tick = setInterval(() => updateCollectLoader(startMs, estimateSec), 500);

    try {
        const stats = await api('/job-sync', { method: 'POST' });
        const newCount = stats.new ?? 0;
        const outCount = stats.outreach_generated ?? 0;
        showToast(`Collection complete — ${newCount} new jobs, ${outCount} outreach items ready to email`);
        await Promise.all([loadJobs(), loadStats(), loadSources(), loadJSearchStatus()]);
    } catch (e) {
        showToast('Collection failed: ' + e.message);
    } finally {
        clearInterval(tick);
        hideCollectLoader();
        state.collecting = false;
        btn.disabled = false;
        btn.textContent = 'Collect Jobs';
    }
}

async function estimateCollectionTime() {
    return 180; // 3 minutes estimate
}

function showCollectLoader(estimateSec) {
    document.getElementById('collect-estimate').textContent = formatSeconds(estimateSec);
    document.getElementById('collect-elapsed').textContent = '0s';
    document.getElementById('collect-loader').hidden = false;
}

function hideCollectLoader() {
    document.getElementById('collect-loader').hidden = true;
}

function updateCollectLoader(startMs, estimateSec) {
    const elapsed = Math.floor((Date.now() - startMs) / 1000);
    const el = document.getElementById('collect-elapsed');
    el.textContent = formatSeconds(elapsed);
    // When we overshoot the estimate, soften the message
    if (elapsed > estimateSec) {
        document.getElementById('collect-estimate').textContent = `${formatSeconds(estimateSec)} (almost there…)`;
    }
}

function formatSeconds(total) {
    total = Math.max(0, Math.round(total));
    if (total < 60) return `${total}s`;
    const m = Math.floor(total / 60);
    const s = total % 60;
    return s ? `${m}m ${s}s` : `${m}m`;
}

async function updateStatus(jobId, status) {
    await api(`/jobs/${jobId}/status?status=${status}`, { method: 'PATCH' });
    showToast(`Status updated to ${status}`);
    await loadJobs();
}

// ── Bangladesh badge helper ──
function bdBadge(value, note) {
    const labels = {
        yes: 'BD OK',
        maybe: 'Maybe BD',
        no: 'Not BD',
        unknown: 'Unknown',
    };
    const label = labels[value] || labels.unknown;
    const cls = `bd-${value || 'unknown'}`;
    const tooltip = note ? ` title="${escapeHtml(note)}"` : '';
    return `<span class="${cls}"${tooltip}>${label}</span>`;
}

// ── Render ──
let chartSourcesInstance = null;
let chartTechInstance = null;
let chartOutreachInstance = null;

function renderStats() {
    const s = state.stats;
    const byStatus = s.by_status || {};

    // Status display config with colors/labels
    const statusMap = [
        { key: 'new', label: 'New Jobs', color: 'var(--accent-green, #34c9ac)' },
        { key: 'applied', label: 'Applied', color: '#60a5fa' },
        { key: 'archive', label: 'Archived', color: '#6b7280' },
    ];

    let statusCardsHtml = statusMap
        .filter(st => (byStatus[st.key] || 0) > 0)
        .map(st => `
        <div class="stat-card">
            <div class="label" style="display:flex;align-items:center;gap:6px;">
                <span style="width:8px;height:8px;border-radius:50%;background-color:${st.color};display:inline-block;"></span>
                ${st.label}
            </div>
            <div class="value">${byStatus[st.key]}</div>
        </div>
    `).join('');

    // Also handle any dynamic custom status not in statusMap (only if count > 0)
    Object.keys(byStatus).forEach(key => {
        if (!statusMap.some(st => st.key === key) && byStatus[key] > 0) {
            const formattedLabel = key.charAt(0).toUpperCase() + key.slice(1);
            statusCardsHtml += `
                <div class="stat-card">
                    <div class="label">${formattedLabel}</div>
                    <div class="value">${byStatus[key]}</div>
                </div>
            `;
        }
    });

    document.getElementById('stats-bar').innerHTML = `
        <div class="stat-card">
            <div class="label">Total Jobs</div>
            <div class="value">${s.total || 0}</div>
        </div>
        <div class="stat-card">
            <div class="label">Avg Score</div>
            <div class="value">${s.avg_score || 0}</div>
        </div>
        ${statusCardsHtml}
    `;

    renderAnalyticsCharts(s);
}

function renderAnalyticsCharts(s) {
    if (typeof Chart === 'undefined') return;

    // 1. Sources Chart
    const sourcesCanvas = document.getElementById('chart-sources');
    if (sourcesCanvas && s.by_source) {
        const labels = Object.keys(s.by_source);
        const data = Object.values(s.by_source);
        if (chartSourcesInstance) chartSourcesInstance.destroy();
        chartSourcesInstance = new Chart(sourcesCanvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Jobs',
                    data,
                    backgroundColor: '#1a7a4e',
                    borderColor: '#34c9ac',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#9eaba4', font: { family: 'Lexend' } }, grid: { display: false } },
                    y: { ticks: { color: '#9eaba4', font: { family: 'Lexend' } }, grid: { color: '#28352f' } }
                }
            }
        });
    }

    // 2. Tech Stack Chart
    const techCanvas = document.getElementById('chart-tech');
    if (techCanvas && s.top_tech) {
        const labels = Object.keys(s.top_tech);
        const data = Object.values(s.top_tech);
        if (chartTechInstance) chartTechInstance.destroy();
        chartTechInstance = new Chart(techCanvas, {
            type: 'bar',
            data: {
                labels,
                datasets: [{
                    label: 'Frequency',
                    data,
                    backgroundColor: '#34c9ac',
                    borderColor: '#0e9f84',
                    borderWidth: 1,
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { ticks: { color: '#9eaba4', font: { family: 'Lexend' } }, grid: { color: '#28352f' } },
                    y: { ticks: { color: '#9eaba4', font: { family: 'Lexend' } }, grid: { display: false } }
                }
            }
        });
    }

    // 3. Outreach Pipeline Chart
    const outreachCanvas = document.getElementById('chart-outreach');
    if (outreachCanvas) {
        const oStats = s.outreach_status || {};
        const keys = Object.keys(oStats);
        const hasData = keys.length > 0 && Object.values(oStats).some(val => val > 0);

        if (chartOutreachInstance) chartOutreachInstance.destroy();

        if (!hasData) {
            // Draw empty state message on canvas
            const ctx = outreachCanvas.getContext('2d');
            ctx.clearRect(0, 0, outreachCanvas.width, outreachCanvas.height);
            ctx.font = '12px Lexend, sans-serif';
            ctx.fillStyle = '#9eaba4';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText('No outreach items generated yet', outreachCanvas.width / 2 || 120, outreachCanvas.height / 2 || 80);
        } else {
            const labels = keys.map(k => k.charAt(0).toUpperCase() + k.slice(1));
            const data = Object.values(oStats);
            const palette = ['#34c9ac', '#f0a500', '#1a7a4e', '#60a5fa', '#7dc4a4', '#ef4444'];
            const backgroundColor = labels.map((_, idx) => palette[idx % palette.length]);

            chartOutreachInstance = new Chart(outreachCanvas, {
                type: 'doughnut',
                data: {
                    labels,
                    datasets: [{
                        data,
                        backgroundColor,
                        borderWidth: 0
                    }]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: { position: 'right', labels: { color: '#9eaba4', font: { family: 'Lexend', size: 11 } } }
                    }
                }
            });
        }
    }
}

function renderSourceFilter() {
    const sel = document.getElementById('filter-source');
    sel.innerHTML = '<option value="">All Sources</option>';
    state.sources.forEach(s => {
        sel.innerHTML += `<option value="${s}">${s}</option>`;
    });
}

function scoreClass(score) {
    if (score >= 60) return 'score-high';
    if (score >= 35) return 'score-mid';
    return 'score-low';
}

function statusClass(status) {
    return `status-${status || 'new'}`;
}

function stripHtml(html) {
    const tmp = document.createElement('div');
    tmp.innerHTML = html;
    return tmp.textContent || tmp.innerText || '';
}

function truncate(str, len = 120) {
    const clean = stripHtml(str);
    return clean.length > len ? clean.substring(0, len) + '...' : clean;
}

function renderJobs() {
    const list = document.getElementById('job-list');

    if (!state.jobs.length) {
        list.innerHTML = `
            <div class="empty-state">
                <h3>No jobs found</h3>
                <p>Click "Collect Jobs" to fetch from all sources, or adjust your filters.</p>
            </div>`;
        return;
    }

    list.innerHTML = state.jobs.map(job => `
        <div class="job-card">
            <input type="checkbox" class="mark-email" title="Mark for email"
                   ${job.mark_for_email ? 'checked' : ''}
                   onclick="event.stopPropagation(); toggleMark('${job.id}')"
                   style="margin-right:8px;transform:scale(1.2);cursor:pointer;">
            <div class="score-badge ${scoreClass(job.relevance_score)}" onclick="openModal('${job.id}')" style="cursor:pointer;">
                ${job.relevance_score}
            </div>
            <div class="job-info" onclick="openModal('${job.id}')" style="cursor:pointer;">
                <h3>${escapeHtml(job.title)}</h3>
                <div class="job-meta">
                    <span>${escapeHtml(job.company)}</span>
                    <span>${escapeHtml(job.location)}</span>
                    <span>${escapeHtml(job.source)}</span>
                    ${job.salary ? `<span>${escapeHtml(job.salary)}</span>` : ''}
                    ${job.posted_date ? `<span>${formatDate(job.posted_date)}</span>` : ''}
                    ${bdBadge(job.india_friendly, job.location_note)}
                    ${job.last_seen ? `<span style="font-size:11px;color:var(--text-muted);">Last seen: ${formatDate(job.last_seen)}</span>` : ''}
                </div>
                <div class="job-tags">
                    ${(job.tech_stack || '').split(',').filter(t => t.trim()).slice(0, 6).map(t =>
                        `<span class="tag">${escapeHtml(t.trim())}</span>`
                    ).join('')}
                </div>
            </div>
            <div class="job-actions">
                <span class="status-badge ${statusClass(job.status)}">${job.status}</span>
                ${job.mark_for_email ? '<span style="color:var(--yellow);font-size:11px;">📧 Marked</span>' : ''}
            </div>
        </div>
    `).join('');
}

function openModal(jobId) {
    const job = state.jobs.find(j => j.id === jobId);
    if (!job) return;

    document.getElementById('modal-content').innerHTML = `
        <h2>${escapeHtml(job.title)}</h2>
        <div class="modal-company">${escapeHtml(job.company)} &mdash; ${escapeHtml(job.location)}</div>
        <div class="modal-details">
            <span class="score-badge ${scoreClass(job.relevance_score)}" style="width:40px;height:40px;font-size:14px;">
                ${job.relevance_score}
            </span>
            <span class="status-badge ${statusClass(job.status)}">${job.status}</span>
            ${bdBadge(job.india_friendly, job.location_note)}
            <span class="tag">${escapeHtml(job.source)}</span>
            ${job.salary ? `<span class="tag">${escapeHtml(job.salary)}</span>` : ''}
            ${job.experience_level ? `<span class="tag">${escapeHtml(job.experience_level)}</span>` : ''}
        </div>
        ${job.location_note ? `<div class="location-note">Location: ${escapeHtml(job.location_note)}</div>` : ''}
        <div class="job-tags" style="margin-bottom:12px;">
            ${(job.tech_stack || '').split(',').filter(t => t.trim()).map(t =>
                `<span class="tag">${escapeHtml(t.trim())}</span>`
            ).join('')}
        </div>
        <div class="modal-desc">${job.description || '<em>No description available</em>'}</div>
        <div class="modal-actions">
            <button class="btn btn-outline" onclick="updateStatus('${job.id}', 'reviewed')">Mark Reviewed</button>
            <button class="btn btn-green" onclick="updateStatus('${job.id}', 'applied')">Mark Applied</button>
            <button class="btn btn-yellow" onclick="updateStatus('${job.id}', 'stale')">Mark Stale</button>
            ${job.url ? `<a href="${escapeHtml(job.url)}" target="_blank" class="btn btn-primary">Apply</a>` : ''}
            <button class="btn btn-outline" onclick="closeModal()">Close</button>
        </div>
    `;
    document.getElementById('modal-overlay').classList.add('active');
}

function closeModal() {
    document.getElementById('modal-overlay').classList.remove('active');
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatDate(dateStr) {
    try {
        const d = new Date(dateStr);
        if (isNaN(d.getTime())) return dateStr;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
        return dateStr;
    }
}

function showActivityModal(title, message, icon = 'ℹ️') {
    const overlay = document.getElementById('activity-modal-overlay');
    if (!overlay) {
        showToast(message);
        return;
    }
    document.getElementById('activity-modal-icon').textContent = icon;
    document.getElementById('activity-modal-title').textContent = title;
    document.getElementById('activity-modal-body').textContent = message;
    overlay.classList.add('active');
}

function closeActivityModal() {
    const overlay = document.getElementById('activity-modal-overlay');
    if (overlay) overlay.classList.remove('active');
}

function showToast(msg, title = 'System Activity') {
    let icon = '✅';
    if (msg.toLowerCase().includes('fail') || msg.toLowerCase().includes('error')) icon = '⚠️';
    else if (msg.toLowerCase().includes('complete') || msg.toLowerCase().includes('success')) icon = '🎉';
    showActivityModal(title, msg, icon);
}

// ── Filter handlers ──
function applyFilters() {
    state.filters.source = document.getElementById('filter-source').value;
    state.filters.status = document.getElementById('filter-status').value;
    state.filters.min_score = parseInt(document.getElementById('filter-score').value) || 0;
    state.filters.search = document.getElementById('filter-search').value;
    state.filters.location = document.getElementById('filter-location').value;
    state.filters.tech = document.getElementById('filter-tech').value;
    state.filters.bd_friendly = document.getElementById('filter-bd').value;
    state.offset = 0;
    loadJobs();
}

function resetFilters() {
    document.getElementById('filter-source').value = '';
    document.getElementById('filter-status').value = '';
    document.getElementById('filter-score').value = '0';
    document.getElementById('filter-search').value = '';
    document.getElementById('filter-location').value = '';
    document.getElementById('filter-tech').value = '';
    document.getElementById('filter-bd').value = '';
    state.filters = { source: '', status: '', min_score: 0, search: '', location: '', tech: '', bd_friendly: '' };
    state.offset = 0;
    loadJobs();
}

function nextPage() {
    state.offset += state.limit;
    loadJobs();
}

function prevPage() {
    state.offset = Math.max(0, state.offset - state.limit);
    loadJobs();
}

// ── Google Sheets Export ──
async function loadJSearchStatus() {
    try {
        const s = await api('/jsearch/status');
        const el = document.getElementById('jsearch-status');
        if (!el) return;
        if (!s.configured) {
            el.textContent = 'JSearch: not configured';
            el.style.color = 'var(--red)';
            return;
        }
        const pct = Math.round((s.month / s.monthly_limit) * 100);
        let color = 'var(--text-muted)';
        if (pct >= 80) color = 'var(--red)';
        else if (pct >= 50) color = 'var(--yellow)';
        else color = 'var(--green)';
        el.innerHTML = `<span title="Today: ${s.today} calls">JSearch: <span style="color:${color};font-weight:600;">${s.month}/${s.monthly_limit}</span> this month (${s.remaining} left)</span>`;
    } catch (e) {}
}

async function checkSheetsStatus() {
    try {
        const data = await api('/export/sheets/status');
        const btn = document.getElementById('btn-export');
        if (!data.configured) {
            btn.title = 'Google Sheets not configured — add GOOGLE_SHEET_ID + credentials.json';
            btn.style.opacity = '0.6';
        }
    } catch (e) {}
}

function openExportModal() {
    document.getElementById('export-overlay').classList.add('active');
}

function closeExportModal() {
    document.getElementById('export-overlay').classList.remove('active');
}

async function doExport() {
    const btn = document.getElementById('btn-do-export');
    btn.disabled = true;
    btn.textContent = 'Exporting...';

    const params = new URLSearchParams();
    params.set('sheet_name', document.getElementById('export-sheet-name').value);
    params.set('min_score', document.getElementById('export-score').value);
    params.set('mode', document.getElementById('export-mode').value);
    const bd = document.getElementById('export-bd').value;
    if (bd) params.set('bd_friendly', bd);

    try {
        const data = await api(`/export/sheets?${params}`, { method: 'POST' });
        if (data.error) {
            showToast('Export failed: ' + data.error);
        } else {
            showToast(`Exported ${data.exported} jobs to Google Sheets!`);
            closeExportModal();
        }
    } catch (e) {
        showToast('Export failed: ' + e.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Export Now';
    }
}

// ── Search Queries Manager ──
async function openQueriesModal() {
    document.getElementById('queries-overlay').classList.add('active');
    await loadQueries();
}

function closeQueriesModal() {
    document.getElementById('queries-overlay').classList.remove('active');
}

async function loadQueries() {
    const data = await api('/search-queries');
    const list = document.getElementById('queries-list');
    if (!data.queries.length) {
        list.innerHTML = '<div style="color:var(--text-muted);padding:12px;">No queries yet. Add one below.</div>';
        return;
    }
    list.innerHTML = `
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
                <tr style="border-bottom:1px solid var(--border);color:var(--text-muted);font-size:11px;text-transform:uppercase;">
                    <th style="text-align:left;padding:8px 4px;">On</th>
                    <th style="text-align:left;padding:8px 4px;">Query</th>
                    <th style="text-align:left;padding:8px 4px;">Country</th>
                    <th style="text-align:left;padding:8px 4px;">Posted</th>
                    <th style="text-align:left;padding:8px 4px;">Remote</th>
                    <th></th>
                </tr>
            </thead>
            <tbody>
                ${data.queries.map(q => `
                    <tr style="border-bottom:1px solid var(--border);">
                        <td style="padding:8px 4px;">
                            <input type="checkbox" ${q.enabled ? 'checked' : ''}
                                onchange="toggleQueryEnabled(${q.id}, this.checked)">
                        </td>
                        <td style="padding:8px 4px;"><input type="text" value="${escapeHtml(q.query)}"
                            onchange="updateQueryField(${q.id}, 'query', this.value)"
                            style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:4px 8px;border-radius:4px;width:100%;font-size:13px;"></td>
                        <td style="padding:8px 4px;">
                            <select onchange="updateQueryField(${q.id}, 'country', this.value)"
                                style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:4px 6px;border-radius:4px;font-size:13px;">
                                ${['BD','US','GB','CA','DE','SG'].map(c => `<option value="${c}" ${c===q.country?'selected':''}>${c}</option>`).join('')}
                            </select>
                        </td>
                        <td style="padding:8px 4px;">
                            <select onchange="updateQueryField(${q.id}, 'date_posted', this.value)"
                                style="background:var(--surface2);border:1px solid var(--border);color:var(--text);padding:4px 6px;border-radius:4px;font-size:13px;">
                                ${['today','3days','week','month','all'].map(d => `<option value="${d}" ${d===q.date_posted?'selected':''}>${d}</option>`).join('')}
                            </select>
                        </td>
                        <td style="padding:8px 4px;">
                            <input type="checkbox" ${q.remote_jobs_only ? 'checked' : ''}
                                onchange="updateQueryField(${q.id}, 'remote_jobs_only', this.checked)">
                        </td>
                        <td style="padding:8px 4px;">
                            <button class="btn btn-outline btn-sm" onclick="deleteQuery(${q.id})">×</button>
                        </td>
                    </tr>
                `).join('')}
            </tbody>
        </table>
    `;
}

async function addQuery() {
    const query = document.getElementById('new-query').value.trim();
    if (!query) { showToast('Query cannot be empty'); return; }
    const body = {
        query,
        country: document.getElementById('new-country').value,
        date_posted: document.getElementById('new-date').value,
        remote_jobs_only: document.getElementById('new-remote').checked,
    };
    await api('/search-queries', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
    });
    document.getElementById('new-query').value = '';
    document.getElementById('new-remote').checked = false;
    showToast('Query added');
    await loadQueries();
}

async function updateQueryField(qid, field, value) {
    const body = {};
    body[field] = value;
    await api(`/search-queries/${qid}`, {
        method: 'PATCH',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(body),
    });
}

async function toggleQueryEnabled(qid, enabled) {
    await updateQueryField(qid, 'enabled', enabled);
    showToast(enabled ? 'Query enabled' : 'Query disabled');
}

function confirmModal(title, message) {
    return new Promise((resolve) => {
        const overlay = document.getElementById('activity-modal-overlay');
        if (!overlay) {
            resolve(window.confirm(message));
            return;
        }
        document.getElementById('activity-modal-title').textContent = title;
        document.getElementById('activity-modal-body').textContent = message;

        const btnOk = document.getElementById('confirm-btn-ok');
        const btnCancel = document.getElementById('confirm-btn-cancel');

        const cleanup = (res) => {
            overlay.classList.remove('active');
            btnOk.onclick = null;
            btnCancel.onclick = null;
            resolve(res);
        };

        btnOk.onclick = () => cleanup(true);
        btnCancel.onclick = () => cleanup(false);
        overlay.classList.add('active');
    });
}

async function deleteQuery(qid) {
    const confirmed = await confirmModal('Delete Query', 'Delete this search query?');
    if (!confirmed) return;
    await api(`/search-queries/${qid}`, {method: 'DELETE'});
    showToast('Query deleted');
    await loadQueries();
}

// ── Mark for Email ──
async function toggleMark(jobId) {
    const data = await api(`/jobs/${jobId}/mark-for-email`, { method: 'POST' });
    showToast(data.mark_for_email ? '📧 Marked for email' : 'Unmarked');
    // Update local state to reflect
    const job = state.jobs.find(j => j.id === jobId);
    if (job) {
        job.mark_for_email = data.mark_for_email ? 1 : 0;
        renderJobs();
    }
}

// ── Keyboard ──
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeModal(); closeExportModal(); closeQueriesModal(); }
});

// ── Init ──
async function loadActiveProfileIndicator() {
    const el = document.getElementById('active-profile-indicator');
    if (!el) return;
    try {
        const a = await api('/profiles/active');
        el.textContent = `Profile: ${a.name || '(none)'}`;
    } catch (e) {
        el.textContent = 'Profile: (none)';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    loadStats();
    loadSources();
    loadJobs();
    checkSheetsStatus();
    loadJSearchStatus();
    loadActiveProfileIndicator();

    // Debounced search
    let searchTimeout;
    document.getElementById('filter-search').addEventListener('input', () => {
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(applyFilters, 400);
    });
});
