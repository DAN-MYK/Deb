import logging
import os

class LoggerSetup:
    def __init__(self):
        # Створюємо папку для логів, якщо її немає
        self.log_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "logs"))
        os.makedirs(self.log_dir, exist_ok=True)

        # Налаштування логування
        self.log_file = os.path.join(self.log_dir, "app.log")
        self.handler = logging.FileHandler(self.log_file)
        self.handler.setLevel(logging.INFO)
        self.formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.handler.setFormatter(self.formatter)

        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(self.handler)
        self.logger.addHandler(logging.StreamHandler())  # Виводимо логи також у консоль

    def get_logger(self):
        return self.logger

    def close(self):
        self.handler.close()
        self.logger.removeHandler(self.handler)

def setup_logging():
    logger_setup = LoggerSetup()
    return logger_setup