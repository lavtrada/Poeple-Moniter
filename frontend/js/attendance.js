let chart = null;

function loadData() {
    fetch('/api/activity')
        .then(r => r.json())
        .then(data => {
            const summary = data.summary || {};
            document.getElementById('totalEmployees').textContent = summary.total_employees || 0;
            document.getElementById('presentToday').textContent = summary.present_count || 0;
            document.getElementById('phoneUsageToday').textContent = summary.phone_usage_count || 0;

            const attendance = data.attendance || [];
            const tbody = document.getElementById('attendanceTableBody');
            if (attendance.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted);">No attendance data for today</td></tr>';
            } else {
                tbody.innerHTML = attendance.map(a => {
                    const statusClass = a.status === 'present' ? 'status-present' : 'status-absent';
                    const checkIn = a.check_in ? new Date(a.check_in).toLocaleTimeString() : '-';
                    const checkOut = a.check_out ? new Date(a.check_out).toLocaleTimeString() : 'Still here';
                    return `<tr>
                        <td>${a.name}</td>
                        <td>${a.department || '-'}</td>
                        <td>${checkIn}</td>
                        <td>${checkOut}</td>
                        <td><span class="status-badge ${statusClass}">${a.status}</span></td>
                    </tr>`;
                }).join('');
            }

            updateChart(attendance);
            loadActivityLog();
        })
        .catch(() => {
            document.getElementById('attendanceTableBody').innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--danger);">Error loading data</td></tr>';
        });
}

function updateChart(attendance) {
    const present = attendance.filter(a => a.status === 'present').length;
    const absent = attendance.filter(a => a.status === 'absent').length + attendance.filter(a => !a.status).length;

    if (chart) chart.destroy();

    const ctx = document.getElementById('attendanceChart').getContext('2d');
    chart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Present', 'Absent'],
            datasets: [{
                data: [present, absent],
                backgroundColor: ['#6366f1', 'rgba(99, 102, 241, 0.12)'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            cutout: '70%',
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#9ca3af', padding: 16, usePointStyle: true, pointStyle: 'circle' }
                },
                title: {
                    display: true,
                    text: `Today's Attendance (${present} Present)`,
                    color: '#f0f0f5',
                    font: { size: 16, weight: '600' }
                }
            }
        }
    });
}

function loadActivityLog() {
    const tbody = document.getElementById('activityTableBody');
    fetch('/api/employees')
        .then(r => r.json())
        .then(employees => {
            if (employees.length === 0) {
                tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">No employees registered</td></tr>';
                return;
            }
            let allLogs = [];
            let promises = employees.map(emp =>
                fetch(`/api/activity/${emp.id}`)
                    .then(r => r.json())
                    .then(logs => {
                        logs.forEach(l => {
                            allLogs.push({...l, name: emp.name, emp_id: emp.id});
                        });
                    })
            );
            return Promise.all(promises).then(() => {
                allLogs.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
                allLogs = allLogs.slice(0, 50);

                if (allLogs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">No activity logs yet</td></tr>';
                    return;
                }

                tbody.innerHTML = allLogs.map(log => {
                    const time = new Date(log.timestamp).toLocaleTimeString();
                    const activityClass = log.activity === 'phone' ? 'activity-badge-phone'
                        : 'activity-badge-' + log.activity;
                    const activityLabel = log.activity.charAt(0).toUpperCase() + log.activity.slice(1);
                    return `<tr>
                        <td>${time}</td>
                        <td>${log.name}</td>
                        <td><span class="activity-badge ${activityClass}">${activityLabel}</span></td>
                        <td>${Math.round(log.confidence * 100)}%</td>
                    </tr>`;
                }).join('');
            });
        })
        .catch(() => {
            tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--danger);">Error loading activity</td></tr>';
        });
}

loadData();
setInterval(loadData, 15000);
