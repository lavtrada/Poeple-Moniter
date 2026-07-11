import cv2
import base64
import threading
import time
import sqlite3
import os
import json
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
from face_tracker import FaceTracker
from employee_manager import EmployeeManager, init_office_db
import numpy as np
from activity_monitor import PhoneDetector, ActivityMonitor

app = Flask(__name__, static_folder='../frontend', static_url_path='')
app.config['SECRET_KEY'] = 'people-counter-secret'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

DB_DIR = os.path.join(os.path.dirname(__file__), 'data')
DB_PATH = os.path.join(DB_DIR, 'counts.db')
CAMERA_CONFIG_PATH = os.path.join(DB_DIR, 'camera_config.json')
os.makedirs(DB_DIR, exist_ok=True)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''CREATE TABLE IF NOT EXISTS counts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  timestamp TEXT NOT NULL,
                  count INTEGER NOT NULL)''')
    conn.commit()
    conn.close()

def save_count(timestamp, count):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO counts (timestamp, count) VALUES (?, ?)",
                 (timestamp.isoformat(), count))
    conn.commit()
    conn.close()

def get_hourly_counts():
    conn = sqlite3.connect(DB_PATH)
    cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
    rows = conn.execute("""
        SELECT strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
               ROUND(AVG(count), 1) as avg_count,
               MAX(count) as max_count,
               SUM(count) as total_count
        FROM counts
        WHERE timestamp > ?
        GROUP BY strftime('%Y-%m-%d %H:00', timestamp)
        ORDER BY hour
    """, (cutoff,)).fetchall()
    conn.close()
    return [{'hour': r[0], 'avg': r[1], 'max': r[2], 'total': r[3]} for r in rows]

def load_camera_config():
    if os.path.exists(CAMERA_CONFIG_PATH):
        with open(CAMERA_CONFIG_PATH, 'r') as f:
            return json.load(f)
    return {'source': 0, 'type': 'local'}

def save_camera_config(config):
    with open(CAMERA_CONFIG_PATH, 'w') as f:
        json.dump(config, f)

init_office_db()

hog = cv2.HOGDescriptor()
hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())

face_tracker = FaceTracker()
emp_manager = face_tracker.emp_manager
phone_detector = PhoneDetector()
activity_monitor = ActivityMonitor()

camera = None
running = False
last_save_time = 0
last_activity_log_time = 0
last_summary_time = 0

def open_camera():
    global camera
    config = load_camera_config()
    source = config.get('source', 0)
    if config.get('type') == 'ip':
        camera = cv2.VideoCapture(source)
    else:
        try:
            camera = cv2.VideoCapture(int(source))
        except (ValueError, TypeError):
            camera = cv2.VideoCapture(0)
    return camera

def process_camera():
    global camera, running, last_save_time, last_activity_log_time, last_summary_time

    camera = open_camera()
    if not camera or not camera.isOpened():
        socketio.emit('error', {'message': 'Failed to access camera. Check camera config.'})
        return

    running = True
    while running:
        ret, frame = camera.read()
        if not ret:
            continue

        boxes, _ = hog.detectMultiScale(frame, winStride=(8, 8), padding=(4, 4), scale=1.05)
        people_count = len(boxes)

        face_results = face_tracker.process_frame(frame)

        person_detections = []
        for (x, y, w, h) in boxes:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            emp_id = None
            emp_name = 'Unknown'
            for fr in face_results:
                fx, fy, fw, fh = fr['box']
                if abs(fx - x) < w and abs(fy - y) < h:
                    emp_id = fr['employee_id']
                    emp_name = fr['name']
                    break
            person_detections.append({
                'box': (x, y, w, h),
                'employee_id': emp_id,
                'employee_name': emp_name
            })

        current_ids = activity_monitor.track_persons(person_detections)
        now = time.time()

        for pid in current_ids:
            pinfo = activity_monitor.get_person_info(pid)
            if pinfo:
                has_phone = phone_detector.detect(frame, pinfo['box'])
                activity_monitor.update_phone_usage(pid, has_phone)

                if pinfo['employee_id'] and now - last_activity_log_time >= 10:
                    emp_manager.log_activity(
                        pinfo['employee_id'],
                        'phone' if has_phone else pinfo['activity'],
                        0.8 if has_phone else pinfo['activity_confidence'] / 100
                    )

        if now - last_activity_log_time >= 10:
            last_activity_log_time = now

        if now - last_save_time >= 5:
            save_count(datetime.now(), people_count)
            last_save_time = now

        if now - last_summary_time >= 60:
            summary = emp_manager.get_daily_summary()
            conn = sqlite3.connect(emp_manager.EMPLOYEE_DB)
            try:
                conn.execute("""INSERT OR REPLACE INTO daily_summary
                    (date, total_employees, present_count, phone_usage_count, phone_usage_minutes, avg_seated_minutes)
                    VALUES (date('now'), ?, ?, ?, ?, ?)""",
                    (summary['total_employees'], summary['present_count'],
                     summary['phone_usage_count'], summary['phone_logs'] * 0.17, 0))
                conn.commit()
            except:
                pass
            conn.close()
            last_summary_time = now

        face_tracker.draw_faces(frame, face_results)

        for pid in current_ids:
            pinfo = activity_monitor.get_person_info(pid)
            if pinfo:
                face_tracker.draw_activity(frame, pinfo)

        info_y = 30
        cv2.putText(frame, f'People: {people_count}', (10, info_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        faces_known = sum(1 for f in face_results if f['known'])
        cv2.putText(frame, f'Known: {faces_known}', (10, info_y + 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)

        _, buffer = cv2.imencode('.jpg', frame)
        frame_b64 = base64.b64encode(buffer).decode('utf-8')

        person_list = []
        for pid in current_ids:
            pinfo = activity_monitor.get_person_info(pid)
            if pinfo:
                person_list.append({
                    'id': pid,
                    'employee_name': pinfo['employee_name'],
                    'employee_id': pinfo['employee_id'],
                    'activity': pinfo['activity'],
                    'phone_usage': pinfo['phone_usage']
                })

        socketio.emit('video_frame', {
            'frame': frame_b64,
            'count': people_count,
            'known_faces': faces_known,
            'total_faces': len(face_results),
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'persons': person_list,
            'summary': emp_manager.get_daily_summary()
        })

        time.sleep(0.033)

    if camera:
        camera.release()

@socketio.on('start')
def handle_start():
    thread = threading.Thread(target=process_camera, daemon=True)
    thread.start()

@socketio.on('stop')
def handle_stop():
    global running
    running = False

@app.route('/api/hourly')
def api_hourly():
    hourly_counts = get_hourly_counts()
    return jsonify(hourly_counts)

@app.route('/api/latest')
def api_latest():
    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT timestamp, count FROM counts ORDER BY id DESC LIMIT 1").fetchone()
    conn.close()
    summary = emp_manager.get_daily_summary()
    return jsonify({'timestamp': row[0] if row else None, 'count': row[1] if row else 0, 'summary': summary})

@app.route('/api/employees', methods=['GET'])
def api_get_employees():
    return jsonify(emp_manager.get_all_employees())

@app.route('/api/employees', methods=['POST'])
def api_add_employee():
    data = request.json
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'error': 'Name is required'}), 400
    email = data.get('email', '')
    department = data.get('department', '')
    emp_id = emp_manager.register_employee(name, email, department)
    return jsonify({'id': emp_id, 'name': name, 'message': 'Employee registered. Capture face samples.'}), 201

@app.route('/api/employees/<int:emp_id>', methods=['GET'])
def api_get_employee(emp_id):
    emp = emp_manager.get_employee(emp_id)
    if emp:
        return jsonify(emp)
    return jsonify({'error': 'Not found'}), 404

@app.route('/api/employees/<int:emp_id>', methods=['DELETE'])
def api_delete_employee(emp_id):
    emp_manager.delete_employee(emp_id)
    return jsonify({'message': 'Employee deleted'})

@app.route('/api/employees/<int:emp_id>/faces', methods=['POST'])
def api_add_face_samples(emp_id):
    data = request.json
    images_b64 = data.get('images', [])
    if not images_b64:
        return jsonify({'error': 'No images provided'}), 400

    emp = emp_manager.get_employee(emp_id)
    if not emp:
        return jsonify({'error': 'Employee not found'}), 404

    face_images = []
    for b64_str in images_b64:
        try:
            img_data = base64.b64decode(b64_str.split(',')[-1])
            nparr = np.frombuffer(img_data, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is not None:
                face_images.append(img)
        except:
            pass

    if not face_images:
        return jsonify({'error': 'No valid images decoded'}), 400

    saved = emp_manager.add_face_samples(emp_id, face_images)
    if saved == 0:
        return jsonify({'error': 'No face detected in captured images. Ensure your face is clearly visible.'}), 400
    return jsonify({'message': f'Added {saved} face samples', 'count': saved})

@app.route('/api/attendance')
def api_attendance():
    return jsonify(emp_manager.get_today_attendance())

@app.route('/api/attendance/<int:employee_id>')
def api_employee_attendance(employee_id):
    conn = sqlite3.connect(emp_manager.EMPLOYEE_DB)
    rows = conn.execute("""
        SELECT date, check_in, check_out, status FROM attendance
        WHERE employee_id=? ORDER BY date DESC LIMIT 30
    """, (employee_id,)).fetchall()
    conn.close()
    return jsonify([{'date': r[0], 'check_in': r[1], 'check_out': r[2], 'status': r[3]} for r in rows])

@app.route('/api/activity')
def api_activity():
    summary = emp_manager.get_daily_summary()
    attendance = emp_manager.get_today_attendance()
    return jsonify({'summary': summary, 'attendance': attendance})

@app.route('/api/activity/<int:employee_id>')
def api_employee_activity(employee_id):
    return jsonify(emp_manager.get_employee_activity(employee_id, hours=4))

@app.route('/api/camera-config', methods=['GET'])
def api_get_camera_config():
    return jsonify(load_camera_config())

@app.route('/api/camera-config', methods=['POST'])
def api_set_camera_config():
    config = request.json
    save_camera_config(config)
    return jsonify({'message': 'Camera config saved. Restart monitoring to apply.'})

@app.route('/')
def serve_index():
    return app.send_static_file('index.html')

@app.route('/register')
def serve_register():
    return app.send_static_file('register.html')

@app.route('/attendance')
def serve_attendance_page():
    return app.send_static_file('attendance.html')

@app.route('/employees')
def serve_employees_page():
    return app.send_static_file('employees.html')

if __name__ == '__main__':
    init_db()
    init_office_db()
    print('Server running at http://localhost:5000')
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
