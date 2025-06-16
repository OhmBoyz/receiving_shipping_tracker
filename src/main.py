# main.py
"""
Launcher for Receiving & Shipping Tracker
Provides login screen and routes user to the appropriate interface based on role.
This file serves as the program entry point.
"""

import logging

from src.ui.admin_interface import start_admin_interface
from src.ui.login import prompt_login
from src.ui.scanner_interface import start_shipper_interface

logger = logging.getLogger(__name__)


def main() -> None:
    """Prompt for login and launch the appropriate interface."""

    while True:
        login_info = prompt_login()
        if login_info is None:
            logger.info("Login cancelled")
            break

        user_id, _username, role = login_info

        if role.upper() == "ADMIN":
            start_admin_interface()
        else:
            start_shipper_interface(user_id)


if __name__ == "__main__":
    main()
