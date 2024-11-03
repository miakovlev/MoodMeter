import hashlib
import logging
import os

# Создание папки для логов, если она отсутствует
if not os.path.exists("logs"):
    os.makedirs("logs")

# Настройка логирования
logger = logging.getLogger("MoodMeter")
logger.setLevel(logging.INFO)

# Формат логов
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# Обработчик для записи логов в файл
file_handler = logging.FileHandler("logs/app.log")
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)

# Обработчик для вывода логов на консоль
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.ERROR)
console_handler.setFormatter(formatter)

# Добавление обработчиков к логгеру
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def hash_password(password: str) -> str:
    """
    Хеширует пароль с использованием алгоритма SHA-256.

    Args:
        password (str): Пароль для хеширования.

    Returns:
        str: Захешированный пароль.
    """
    return hashlib.sha256(password.encode()).hexdigest()
