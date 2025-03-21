import os

# Базовий каталог для даних
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))

# Підтримувані формати файлів
SUPPORTED_EXTENSIONS = (".xlsx", ".xlsm", ".xls")

# Формати дат для парсингу
DATE_FORMATS = [
    '%Y-%m-%d',
    '%d.%m.%Y %H:%M:%S',
    '%d.%m.%Y',
    '%Y-%m-%d %H:%M:%S',
]