import cv2
import numpy as np
import time
from datetime import datetime
from employee_manager import EmployeeManager

class FaceTracker:
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )
        self.emp_manager = EmployeeManager()
        self.recognized_faces = {}
        self.recognition_cooldown = 2.0
        self.last_recognition_time = {}

    def detect_faces(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))
        return faces

    def process_frame(self, frame):
        faces = self.detect_faces(frame)
        face_results = []

        for (x, y, w, h) in faces:
            padding = 15
            x1, y1 = max(0, x - padding), max(0, y - padding)
            x2, y2 = min(frame.shape[1], x + w + padding), min(frame.shape[0], y + h + padding)
            face_roi = frame[y1:y2, x1:x2]
            if face_roi.size == 0:
                continue

            emp_id, confidence, name = self.emp_manager.predict_face(face_roi)
            known = emp_id is not None

            if known:
                now = time.time()
                if emp_id not in self.last_recognition_time or now - self.last_recognition_time[emp_id] > self.recognition_cooldown:
                    self.emp_manager.mark_attendance(emp_id)
                    self.last_recognition_time[emp_id] = now
                    self.recognized_faces[emp_id] = {'name': name, 'last_seen': now}

            face_results.append({
                'box': (x, y, w, h),
                'employee_id': emp_id,
                'name': name,
                'known': known,
                'confidence': confidence
            })

        return face_results

    def draw_faces(self, frame, face_results):
        for fr in face_results:
            x, y, w, h = fr['box']
            known = fr['known']
            name = fr['name']
            conf = fr['confidence']

            if known:
                color = (0, 255, 0)
                label = f'{name} ({conf:.0f}%)'
            else:
                color = (0, 165, 255)
                label = 'Unknown'

            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, label, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

    def draw_activity(self, frame, person_info):
        if person_info is None:
            return
        box = person_info.get('box')
        if box is None:
            return
        x, y, w, h = box
        activity = person_info.get('activity', '')
        phone = person_info.get('phone_usage', False)
        name = person_info.get('employee_name', '')

        activity_color = (100, 200, 255)
        if phone:
            activity_color = (0, 0, 255)

        activity_label = activity.upper()
        if phone:
            activity_label += ' [PHONE]'

        cv2.putText(frame, activity_label, (x, y + h + 15),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, activity_color, 1)

    def get_stats(self):
        return self.emp_manager.get_daily_summary()
