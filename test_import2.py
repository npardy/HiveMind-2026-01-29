import sys
sys.path.insert(0, r'H:\\')
from notification_watcher import NotificationWatcher
print("OK - NotificationWatcher imported successfully")

# Check the method exists
print(f"Has _post_time_to_qbo: {hasattr(NotificationWatcher, '_post_time_to_qbo')}")
print(f"Has _handle_field_data_uploaded: {hasattr(NotificationWatcher, '_handle_field_data_uploaded')}")
