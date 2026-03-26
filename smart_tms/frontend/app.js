document.addEventListener('DOMContentLoaded', () => {
    // Same host as the dashboard; port 5000 is the Smart TMS API (avoids localhost vs 127.0.0.1 fetch blocks)
    const API_BASE =
        window.location.protocol === 'file:' || !window.location.hostname
            ? 'http://127.0.0.1:5000'
            : `${window.location.protocol}//${window.location.hostname}:5000`;

    // State Management
    let currentJunctionId = 1; // Default to first junction
    let currentTimeframe = 0;  // Default time step
    
    // DOM Elements
    const navItemsList = document.getElementById('nav-items');
    const delayAmount = document.getElementById('delay-amount');
    const congestionFill = document.getElementById('congestion-fill');
    const junctionNameEl = document.getElementById('current-junction-name');
    const junctionStatusEl = document.getElementById('current-junction-status');
    
    // Buttons

    const btn2d = document.getElementById('btn-2d');
    const btnCv = document.getElementById('btn-cv');
    const btnEmergency = document.getElementById('btn-emergency');
    
    let junctionDataCache = {};
    let emergencyActive = false;
    
    // 1. Initialize Dashboard
    async function initDashboard() {
        try {
            
            // Populate Sidebar with Roads
            navItemsList.innerHTML = '';
            const roads = ['North', 'South', 'East', 'West'];
            roads.forEach((road, idx) => {
                const j_id = idx + 1;
                junctionDataCache[road] = road;
                
                const li = document.createElement('li');
                li.className = `nav-item ${j_id === currentJunctionId ? 'active' : ''}`;
                li.innerHTML = `<span class="nav-text">${road} Road</span>`;
                li.dataset.road = road;
                
                // Click handler
                li.addEventListener('click', () => {
                    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
                    li.classList.add('active');
                    currentJunctionId = road; // using string name directly now
                    updateDashboard();
                });
                
                navItemsList.appendChild(li);
            });
            currentJunctionId = 'North';

            // Start polling loop
            updateDashboard();
            setInterval(updateDashboard, 5000); // Poll every 5 seconds for simulation
            
        } catch (error) {
            console.error("Failed to initialize dashboard:", error);
            junctionStatusEl.innerText = "System Offline - Backend Error";
            junctionStatusEl.style.color = "var(--accent-red)";
        }
    }

    // 2. Fetch Data and Update UI
    async function updateDashboard() {
        if (!currentJunctionId) return;

        // Update Text
        junctionNameEl.innerText = `${currentJunctionId} Road Control`;

        // Fetch Metrics Data
        try {
            const response = await fetch(`${API_BASE}/api/status`);
            const data = await response.json();
            
            const stats = {
                cars: data.controller.vehicle_counts[currentJunctionId],
                green_time: data.controller.calculated_green_times[currentJunctionId],
                active: data.engine.active_road === currentJunctionId,
                engine_state: data.engine.state,
                time_left: data.engine.time_left
            };

            const cv_running = data.cv_active;
            const pText = document.getElementById('camera-feed-placeholder');
            const feedImg = document.getElementById('live-cv-feed');
            
            if (btnCv) {
                btnCv.textContent = cv_running ? 'CV Core: ON' : 'CV Core: OFF';
            }

            if (cv_running) {
                pText.innerText = "CV Engine Running...";
                if (feedImg && feedImg.style.display === 'none') {
                    feedImg.src = `${API_BASE}/api/video_feed?` + new Date().getTime();
                    feedImg.style.display = 'block';
                }
            } else {
                pText.innerText = "A.I. CAMERA FEED OFFLINE";
                if (feedImg) {
                    feedImg.style.display = 'none';
                    feedImg.removeAttribute('src');
                }
            }

            if (stats.active) {
                junctionStatusEl.innerText = `🚦 ${stats.engine_state} LIGHT (${stats.time_left}s remaining)`;
                if (stats.engine_state === "GREEN") delayAmount.innerText = 0;
            } else {
                junctionStatusEl.innerText = `🛑 RED LIGHT (Queue: ${stats.cars} vehicles)`;
            }

            // Update delay approximation
            if (!stats.active) {
                animateValue(delayAmount, parseFloat(delayAmount.innerText) || 0, stats.green_time, 500);
            }
                
            // Update Progress Bar
            let progress_percent = Math.min(100, (stats.cars / 20) * 100);
            congestionFill.style.width = `${progress_percent}%`;
                
            // Change color based on severity
            if (progress_percent > 70) {
                congestionFill.style.background = 'linear-gradient(90deg, var(--accent-yellow), var(--accent-red))';
                congestionFill.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.6)';
            } else if (progress_percent > 40) {
                congestionFill.style.background = 'linear-gradient(90deg, var(--accent-green), var(--accent-yellow))';
                congestionFill.style.boxShadow = '0 0 10px rgba(245, 158, 11, 0.5)';
            } else {
                congestionFill.style.background = 'linear-gradient(90deg, #34d399, var(--accent-green))';
                congestionFill.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.4)';
            }
        } catch (error) {
            console.error("Error fetching metrics:", error);
        }
    }

    // 3. Launch Endpoints
    async function launchSim(type) {
        try {
            const res = await fetch(`${API_BASE}/api/launch/${type}`, { method: 'POST' });
            if (!res.ok) console.error('Launch failed:', type, res.status);
            await updateDashboard();
        } catch (e) { console.error(e); }
    }
    

    btn2d.addEventListener('click', () => launchSim('2d_sandbox'));
    btnCv.addEventListener('click', () => launchSim('cv_processor'));

    if (btnEmergency) {
        btnEmergency.addEventListener('click', async () => {
            emergencyActive = !emergencyActive;
            try {
                const res = await fetch(`${API_BASE}/api/override`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ 
                        road: currentJunctionId, 
                        status: emergencyActive 
                    })
                });
                if (res.ok) {
                    btnEmergency.style.background = emergencyActive ? 'var(--status-critical)' : 'rgba(255, 23, 68, 0.1)';
                    btnEmergency.style.color = emergencyActive ? '#fff' : 'var(--status-critical)';
                    btnEmergency.textContent = emergencyActive ? '🚨 OVERRIDE ACTIVE' : 'EMERGENCY OVERRIDE';
                    updateDashboard();
                }
            } catch (e) {
                console.error("Emergency override failed:", e);
            }
        });
    }

    // Utility: Animate Number Counter
    function animateValue(obj, start, end, duration) {
        let startTimestamp = null;
        const step = (timestamp) => {
            if (!startTimestamp) startTimestamp = timestamp;
            const progress = Math.min((timestamp - startTimestamp) / duration, 1);
            // Ease out quad
            const easeProgress = progress * (2 - progress);
            const currentVal = (easeProgress * (end - start) + start).toFixed(1);
            obj.innerHTML = currentVal;
            if (progress < 1) {
                window.requestAnimationFrame(step);
            } else {
                obj.innerHTML = end.toFixed(1);
            }
        };
        window.requestAnimationFrame(step);
    }

    // Start App
    initDashboard();
});
