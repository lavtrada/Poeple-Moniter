const empName = document.getElementById('empName');
const empEmail = document.getElementById('empEmail');
const empDepartment = document.getElementById('empDepartment');
const registerBtn = document.getElementById('registerBtn');
const registerStatus = document.getElementById('registerStatus');
const faceCaptureSection = document.getElementById('faceCaptureSection');
const captureVideo = document.getElementById('captureVideo');
const captureStatus = document.getElementById('captureStatus');
const captureBtn = document.getElementById('captureBtn');
const doneBtn = document.getElementById('doneBtn');
const previewList = document.getElementById('previewList');
const trainProgress = document.getElementById('trainProgress');
const progressFill = document.getElementById('progressFill');

let currentEmpId = null;
let capturedImages = [];
let captureStream = null;

registerBtn.addEventListener('click', async () => {
    const name = empName.value.trim();
    if (!name) {
        registerStatus.textContent = 'Please enter employee name';
        registerStatus.style.cssText = 'color:var(--danger);';
        return;
    }

    registerBtn.disabled = true;
    registerStatus.textContent = 'Registering...';
    registerStatus.style.cssText = 'color:var(--text-muted);';

    try {
        const res = await fetch('/api/employees', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                name: name,
                email: empEmail.value.trim(),
                department: empDepartment.value.trim()
            })
        });
        const data = await res.json();
        if (res.ok) {
            currentEmpId = data.id;
            registerStatus.textContent = `Registered! ID: ${data.id}. Now capture face samples.`;
            registerStatus.style.cssText = 'color:var(--primary);';
            faceCaptureSection.style.display = 'block';
            faceCaptureSection.scrollIntoView({ behavior: 'smooth' });
            startCaptureCamera();
        } else {
            registerStatus.textContent = 'Error: ' + (data.error || 'Unknown error');
            registerStatus.style.cssText = 'color:var(--danger);';
            registerBtn.disabled = false;
        }
    } catch (err) {
        registerStatus.textContent = 'Error: ' + err.message;
        registerStatus.style.cssText = 'color:var(--danger);';
        registerBtn.disabled = false;
    }
});

function startCaptureCamera() {
    navigator.mediaDevices.getUserMedia({video: {width: 320, height: 240}})
        .then(stream => {
            captureStream = stream;
            captureVideo.srcObject = stream;
            captureStatus.textContent = 'Camera ready';
            captureBtn.disabled = false;
        })
        .catch(err => {
            captureStatus.textContent = 'Camera error: ' + err.message;
            captureStatus.style.cssText = 'color:var(--danger);';
        });
}

captureBtn.addEventListener('click', () => {
    if (!captureStream) return;

    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 240;
    canvas.getContext('2d').drawImage(captureVideo, 0, 0);

    const dataUrl = canvas.toDataURL('image/jpeg');
    const index = capturedImages.length;
    capturedImages.push(dataUrl);

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
        capturedImages.splice(idx, 1);
        div.remove();
        refreshPreviewIndices();
        captureBtn.textContent = `Capture (${capturedImages.length})`;
        doneBtn.disabled = capturedImages.length < 3;
    });
    previewList.appendChild(div);

    captureBtn.textContent = `Capture (${capturedImages.length})`;
    if (capturedImages.length >= 3) {
        doneBtn.disabled = false;
    }
});

function refreshPreviewIndices() {
    const items = previewList.querySelectorAll('.preview-item');
    items.forEach((item, i) => {
        item.dataset.index = i;
        item.querySelector('span').textContent = `#${i + 1}`;
        item.querySelector('.preview-remove').dataset.index = i;
    });
}

doneBtn.addEventListener('click', async () => {
    if (capturedImages.length < 3) {
        alert('Capture at least 3 face samples');
        return;
    }

    doneBtn.disabled = true;
    trainProgress.style.display = 'block';
    progressFill.style.width = '0%';

    try {
        const res = await fetch(`/api/employees/${currentEmpId}/faces`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({images: capturedImages})
        });
        const data = await res.json();
        if (res.ok) {
            progressFill.style.width = '100%';
            setTimeout(() => {
                alert(`Done! ${data.count} face samples added and model trained.`);
                window.location.href = '/employees';
            }, 500);
        } else {
            alert('Error: ' + (data.error || 'Upload failed'));
            doneBtn.disabled = false;
        }
    } catch (err) {
        alert('Error: ' + err.message);
        doneBtn.disabled = false;
    }
});

window.addEventListener('beforeunload', () => {
    if (captureStream) {
        captureStream.getTracks().forEach(t => t.stop());
    }
});
