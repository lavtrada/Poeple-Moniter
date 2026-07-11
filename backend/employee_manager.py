import cv2
import numpy as np
import sqlite3
import os
import json
from datetime import datetime, date, timedelta

DB_DIR = os.path.join(os.path.dirname(__file__), 'data')
EMPLOYEE_DB = os.path.join(DB_DIR, 'office.db')
FACE_TRAIN_DIR = os.path.join(DB_DIR, 'faces', 'train')
REGISTERED_DIR = os.path.join(DB_DIR, 'faces', 'registered')

os.makedirs(DB_DIR, exist_ok=True)
os.makedirs(FACE_TRAIN_DIR, exist_ok=True)
os.makedirs(REGISTERED_DIR, exist_ok=True)

def init_office_db():
    conn = sqlite3.connect(EMPLOYEE_DB)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute('''CREATE TABLE IF NOT EXISTS employees
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  email TEXT UNIQUE,
                  department TEXT DEFAULT '',
                  photo_path TEXT,
                  registered_at TEXT NOT NULL,
                  active INTEGER DEFAULT 1)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS attendance
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  employee_id INTEGER NOT NULL,
                  date TEXT NOT NULL,
                  check_in TEXT,
                  check_out TEXT,
                  status TEXT DEFAULT 'present',
                  FOREIGN KEY (employee_id) REFERENCES employees(id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS activity_log
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  employee_id INTEGER,
                  timestamp TEXT NOT NULL,
                  activity TEXT NOT NULL,
                  confidence REAL DEFAULT 1.0,
                  FOREIGN KEY (employee_id) REFERENCES employees(id))''')
    conn.execute('''CREATE TABLE IF NOT EXISTS daily_summary
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  date TEXT UNIQUE NOT NULL,
                  total_employees INTEGER DEFAULT 0,
                  present_count INTEGER DEFAULT 0,
                  avg_seated_minutes REAL DEFAULT 0,
                  phone_usage_minutes REAL DEFAULT 0,
                  phone_usage_count INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

class EmployeeManager:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.recognizer = cv2.face.LBPHFaceRecognizer_create()
        self.EMPLOYEE_DB = EMPLOYEE_DB
        self.employee_labels = {}
        self.label_employee = {}
        self.trained = False
        self.load_employees()
        self.train_recognizer()

    def load_employees(self):
        conn = sqlite3.connect(EMPLOYEE_DB)
        rows = conn.execute("SELECT id, name FROM employees WHERE active=1").fetchall()
        conn.close()
        self.employee_labels = {row[0]: row[1] for row in rows}
        self.label_employee = {row[0]: row[0] for row in rows}

    def get_all_employees(self):
        conn = sqlite3.connect(EMPLOYEE_DB)
        rows = conn.execute("SELECT id, name, email, department, registered_at, active FROM employees ORDER BY name").fetchall()
        conn.close()
        return [{'id': r[0], 'name': r[1], 'email': r[2], 'department': r[3], 'registered_at': r[4], 'active': r[5]} for r in rows]

    def get_employee(self, emp_id):
        conn = sqlite3.connect(EMPLOYEE_DB)
        row = conn.execute("SELECT id, name, email, department, photo_path, registered_at, active FROM employees WHERE id=?", (emp_id,)).fetchone()
        conn.close()
        if row:
            return {'id': row[0], 'name': row[1], 'email': row[2], 'department': row[3], 'photo_path': row[4], 'registered_at': row[5], 'active': row[6]}
        return None

    def register_employee(self, name, email='', department='', face_images=None):
        now = datetime.now().isoformat()
        conn = sqlite3.connect(EMPLOYEE_DB)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO employees (name, email, department, registered_at) VALUES (?, ?, ?, ?)",
                      (name, email, department, now))
        emp_id = cursor.lastrowid
        conn.commit()
        conn.close()

        if face_images:
            self.add_face_samples(emp_id, face_images)
        else:
            self.load_employees()
            self.train_recognizer()
        return emp_id

    def extract_face(self, img):
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        if len(faces) > 0:
            x, y, w, h = faces[0]
            padding = 10
            x1, y1 = max(0, x - padding), max(0, y - padding)
            x2, y2 = min(img.shape[1], x + w + padding), min(img.shape[0], y + h + padding)
            return img[y1:y2, x1:x2]
        return None

    def add_face_samples(self, emp_id, face_images):
        emp_dir = os.path.join(FACE_TRAIN_DIR, str(emp_id))
        reg_dir = os.path.join(REGISTERED_DIR, str(emp_id))
        os.makedirs(emp_dir, exist_ok=True)
        os.makedirs(reg_dir, exist_ok=True)
        existing = len([f for f in os.listdir(emp_dir) if f.endswith('.jpg')])
        saved = 0
        for i, img in enumerate(face_images):
            face = self.extract_face(img)
            if face is not None:
                gray = cv2.cvtColor(face, cv2.COLOR_BGR2GRAY)
                gray = cv2.equalizeHist(gray)
                gray = cv2.resize(gray, (100, 100))
                path = os.path.join(emp_dir, f'{existing + saved}.jpg')
                cv2.imwrite(path, gray)
                cv2.imwrite(os.path.join(reg_dir, f'{existing + saved}.jpg'), face)
                saved += 1
        if saved == 0:
            return 0
        if face_images and existing == 0:
            conn = sqlite3.connect(EMPLOYEE_DB)
            first_path = os.path.join(emp_dir, '0.jpg')
            conn.execute("UPDATE employees SET photo_path=? WHERE id=?", (first_path, emp_id))
            conn.commit()
            conn.close()
        self.train_recognizer()
        return saved

    def train_recognizer(self):
        faces = []
        labels = []
        self.employee_labels = {}
        self.label_employee = {}

        conn = sqlite3.connect(EMPLOYEE_DB)
        rows = conn.execute("SELECT id, name FROM employees WHERE active=1").fetchall()
        conn.close()

        for emp_id, name in rows:
            emp_dir = os.path.join(FACE_TRAIN_DIR, str(emp_id))
            if not os.path.isdir(emp_dir):
                continue
            for fname in os.listdir(emp_dir):
                if fname.endswith('.jpg'):
                    img = cv2.imread(os.path.join(emp_dir, fname), cv2.IMREAD_GRAYSCALE)
                    if img is not None:
                        img = cv2.equalizeHist(img)
                        img = cv2.resize(img, (100, 100))
                        faces.append(img)
                        labels.append(emp_id)
            self.employee_labels[emp_id] = name
            self.label_employee[emp_id] = emp_id

        if len(faces) > 0 and len(set(labels)) > 0:
            self.recognizer.train(faces, np.array(labels))
            self.trained = True

    def predict_face(self, face_roi):
        if face_roi.size == 0:
            return None, 0, 'Unknown'
        gray = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        gray = cv2.resize(gray, (100, 100))

        if self.trained:
            label, confidence = self.recognizer.predict(gray)
            if confidence < 90:
                conf_score = max(0, min(100, 100 - confidence))
                name = self.employee_labels.get(label, 'Unknown')
                return label, conf_score, name
        return None, 0, 'Unknown'

    def delete_employee(self, emp_id):
        conn = sqlite3.connect(EMPLOYEE_DB)
        conn.execute("UPDATE employees SET active=0 WHERE id=?", (emp_id,))
        conn.commit()
        conn.close()
        self.load_employees()
        self.train_recognizer()

    def mark_attendance(self, employee_id):
        today = date.today().isoformat()
        now = datetime.now().isoformat()
        conn = sqlite3.connect(EMPLOYEE_DB)
        existing = conn.execute("SELECT id, check_in FROM attendance WHERE employee_id=? AND date=?", (employee_id, today)).fetchone()
        if existing:
            conn.execute("UPDATE attendance SET check_out=? WHERE id=?", (now, existing[0]))
        else:
            conn.execute("INSERT INTO attendance (employee_id, date, check_in, status) VALUES (?, ?, ?, 'present')",
                        (employee_id, today, now))
        conn.commit()
        conn.close()

    def get_today_attendance(self):
        today = date.today().isoformat()
        conn = sqlite3.connect(EMPLOYEE_DB)
        rows = conn.execute("""
            SELECT e.id, e.name, e.department, a.check_in, a.check_out, a.status
            FROM employees e
            LEFT JOIN attendance a ON e.id = a.employee_id AND a.date = ?
            WHERE e.active=1
            ORDER BY a.check_in DESC, e.name
        """, (today,)).fetchall()
        conn.close()
        return [{'id': r[0], 'name': r[1], 'department': r[2], 'check_in': r[3], 'check_out': r[4], 'status': r[5] or 'absent'} for r in rows]

    def log_activity(self, employee_id, activity, confidence=1.0):
        now = datetime.now().isoformat()
        conn = sqlite3.connect(EMPLOYEE_DB)
        conn.execute("INSERT INTO activity_log (employee_id, timestamp, activity, confidence) VALUES (?, ?, ?, ?)",
                    (employee_id, now, activity, confidence))
        conn.commit()
        conn.close()

    def get_employee_activity(self, employee_id, hours=2):
        cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()
        conn = sqlite3.connect(EMPLOYEE_DB)
        rows = conn.execute("""
            SELECT timestamp, activity, confidence FROM activity_log
            WHERE employee_id=? AND timestamp > ?
            ORDER BY timestamp DESC LIMIT 100
        """, (employee_id, cutoff)).fetchall()
        conn.close()
        return [{'timestamp': r[0], 'activity': r[1], 'confidence': r[2]} for r in rows]

    def get_present_employees(self, within_minutes=2):
        recent = (datetime.now() - timedelta(minutes=within_minutes)).isoformat()
        conn = sqlite3.connect(EMPLOYEE_DB)
        rows = conn.execute("""
            SELECT DISTINCT employee_id FROM activity_log
            WHERE timestamp > ? AND activity != 'away'
        """, (recent,)).fetchall()
        conn.close()
        return [r[0] for r in rows]

    def get_daily_summary(self):
        today = date.today().isoformat()
        conn = sqlite3.connect(EMPLOYEE_DB)
        total = conn.execute("SELECT COUNT(*) FROM employees WHERE active=1").fetchone()[0]
        present = conn.execute("SELECT COUNT(DISTINCT employee_id) FROM activity_log WHERE date(timestamp)=? AND activity!='away'", (today,)).fetchone()[0]
        phone_count = conn.execute("""
            SELECT COUNT(DISTINCT employee_id) FROM activity_log
            WHERE date(timestamp)=? AND activity='phone'
        """, (today,)).fetchone()[0]
        phone_logs = conn.execute("""
            SELECT COUNT(*) FROM activity_log
            WHERE date(timestamp)=? AND activity='phone'
        """, (today,)).fetchone()[0]
        seated_logs = conn.execute("""
            SELECT COUNT(*) FROM activity_log
            WHERE date(timestamp)=? AND activity='seated'
        """, (today,)).fetchone()[0]
        conn.close()
        return {
            'total_employees': total,
            'present_count': present,
            'phone_usage_count': phone_count,
            'phone_logs': phone_logs,
            'seated_logs': seated_logs
        }
