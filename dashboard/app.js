function initApp() {
    // DOM Elements
    const sectorsGrid = document.getElementById('sectors-grid');
    const loadingOverlay = document.getElementById('loading-overlay');
    const errorBanner = document.getElementById('error-banner');
    const errorMessage = document.getElementById('error-message');
    const totalSignalsCount = document.getElementById('total-signals-count');
    const lastUpdatedTime = document.getElementById('last-updated-time');
    
    // Modal Elements
    const detailsModal = document.getElementById('details-modal');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const modalSectorName = document.getElementById('modal-sector-name');
    const modalSectorCategory = document.getElementById('modal-sector-category');
    const modalHealthScore = document.getElementById('modal-health-score');
    const modalSectorStatus = document.getElementById('modal-sector-status');
    const modalSectorConfidence = document.getElementById('modal-sector-confidence');
    const modalSectorSummary = document.getElementById('modal-sector-summary');
    const modalSignalsList = document.getElementById('modal-signals-list');

    // Setup Wizard Elements
    const wizardOverlay = document.getElementById('wizard-overlay');
    const wizardStep1 = document.getElementById('wizard-step-1');
    const wizardStep2 = document.getElementById('wizard-step-2');
    const wizardStepProgress = document.getElementById('wizard-step-progress');
    const wizardError = document.getElementById('wizard-error');
    const wizardErrorMsg = document.getElementById('wizard-error-msg');
    
    // Wizard Inputs & Buttons
    const inputUrl = document.getElementById('moneycontrol-url');
    const dateRangeSelect = document.getElementById('date-range-select');
    const customDateContainer = document.getElementById('custom-date-container');
    const inputDate = document.getElementById('cutoff-date');
    const inputKey = document.getElementById('gemini-key');
    const btnVerifyLink = document.getElementById('btn-verify-link');
    const btnBackStep1 = document.getElementById('btn-back-step-1');
    const btnRunPipeline = document.getElementById('btn-run-pipeline');
    const btnResetPipeline = document.getElementById('btn-reset-pipeline');
    
    // Progress UI
    const progressTitle = document.getElementById('progress-title');
    const progressSubtitle = document.getElementById('progress-subtitle');
    const progressBarFill = document.getElementById('progress-bar-fill');

    let dashboardData = null;

    // Strict HTML Sanitizer for XSS prevention
    function escapeHTML(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // Sanitize URLs to prevent javascript: or data: XSS vectors in target hrefs
    function sanitizeUrl(urlStr) {
        if (!urlStr) return '#';
        const trimmed = urlStr.trim();
        if (trimmed.startsWith('https://') || trimmed.startsWith('http://')) {
            return trimmed;
        }
        return '#';
    }

    // Set custom date bounds to prevent invalid dates selection
    const todayStr = new Date().toISOString().split('T')[0];
    inputDate.setAttribute('max', todayStr);
    inputDate.setAttribute('min', '2000-01-01');
    inputDate.value = todayStr; // default to today

    // Toggle custom date visibility
    function toggleCustomDate() {
        if (dateRangeSelect.value === 'custom') {
            customDateContainer.classList.remove('hidden');
        } else {
            customDateContainer.classList.add('hidden');
        }
    }
    dateRangeSelect.addEventListener('change', toggleCustomDate);
    toggleCustomDate(); // Sync initially on page load

    // Helper: Compute cutoff date string based on select option
    function calculateCutoffDate(selectValue) {
        const today = new Date();
        if (selectValue === 'last-month') {
            today.setDate(today.getDate() - 30);
        } else if (selectValue === 'last-6-months') {
            today.setDate(today.getDate() - 180);
        } else if (selectValue === 'last-year') {
            today.setDate(today.getDate() - 365);
        } else if (selectValue === 'all-time') {
            return '2000-01-01'; // Year 2000 as "All Time" boundary
        } else if (selectValue === 'custom') {
            return inputDate.value; // Returns YYYY-MM-DD
        }
        return today.toISOString().split('T')[0];
    }

    // Load inputs/state from sessionStorage or localStorage on startup
    let cachedUrl = '';
    const cachedStateStr = localStorage.getItem('apex_state');
    if (cachedStateStr) {
        try {
            const parsedState = JSON.parse(cachedStateStr);
            cachedUrl = parsedState.url || '';
        } catch (e) {}
    }
    if (sessionStorage.getItem('moneycontrol_url')) {
        inputUrl.value = sessionStorage.getItem('moneycontrol_url');
    } else if (cachedUrl) {
        inputUrl.value = cachedUrl;
    }
    if (sessionStorage.getItem('gemini_api_key')) {
        inputKey.value = sessionStorage.getItem('gemini_api_key');
    }

    // Helper to query and load existing state from the backend server DB
    async function loadStateFromServer() {
        showLoading(true);
        hideError();
        try {
            const [sigRes, evRes, clRes, artRes, regRes] = await Promise.all([
                fetch('/api/signals'),
                fetch('/api/events'),
                fetch('/api/clusters'),
                fetch('/api/articles'),
                fetch('/api/event-types')
            ]);
            
            if (sigRes.ok && evRes.ok && clRes.ok && artRes.ok && regRes.ok) {
                const signals = await sigRes.json();
                const events = await evRes.json();
                const clusters = await clRes.json();
                const articles = await artRes.json();
                const registry = await regRes.json();
                
                if (signals && signals.length > 0) {
                    const stateData = {
                        url: 'https://www.moneycontrol.com/company-article/tataconsultancyservices/news/TCS',
                        cutoff_date: '2000-01-01', // Default historical boundary for DB recovery
                        articles: articles,
                        events: events,
                        signals: signals,
                        registry: registry
                    };
                    localStorage.setItem('apex_state', JSON.stringify(stateData));
                    localStorage.removeItem('apex_evaluations'); // Force re-evaluation with key
                    
                    // Pre-populate input URL if it was empty
                    if (!inputUrl.value) {
                        inputUrl.value = stateData.url;
                    }
                    return true;
                }
            }
        } catch (err) {
            console.warn('Failed to load pre-existing state from DB server:', err);
        } finally {
            showLoading(false);
        }
        return false;
    }

    // Check if fully evaluated dashboard exists
    if (localStorage.getItem('apex_evaluations')) {
        wizardOverlay.classList.add('hidden');
        fetchDashboardData();
    } else {
        // Always show setup wizard Step 1 on startup/fresh load
        wizardOverlay.classList.remove('hidden');
        wizardStep1.classList.remove('hidden');
        wizardStep2.classList.add('hidden');
        
        if (!localStorage.getItem('apex_state')) {
            loadStateFromServer();
        }
    }

    // Helper: Format Date
    function formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        try {
            const date = new Date(dateStr.replace(' IST', '').trim());
            if (isNaN(date.getTime())) return dateStr;
            return date.toLocaleDateString('en-US', {
                year: 'numeric',
                month: 'short',
                day: 'numeric',
                hour: '2-digit',
                minute: '2-digit'
            });
        } catch (e) {
            return dateStr;
        }
    }

    // Helper: Map status to CSS classes
    function getStatusClass(status) {
        const lower = (status || '').toLowerCase();
        if (lower.includes('health')) return 'healthy';
        if (lower.includes('stable')) return 'stable';
        if (lower.includes('warn')) return 'warning';
        if (lower.includes('crit')) return 'critical';
        return 'stable';
    }

    // Fetch Dashboard Data (stateless browser-cached model)
    async function fetchDashboardData() {
        // 1. Load cached evaluations if available to skip slow APIs and allow direct rendering
        const cachedEvalStr = localStorage.getItem('apex_evaluations');
        if (cachedEvalStr) {
            dashboardData = JSON.parse(cachedEvalStr);
            renderDashboard(dashboardData);
            return;
        }

        // 2. Check if we have the state to perform evaluations
        const cachedStateStr = localStorage.getItem('apex_state');
        if (!cachedStateStr) {
            wizardOverlay.classList.remove('hidden');
            return;
        }
        const state = JSON.parse(cachedStateStr);

        // 3. We need the API key to perform sector evaluations
        const apiKey = sessionStorage.getItem('gemini_api_key');
        if (!apiKey) {
            // Show setup wizard at Step 1 (the beginning)
            wizardOverlay.classList.remove('hidden');
            wizardStep1.classList.remove('hidden');
            wizardStep2.classList.add('hidden');
            return;
        }

        showLoading(true);
        hideError();
        
        try {
            const response = await fetch('/api/evaluate-sectors', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    signals: state.signals,
                    registry: state.registry,
                    gemini_api_key: apiKey
                })
            });
            
            if (!response.ok) {
                throw new Error(`Server returned HTTP ${response.status}: ${response.statusText}`);
            }
            const evalResult = await response.json();
            
            if (evalResult.error) {
                throw new Error(evalResult.error);
            }

            dashboardData = {
                last_updated: new Date().toISOString(),
                signals_count: state.signals.length,
                sectors: evalResult.evaluations
            };

            // Cache evaluations locally
            localStorage.setItem('apex_evaluations', JSON.stringify(dashboardData));
            renderDashboard(dashboardData);
        } catch (err) {
            console.error('Error fetching dashboard data:', err);
            showError(`Failed to evaluate sector safety: ${err.message}`);
        } finally {
            showLoading(false);
        }
    }

    // Show/Hide Loading
    function showLoading(show) {
        if (show) {
            loadingOverlay.classList.remove('hidden');
            sectorsGrid.classList.add('hidden');
        } else {
            loadingOverlay.classList.add('hidden');
            sectorsGrid.classList.remove('hidden');
        }
    }

    // Show/Hide Error
    function showError(msg) {
        errorMessage.textContent = msg;
        errorBanner.classList.remove('hidden');
    }

    function hideError() {
        errorBanner.classList.add('hidden');
    }

    // Render Dashboard Grid & Stats (XSS Protected)
    function renderDashboard(data) {
        totalSignalsCount.textContent = data.signals_count !== undefined ? escapeHTML(data.signals_count) : '0';
        lastUpdatedTime.textContent = data.last_updated ? escapeHTML(formatDate(data.last_updated)) : 'N/A';

        sectorsGrid.innerHTML = '';
        const sectors = data.sectors || {};
        const sectorKeys = Object.keys(sectors);

        if (sectorKeys.length === 0) {
            sectorsGrid.innerHTML = '<div class="loading-overlay"><h3>No data available. Process some news articles first!</h3></div>';
            return;
        }

        let renderedCount = 0;
        sectorKeys.forEach(key => {
            const sector = sectors[key];
            const signalsCount = sector.signals ? sector.signals.length : 0;

            // Skip rendering clusters with no signals
            if (signalsCount === 0) {
                return;
            }
            renderedCount++;

            const statusClass = getStatusClass(sector.status);

            const card = document.createElement('div');
            card.className = `sector-card status-${statusClass}`;
            card.innerHTML = `
                <div class="card-header">
                    <div class="card-title-group">
                        <span class="card-category">${escapeHTML(sector.category || 'General')}</span>
                        <h3>${escapeHTML(sector.name)}</h3>
                    </div>
                    <div class="score-circle-wrapper">
                        <div class="score-circle">${escapeHTML(sector.health_score)}</div>
                    </div>
                </div>
                <div class="card-body">
                    <p>${escapeHTML(sector.summary || sector.description || 'No description available.')}</p>
                </div>
                <div class="card-footer">
                    <span class="card-signals-pill">${escapeHTML(signalsCount)} signal${signalsCount === 1 ? '' : 's'}</span>
                    <span class="card-status-label">${escapeHTML(sector.status)}</span>
                </div>
            `;

            card.addEventListener('click', () => openModal(sector));
            sectorsGrid.appendChild(card);
        });

        if (renderedCount === 0) {
            sectorsGrid.innerHTML = '<div class="loading-overlay"><h3>No active signals detected in any sector.</h3></div>';
        }
    }

    // Open Modal with Detailed Signals (XSS Protected)
    function openModal(sector) {
        modalSectorName.textContent = sector.name;
        modalSectorCategory.textContent = sector.category || 'General';
        modalHealthScore.textContent = sector.health_score;
        modalSectorConfidence.textContent = Math.round((sector.confidence || 0) * 100) + '%';
        modalSectorSummary.textContent = sector.summary || 'No detailed evaluation summary available.';
        
        modalSectorStatus.textContent = sector.status;
        modalSectorStatus.className = 'status-badge';
        const statusClass = getStatusClass(sector.status);
        modalSectorStatus.classList.add(`badge-${statusClass}`);

        modalSignalsList.innerHTML = '';
        const signals = sector.signals || [];

        if (signals.length === 0) {
            modalSignalsList.innerHTML = '<p class="text-muted" style="padding: 1rem 0; text-align: center;">No contributing signals recorded for this sector.</p>';
        } else {
            signals.forEach(sig => {
                const strengthVal = parseFloat(sig.decayed_strength || sig.strength || 0);
                let scoreClass = 'score-neutral';
                let strengthPrefix = '';
                
                if (strengthVal > 0) {
                    scoreClass = 'score-positive';
                    strengthPrefix = '+';
                } else if (strengthVal < 0) {
                    scoreClass = 'score-negative';
                }

                const row = document.createElement('div');
                row.className = 'signal-row';
                row.innerHTML = `
                    <div class="signal-info">
                        <span class="signal-type-tag">${escapeHTML(sig.type || 'Signal')}</span>
                        <p class="signal-desc">${escapeHTML(sig.summary || 'No details provided.')}</p>
                        <div class="signal-trace">
                            <span>Date: ${escapeHTML(formatDate(sig.date))}</span> &bull; 
                            <span>Article: <a href="${escapeHTML(sanitizeUrl(sig.article_url))}" target="_blank" class="signal-link">${escapeHTML(sig.article_title || 'View Source')}</a></span>
                        </div>
                    </div>
                    <div class="signal-score ${scoreClass}">
                        ${strengthPrefix}${strengthVal.toFixed(2)}
                    </div>
                `;
                modalSignalsList.appendChild(row);
            });
        }

        detailsModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() {
        detailsModal.classList.add('hidden');
        document.body.style.overflow = '';
    }

    closeModalBtn.addEventListener('click', closeModal);
    
    detailsModal.addEventListener('click', (e) => {
        if (e.target === detailsModal) {
            closeModal();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && !detailsModal.classList.contains('hidden')) {
            closeModal();
        }
    });

    // WIZARD EVENT HANDLERS

    function showWizardError(msg) {
        wizardErrorMsg.textContent = msg;
        wizardError.classList.remove('hidden');
    }

    function hideWizardError() {
        wizardError.classList.add('hidden');
    }

    // Step 1: Link Verification
    btnVerifyLink.addEventListener('click', async () => {
        hideWizardError();
        const url = inputUrl.value.trim();
        
        if (!url) {
            showWizardError("Please enter a Moneycontrol link.");
            return;
        }

        if (!url.startsWith("https://www.moneycontrol.com/")) {
            showWizardError("Link must start with https://www.moneycontrol.com/");
            return;
        }

        // Show loading state on button
        btnVerifyLink.disabled = true;
        btnVerifyLink.textContent = "Verifying link...";

        try {
            const res = await fetch('/api/verify-link', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ url })
            });
            const data = await res.json();
            
            if (!res.ok || !data.success) {
                throw new Error(data.error || "Failed to verify URL connection.");
            }

            sessionStorage.setItem('moneycontrol_url', url);
            wizardStep1.classList.add('hidden');
            wizardStep2.classList.remove('hidden');
        } catch (err) {
            showWizardError(err.message);
        } finally {
            btnVerifyLink.disabled = false;
            btnVerifyLink.textContent = "Verify Link";
        }
    });

    // Step 2 Back Button
    btnBackStep1.addEventListener('click', () => {
        hideWizardError();
        wizardStep2.classList.add('hidden');
        wizardStep1.classList.remove('hidden');
    });

    // Step 2 Run Pipeline Button
    btnRunPipeline.addEventListener('click', async () => {
        hideWizardError();
        const geminiKey = inputKey.value.trim();

        if (!geminiKey) {
            showWizardError("Please enter your Gemini API Key.");
            return;
        }

        // Validate API Key format (matching relaxed backend regex)
        const keyValid = /^[a-zA-Z0-9_\-\.\+\/=]+$/.test(geminiKey) && geminiKey.length >= 10 && geminiKey.length <= 150;
        if (!keyValid) {
            showWizardError("Invalid API key format. Key contains invalid characters.");
            return;
        }

        const url = sessionStorage.getItem('moneycontrol_url');
        const rangeVal = dateRangeSelect.value;
        const cutoffDate = calculateCutoffDate(rangeVal);

        if (!url) {
            showWizardError("Link is not verified. Please go back.");
            return;
        }

        if (rangeVal === 'custom' && !cutoffDate) {
            showWizardError("Please select a cutoff date.");
            return;
        }

        // Prevent future dates input validation
        if (new Date(cutoffDate) > new Date()) {
            showWizardError("Analysis cutoff date cannot be in the future.");
            return;
        }

        // Save dynamic credentials
        sessionStorage.setItem('gemini_api_key', geminiKey);

        // Check if we can reuse the cached state (url and cutoff_date match exactly)
        let canReuseState = false;
        const cachedStateStr = localStorage.getItem('apex_state');
        if (cachedStateStr) {
            try {
                const cachedState = JSON.parse(cachedStateStr);
                const normalizeUrl = (u) => (u || '').trim().replace(/\/$/, '').toLowerCase();
                if (normalizeUrl(cachedState.url) === normalizeUrl(url) && cachedState.cutoff_date === cutoffDate && cachedState.signals && cachedState.signals.length > 0) {
                    canReuseState = true;
                }
            } catch (e) {
                console.warn("Failed to check cached state:", e);
            }
        }

        if (canReuseState) {
            wizardOverlay.classList.add('hidden');
            await fetchDashboardData();
            return;
        }

        // Verify key against Google (server-side check)
        btnRunPipeline.disabled = true;
        const originalText = btnRunPipeline.textContent;
        btnRunPipeline.textContent = "Verifying API key...";

        try {
            const keyCheckRes = await fetch('/api/verify-key', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ gemini_api_key: geminiKey })
            });
            const keyCheckData = await keyCheckRes.json();
            
            if (!keyCheckRes.ok || !keyCheckData.success) {
                throw new Error(keyCheckData.error || "Gemini API Key verification failed.");
            }
        } catch (err) {
            showWizardError(err.message);
            return;
        } finally {
            btnRunPipeline.disabled = false;
            btnRunPipeline.textContent = originalText;
        }

        // Show Progress Step
        wizardStep2.classList.add('hidden');
        wizardStepProgress.classList.remove('hidden');
        
        // Progress updates
        const progressSteps = [
            { pct: 15, title: "Crawling Moneycontrol...", desc: "Locating article feeds up to cutoff date..." },
            { pct: 35, title: "Streaming raw texts...", desc: "Fetching full article texts from URLs..." },
            { pct: 60, title: "Evaluating corporate events...", desc: "Consolidating batch prompt analysis in Gemini..." },
            { pct: 80, title: "Resolving event taxonomy...", desc: "Registering new events and calculating weights..." },
            { pct: 95, title: "Generating signal metrics...", desc: "Applying exponential time-decay scores..." }
        ];

        let stepIdx = 0;
        const progressInterval = setInterval(() => {
            if (stepIdx < progressSteps.length) {
                const step = progressSteps[stepIdx];
                progressTitle.textContent = step.title;
                progressSubtitle.textContent = step.desc;
                progressBarFill.style.width = `${step.pct}%`;
                stepIdx++;
            }
        }, 2500);

        try {
            const res = await fetch('/api/run-pipeline', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    url: url,
                    cutoff_date: cutoffDate,
                    gemini_api_key: geminiKey
                })
            });
            
            const data = await res.json();
            clearInterval(progressInterval);

            if (!res.ok || !data.success) {
                throw new Error(data.error || "Pipeline execution failed.");
            }

            // Save dynamic credentials
            sessionStorage.setItem('gemini_api_key', geminiKey);
            
            // Save state returned by stateless backend to local storage, including analyzed url & cutoff_date
            const stateData = {
                url: url,
                cutoff_date: cutoffDate,
                articles: data.articles,
                events: data.events,
                signals: data.signals,
                registry: data.registry
            };
            localStorage.setItem('apex_state', JSON.stringify(stateData));
            localStorage.removeItem('apex_evaluations'); // Clear stale score cache

            progressTitle.textContent = "Pipeline complete!";
            progressSubtitle.textContent = "Loading health evaluations...";
            progressBarFill.style.width = "100%";

            setTimeout(() => {
                wizardOverlay.classList.add('hidden');
                fetchDashboardData();
            }, 1000);

        } catch (err) {
            clearInterval(progressInterval);
            wizardStepProgress.classList.add('hidden');
            wizardStep2.classList.remove('hidden');
            showWizardError(`Pipeline failed: ${err.message}`);
        }
    });

    // Reset pipeline button action
    btnResetPipeline.addEventListener('click', async () => {
        if (confirm("Resetting will clear all current dashboard data. Proceed?")) {
            showLoading(true);
            try {
                const res = await fetch('/api/reset', { method: 'POST' });
                if (!res.ok) {
                    const data = await res.json();
                    throw new Error(data.error || "Failed to reset server database.");
                }
            } catch (err) {
                console.error("Server reset error:", err);
                alert("Warning: Could not clear server-side database. " + err.message);
            }
            
            // Clear local caches
            localStorage.removeItem('apex_state');
            localStorage.removeItem('apex_evaluations');
            sessionStorage.removeItem('moneycontrol_url');
            sessionStorage.removeItem('gemini_api_key');
            
            window.location.reload();
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
