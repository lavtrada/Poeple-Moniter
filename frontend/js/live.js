const socket = io('http://localhost:5000');
const videoFeed = document.getElementById('videoFeed');
const currentCount = document.getElementById('currentCount');
const knownFaces = document.getElementById('knownFaces');
const totalFaces = document.getElementById('totalFaces');
const presentToday = document.getElementById('presentToday');
const phoneAlerts = document.getElementById('phoneAlerts');
const lastUpdated = document.getElementById('lastUpdated');
const statusText = document.getElementById('statusText');
const liveDot = document.getElementById('liveDot');
const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const personsList = document.getElementById('personsList');
const personsCount = document.getElementById('personsCount');
const cameraConfigBtn = document.getElementById('cameraConfigBtn');
const cameraModal = document.getElementById('cameraModal');
const modalClose = document.getElementById('modalClose');
const cameraType = document.getElementById('cameraType');
const cameraSource = document.getElementById('cameraSource');
const saveCameraConfig = document.getElementById('saveCameraConfig');

function getInitials(name) {
    return name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() || '?';
}

socket.on('connect', () => {
    statusText.textContent = 'Connected. Click Start to monitor.';
    liveDot.className = 'live-dot inactive';
});

socket.on('disconnect', () => {
    statusText.textContent = 'Disconnected from server';
    liveDot.className = 'live-dot inactive';
});

socket.on('video_frame', (data) => {
    videoFeed.src = 'data:image/jpeg;base64,' + data.frame;
    currentCount.textContent = data.count;
    knownFaces.textContent = data.known_faces || 0;
    totalFaces.textContent = data.total_faces || 0;
    lastUpdated.textContent = data.timestamp;

    if (data.summary) {
        presentToday.textContent = data.summary.present_count || 0;
        phoneAlerts.textContent = data.summary.phone_usage_count || 0;
    }

    if (data.persons && data.persons.length > 0) {
        let html = '';
        data.persons.forEach(p => {
            const name = p.employee_name || 'Unknown';
            const activity = p.activity || 'unknown';
            const phone = p.phone_usage;
            const activityClass = phone ? 'activity-phone' : 'activity-' + activity;
            const initials = getInitials(name);
            const activityLabel = phone ? 'On Phone' : activity.charAt(0).toUpperCase() + activity.slice(1);
            html += `<div class="person-item ${activityClass}">
                <div class="person-avatar">${initials}</div>
                <div class="person-info">
                    <div class="person-name">${name}</div>
                    <div class="person-activity">${activityLabel}</div>
                </div>
            </div>`;
        });
        personsList.innerHTML = html;
        personsCount.textContent = data.persons.length;
    } else {
        personsList.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:12px 0;text-align:center;">No persons detected</div>';
        personsCount.textContent = '0';
    }

    if (statusText.textContent === 'Starting camera...') {
        statusText.textContent = 'Monitoring active';
        liveDot.className = 'live-dot';
    }
});

socket.on('error', (data) => {
    statusText.textContent = 'Error: ' + data.message;
    liveDot.className = 'live-dot inactive';
});

startBtn.addEventListener('click', () => {
    socket.emit('start');
    startBtn.disabled = true;
    stopBtn.disabled = false;
    statusText.textContent = 'Starting camera...';
    liveDot.className = 'live-dot inactive';
});

stopBtn.addEventListener('click', () => {
    socket.emit('stop');
    startBtn.disabled = false;
    stopBtn.disabled = true;
    videoFeed.src = '';
    statusText.textContent = 'Monitoring stopped';
    liveDot.className = 'live-dot inactive';
    currentCount.textContent = '0';
    knownFaces.textContent = '0';
    totalFaces.textContent = '0';
    personsList.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:12px 0;text-align:center;">Monitoring stopped</div>';
    personsCount.textContent = '0';
});

cameraConfigBtn.addEventListener('click', () => {
    fetch('/api/camera-config')
        .then(r => r.json())
        .then(config => {
            cameraType.value = config.type || 'local';
            cameraSource.value = String(config.source || 0);
            cameraModal.style.display = 'flex';
        });
});

modalClose.addEventListener('click', () => {
    cameraModal.style.display = 'none';
});

cameraType.addEventListener('change', () => {
    const label = cameraType.value === 'ip' ? 'RTSP URL' : 'Camera Index';
    cameraSource.previousElementSibling.textContent = label;
    cameraSource.placeholder = cameraType.value === 'ip' ? 'rtsp://user:pass@192.168.1.100:554/stream' : '0';
});

saveCameraConfig.addEventListener('click', () => {
    const config = {
        type: cameraType.value,
        source: cameraType.value === 'ip' ? cameraSource.value : parseInt(cameraSource.value) || 0
    };
    fetch('/api/camera-config', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(config)
    }).then(r => r.json()).then(data => {
        alert(data.message);
        cameraModal.style.display = 'none';
    });
});
