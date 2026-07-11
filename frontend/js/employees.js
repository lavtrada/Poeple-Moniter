const tbody = document.getElementById('employeesTableBody');
const faceSamplesSection = document.getElementById('faceSamplesSection');
const sampleEmpName = document.getElementById('sampleEmpName');
const sampleVideo = document.getElementById('sampleVideo');
const sampleCaptureBtn = document.getElementById('sampleCaptureBtn');
const sampleUploadBtn = document.getElementById('sampleUploadBtn');
const sampleCancelBtn = document.getElementById('sampleCancelBtn');
const samplePreviewList = document.getElementById('samplePreviewList');

let sampleStream = null;
let sampleImages = [];
let sampleEmpId = null;

function loadEmployees() {
    fetch('/api/employees')
        .then(r => r.json())
        .then(employees => {
            if (employees.length === 0) {
                tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);">No employees registered yet. <a href="/register" style="color:var(--primary);">Add one</a></td></tr>';
                return;
            }
            tbody.innerHTML = employees.map(emp => `
                <tr>
                    <td><span style="color:var(--text-muted);">${emp.id}</span></td>
                    <td><strong>${emp.name}</strong></td>
                    <td>${emp.email || '<span style="color:var(--text-muted);">-</span>'}</td>
                    <td>${emp.department || '<span style="color:var(--text-muted);">-</span>'}</td>
                    <td><span style="color:var(--text-muted);font-size:12px;">${new Date(emp.registered_at).toLocaleDateString()}</span></td>
                    <td><span class="status-badge ${emp.active ? 'status-active' : 'status-inactive'}">${emp.active ? 'Active' : 'Inactive'}</span></td>
                    <td>
                        <button class="action-btn action-btn-edit" onclick="addFaces(${emp.id}, '${emp.name}')">Faces</button>
                        <button class="action-btn action-btn-delete" onclick="deleteEmp(${emp.id})">Delete</button>
                    </td>
                </tr>
            `).join('');
        })
        .catch(() => {
            tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--danger);">Error loading employees</td></tr>';
        });
}

window.addFaces = function(id, name) {
    sampleEmpId = id;
    sampleEmpName.textContent = name;
    sampleImages = [];
    samplePreviewList.innerHTML = '';
    sampleCaptureBtn.textContent = 'Capture';
    sampleUploadBtn.disabled = true;
    faceSamplesSection.style.display = 'block';
    faceSamplesSection.scrollIntoView({ behavior: 'smooth' });
    startSampleCamera();
};

window.deleteEmp = function(id) {
    if (!confirm('Delete this employee?')) return;
    fetch(`/api/employees/${id}`, {method: 'DELETE'})
        .then(r => r.json())
        .then(() => loadEmployees())
        .catch(() => alert('Delete failed'));
};

function startSampleCamera() {
    if (sampleStream) sampleStream.getTracks().forEach(t => t.stop());
    navigator.mediaDevices.getUserMedia({video: {width: 320, height: 240}})
        .then(stream => {
            sampleStream = stream;
            sampleVideo.srcObject = stream;
            sampleCaptureBtn.disabled = false;
        })
        .catch(err => alert('Camera error: ' + err.message));
}

sampleCaptureBtn.addEventListener('click', () => {
    if (!sampleStream) return;
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 240;
    canvas.getContext('2d').drawImage(sampleVideo, 0, 0);
    const dataUrl = canvas.toDataURL('image/jpeg');
    const index = sampleImages.length;
    sampleImages.push(dataUrl);
    const div = document.createElement('div');
    div.className = 'preview-item';
    div.dataset.index = index;
    div.innerHTML = `
        <img src="${dataUrl}">
        <button class="preview-remove" data-index="${index}">&times;</button>
        <span>#${index + 1}</span>
    `;
    div.querySelector('.preview-remove').addEventListener('click', (e) => {
        e.stopPropagation();
        const idx = parseInt(div.dataset.index);
        sampleImages.splice(idx, 1);
        div.remove();
        const items = samplePreviewList.querySelectorAll('.preview-item');
        items.forEach((item, i) => {
            item.dataset.index = i;
            item.querySelector('span').textContent = `#${i + 1}`;
        });
        sampleCaptureBtn.textContent = `Capture (${sampleImages.length})`;
        sampleUploadBtn.disabled = sampleImages.length < 1;
    });
    samplePreviewList.appendChild(div);
    sampleCaptureBtn.textContent = `Capture (${sampleImages.length})`;
    if (sampleImages.length >= 1) sampleUploadBtn.disabled = false;
});

sampleUploadBtn.addEventListener('click', async () => {
    if (sampleImages.length === 0) return;
    sampleUploadBtn.disabled = true;
    try {
        const res = await fetch(`/api/employees/${sampleEmpId}/faces`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({images: sampleImages})
        });
        const data = await res.json();
        if (res.ok) {
            alert(`${data.count} samples added!`);
            faceSamplesSection.style.display = 'none';
            if (sampleStream) sampleStream.getTracks().forEach(t => t.stop());
            loadEmployees();
        } else {
            alert('Error: ' + (data.error || 'Failed'));
            sampleUploadBtn.disabled = false;
        }
    } catch (err) {
        alert('Error: ' + err.message);
        sampleUploadBtn.disabled = false;
    }
});

sampleCancelBtn.addEventListener('click', () => {
    faceSamplesSection.style.display = 'none';
    if (sampleStream) sampleStream.getTracks().forEach(t => t.stop());
});

loadEmployees();
