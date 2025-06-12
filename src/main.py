# main.py
"""
Launcher for Receiving & Shipping Tracker
Provides login screen and routes user to the appropriate interface based on role.
This file serves as the program entry point.
"""

# TODO: Initialize app (can use tkinter, customtkinter, or other GUI framework)
# TODO: Prompt user for login (username + password)
# TODO: Validate login against `users` table in SQLite DB (`receiving_tracker.db`)
# TODO: On success, start a session and record it in `scan_sessions`
# TODO: If role == 'admin':
#           Show admin interface (upload waybill, view summaries, manage users)
#       elif role == 'shipper':
#           Show receiving interface (select palette, scan parts, see progress)
# TODO: If login fails, show error and allow retry

# TODO: Ensure proper error handling and logging
# TODO: At shutdown, close any open sessions properly (update `end_time`)

# Example code structure (suggestion):
# def main():
#     show_login_screen()
#     if authenticated:
#         start_user_session()
#         if role == 'admin':
#             launch_admin_interface()
#         elif role == 'shipper':
#             launch_shipper_interface()
#
# if __name__ == "__main__":
#     main()
