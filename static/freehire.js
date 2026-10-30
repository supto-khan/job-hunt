/**
 * FreeHire Direct Search & Ingestion Client
 */

const fhState = {
    jobs: [],
    total: 0,
    offset: 0,
    limit: 25,
    loading: false,
    activeProfile: null,
};

document.addEventListener('DOMContentLoaded', () => {
    loadActiveProfile();
    // Auto-search on page load with default remote tech jobs
    executeSearch(0);
});

async function loadActiveProfile() {
    try {
        const resp = await fetch('/api/profiles');
        if (!resp.ok) return;
        const data = await resp.json();
        const active = (data.profiles || []).find(p => p.is_active);
        if (active) {
            fhState.activeProfile = active;
            const ind = document.getElementById('active-profile-indicator');
            if (ind) ind.textContent = `Profile: ${active.name}`;
        }
    } catch (e) {
        console.warn('Could not load active profile:', e);
    }
}

function loadProfileKeywords() {
    if (!fhState.activeProfile) {
        alert('No active candidate profile loaded yet.');
        return;
    }
    const cfg = fhState.activeProfile.config || {};
    const search = cfg.search || {};
    const defaultTerms = search.default_terms || [];
    const coreTech = (cfg.scoring || {}).core_tech || search.relevant_tech || [];

    if (defaultTerms.length > 0) {
        document.getElementById('fh-query').value = defaultTerms[0];
    } else if (search.title_keywords_positive && search.title_keywords_positive.length > 0) {
        document.getElementById('fh-query').value = search.title_keywords_positive.slice(0, 2).join(' ');
    }

    if (coreTech.length > 0) {
        document.getElementById('fh-skills').value = coreTech.slice(0, 4).join(', ');
    }

    document.getElementById('fh-work-mode').value = 'remote';
    document.getElementById('fh-posted').value = '14';
    executeSearch(0);
}

function resetFhFilters() {
    document.getElementById('fh-query').value = '';
    document.getElementById('fh-work-mode').value = 'remote';
    document.getElementById('fh-seniority').value = 'all';
    document.getElementById('fh-region').value = 'all';
    document.getElementById('fh-category').value = 'all';
    document.getElementById('fh-posted').value = '14';
    document.getElementById('fh-skills').value = '';
    document.getElementById('fh-skills-mode').value = 'or';
    executeSearch(0);
}

function addSkillFilter(skill) {
    const input = document.getElementById('fh-skills');
    const existing = input.value.split(',').map(s => s.trim()).filter(Boolean);
    if (!existing.includes(skill)) {
        existing.push(skill);
        input.value = existing.join(', ');
        executeSearch(0);
    }
}

async function executeSearch(offset = 0) {
    if (fhState.loading) return;

    fhState.loading = true;
    fhState.offset = offset;
    fhState.limit = parseInt(document.getElementById('fh-limit').value || '25', 10);

    const btn = document.getElementById('btn-search');
    const btnText = document.getElementById('btn-search-text');
    if (btnText) btnText.textContent = 'Searching…';
    if (btn) btn.disabled = true;

    const statusText = document.getElementById('search-status-text');
    statusText.innerHTML = '<span class="text-brand-primary font-medium">⚡ Fetching live ATS jobs from FreeHire…</span>';

    const params = new URLSearchParams({
        limit: fhState.limit,
        offset: fhState.offset,
    });

    const q = document.getElementById('fh-query').value.trim();
    if (q) params.set('q', q);

    const workMode = document.getElementById('fh-work-mode').value;
    if (workMode) params.set('work_mode', workMode);

    const seniority = document.getElementById('fh-seniority').value;
    if (seniority) params.set('seniority', seniority);

    const region = document.getElementById('fh-region').value;
    if (region) params.set('regions', region);

    const category = document.getElementById('fh-category').value;
    if (category) params.set('category', category);

    const posted = document.getElementById('fh-posted').value;
    if (posted) params.set('posted_within_days', posted);

    const skills = document.getElementById('fh-skills').value.trim();
    if (skills) {
        params.set('skills', skills);
        params.set('skills_mode', document.getElementById('fh-skills-mode').value);
    }

    const hideAppliedCheckbox = document.getElementById('fh-hide-applied');
    const includeApplied = hideAppliedCheckbox ? !hideAppliedCheckbox.checked : false;
    params.set('include_applied', includeApplied);

    try {
        const resp = await fetch(`/api/freehire/search?${params.toString()}`);
        const data = await resp.json();

        if (data.error) {
            statusText.innerHTML = `<span class="text-red-400">⚠️ ${escapeHtml(data.error)}</span>`;
            document.getElementById('fh-job-list').innerHTML = `
                <div class="empty-state py-8 text-center text-red-400">
                    <p>${escapeHtml(data.error)}</p>
                </div>
            `;
            return;
        }

        fhState.jobs = (data.jobs || []).filter(j => {
            const u = (j.url || '').toLowerCase();
            const c = (j.company || '').toLowerCase();
            return !u.includes('whatjobs.com') && !u.includes('whatjobs') && !c.includes('whatjobs');
        });
        fhState.total = data.total || 0;
        fhState.hiddenApplied = data.hidden_applied || 0;
        renderJobs();
        updatePagination();
    } catch (err) {
        statusText.innerHTML = `<span class="text-red-400">⚠️ Network error: ${escapeHtml(err.message)}</span>`;
    } finally {
        fhState.loading = false;
        if (btnText) btnText.textContent = 'Search FreeHire';
        if (btn) btn.disabled = false;
    }
}

