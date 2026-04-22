from plyer import notification
import os

def send_desktop_notification(title, message):
    try:
        notification.notify(
            title=title,
            message=message,
            app_name='APK Builder',
            timeout=10,
        )
    except Exception as e:
        print(f"Failed to send desktop notification: {e}")
