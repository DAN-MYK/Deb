from app.config.logging_config import setup_logging

class TableFormatter:
    def __init__(self):
        self.logger_setup = setup_logging()
        self.logger = self.logger_setup.get_logger()  # Правильна ініціалізація логера
        self.logger.info("Initializing TableFormatter")

    def format_number(self, number):
        if isinstance(number, (int, float)):
            return f"{number:,.2f}".replace(',', ' ').replace('.', ',')
        return number

    def format_percentage(self, value):
        if isinstance(value, (int, float)):
            return f"{value:.2f}%"
        return value

    def __del__(self):
        self.logger.info("Closing TableFormatter")
        self.logger_setup.close()