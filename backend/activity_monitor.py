import cv2
import numpy as np
import time
from collections import defaultdict

class PhoneDetector:
    def __init__(self):
        self.screen_aspect_min = 1.3
        self.screen_aspect_max = 2.5
        self.min_area = 800
        self.max_area = 15000

    def detect_phone_near_person(self, frame, person_box):
        px, py, pw, ph = person_box
        search_x1 = max(0, px - pw // 2)
        search_y1 = max(0, py - ph // 4)
        search_x2 = min(frame.shape[1], px + pw + pw // 2)
        search_y2 = min(frame.shape[0], py + ph)

        roi = frame[search_y1:search_y2, search_x1:search_x2]
        if roi.size == 0:
            return False

        gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        kernel = np.ones((3, 3), np.uint8)
        thresh = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area or area > self.max_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 20 or h < 30:
                continue
            aspect = h / w if w > 0 else 0
            if aspect < 1.0:
                aspect = w / h
            if self.screen_aspect_min <= aspect <= self.screen_aspect_max:
                hull = cv2.convexHull(cnt)
                hull_area = cv2.contourArea(hull)
                if hull_area > 0:
                    solidity = float(area) / hull_area
                    if solidity > 0.7:
                        return True
        return False

    def detect_phone_glow(self, frame, person_box):
        px, py, pw, ph = person_box
        search_x1 = max(0, px - pw // 3)
        search_y1 = max(0, py - ph // 4)
        search_x2 = min(frame.shape[1], px + pw + pw // 3)
        search_y2 = min(frame.shape[0], py + ph)

        roi = frame[search_y1:search_y2, search_x1:search_x2]
        if roi.size == 0:
            return False

        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower_white = np.array([0, 0, 180])
        upper_white = np.array([180, 40, 255])
        mask = cv2.inRange(hsv, lower_white, upper_white)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < self.min_area or area > self.max_area:
                continue
            x, y, w, h = cv2.boundingRect(cnt)
            if w < 15 or h < 25:
                continue
            aspect = h / w if w > 0 else 0
            if aspect < 1.0:
                aspect = w / h
            if 1.2 <= aspect <= 3.0:
                return True
        return False

    def detect(self, frame, person_box):
        return self.detect_phone_near_person(frame, person_box) or self.detect_phone_glow(frame, person_box)


class ActivityMonitor:
    def __init__(self, tracking_timeout=30):
        self.tracking_timeout = tracking_timeout
        self.person_tracks = {}
        self.next_id = 0

    def get_person_center(self, box):
        x, y, w, h = box
        return (x + w // 2, y + h // 2)

    def get_box_area(self, box):
        x, y, w, h = box
        return w * h

    def track_persons(self, detections):
        current_ids = []
        for det in detections:
            box = det['box']
            cx, cy = self.get_person_center(box)
            area = self.get_box_area(box)

            matched_id = None
            best_dist = 10000
            for pid, pdata in list(self.person_tracks.items()):
                if time.time() - pdata['last_seen'] > self.tracking_timeout:
                    del self.person_tracks[pid]
                    continue
                pcx, pcy = pdata['center']
                dist = np.sqrt((cx - pcx) ** 2 + (cy - pcy) ** 2)
                prev_area = pdata['area']
                area_ratio = min(area, prev_area) / max(area, prev_area) if max(area, prev_area) > 0 else 0
                if dist < 150 and area_ratio > 0.5:
                    if dist < best_dist:
                        best_dist = dist
                        matched_id = pid

            if matched_id is not None:
                pid = matched_id
                pdata = self.person_tracks[pid]
                pdata['center'] = (cx, cy)
                pdata['area'] = area
                pdata['last_seen'] = time.time()
                pdata['positions'].append((cx, cy, time.time()))
                if len(pdata['positions']) > 50:
                    pdata['positions'].pop(0)
            else:
                pid = self.next_id
                self.next_id += 1
                self.person_tracks[pid] = {
                    'center': (cx, cy),
                    'area': area,
                    'box': box,
                    'first_seen': time.time(),
                    'last_seen': time.time(),
                    'positions': [(cx, cy, time.time())],
                    'employee_id': det.get('employee_id'),
                    'employee_name': det.get('employee_name', 'Unknown'),
                    'phone_usage': False
                }
            current_ids.append(pid)
        return current_ids

    def classify_activity(self, pid):
        if pid not in self.person_tracks:
            return 'away', 0
        pdata = self.person_tracks[pid]
        positions = pdata['positions']
        if len(positions) < 5:
            return 'unknown', 0

        recent = positions[-10:]
        xs = [p[0] for p in recent]
        ys = [p[1] for p in recent]
        movement = np.std(xs) + np.std(ys)
        y_range = max(ys) - min(ys)

        box = pdata['box']
        _, _, w, h = box
        aspect = h / w if w > 0 else 0
        time_present = time.time() - pdata['first_seen']

        if movement < 8 and y_range < 15:
            if aspect > 1.1:
                return 'seated', min(95, 70 + movement * 2)
            else:
                return 'seated', 60
        elif movement < 20:
            return 'seated', 50
        else:
            if y_range > 50:
                return 'walking', min(95, 70 + movement)
            else:
                return 'standing', 60

    def update_phone_usage(self, pid, is_using_phone):
        if pid in self.person_tracks:
            self.person_tracks[pid]['phone_usage'] = is_using_phone

    def get_person_info(self, pid):
        if pid not in self.person_tracks:
            return None
        pdata = self.person_tracks[pid]
        activity, conf = self.classify_activity(pid)
        return {
            'id': pid,
            'box': pdata['box'],
            'employee_id': pdata.get('employee_id'),
            'employee_name': pdata.get('employee_name', 'Unknown'),
            'activity': activity,
            'activity_confidence': conf,
            'phone_usage': pdata.get('phone_usage', False),
            'first_seen': pdata.get('first_seen', 0)
        }
