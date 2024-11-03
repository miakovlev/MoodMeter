import hashlib
import logging
import os

# Create a folder for logs if it doesn't exist
if not os.path.exists("logs"):
    os.makedirs("logs")

# Logging setup
logger = logging.getLogger("MoodMeter")
logger.setLevel(logging.INFO)

# Log format
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# File handler for logging to a file
file_handler = logging.FileHandler("logs/app.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Console handler for logging to the console
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(formatter)

# Adding handlers to the logger
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def hash_password(password: str) -> str:
    """
    Hashes a password using the SHA-256 algorithm.

    Args:
        password (str): The password to be hashed.

    Returns:
        str: The hashed password.
    """
    return hashlib.sha256(password.encode()).hexdigest()
