# main.py
"""
Launcher for Receiving & Shipping Tracker
Provides login screen and routes user to the appropriate interface based on role.
This file serves as the program entry point.
"""

from ui.admin_interface import start_admin_interface
from ui.login import end_session, prompt_login
from ui.scanner_interface import start_shipper_interface


def main() -> None:
    """Prompt for login and launch the appropriate interface."""

    login_info = prompt_login()
    if login_info is None:
        print("Login cancelled")
        return

    session_id, user_id, _username, role = login_info

    try:
        if role.upper() == "ADMIN":
            start_admin_interface()
        else:
            start_shipper_interface(user_id)
    finally:
        end_session(session_id)


if __name__ == "__main__":
    main()
