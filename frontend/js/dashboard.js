async function loadDashboard() {
    try {
        const res = await fetch('/api/hourly');
        const data = await res.json();

        if (!data.length) {
            document.querySelector('.chart-container').innerHTML =
                '<div class="overlay-status">No data yet. Start monitoring on Live View.</div>';
            return;
        }

        const hours = data.map(d => (d.hour.split(' ')[1] || d.hour).substring(0, 5));
        const avg = data.map(d => d.avg || 0);
        const maxVals = data.map(d => d.max || 0);
        const uniqueFaces = data.map(d => d.unique_faces || 0);
        const faceApps = data.map(d => d.face_appearances || 0);

        const overallAvg = avg.reduce((a, b) => a + b, 0) / avg.length;
        const peak = Math.max(...maxVals);
        const total = data.reduce((s, d) => s + (d.total || 0), 0);
        const totalUnique = uniqueFaces.length ? Math.max(...uniqueFaces) : 0;
        const peakUnique = uniqueFaces.length ? Math.max(...uniqueFaces) : 0;
        const totalFaceApps = faceApps.reduce((a, b) => a + b, 0);

        document.getElementById('avgCount').textContent = overallAvg.toFixed(1);
        document.getElementById('peakCount').textContent = peak;
        document.getElementById('totalPeople').textContent = total;
        document.getElementById('totalUniqueFaces').textContent = totalUnique;
        document.getElementById('peakUniqueFaces').textContent = peakUnique;
        document.getElementById('totalFaceAppearances').textContent = totalFaceApps;

        new Chart(document.getElementById('hourlyChart'), {
            type: 'bar',
            data: {
                labels: hours,
                datasets: [
                    {
                        label: 'Avg People',
                        data: avg,
                        backgroundColor: 'rgba(99, 102, 241, 0.5)',
                        borderColor: '#6366f1',
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: 'Max People',
                        data: maxVals,
                        backgroundColor: 'rgba(239, 68, 68, 0.5)',
                        borderColor: '#ef4444',
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                    {
                        label: 'Unique Faces',
                        data: uniqueFaces,
                        backgroundColor: 'rgba(34, 197, 94, 0.5)',
                        borderColor: '#22c55e',
                        borderWidth: 1,
                        borderRadius: 4,
                    },
                ],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { labels: { color: '#9ca3af' } },
                },
                scales: {
                    x: { ticks: { color: '#6b7280' }, grid: { color: 'rgba(99, 102, 241, 0.06)' } },
                    y: {
                        beginAtZero: true,
                        ticks: { color: '#6b7280', stepSize: 1 },
                        grid: { color: 'rgba(99, 102, 241, 0.06)' },
                    },
                },
            },
        });

        const tbody = document.getElementById('tableBody');
        data.forEach(d => {
            const tr = document.createElement('tr');
            const time = (d.hour.split(' ')[1] || d.hour).substring(0, 5);
            tr.innerHTML = `<td>${time}</td><td>${d.avg || 0}</td><td>${d.max || 0}</td><td>${d.total || 0}</td><td>${d.unique_faces || 0}</td><td>${d.face_appearances || 0}</td>`;
            tbody.appendChild(tr);
        });
    } catch (err) {
        document.querySelector('.chart-container').innerHTML =
            '<div class="overlay-status" style="color:var(--danger);">Failed to load data. Is the backend running?</div>';
    }
}

loadDashboard();
