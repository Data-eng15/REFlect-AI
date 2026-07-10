"""
Dashboard UI HTML template.
Single-page interactive ops dashboard with real-time metrics.
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>REFlect AI - Backend Operations Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
            background: linear-gradient(135deg, #1e1e2e 0%, #2d2d44 100%);
            color: #e0e0e0;
            min-height: 100vh;
            padding: 20px;
        }

        .container {
            max-width: 1600px;
            margin: 0 auto;
        }

        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #3d3d5c;
        }

        h1 {
            font-size: 28px;
            font-weight: 600;
        }

        .header-info {
            display: flex;
            gap: 20px;
            align-items: center;
        }

        .status-badge {
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: 600;
            font-size: 14px;
        }

        .status-healthy {
            background: #10b981;
            color: white;
        }

        .status-degraded {
            background: #f59e0b;
            color: white;
        }

        .status-critical {
            background: #ef4444;
            color: white;
        }

        .last-update {
            font-size: 12px;
            color: #999;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .card {
            background: #2d2d44;
            border: 1px solid #3d3d5c;
            border-radius: 8px;
            padding: 20px;
            transition: all 0.3s ease;
        }

        .card:hover {
            border-color: #5d5d7c;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }

        .card h3 {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            color: #999;
            margin-bottom: 10px;
        }

        .metric-value {
            font-size: 32px;
            font-weight: 700;
            color: #fff;
        }

        .metric-unit {
            font-size: 14px;
            color: #666;
            margin-left: 5px;
        }

        .metric-change {
            font-size: 12px;
            margin-top: 5px;
        }

        .metric-change.positive {
            color: #10b981;
        }

        .metric-change.negative {
            color: #ef4444;
        }

        .chart-container {
            position: relative;
            height: 300px;
            margin-bottom: 30px;
            padding: 20px;
            background: #2d2d44;
            border: 1px solid #3d3d5c;
            border-radius: 8px;
        }

        .charts-row {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .table-card {
            background: #2d2d44;
            border: 1px solid #3d3d5c;
            border-radius: 8px;
            overflow: hidden;
        }

        .table-card h3 {
            font-size: 12px;
            font-weight: 600;
            text-transform: uppercase;
            color: #999;
            padding: 20px;
            border-bottom: 1px solid #3d3d5c;
        }

        table {
            width: 100%;
            border-collapse: collapse;
        }

        th {
            background: #3d3d5c;
            padding: 12px 16px;
            text-align: left;
            font-size: 12px;
            font-weight: 600;
            color: #999;
            text-transform: uppercase;
        }

        td {
            padding: 12px 16px;
            border-top: 1px solid #3d3d5c;
            font-size: 13px;
        }

        tr:hover td {
            background: #35355c;
        }

        .status-ok {
            color: #10b981;
        }

        .status-error {
            color: #ef4444;
        }

        .status-cached {
            color: #3b82f6;
        }

        .progress-bar {
            width: 100%;
            height: 6px;
            background: #3d3d5c;
            border-radius: 3px;
            overflow: hidden;
            margin-top: 8px;
        }

        .progress-fill {
            height: 100%;
            background: linear-gradient(90deg, #3b82f6 0%, #10b981 100%);
            border-radius: 3px;
        }

        footer {
            text-align: center;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid #3d3d5c;
            color: #666;
            font-size: 12px;
        }

        .alert {
            padding: 16px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: flex;
            gap: 12px;
            align-items: flex-start;
        }

        .alert-warning {
            background: rgba(245, 158, 11, 0.1);
            border: 1px solid #f59e0b;
            color: #fcd34d;
        }

        .alert-error {
            background: rgba(239, 68, 68, 0.1);
            border: 1px solid #ef4444;
            color: #fca5a5;
        }

        .alert-icon {
            font-weight: bold;
            flex-shrink: 0;
        }

        .refresh-btn {
            padding: 8px 16px;
            background: #3b82f6;
            border: none;
            border-radius: 6px;
            color: white;
            cursor: pointer;
            font-size: 12px;
            font-weight: 600;
            transition: all 0.2s ease;
        }

        .refresh-btn:hover {
            background: #2563eb;
        }

        .refresh-btn:active {
            transform: scale(0.98);
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>🚀 REFlect AI Backend Operations</h1>
                <p style="color: #666; margin-top: 4px;">Real-time system monitoring dashboard</p>
            </div>
            <div class="header-info">
                <button class="refresh-btn" onclick="refreshMetrics()">Refresh Now</button>
                <div class="status-badge" id="health-badge">LOADING</div>
                <div style="text-align: right;">
                    <div style="font-size: 13px; font-weight: 600;" id="uptime">Uptime: --</div>
                    <div class="last-update" id="last-update">Last updated: --</div>
                </div>
            </div>
        </header>

        <div id="alerts-container"></div>

        <!-- Key Metrics -->
        <div class="grid">
            <div class="card">
                <h3>Requests Per Second</h3>
                <div class="metric-value"><span id="rps">0.00</span><span class="metric-unit">RPS</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 20%;"></div></div>
                <div class="metric-change positive">Optimal: < 0.5 RPS</div>
            </div>

            <div class="card">
                <h3>Average Latency</h3>
                <div class="metric-value"><span id="avg-latency">0</span><span class="metric-unit">ms</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 25%;"></div></div>
                <div class="metric-change">Local: ~3,500ms | Cache: ~0ms</div>
            </div>

            <div class="card">
                <h3>Cache Hit Rate</h3>
                <div class="metric-value"><span id="cache-hit-rate">0</span><span class="metric-unit">%</span></div>
                <div class="progress-bar"><div class="progress-fill" id="cache-progress" style="width: 94%;"></div></div>
                <div class="metric-change positive" id="cache-count">Hits: 0 | Misses: 0</div>
            </div>

            <div class="card">
                <h3>Error Rate</h3>
                <div class="metric-value"><span id="error-rate">0</span><span class="metric-unit">%</span></div>
                <div class="progress-bar"><div class="progress-fill" style="width: 5%; background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);"></div></div>
                <div class="metric-change positive">Target: < 5%</div>
            </div>

            <div class="card">
                <h3>Total Requests</h3>
                <div class="metric-value" id="total-requests">0</div>
                <div class="metric-change positive" id="error-count">Errors: 0</div>
            </div>

            <div class="card">
                <h3>Inference Status</h3>
                <div class="metric-value"><span id="inference-count">0</span></div>
                <div class="metric-change" id="inference-status">Avg: 0ms | Errors: 0</div>
            </div>
        </div>

        <!-- Charts -->
        <div class="charts-row">
            <div class="chart-container">
                <canvas id="latencyChart"></canvas>
            </div>
            <div class="chart-container">
                <canvas id="errorChart"></canvas>
            </div>
        </div>

        <!-- Recent Requests -->
        <div class="table-card">
            <h3>Recent Requests (Last 20)</h3>
            <table>
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Endpoint</th>
                        <th>Status</th>
                        <th>Latency</th>
                        <th>Cache</th>
                    </tr>
                </thead>
                <tbody id="requests-table-body">
                    <tr><td colspan="5" style="text-align: center; color: #666;">No requests yet</td></tr>
                </tbody>
            </table>
        </div>

        <footer>
            <p>Backend Operations Dashboard v1.0 | Designed for DevOps & Backend Engineers</p>
            <p>Auto-refresh every 5 seconds | All times in UTC</p>
        </footer>
    </div>

    <script>
        let latencyChart, errorChart;

        async function fetchMetrics() {
            try {
                const response = await fetch('/api/metrics');
                const data = await response.json();
                return data;
            } catch (error) {
                console.error('Failed to fetch metrics:', error);
                return null;
            }
        }

        function updateMetrics(metrics) {
            if (!metrics) return;

            const now = new Date();
            document.getElementById('last-update').textContent = `Last updated: ${now.toLocaleTimeString()}`;
            document.getElementById('uptime').textContent = `Uptime: ${metrics.uptime_hours}h`;

            // Update key metrics
            document.getElementById('rps').textContent = metrics.current_rps.toFixed(2);
            document.getElementById('avg-latency').textContent = Math.round(metrics.avg_latency_ms);
            document.getElementById('cache-hit-rate').textContent = Math.round(metrics.cache_hit_rate_pct);
            document.getElementById('error-rate').textContent = metrics.error_rate_pct.toFixed(1);
            document.getElementById('total-requests').textContent = metrics.total_requests;
            document.getElementById('error-count').textContent = `Errors: ${metrics.total_errors}`;
            document.getElementById('cache-count').textContent = `Hits: ${metrics.cache_hits} | Misses: ${metrics.cache_misses}`;

            document.getElementById('inference-count').textContent = metrics.inference_calls;
            document.getElementById('inference-status').textContent = `Avg: ${Math.round(metrics.avg_inference_ms)}ms | Errors: ${metrics.inference_errors}`;

            // Update progress bar
            document.getElementById('cache-progress').style.width = `${metrics.cache_hit_rate_pct}%`;

            // Update health badge
            const healthBadge = document.getElementById('health-badge');
            healthBadge.textContent = metrics.health_status;
            healthBadge.className = `status-badge status-${metrics.health_status.toLowerCase()}`;

            // Update recent requests table
            const tbody = document.getElementById('requests-table-body');
            tbody.innerHTML = '';
            metrics.recent_requests.slice().reverse().forEach(req => {
                const time = new Date(req.timestamp).toLocaleTimeString();
                const statusClass = req.status < 400 ? 'status-ok' : 'status-error';
                const cachedClass = req.cached ? 'status-cached' : '';
                tbody.innerHTML += \`
                    <tr>
                        <td>\${time}</td>
                        <td>\${req.endpoint}</td>
                        <td class="\${statusClass}">\${req.status}</td>
                        <td>\${Math.round(req.latency_ms)}ms</td>
                        <td class="\${cachedClass}">\${req.cached ? '✓ Cached' : 'Fresh'}</td>
                    </tr>
                \`;
            });

            // Update alerts
            updateAlerts(metrics);

            // Update charts
            updateCharts(metrics);
        }

        function updateAlerts(metrics) {
            const container = document.getElementById('alerts-container');
            container.innerHTML = '';

            if (metrics.error_rate_pct > 10) {
                container.innerHTML += \`
                    <div class="alert alert-error">
                        <span class="alert-icon">⚠️</span>
                        <div>High error rate detected: \${metrics.error_rate_pct.toFixed(1)}% (\${metrics.total_errors}/\${metrics.total_requests})</div>
                    </div>
                \`;
            }

            if (metrics.cache_hit_rate_pct < 50) {
                container.innerHTML += \`
                    <div class="alert alert-warning">
                        <span class="alert-icon">⚠️</span>
                        <div>Cache hit rate low: \${metrics.cache_hit_rate_pct.toFixed(1)}%. Consider monitoring inference performance.</div>
                    </div>
                \`;
            }

            if (metrics.inference_error_rate_pct > 5) {
                container.innerHTML += \`
                    <div class="alert alert-error">
                        <span class="alert-icon">⚠️</span>
                        <div>Inference errors detected: \${metrics.inference_error_rate_pct.toFixed(1)}% (\${metrics.inference_errors}/\${metrics.inference_calls})</div>
                    </div>
                \`;
            }

            if (metrics.current_rps > 0.5) {
                container.innerHTML += \`
                    <div class="alert alert-warning">
                        <span class="alert-icon">ℹ️</span>
                        <div>Current RPS: \${metrics.current_rps.toFixed(2)}. Consider load balancing if sustained.</div>
                    </div>
                \`;
            }
        }

        function updateCharts(metrics) {
            // Latency chart
            if (!latencyChart) {
                const ctx = document.getElementById('latencyChart').getContext('2d');
                latencyChart = new Chart(ctx, {
                    type: 'line',
                    data: {
                        labels: ['Avg Latency', 'Local Inference', 'Cache Hit', 'P95 Estimate'],
                        datasets: [{
                            label: 'Latency (ms)',
                            data: [
                                metrics.avg_latency_ms,
                                metrics.avg_inference_ms,
                                0.002,
                                Math.max(metrics.avg_latency_ms * 1.5, 1000)
                            ],
                            borderColor: '#3b82f6',
                            backgroundColor: 'rgba(59, 130, 246, 0.1)',
                            borderWidth: 2,
                            fill: true,
                            tension: 0.4,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: { legend: { display: false } },
                        scales: { y: { beginAtZero: true } }
                    }
                });
            }

            // Error chart
            if (!errorChart) {
                const ctx = document.getElementById('errorChart').getContext('2d');
                errorChart = new Chart(ctx, {
                    type: 'doughnut',
                    data: {
                        labels: ['Success', 'Errors'],
                        datasets: [{
                            data: [
                                metrics.total_requests - metrics.total_errors,
                                metrics.total_errors
                            ],
                            backgroundColor: ['#10b981', '#ef4444'],
                            borderColor: '#2d2d44',
                            borderWidth: 2,
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { position: 'bottom' }
                        }
                    }
                });
            }
        }

        async function refreshMetrics() {
            const metrics = await fetchMetrics();
            updateMetrics(metrics);
        }

        // Auto-refresh every 5 seconds
        setInterval(refreshMetrics, 5000);
        refreshMetrics(); // Initial load
    </script>
</body>
</html>
"""
