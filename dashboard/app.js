/* ===== Apex ISE — Multi-Stock Dashboard App ===== */
function initApp() {
    // ─── DOM Elements ───
    const wizardOverlay = document.getElementById('wizard-overlay');
    const wizardStepMain = document.getElementById('wizard-step-main');
    const wizardStepProgress = document.getElementById('wizard-step-progress');
    const wizardError = document.getElementById('wizard-error');
    const wizardErrorMsg = document.getElementById('wizard-error-msg');
    const stockSelect = document.getElementById('stock-select');
    const dateRangeSelect = document.getElementById('date-range-select');
    const customDateContainer = document.getElementById('custom-date-container');
    const inputDate = document.getElementById('cutoff-date');
    const inputKey = document.getElementById('gemini-key');
    const btnRunPipeline = document.getElementById('btn-run-pipeline');
    const btnResetPipeline = document.getElementById('btn-reset-pipeline');
    const btnCompare = document.getElementById('btn-compare');
    const comparePanel = document.getElementById('compare-panel');
    const closeComparePanel = document.getElementById('close-compare-panel');
    const stockListEl = document.getElementById('stock-list');
    const activeStockName = document.getElementById('active-stock-name');
    const totalSignalsCount = document.getElementById('total-signals-count');
    const lastUpdatedTime = document.getElementById('last-updated-time');
    const loadingOverlay = document.getElementById('loading-overlay');
    const errorBanner = document.getElementById('error-banner');
    const errorMessage = document.getElementById('error-message');
    const sectorsGrid = document.getElementById('sectors-grid');
    const detailsModal = document.getElementById('details-modal');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const modalSectorName = document.getElementById('modal-sector-name');
    const modalSectorCategory = document.getElementById('modal-sector-category');
    const modalHealthScore = document.getElementById('modal-health-score');
    const modalSectorStatus = document.getElementById('modal-sector-status');
    const modalSectorConfidence = document.getElementById('modal-sector-confidence');
    const modalSectorSummary = document.getElementById('modal-sector-summary');
    const modalSignalsList = document.getElementById('modal-signals-list');
    const progressTitle = document.getElementById('progress-title');
    const progressSubtitle = document.getElementById('progress-subtitle');
    const progressBarFill = document.getElementById('progress-bar-fill');
    const dashboardWrapper = document.getElementById('dashboard-wrapper');
    const compareStockPanel = document.getElementById('compare-stock-panel');
    const compareStockTitle = document.getElementById('compare-stock-title');
    const btnCloseCompareView = document.getElementById('btn-close-compare-view');
    const compareSectorsGrid = document.getElementById('compare-sectors-grid');
    const priceChartCanvas = document.getElementById('price-chart');
    const chartTooltip = document.getElementById('chart-tooltip');
    const comparePriceChartCanvas = document.getElementById('compare-price-chart');
    const compareChartTooltip = document.getElementById('compare-chart-tooltip');
    const btnClosePrimaryView = document.getElementById('btn-close-primary-view');
    const primaryStockHeader = document.getElementById('primary-stock-header');
    const primaryStockTitle = document.getElementById('primary-stock-title');

    // ─── State ───
    let STOCKS = [];
    let currentStockKey = null;
    let compareStockKey = null;
    let preparedStocks = new Set();
    let bgAbortController = null;
    let bgQueueRunning = false;

    // ─── Sanitizers ───
    function escapeHTML(str) {
        if (!str) return '';
        return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#039;');
    }
    function sanitizeUrl(u) {
        if (!u) return '#';
        const t = u.trim();
        return (t.startsWith('https://') || t.startsWith('http://')) ? t : '#';
    }

    // ─── Date Helpers ───
    const todayStr = new Date().toISOString().split('T')[0];
    inputDate.setAttribute('max', todayStr);
    inputDate.setAttribute('min', '2000-01-01');
    inputDate.value = todayStr;

    function toggleCustomDate() {
        customDateContainer.classList.toggle('hidden', dateRangeSelect.value !== 'custom');
    }
    dateRangeSelect.addEventListener('change', toggleCustomDate);
    toggleCustomDate();

    function calculateCutoffDate(val) {
        const d = new Date();
        if (val === 'last-month') { d.setDate(d.getDate() - 30); }
        else if (val === 'last-6-months') { d.setDate(d.getDate() - 180); }
        else if (val === 'last-year') { d.setDate(d.getDate() - 365); }
        else if (val === 'all-time') return '2000-01-01';
        else if (val === 'custom') return inputDate.value;
        return d.toISOString().split('T')[0];
    }

    function formatDate(dateStr) {
        if (!dateStr) return 'N/A';
        try {
            const date = new Date(dateStr.replace(' IST', '').trim());
            if (isNaN(date.getTime())) return dateStr;
            return date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' });
        } catch (e) { return dateStr; }
    }

    function parseSignalDate(dateStr) {
        if (!dateStr) return null;
        let clean = dateStr.replace(/\bIST\b/g, '').replace(/\bUTC\b/g, '').trim();
        
        // Handle "3.47 pm | 19 Jun 2026" or similar format
        if (clean.includes('|')) {
            const parts = clean.split('|');
            const timePart = parts[0].trim().replace('.', ':');
            const datePart = parts[1].trim();
            clean = `${datePart} ${timePart}`;
        }
        
        const parsed = new Date(clean);
        if (!isNaN(parsed.getTime())) {
            return parsed;
        }
        return null;
    }

    function getStatusClass(status) {
        const l = (status || '').toLowerCase();
        if (l.includes('health')) return 'healthy';
        if (l.includes('stable')) return 'stable';
        if (l.includes('warn')) return 'warning';
        if (l.includes('crit')) return 'critical';
        return 'stable';
    }

    // ─── Per-stock storage keys ───
    function stateKey(key) { return `apex_state_${key}`; }
    function evalKey(key) { return `apex_eval_${key}`; }
    function pricesKey(key) { return `apex_prices_${key}`; }

    // ─── Load Stocks & Populate Dropdown ───
    async function loadStocks() {
        try {
            const res = await fetch('/api/stocks');
            const data = await res.json();
            if (data.success) {
                STOCKS = data.stocks;
                stockSelect.innerHTML = '<option value="">-- Choose a stock --</option>';
                STOCKS.forEach(s => {
                    const opt = document.createElement('option');
                    opt.value = s.key;
                    opt.textContent = s.name;
                    stockSelect.appendChild(opt);
                });
            }
        } catch (e) { console.error('Failed to load stocks:', e); }
    }

    function getStock(key) { return STOCKS.find(s => s.key === key) || null; }

    // Restore session
    if (sessionStorage.getItem('gemini_api_key')) {
        inputKey.value = sessionStorage.getItem('gemini_api_key');
    }

    // ─── Show/Hide Helpers ───
    function showLoading(show) {
        loadingOverlay.classList.toggle('hidden', !show);
        sectorsGrid.classList.toggle('hidden', show);
    }
    function showError(msg) { errorMessage.textContent = msg; errorBanner.classList.remove('hidden'); }
    function hideError() { errorBanner.classList.add('hidden'); }
    function showWizardError(msg) { wizardErrorMsg.textContent = msg; wizardError.classList.remove('hidden'); }
    function hideWizardError() { wizardError.classList.add('hidden'); }

    // ═══════════════════════════════════════════════════
    // CHART RENDERER (ApexCharts.js)
    // ═══════════════════════════════════════════════════
    function renderChart(containerEl, tooltipEl, prices, signals, dateRange) {
        // Destroy previous chart instance
        if (containerEl._chartInstance) {
            containerEl._chartInstance.destroy();
            containerEl._chartInstance = null;
        }
        // Remove previous window click handler
        if (containerEl._cleanupWindowClick) {
            window.removeEventListener('click', containerEl._cleanupWindowClick);
            containerEl._cleanupWindowClick = null;
        }

        // Hide tooltip on re-render
        if (tooltipEl) {
            tooltipEl.classList.add('hidden');
            tooltipEl.classList.remove('pinned');
        }

        if (!prices || prices.length === 0) {
            containerEl.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #86868b; font-family: Inter, sans-serif; font-size: 14px;">No price data available</div>';
            return [];
        }

        const activePrices = prices;
        const minPrice = Math.min(...activePrices.map(p => p.close)) * 0.995;
        const maxPrice = Math.max(...activePrices.map(p => p.close)) * 1.005;

        // ── Build signal-to-date map (supports multiple signals per date) ──
        const signalsByDate = {};  // { priceDate: [sig1, sig2, ...] }
        const signalDots = [];

        (signals || []).forEach(sig => {
            const parsedDate = parseSignalDate(sig.date || sig.timestamp);
            if (!parsedDate) return;

            const sigTime = parsedDate.getTime();
            const sigDateStr = parsedDate.toISOString().split('T')[0];

            let closestIdx = -1;
            let minDiff = Infinity;
            activePrices.forEach((p, idx) => {
                const pTime = new Date(p.date).getTime();
                if (isNaN(pTime)) return;
                const diff = Math.abs(pTime - sigTime);
                if (diff < minDiff) {
                    minDiff = diff;
                    closestIdx = idx;
                }
            });

            if (closestIdx !== -1 && minDiff <= 4 * 24 * 60 * 60 * 1000) {
                const pm = activePrices[closestIdx];
                const dotInfo = {
                    priceDate: pm.date,
                    price: pm.close,
                    date: sigDateStr,
                    cluster: sig.cluster_type || sig.type || 'signal',
                    summary: sig.event_summary || sig.summary || '',
                    articleUrl: sig.article_url || '#',
                    articleTitle: sig.article_title || 'View Source',
                    strength: sig.decayed_strength || sig.strength || 0,
                    dataPointIndex: closestIdx
                };
                signalDots.push(dotInfo);

                if (!signalsByDate[pm.date]) signalsByDate[pm.date] = [];
                signalsByDate[pm.date].push(dotInfo);
            }
        });

        // Series data
        const seriesData = activePrices.map(p => ({ x: p.date, y: p.close }));

        // Discrete markers for signal dots (keeps normal points invisible, draws red dots on signal indices)
        const discreteMarkers = [];
        const seenIndices = new Set();
        signalDots.forEach(dot => {
            if (seenIndices.has(dot.dataPointIndex)) return;
            seenIndices.add(dot.dataPointIndex);
            discreteMarkers.push({
                seriesIndex: 0,
                dataPointIndex: dot.dataPointIndex,
                fillColor: '#d12424',
                strokeColor: '#ffffff',
                size: 6,
                shape: 'circle'
            });
        });

        // ── Tooltip helper ──
        let isPinned = false;

        function buildTooltipHTML(priceDate, price) {
            const sigs = signalsByDate[priceDate];
            let html = `<div class="tooltip-date">${escapeHTML(priceDate)}</div>`;
            html += `<div class="tooltip-price">₹${price.toFixed(2)}</div>`;

            if (sigs && sigs.length > 0) {
                sigs.forEach(sig => {
                    html += `<div class="signal-entry">`;
                    html += `<div class="tooltip-cluster"><strong>Cluster:</strong> ${escapeHTML(sig.cluster.replace(/_/g, ' ').toUpperCase())}</div>`;
                    html += `<div style="margin-top: 0.2rem; font-weight: 500; font-size: 0.75rem;">${escapeHTML(sig.summary)}</div>`;
                    html += `<div style="margin-top: 0.25rem;"><a href="${escapeHTML(sanitizeUrl(sig.articleUrl))}" target="_blank" class="tooltip-link">${escapeHTML(sig.articleTitle)}</a></div>`;
                    html += `</div>`;
                });
            }
            return html;
        }

        function positionTooltip(tooltipEl, chartContainer, dataPointIndex) {
            // Use the ApexCharts internal plotted point position
            const containerRect = chartContainer.getBoundingClientRect();
            const svgPoints = chartContainer.querySelectorAll('.apexcharts-series path, .apexcharts-series circle');

            // Estimate x position from data point index
            const plotArea = chartContainer.querySelector('.apexcharts-plot-area');
            let tx = 0, ty = 0;
            if (plotArea) {
                const plotRect = plotArea.getBoundingClientRect();
                const totalPoints = activePrices.length;
                const fraction = dataPointIndex / (totalPoints - 1 || 1);
                tx = plotRect.left - containerRect.left + fraction * plotRect.width + 12;
                ty = 30; // Just below top of chart
            }

            // Clamp within container
            const tooltipWidth = 260;
            if (tx + tooltipWidth > containerRect.width) {
                tx = tx - tooltipWidth - 24;
            }
            if (tx < 0) tx = 8;

            tooltipEl.style.left = tx + 'px';
            tooltipEl.style.top = ty + 'px';
        }

        function showOurTooltip(dataPointIndex, pinned) {
            if (!tooltipEl) return;
            const p = activePrices[dataPointIndex];
            if (!p) return;

            isPinned = pinned;
            tooltipEl.innerHTML = buildTooltipHTML(p.date, p.close);
            tooltipEl.classList.remove('hidden');
            if (pinned) {
                tooltipEl.classList.add('pinned');
            } else {
                tooltipEl.classList.remove('pinned');
            }
            positionTooltip(tooltipEl, containerEl.closest('.chart-container'), dataPointIndex);
        }

        function hideOurTooltip() {
            if (!tooltipEl || isPinned) return;
            tooltipEl.classList.add('hidden');
            tooltipEl.classList.remove('pinned');
        }

        // ── ApexCharts options ──
        const options = {
            chart: {
                type: 'area',
                height: '100%',
                width: '100%',
                toolbar: { show: false },
                zoom: { enabled: false },
                fontFamily: 'Inter, sans-serif',
                sparkline: { enabled: false },
                events: {
                    mouseLeave: function() {
                        hideOurTooltip();
                    },
                    click: function(event, chartContext, config) {
                        if (config && config.dataPointIndex !== undefined && config.dataPointIndex >= 0) {
                            const p = activePrices[config.dataPointIndex];
                            if (p && signalsByDate[p.date]) {
                                // Pin the tooltip
                                showOurTooltip(config.dataPointIndex, true);
                                event.stopPropagation();
                            } else {
                                // Clicked non-signal point — dismiss if pinned
                                isPinned = false;
                                hideOurTooltip();
                            }
                        }
                    }
                }
            },
            series: [{ name: 'Price', data: seriesData }],
            stroke: {
                curve: 'smooth',
                width: 2,
                colors: ['#0071e3']
            },
            fill: {
                type: 'gradient',
                gradient: {
                    shadeIntensity: 1,
                    opacityFrom: 0.15,
                    opacityTo: 0.0,
                    stops: [0, 100]
                },
                colors: ['#0071e3']
            },
            markers: {
                size: 0,
                discrete: discreteMarkers
            },
            dataLabels: {
                enabled: false
            },
            grid: {
                borderColor: 'rgba(0,0,0,0.05)',
                xaxis: { lines: { show: false } },
                yaxis: { lines: { show: true } },
                padding: { top: 10, right: 15, bottom: 0, left: 10 }
            },
            xaxis: {
                type: 'category',
                labels: {
                    hideOverlappingLabels: true,
                    style: { colors: '#86868b', fontSize: '11px' },
                    formatter: function(value) {
                        if (!value) return '';
                        const d = new Date(value);
                        if (isNaN(d.getTime())) return value;
                        if (dateRange === 'last-month') return d.getDate() + ' ' + d.toLocaleString('en-US', { month: 'short' });
                        if (dateRange === 'last-6-months') return d.toLocaleString('en-US', { month: 'short', year: '2-digit' });
                        return d.toLocaleString('en-US', { month: 'short', year: 'numeric' });
                    }
                },
                axisBorder: { show: false },
                axisTicks: { show: false }
            },
            yaxis: {
                min: minPrice,
                max: maxPrice,
                labels: {
                    style: { colors: '#86868b', fontSize: '11px' },
                    formatter: function(value) {
                        return '₹' + value.toFixed(0);
                    }
                }
            },
            tooltip: {
                enabled: true,
                shared: false,
                intersect: false,
                custom: function({ series, seriesIndex, dataPointIndex, w }) {
                    if (!isPinned) {
                        showOurTooltip(dataPointIndex, false);
                    }
                    return '';
                }
            }
        };

        const chart = new ApexCharts(containerEl, options);
        chart.render();
        containerEl._chartInstance = chart;

        // ── Window click to dismiss pinned tooltip ──
        const handleWindowClick = (e) => {
            if (!isPinned) return;
            // Don't dismiss if clicking inside the tooltip itself
            if (tooltipEl && tooltipEl.contains(e.target)) return;
            // Don't dismiss if clicking on the chart area (chart click handler will decide)
            if (containerEl.contains(e.target)) return;
            isPinned = false;
            if (tooltipEl) {
                tooltipEl.classList.remove('pinned');
                tooltipEl.classList.add('hidden');
            }
        };
        window.addEventListener('click', handleWindowClick);
        containerEl._cleanupWindowClick = handleWindowClick;

        return signalDots;
    }

    // ═══════════════════════════════════════════════════
    // DASHBOARD RENDERING
    // ═══════════════════════════════════════════════════
    function renderDashboard(data, gridEl) {
        gridEl.innerHTML = '';
        const sectors = data.sectors || {};
        
        // Convert to array and sort by signal count descending
        const sectorsList = Object.keys(sectors).map(key => ({
            key: key,
            ...sectors[key]
        }));
        
        sectorsList.sort((a, b) => {
            const countA = a.signals ? a.signals.length : 0;
            const countB = b.signals ? b.signals.length : 0;
            return countB - countA;
        });

        let rendered = 0;
        sectorsList.forEach(sector => {
            const sigCount = sector.signals ? sector.signals.length : 0;
            if (sigCount === 0) return;
            rendered++;
            const statusClass = getStatusClass(sector.status);
            const card = document.createElement('div');
            card.className = `sector-card status-${statusClass}`;
            card.innerHTML = `
                <div class="card-header">
                    <div class="card-title-group">
                        <span class="card-category">${escapeHTML(sector.category || 'General')}</span>
                        <h3>${escapeHTML(sector.name)}</h3>
                    </div>
                    <div class="score-circle-wrapper"><div class="score-circle">${escapeHTML(sector.health_score)}</div></div>
                </div>
                <div class="card-body"><p>${escapeHTML(sector.summary || sector.description || 'No description.')}</p></div>
                <div class="card-footer">
                    <span class="card-signals-pill">${escapeHTML(sigCount)} signal${sigCount === 1 ? '' : 's'}</span>
                    <span class="card-status-label">${escapeHTML(sector.status)}</span>
                </div>`;
            card.addEventListener('click', () => openModal(sector));
            gridEl.appendChild(card);
        });
        if (rendered === 0) {
            gridEl.innerHTML = '<div class="loading-overlay"><h3>No active signals detected in any sector.</h3></div>';
        }
    }

    // ═══════════════════════════════════════════════════
    // MODAL
    // ═══════════════════════════════════════════════════
    function openModal(sector) {
        modalSectorName.textContent = sector.name;
        modalSectorCategory.textContent = sector.category || 'General';
        modalHealthScore.textContent = sector.health_score;
        modalSectorConfidence.textContent = Math.round((sector.confidence || 0) * 100) + '%';
        modalSectorSummary.textContent = sector.summary || 'No evaluation summary available.';
        modalSectorStatus.textContent = sector.status;
        modalSectorStatus.className = 'status-badge badge-' + getStatusClass(sector.status);
        modalSignalsList.innerHTML = '';
        (sector.signals || []).forEach(sig => {
            const sv = parseFloat(sig.decayed_strength || sig.strength || 0);
            let sc = 'score-neutral', sp = '';
            if (sv > 0) { sc = 'score-positive'; sp = '+'; } else if (sv < 0) { sc = 'score-negative'; }
            const row = document.createElement('div');
            row.className = 'signal-row';
            row.innerHTML = `
                <div class="signal-info">
                    <span class="signal-type-tag">${escapeHTML(sig.type || 'Signal')}</span>
                    <p class="signal-desc">${escapeHTML(sig.summary || 'No details.')}</p>
                    <div class="signal-trace">
                        <span>Date: ${escapeHTML(formatDate(sig.date))}</span> &bull;
                        <a href="${escapeHTML(sanitizeUrl(sig.article_url))}" target="_blank" class="signal-link">${escapeHTML(sig.article_title || 'Source')}</a>
                    </div>
                </div>
                <div class="signal-score ${sc}">${sp}${sv.toFixed(2)}</div>`;
            modalSignalsList.appendChild(row);
        });
        if (!sector.signals || sector.signals.length === 0) {
            modalSignalsList.innerHTML = '<p style="padding:1rem 0;text-align:center;color:#86868b;">No contributing signals.</p>';
        }
        detailsModal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
    }

    function closeModal() { detailsModal.classList.add('hidden'); document.body.style.overflow = ''; }
    closeModalBtn.addEventListener('click', closeModal);
    detailsModal.addEventListener('click', e => { if (e.target === detailsModal) closeModal(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && !detailsModal.classList.contains('hidden')) closeModal(); });

    // ═══════════════════════════════════════════════════
    // STOCK PREPARATION (Pipeline + Evaluation + Prices)
    // ═══════════════════════════════════════════════════
    async function prepareStock(stockKey, apiKey, cutoffDate, dateRange, signal) {
        const stock = getStock(stockKey);
        if (!stock) throw new Error('Unknown stock');

        // Check if already prepared
        if (sessionStorage.getItem(evalKey(stockKey)) && sessionStorage.getItem(pricesKey(stockKey))) {
            preparedStocks.add(stockKey);
            return JSON.parse(sessionStorage.getItem(evalKey(stockKey)));
        }

        if (signal) signal.abort; // allow external abort check

        // 1. Run pipeline
        const pipelineRes = await fetch('/api/run-pipeline', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url: stock.url, cutoff_date: cutoffDate, gemini_api_key: apiKey })
        });
        const pipelineData = await pipelineRes.json();
        if (!pipelineRes.ok || !pipelineData.success) throw new Error(pipelineData.error || 'Pipeline failed');

        sessionStorage.setItem(stateKey(stockKey), JSON.stringify({
            articles: pipelineData.articles, events: pipelineData.events,
            signals: pipelineData.signals, registry: pipelineData.registry
        }));

        // 2. Evaluate sectors
        const evalRes = await fetch('/api/evaluate-sectors', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ signals: pipelineData.signals, registry: pipelineData.registry, gemini_api_key: apiKey })
        });
        const evalResult = await evalRes.json();
        if (!evalRes.ok || evalResult.error) throw new Error(evalResult.error || 'Evaluation failed');

        const dashData = {
            last_updated: new Date().toISOString(),
            signals_count: pipelineData.signals.length,
            sectors: evalResult.evaluations
        };
        sessionStorage.setItem(evalKey(stockKey), JSON.stringify(dashData));

        // 3. Fetch stock prices
        const endDate = new Date();
        endDate.setDate(endDate.getDate() + 1);
        try {
            const priceRes = await fetch('/api/stock-prices', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ ticker: stock.ticker, start_date: cutoffDate, end_date: endDate.toISOString().split('T')[0] })
            });
            const priceData = await priceRes.json();
            if (priceData.success) {
                sessionStorage.setItem(pricesKey(stockKey), JSON.stringify(priceData.prices));
            }
        } catch (e) { console.warn('Price fetch failed:', e); }

        preparedStocks.add(stockKey);
        return dashData;
    }

    // ═══════════════════════════════════════════════════
    // DISPLAY DASHBOARD FOR A STOCK
    // ═══════════════════════════════════════════════════
    function showDashboardForStock(stockKey) {
        const stock = getStock(stockKey);
        if (!stock) return;
        currentStockKey = stockKey;
        sessionStorage.setItem('apex_current_stock', stockKey);
        activeStockName.textContent = stock.name;

        const evalData = JSON.parse(sessionStorage.getItem(evalKey(stockKey)) || 'null');
        if (!evalData) return;

        totalSignalsCount.textContent = evalData.signals_count || 0;
        lastUpdatedTime.textContent = formatDate(evalData.last_updated);
        renderDashboard(evalData, sectorsGrid);

        // Render chart
        const prices = JSON.parse(sessionStorage.getItem(pricesKey(stockKey)) || '[]');
        const allSignals = [];
        Object.values(evalData.sectors || {}).forEach(sec => {
            (sec.signals || []).forEach(s => allSignals.push(s));
        });
        const dateRange = sessionStorage.getItem('apex_date_range') || 'last-6-months';
        renderChart(priceChartCanvas, chartTooltip, prices, allSignals, dateRange);
    }

    // ═══════════════════════════════════════════════════
    // COMPARE PANEL (Stock List Sidebar)
    // ═══════════════════════════════════════════════════
    function renderStockList() {
        stockListEl.innerHTML = '';
        STOCKS.forEach(s => {
            if (s.key === currentStockKey) return;
            const isPrepared = preparedStocks.has(s.key);
            const card = document.createElement('div');
            card.className = 'stock-card';
            card.innerHTML = `
                <div class="stock-card-info">
                    <span class="stock-card-name">${escapeHTML(s.name)}</span>
                    <span class="stock-card-ticker">${escapeHTML(s.ticker)}</span>
                </div>
                <div class="stock-card-actions">
                    <button class="btn btn-sm btn-primary stock-open-btn" data-key="${s.key}">Open</button>
                    <button class="btn btn-sm btn-secondary stock-compare-btn" data-key="${s.key}" ${!isPrepared ? 'disabled' : ''}>Compare</button>
                </div>
                <div class="stock-progress-bar ${isPrepared ? 'prepared' : ''}">
                    <div class="stock-progress-fill" data-stock="${s.key}"></div>
                </div>`;
            card.querySelector('.stock-open-btn').addEventListener('click', () => openStock(s.key));
            card.querySelector('.stock-compare-btn').addEventListener('click', () => compareWith(s.key));
            stockListEl.appendChild(card);
        });
    }

    async function openStock(key) {
        const apiKey = sessionStorage.getItem('gemini_api_key');
        const cutoffDate = sessionStorage.getItem('apex_cutoff_date');
        const dateRange = sessionStorage.getItem('apex_date_range');
        if (!apiKey || !cutoffDate) { alert('Please run analysis first.'); return; }

        comparePanel.classList.add('hidden');

        if (preparedStocks.has(key)) {
            showDashboardForStock(key);
            renderStockList();
            return;
        }

        // Cancel background queue, prepare this stock immediately
        if (bgAbortController) bgAbortController.abort();
        showLoading(true);
        try {
            await prepareStock(key, apiKey, cutoffDate, dateRange);
            showDashboardForStock(key);
        } catch (e) { showError('Failed to prepare stock: ' + e.message); }
        finally { showLoading(false); }
        renderStockList();
        startBackgroundQueue();
    }

    async function compareWith(key) {
        if (!preparedStocks.has(key)) return;
        compareStockKey = key;
        const stock = getStock(key);
        compareStockTitle.textContent = stock.name;
        compareStockPanel.classList.remove('hidden');
        dashboardWrapper.classList.add('split-view');
        comparePanel.classList.add('hidden');

        // Show primary stock header with title
        const primaryStock = getStock(currentStockKey);
        if (primaryStock && primaryStockTitle && primaryStockHeader) {
            primaryStockTitle.textContent = primaryStock.name;
            primaryStockHeader.classList.remove('hidden');
        }

        const evalData = JSON.parse(sessionStorage.getItem(evalKey(key)) || 'null');
        if (evalData) {
            renderDashboard(evalData, compareSectorsGrid);
            const prices = JSON.parse(sessionStorage.getItem(pricesKey(key)) || '[]');
            const allSignals = [];
            Object.values(evalData.sectors || {}).forEach(sec => {
                (sec.signals || []).forEach(s => allSignals.push(s));
            });
            const dateRange = sessionStorage.getItem('apex_date_range') || 'last-6-months';
            renderChart(comparePriceChartCanvas, compareChartTooltip, prices, allSignals, dateRange);
        }
    }

    function exitComparison() {
        compareStockKey = null;
        compareStockPanel.classList.add('hidden');
        if (primaryStockHeader) primaryStockHeader.classList.add('hidden');
        dashboardWrapper.classList.remove('split-view');
        // Re-render primary chart to fill space
        const dateRange = sessionStorage.getItem('apex_date_range') || 'last-6-months';
        const prices = JSON.parse(sessionStorage.getItem(pricesKey(currentStockKey)) || '[]');
        const evalData = JSON.parse(sessionStorage.getItem(evalKey(currentStockKey)) || 'null');
        if (evalData) {
            const allSignals = [];
            Object.values(evalData.sectors || {}).forEach(sec => (sec.signals || []).forEach(s => allSignals.push(s)));
            setTimeout(() => renderChart(priceChartCanvas, chartTooltip, prices, allSignals, dateRange), 100);
        }
    }

    btnCloseCompareView.addEventListener('click', exitComparison);
    if (btnClosePrimaryView) {
        btnClosePrimaryView.addEventListener('click', exitComparison);
    }

    // Compare panel toggle
    btnCompare.addEventListener('click', () => {
        renderStockList();
        comparePanel.classList.toggle('hidden');
    });
    closeComparePanel.addEventListener('click', () => comparePanel.classList.add('hidden'));

    // ═══════════════════════════════════════════════════
    // BACKGROUND PREPARATION QUEUE
    // ═══════════════════════════════════════════════════
    async function startBackgroundQueue() {
        if (bgQueueRunning) return;
        bgQueueRunning = true;
        bgAbortController = new AbortController();

        const apiKey = sessionStorage.getItem('gemini_api_key');
        const cutoffDate = sessionStorage.getItem('apex_cutoff_date');
        const dateRange = sessionStorage.getItem('apex_date_range');
        if (!apiKey || !cutoffDate) { bgQueueRunning = false; return; }

        const queue = STOCKS.filter(s => !preparedStocks.has(s.key)).sort((a, b) => a.name.localeCompare(b.name));
        let index = 0;
        let activeWorkers = 0;

        async function processNext() {
            if (bgAbortController.signal.aborted || index >= queue.length) {
                checkFinish();
                return;
            }

            const stock = queue[index++];
            if (!stock) {
                checkFinish();
                return;
            }

            if (preparedStocks.has(stock.key)) {
                setTimeout(processNext, 50);
                return;
            }

            activeWorkers++;
            const fillEl = document.querySelector(`.stock-progress-fill[data-stock="${stock.key}"]`);
            if (fillEl) {
                fillEl.style.width = '30%';
                fillEl.style.backgroundColor = '#0071e3';
            }

            try {
                await prepareStock(stock.key, apiKey, cutoffDate, dateRange, bgAbortController.signal);
                if (fillEl) {
                    fillEl.style.width = '100%';
                    fillEl.style.backgroundColor = '#107c41';
                    fillEl.parentElement.classList.add('prepared');
                }
                // Enable compare button
                const btn = document.querySelector(`.stock-compare-btn[data-key="${stock.key}"]`);
                if (btn) btn.disabled = false;
            } catch (e) {
                if (bgAbortController.signal.aborted) {
                    activeWorkers--;
                    return;
                }
                console.warn(`Background prep failed for ${stock.name}:`, e);
                if (fillEl) {
                    fillEl.style.width = '100%';
                    fillEl.style.backgroundColor = '#d12424';
                }
            } finally {
                activeWorkers--;
                setTimeout(processNext, 100);
            }
        }

        function checkFinish() {
            if (activeWorkers === 0 && (index >= queue.length || bgAbortController.signal.aborted)) {
                bgQueueRunning = false;
            }
        }

        // Spawn 2 workers with 500ms stagger delay
        const CONCURRENCY = 2;
        for (let i = 0; i < CONCURRENCY; i++) {
            setTimeout(processNext, i * 500);
        }
    }

    // ═══════════════════════════════════════════════════
    // WIZARD FLOW
    // ═══════════════════════════════════════════════════
    btnRunPipeline.addEventListener('click', async () => {
        hideWizardError();
        const selectedKey = stockSelect.value;
        const geminiKey = inputKey.value.trim();
        const rangeVal = dateRangeSelect.value;
        const cutoffDate = calculateCutoffDate(rangeVal);

        if (!selectedKey) { showWizardError('Please select a stock.'); return; }
        if (!geminiKey) { showWizardError('Please enter your Gemini API Key.'); return; }
        if (!/^[a-zA-Z0-9_\-\.+\/=]+$/.test(geminiKey) || geminiKey.length < 10) {
            showWizardError('Invalid API key format.'); return;
        }
        if (rangeVal === 'custom' && !cutoffDate) { showWizardError('Please select a cutoff date.'); return; }
        if (new Date(cutoffDate) > new Date()) { showWizardError('Date cannot be in the future.'); return; }

        // Verify key
        btnRunPipeline.disabled = true;
        btnRunPipeline.textContent = 'Verifying API key...';
        try {
            const kRes = await fetch('/api/verify-key', {
                method: 'POST', headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ gemini_api_key: geminiKey })
            });
            const kData = await kRes.json();
            if (!kRes.ok || !kData.success) throw new Error(kData.error || 'Key verification failed.');
        } catch (e) { showWizardError(e.message); btnRunPipeline.disabled = false; btnRunPipeline.textContent = 'Start Analysis'; return; }

        sessionStorage.setItem('gemini_api_key', geminiKey);
        sessionStorage.setItem('apex_cutoff_date', cutoffDate);
        sessionStorage.setItem('apex_date_range', rangeVal);

        // Check if already prepared
        if (preparedStocks.has(selectedKey)) {
            wizardOverlay.classList.add('hidden');
            showDashboardForStock(selectedKey);
            startBackgroundQueue();
            btnRunPipeline.disabled = false;
            btnRunPipeline.textContent = 'Start Analysis';
            return;
        }

        // Show progress
        wizardStepMain.classList.add('hidden');
        wizardStepProgress.classList.remove('hidden');
        btnRunPipeline.disabled = false;
        btnRunPipeline.textContent = 'Start Analysis';

        const progressSteps = [
            { pct: 15, title: 'Crawling news feed...', desc: 'Fetching articles from Moneycontrol...' },
            { pct: 35, title: 'Extracting content...', desc: 'Reading full article texts...' },
            { pct: 55, title: 'Analyzing events...', desc: 'Processing with Gemini AI...' },
            { pct: 75, title: 'Clustering signals...', desc: 'Mapping events to sectors...' },
            { pct: 90, title: 'Evaluating health...', desc: 'Generating sector safety scores...' }
        ];
        let stepIdx = 0;
        const progressInterval = setInterval(() => {
            if (stepIdx < progressSteps.length) {
                const s = progressSteps[stepIdx];
                progressTitle.textContent = s.title;
                progressSubtitle.textContent = s.desc;
                progressBarFill.style.width = s.pct + '%';
                stepIdx++;
            }
        }, 3000);

        try {
            await prepareStock(selectedKey, geminiKey, cutoffDate, rangeVal);
            clearInterval(progressInterval);
            progressTitle.textContent = 'Analysis complete!';
            progressSubtitle.textContent = 'Loading dashboard...';
            progressBarFill.style.width = '100%';

            setTimeout(() => {
                wizardOverlay.classList.add('hidden');
                wizardStepProgress.classList.add('hidden');
                wizardStepMain.classList.remove('hidden');
                showDashboardForStock(selectedKey);
                startBackgroundQueue();
            }, 800);
        } catch (e) {
            clearInterval(progressInterval);
            wizardStepProgress.classList.add('hidden');
            wizardStepMain.classList.remove('hidden');
            showWizardError('Pipeline failed: ' + e.message);
        }
    });

    // ─── Reset ───
    btnResetPipeline.addEventListener('click', () => {
        if (!confirm('Reset all dashboard data?')) return;
        STOCKS.forEach(s => {
            sessionStorage.removeItem(stateKey(s.key));
            sessionStorage.removeItem(evalKey(s.key));
            sessionStorage.removeItem(pricesKey(s.key));
        });
        sessionStorage.clear();
        preparedStocks.clear();
        if (bgAbortController) bgAbortController.abort();
        window.location.reload();
    });

    // ─── Window resize handler for chart ───
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
            if (currentStockKey) {
                const prices = JSON.parse(sessionStorage.getItem(pricesKey(currentStockKey)) || '[]');
                const evalData = JSON.parse(sessionStorage.getItem(evalKey(currentStockKey)) || 'null');
                if (evalData) {
                    const allSignals = [];
                    Object.values(evalData.sectors || {}).forEach(sec => (sec.signals || []).forEach(s => allSignals.push(s)));
                    const dateRange = sessionStorage.getItem('apex_date_range') || 'last-6-months';
                    renderChart(priceChartCanvas, chartTooltip, prices, allSignals, dateRange);
                }
            }
        }, 250);
    });

    // ─── Init ───
    loadStocks().then(() => {
        // Check if any stock already prepared
        STOCKS.forEach(s => {
            if (sessionStorage.getItem(evalKey(s.key)) && sessionStorage.getItem(pricesKey(s.key))) {
                preparedStocks.add(s.key);
            }
        });

        const lastStock = sessionStorage.getItem('apex_current_stock');
        if (lastStock && preparedStocks.has(lastStock)) {
            wizardOverlay.classList.add('hidden');
            showDashboardForStock(lastStock);
            startBackgroundQueue();
        } else {
            wizardOverlay.classList.remove('hidden');
        }
    });
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initApp);
} else {
    initApp();
}
