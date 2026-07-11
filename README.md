# People Counter / People Monitor

Real-time people counting and monitoring system using computer vision (OpenCV). Tracks people in frame, recognizes registered employees via face recognition, monitors phone usage, and logs attendance.

## Features

- Live people detection (HOG + SVM)
- Face recognition for employee identification
- Phone usage detection
- Activity monitoring
- Attendance tracking
- Daily summaries
- Dashboard with hourly trends
- IP camera / mobile phone camera support

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt
python app.py
```

Server runs at `http://localhost:5000`

### Camera Config

- **Local webcam**: Default (index 0)
- **Mobile phone camera**: Install IP Webcam app on phone, start server, paste the RTSP/HTTP URL in the camera config modal on the live page.

## Tech Stack

- **Backend**: Flask, Flask-SocketIO, OpenCV
- **Frontend**: HTML, CSS, JavaScript, Chart.js
- **Database**: SQLite
