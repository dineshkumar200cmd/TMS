document.addEventListener('DOMContentLoaded', () => {
    // State Management
    let currentJunctionId = 1; // Default to first junction
    let currentTimeframe = 0;  // Default time step
    
    // DOM Elements
    const navItemsList = document.getElementById('nav-items');
    const cameraFeed = document.getElementById('camera-feed');
    const delayAmount = document.getElementById('delay-amount');
    const congestionFill = document.getElementById('congestion-fill');
    const junctionNameEl = document.getElementById('current-junction-name');
    const junctionStatusEl = document.getElementById('current-junction-status');
    const timeframeBtns = document.querySelectorAll('.toggle-btn');
    
    let junctionDataCache = {};
    
    // 1. Initialize Dashboard
    async function initDashboard() {
        try {
            // Fetch list of junctions
            const response = await fetch('http://127.0.0.1:5001/api/junctions');
            const junctions = await response.json();
            
            // Populate Sidebar
            navItemsList.innerHTML = '';
            junctions.forEach(j => {
                junctionDataCache[j.id] = j.name;
                
                const li = document.createElement('li');
                li.className = `nav-item ${j.id === currentJunctionId ? 'active' : ''}`;
                li.innerHTML = `
                    <span class="nav-text">${j.name}</span>
                `;
                li.dataset.id = j.id;
                
                // Click handler
                li.addEventListener('click', () => {
                    document.querySelectorAll('.nav-item').forEach(el => el.classList.remove('active'));
                    li.classList.add('active');
                    currentJunctionId = j.id;
                    updateDashboard();
                });
                
                navItemsList.appendChild(li);
            });

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
        const name = junctionDataCache[currentJunctionId] || `Zone ${currentJunctionId}`;
        junctionNameEl.innerText = name;
        junctionStatusEl.innerText = `Monitoring Live Traffic Feed at T=${currentTimeframe}s`;

        // Update Image
        // Append a timestamp to prevent browser caching
        const imgUrl = `http://127.0.0.1:5001/api/image/${currentTimeframe}/${currentJunctionId}?t=${new Date().getTime()}`;
        
        // Add a slight fade effect by resetting opacity
        cameraFeed.style.opacity = 0.5;
        cameraFeed.src = imgUrl;
        cameraFeed.onload = () => { cameraFeed.style.opacity = 1; };
        
        // Fetch Metrics Data
        try {
            const response = await fetch(`http://127.0.0.1:5001/api/data/${currentTimeframe}`);
            const data = await response.json();
            
            if (data[currentJunctionId]) {
                const stats = data[currentJunctionId];
                
                // Animate Numbers
                animateValue(delayAmount, parseFloat(delayAmount.innerText) || 0, stats.duration_mins, 500);
                
                // Update Progress Bar
                congestionFill.style.width = `${stats.progress_percent}%`;
                
                // Change color based on severity
                if (stats.progress_percent > 70) {
                    congestionFill.style.background = 'linear-gradient(90deg, var(--accent-yellow), var(--accent-red))';
                    congestionFill.style.boxShadow = '0 0 15px rgba(239, 68, 68, 0.6)';
                } else if (stats.progress_percent > 40) {
                    congestionFill.style.background = 'linear-gradient(90deg, var(--accent-green), var(--accent-yellow))';
                    congestionFill.style.boxShadow = '0 0 10px rgba(245, 158, 11, 0.5)';
                } else {
                    congestionFill.style.background = 'linear-gradient(90deg, #34d399, var(--accent-green))';
                    congestionFill.style.boxShadow = '0 0 10px rgba(16, 185, 129, 0.4)';
                }
            }
        } catch (error) {
            console.error("Error fetching metrics:", error);
        }
    }

    // 3. Timeframe Toggle Logic
    timeframeBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            timeframeBtns.forEach(b => b.classList.remove('active'));
            const targetBtn = e.currentTarget;
            targetBtn.classList.add('active');
            
            currentTimeframe = parseInt(targetBtn.dataset.time, 10);
            updateDashboard(); // Immediate update on switch
        });
    });

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