function renderJobs() {
    const list = document.getElementById('fh-job-list');
    const statusText = document.getElementById('search-status-text');

    if (!fhState.jobs.length) {
        const appliedNote = (fhState.hiddenApplied > 0)
            ? ` (${fhState.hiddenApplied} already applied jobs hidden)`
            : '';
        statusText.innerHTML = `<span>Found <strong class="text-brand-dark">0</strong> matching postings${appliedNote}</span>`;
        list.innerHTML = `
            <div class="empty-state py-12 text-center">
                <div class="text-3xl mb-2">🍃</div>
                <h3 class="text-base font-semibold text-brand-dark mb-1">No postings match these filters</h3>
                <p class="text-xs text-brand-muted">Try broadening your keyword, switching work format to "All Formats", or resetting filters.</p>
                ${fhState.hiddenApplied > 0 ? `<p class="text-xs text-brand-primary mt-2">✨ <strong>${fhState.hiddenApplied}</strong> jobs you already applied for are filtered out.</p>` : ''}
            </div>
        `;
        return;
    }

    const hiddenBadge = (fhState.hiddenApplied > 0)
        ? ` <span class="text-brand-muted font-normal bg-slate-100 px-2 py-0.5 rounded-full border border-slate-200">(${fhState.hiddenApplied} applied hidden)</span>`
        : '';

    statusText.innerHTML = `<span>Found <strong class="text-brand-primary font-semibold">${fhState.total.toLocaleString()}</strong> live postings${hiddenBadge} &middot; Showing ${fhState.offset + 1}–${Math.min(fhState.offset + fhState.jobs.length, fhState.total)}</span>`;

    list.innerHTML = fhState.jobs.map(job => {
        const modeClass = job.work_mode === 'remote' ? 'mode-remote' : (job.work_mode === 'hybrid' ? 'mode-hybrid' : 'mode-onsite');
        const modeLabel = job.work_mode ? (job.work_mode.charAt(0).toUpperCase() + job.work_mode.slice(1)) : 'Unspecified';

        const skillsHtml = (job.skills || []).slice(0, 7).map(s => `
            <span class="tag skill-chip" title="Filter by ${escapeHtml(s)}" onclick="event.stopPropagation(); addSkillFilter('${escapeHtml(s)}')">
                ${escapeHtml(s)}
            </span>
        `).join('');

        let actionButtonHtml = '';
        if (job.is_applied || job.saved_status === 'applied') {
            actionButtonHtml = `<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold">
                ✓ Already Applied
            </span>`;
        } else if (job.is_saved) {
            actionButtonHtml = `
                <div class="flex items-center gap-1.5">
                    <span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 border border-brand-primary/40 text-brand-primary text-xs font-medium">
                        ✓ In Pipeline (${job.saved_score || 0}%)
                    </span>
                    <button id="apply-btn-${job.id}" onclick="event.stopPropagation(); markJobApplied('${job.id}')" class="btn btn-outline btn-sm text-blue-600 border-blue-300 hover:bg-blue-50 transition flex items-center gap-1" title="Mark as applied">
                        <span>✓</span> Applied
                    </button>
                </div>`;
        } else {
            actionButtonHtml = `
                <div class="flex items-center gap-1.5">
                    <button id="import-btn-${job.id}" onclick="event.stopPropagation(); importJob('${job.id}')" class="btn btn-outline btn-sm text-brand-primary border-brand-primary/40 hover:bg-emerald-50 transition flex items-center gap-1">
                        <span>📥</span> Import
                    </button>
                    <button id="apply-btn-${job.id}" onclick="event.stopPropagation(); markJobApplied('${job.id}')" class="btn btn-outline btn-sm text-blue-600 border-blue-300 hover:bg-blue-50 transition flex items-center gap-1" title="Mark this job as Applied (will hide it from search)">
                        <span>✓</span> Applied
                    </button>
                </div>`;
        }

        return `
            <div id="fh-card-${job.id}" class="bg-white border border-slate-200 hover:border-brand-primary rounded-xl p-4 transition duration-150 shadow-sm hover:shadow-md flex flex-col md:flex-row justify-between gap-4 cursor-pointer" onclick="openFhModal('${job.id}')">
                <div class="flex-1 min-w-0">
                    <div class="flex flex-wrap items-center gap-2 mb-1.5">
                        <span class="font-semibold text-xs text-brand-dark">${escapeHtml(job.company)}</span>
                        <span class="ats-pill">${escapeHtml(job.source || 'ATS')}</span>
                        <span class="text-[11px] px-2 py-0.5 rounded-full font-medium ${modeClass}">${modeLabel}</span>
                        ${job.seniority ? `<span class="text-[11px] px-2 py-0.5 rounded-full bg-slate-100 text-slate-700 border border-slate-200 uppercase font-medium">${escapeHtml(job.seniority)}</span>` : ''}
                        ${job.salary ? `<span class="text-[11px] px-2 py-0.5 rounded-full bg-amber-50 text-amber-700 border border-amber-200 font-semibold">${escapeHtml(job.salary)}</span>` : ''}
                    </div>

                    <h3 class="text-base font-semibold text-brand-dark hover:text-brand-primary transition mb-1 leading-snug">
                        ${escapeHtml(job.title)}
                    </h3>

                    <div class="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-brand-muted mb-2">
                        <span class="flex items-center gap-1">
                            📍 ${escapeHtml(job.location)}
                        </span>
                        ${job.posted_at ? `<span>⏱ ${formatRelativeDate(job.posted_at)}</span>` : ''}
                    </div>

                    ${job.summary ? `
                        <p class="text-xs text-brand-dark/90 line-clamp-2 mb-3 bg-slate-50 p-2.5 rounded-lg border border-slate-200/80">
                            ${escapeHtml(job.summary)}
                        </p>
                    ` : ''}

                    <div class="flex flex-wrap gap-1.5 mt-2">
                        ${skillsHtml}
                    </div>
                </div>

                <div class="flex flex-row md:flex-col justify-end items-end gap-2 shrink-0 border-t md:border-t-0 border-slate-200 pt-3 md:pt-0">
                    <div class="flex items-center gap-2">
                        <a href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer" onclick="event.stopPropagation()" class="btn btn-outline btn-sm flex items-center gap-1">
                            Apply ↗
                        </a>
                        ${actionButtonHtml}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

async function importJob(jobId) {
    const job = fhState.jobs.find(j => j.id === jobId);
    if (!job) return;

    const btn = document.getElementById(`import-btn-${jobId}`);
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Scoring…';
    }

    try {
        const resp = await fetch('/api/freehire/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: job.title,
                company: job.company,
                location: job.location,
                description: job.description || job.summary || '',
                url: job.url,
                source: 'freehire',
                posted_at: job.posted_at,
                skills: job.skills || [],
                salary: job.salary,
                seniority: job.seniority,
                work_mode: job.work_mode,
            })
        });

        const result = await resp.json();
        if (result.ok) {
            job.is_saved = true;
            job.saved_score = result.score;
            job.saved_status = result.status;

            if (btn) {
                btn.outerHTML = `<span class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-50 border border-brand-primary text-brand-primary text-xs font-semibold animate-pulse">
                    ✓ Saved (${result.score}%)
                </span>`;
            }
        } else {
            alert('Could not import job: ' + (result.error || 'Unknown error'));
            if (btn) {
                btn.disabled = false;
                btn.textContent = '📥 Import to Hunter';
            }
        }
    } catch (e) {
        alert('Network error while importing: ' + e.message);
        if (btn) {
            btn.disabled = false;
            btn.textContent = '📥 Import to Hunter';
        }
    }
}

async function markJobApplied(jobId) {
    closeFhModal();
    const job = fhState.jobs.find(j => j.id === jobId);
    if (!job) return;

    const btn = document.getElementById(`apply-btn-${jobId}`);
    if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span>⏳</span> Saving…';
    }

    try {
        const resp = await fetch('/api/freehire/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: job.title,
                company: job.company,
                location: job.location,
                description: job.description || job.summary || '',
                url: job.url,
                source: 'freehire',
                posted_at: job.posted_at,
                skills: job.skills || [],
                salary: job.salary,
                seniority: job.seniority,
                work_mode: job.work_mode,
                status: 'applied',
            })
        });

        const result = await resp.json();
        if (result.ok) {
            job.is_saved = true;
            job.is_applied = true;
            job.saved_status = 'applied';

            const hideAppliedCheckbox = document.getElementById('fh-hide-applied');
            const shouldHide = hideAppliedCheckbox ? hideAppliedCheckbox.checked : true;

            const card = document.getElementById(`fh-card-${jobId}`);
            if (shouldHide && card) {
                card.style.transition = 'all 0.35s ease-out';
                card.style.opacity = '0';
                card.style.transform = 'translateY(-8px) scale(0.97)';
                setTimeout(() => {
                    fhState.jobs = fhState.jobs.filter(j => j.id !== jobId);
                    fhState.hiddenApplied = (fhState.hiddenApplied || 0) + 1;
                    renderJobs();
                }, 350);
            } else {
                renderJobs();
            }
        } else {
            alert('Could not mark applied: ' + (result.error || 'Unknown error'));
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span>✓</span> Applied';
            }
        }
    } catch (e) {
        alert('Network error: ' + e.message);
        if (btn) {
            btn.disabled = false;
            btn.innerHTML = '<span>✓</span> Applied';
        }
    }
}

function updatePagination() {
    const pag = document.getElementById('fh-pagination');
    const label = document.getElementById('fh-pagination-label');
    const pageInfo = document.getElementById('fh-page-info');
    const btnPrev = document.getElementById('btn-prev');
    const btnNext = document.getElementById('btn-next');

    if (fhState.total <= fhState.limit) {
        pag.hidden = true;
        if (pageInfo) pageInfo.textContent = 'Page 1 of 1';
        return;
    }

    pag.hidden = false;
    const currentPage = Math.floor(fhState.offset / fhState.limit) + 1;
    const totalPages = Math.ceil(fhState.total / fhState.limit);

    label.textContent = `Page ${currentPage} of ${totalPages.toLocaleString()}`;
    if (pageInfo) pageInfo.textContent = `Page ${currentPage} of ${totalPages.toLocaleString()}`;

    btnPrev.disabled = fhState.offset <= 0;
    btnNext.disabled = fhState.offset + fhState.limit >= fhState.total;
}

function prevFhPage() {
    if (fhState.offset > 0) {
        executeSearch(Math.max(0, fhState.offset - fhState.limit));
        window.scrollTo({ top: 180, behavior: 'smooth' });
    }
}

function nextFhPage() {
    if (fhState.offset + fhState.limit < fhState.total) {
        executeSearch(fhState.offset + fhState.limit);
        window.scrollTo({ top: 180, behavior: 'smooth' });
    }
}

function openFhModal(jobId) {
    const job = fhState.jobs.find(j => j.id === jobId);
    if (!job) return;

    const modal = document.getElementById('fh-modal-content');
    modal.innerHTML = `
        <div class="flex items-start justify-between gap-4 border-b border-slate-200 pb-4 mb-4">
            <div>
                <div class="flex items-center gap-2 mb-1 flex-wrap">
                    <span class="font-semibold text-sm text-brand-dark">${escapeHtml(job.company)}</span>
                    <span class="ats-pill">${escapeHtml(job.source || 'ATS')}</span>
                    ${job.work_mode ? `<span class="text-[11px] px-2 py-0.5 rounded-full font-medium ${job.work_mode === 'remote' ? 'mode-remote' : 'mode-hybrid'}">${escapeHtml(job.work_mode)}</span>` : ''}
                </div>
                <h2 class="text-xl font-bold text-brand-dark leading-tight">${escapeHtml(job.title)}</h2>
                <div class="text-xs text-brand-muted mt-1 flex flex-wrap gap-3">
                    <span>📍 ${escapeHtml(job.location)}</span>
                    ${job.salary ? `<span class="text-amber-700 font-semibold">💰 ${escapeHtml(job.salary)}</span>` : ''}
                    ${job.seniority ? `<span>Seniority: ${escapeHtml(job.seniority)}</span>` : ''}
                </div>
            </div>
            <button onclick="closeFhModal()" class="text-brand-muted hover:text-brand-dark text-xl px-2">&times;</button>
        </div>

        ${job.summary ? `
            <div class="mb-4 bg-emerald-50/70 border border-emerald-200 rounded-lg p-3 text-xs text-brand-dark">
                <div class="font-semibold text-brand-primary mb-1">Role Synopsis:</div>
                ${escapeHtml(job.summary)}
            </div>
        ` : ''}

        <div class="mb-4">
            <h4 class="text-xs font-semibold uppercase text-brand-muted tracking-wider mb-2">Detected Tech Stack &amp; Skills</h4>
            <div class="flex flex-wrap gap-1.5">
                ${(job.skills || []).map(s => `
                    <span class="tag skill-chip text-xs" onclick="addSkillFilter('${escapeHtml(s)}')">${escapeHtml(s)}</span>
                `).join('')}
            </div>
        </div>

        <div class="mb-6">
            <h4 class="text-xs font-semibold uppercase text-brand-muted tracking-wider mb-2">Job Description</h4>
            <div class="text-xs text-brand-dark leading-relaxed max-h-96 overflow-y-auto bg-slate-50 p-4 rounded-lg border border-slate-200 whitespace-pre-line">
                ${job.description || '<em>No detailed description provided by posting.</em>'}
            </div>
        </div>

        <div class="flex items-center justify-between pt-4 border-t border-slate-200">
            <button onclick="closeFhModal()" class="btn btn-outline">Close</button>
            <div class="flex items-center gap-2">
                ${job.is_applied || job.saved_status === 'applied'
                    ? `<span class="px-3 py-1.5 rounded-lg bg-blue-50 border border-blue-200 text-blue-700 text-xs font-semibold">✓ Already Applied</span>`
                    : `
                        <button onclick="markJobApplied('${job.id}'); setTimeout(closeFhModal, 400);" class="btn btn-outline text-xs text-blue-600 border-blue-300 hover:bg-blue-50 flex items-center gap-1">
                            <span>✓</span> Mark Applied
                        </button>
                        ${job.is_saved
                            ? `<span class="text-xs text-brand-primary font-semibold">✓ Saved (${job.saved_score}%)</span>`
                            : `<button onclick="importJob('${job.id}'); setTimeout(closeFhModal, 500);" class="btn btn-primary text-xs">
                                 📥 Import
                               </button>`
                        }
                    `
                }
                <a href="${escapeHtml(job.url)}" target="_blank" rel="noopener noreferrer" class="btn btn-green text-xs flex items-center gap-1">
                    Open Official ATS Posting ↗
                </a>
            </div>
        </div>
    `;

    document.getElementById('fh-modal-overlay').classList.add('active');
}

function closeFhModal() {
    document.getElementById('fh-modal-overlay').classList.remove('active');
}

function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatRelativeDate(dateStr) {
    if (!dateStr) return '';
    try {
        const d = new Date(dateStr);
        const now = new Date();
        const diffMs = now - d;
        const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
        if (diffDays === 0) return 'Today';
        if (diffDays === 1) return 'Yesterday';
        if (diffDays < 30) return `${diffDays}d ago`;
        return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
    } catch {
        return dateStr;
    }
}
