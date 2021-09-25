config = {
    "influx": {
        "host": "influx1.mydomain.com",
        "port": 8086,
        "database": "amcrest",
        "ssl": True,
        "username": "username",
        "password": "password",
        "location": "camera-room"
    },
    "amcrest": {
        "host": "192.168.1.1",
        "port": 80,
        "username": "admin",
        "password": "password",
        "events": [
            "VideoLoss"
        ]
    }
}
