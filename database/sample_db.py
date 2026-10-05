from __future__ import annotations
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import random

def init_sample_database(db_path: str = "./data/detections.db") -> None:
    """Creates a sample surveillance, detection, and alert database if it does not exist."""
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    # If the file already exists and has data, don't overwrite
    if path.exists() and path.stat().st_size > 0:
        return

    conn = sqlite3.connect(str(path))
    cursor = conn.cursor()

    # 1. Cameras / Devices Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cameras (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name VARCHAR(100) NOT NULL,
        location VARCHAR(100) NOT NULL,
        ip_address VARCHAR(45),
        status VARCHAR(20) DEFAULT 'online', -- 'online', 'offline', 'maintenance'
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # 2. Detections Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS detections (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        camera_id INTEGER NOT NULL,
        object_type VARCHAR(50) NOT NULL, -- 'person', 'face', 'vehicle', 'unauthorized_entry'
        person_name VARCHAR(100),         -- recognized name if face detected or 'Unknown'
        confidence REAL NOT NULL,         -- e.g. 0.95
        timestamp DATETIME NOT NULL,
        image_url VARCHAR(255),
        FOREIGN KEY (camera_id) REFERENCES cameras (id)
    );
    """)

    # 3. Alerts Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        detection_id INTEGER,
        camera_id INTEGER NOT NULL,
        alert_type VARCHAR(50) NOT NULL, -- 'perimeter_breach', 'blacklisted_person', 'crowd_gathering', 'loitering', 'unknown_face'
        severity VARCHAR(20) NOT NULL,   -- 'low', 'medium', 'high', 'critical'
        status VARCHAR(20) DEFAULT 'new', -- 'new', 'acknowledged', 'resolved'
        description TEXT NOT NULL,
        created_at DATETIME NOT NULL,
        resolved_at DATETIME,
        FOREIGN KEY (detection_id) REFERENCES detections (id),
        FOREIGN KEY (camera_id) REFERENCES cameras (id)
    );
    """)

    # 4. System Logs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        log_level VARCHAR(20) NOT NULL, -- 'INFO', 'WARNING', 'ERROR'
        module VARCHAR(50) NOT NULL,
        message TEXT NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Seed Cameras
    cameras = [
        ("Main Gate Cam 01", "Main Entrance Gate", "192.168.1.101", "online"),
        ("Lobby Cam 02", "Ground Floor Lobby", "192.168.1.102", "online"),
        ("Perimeter North Cam 03", "North Boundary Fence", "192.168.1.103", "online"),
        ("Server Room Cam 04", "Building B Server Room", "192.168.1.104", "online"),
        ("Parking Lot Cam 05", "South Basement Parking", "192.168.1.105", "online"),
        ("Exit Gate Cam 06", "West Exit Gate", "192.168.1.106", "maintenance"),
    ]
    cursor.executemany(
        "INSERT INTO cameras (name, location, ip_address, status) VALUES (?, ?, ?, ?);",
        cameras
    )

    now = datetime.now()
    known_names = ["John Doe", "Sarah Connor", "Alex Miller", "Bruce Wayne", "Clark Kent", "Unknown"]
    objects = ["person", "face", "vehicle", "unauthorized_entry"]
    alert_types = [
        ("blacklisted_person", "critical", "Blacklisted individual detected at entrance"),
        ("perimeter_breach", "critical", "Motion detected in restricted perimeter zone"),
        ("unknown_face", "medium", "Unidentified person lingered near entrance"),
        ("loitering", "low", "Individual stayed in lobby for over 15 minutes"),
        ("crowd_gathering", "high", "High density crowd detected near server corridor"),
    ]

    # Generate detections & alerts for past 7 days up to today
    detection_id_counter = 1
    for days_ago in range(7, -1, -1):
        day_date = now - timedelta(days=days_ago)
        # 15-30 detections per day
        num_detections = random.randint(15, 30)
        for _ in range(num_detections):
            cam_id = random.randint(1, 5)
            obj = random.choice(objects)
            person = random.choice(known_names) if obj in ("person", "face") else None
            conf = round(random.uniform(0.78, 0.99), 2)
            hour = random.randint(0, 23)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            dt_str = day_date.replace(hour=hour, minute=minute, second=second).strftime("%Y-%m-%d %H:%M:%S")
            img_url = f"/snapshots/cam_{cam_id}_{dt_str.replace(' ', '_').replace(':', '-')}.jpg"

            cursor.execute(
                "INSERT INTO detections (camera_id, object_type, person_name, confidence, timestamp, image_url) VALUES (?, ?, ?, ?, ?, ?);",
                (cam_id, obj, person, conf, dt_str, img_url)
            )

            # Occasionally create an alert for this detection
            if random.random() < 0.35 or obj == "unauthorized_entry" or person == "Bruce Wayne":
                atype, asev, desc_template = random.choice(alert_types)
                if person and person != "Unknown":
                    desc = f"{desc_template}: {person}"
                else:
                    desc = desc_template
                
                # If older than 1 day, high chance it's resolved
                if days_ago > 0:
                    astatus = random.choice(["resolved", "resolved", "acknowledged"])
                    resolved_time = (day_date + timedelta(hours=random.randint(1, 4))).strftime("%Y-%m-%d %H:%M:%S")
                else:
                    astatus = random.choice(["new", "new", "acknowledged"])
                    resolved_time = None

                cursor.execute(
                    "INSERT INTO alerts (detection_id, camera_id, alert_type, severity, status, description, created_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?);",
                    (detection_id_counter, cam_id, atype, asev, astatus, desc, dt_str, resolved_time)
                )

            detection_id_counter += 1

    # Insert sample system logs
    logs = [
        ("INFO", "CameraEngine", "All camera video streams synchronized successfully."),
        ("WARNING", "InferenceEngine", "GPU temperature exceeded 75C on worker node 1."),
        ("INFO", "AlertNotifier", "Telegram and webhook alert channel active."),
        ("ERROR", "StorageService", "Failed to upload snapshot frame: S3 socket timeout."),
    ]
    for level, mod, msg in logs:
        cursor.execute(
            "INSERT INTO system_logs (log_level, module, message) VALUES (?, ?, ?);",
            (level, mod, msg)
        )

    conn.commit()
    conn.close()
