import tkinter as tk
from tkinter import messagebox
from app.gui.forms.act import ActForm
from app.gui.forms.payment import PaymentForm
from app.gui.forms.act_adjustment import ActAdjustmentForm
from app.gui.dialogs.save_table import SaveTableDialog
from app.core.data.processor import DataProcessor
from app.core.data.db import DatabaseManager
from app.gui.windows.table_manager import TableManager
from app.config.logging_config import setup_logging

class PaymentAnalyzerApp:
    def __init__(self, root):
        self.logger_setup = setup_logging()
        self.logger = self.logger_setup.get_logger()
        self.logger.info("Initializing PaymentAnalyzerApp")

        self.root = root
        self.root.title("Deb - Аналіз платежів та актів")
        self.root.geometry("1000x600")
        
        self.data_processor = DataProcessor()
        self.db_manager = DatabaseManager()
        
        self.table_manager = TableManager(self.root, self.db_manager)
        
        self.create_widgets()
        self.table_manager.update_all()

    def create_widgets(self):
        self.logger.info("Creating widgets for PaymentAnalyzerApp")
        # Створюємо контейнер для кнопок
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=5)

        # Додаємо кнопки горизонтально
        tk.Button(button_frame, text="Акт", command=self.open_act_form).pack(side="left", padx=5)
        tk.Button(button_frame, text="Оплати", command=self.open_payment_form).pack(side="left", padx=5)
        tk.Button(button_frame, text="Коригування актів", command=self.open_act_adjustment_form).pack(side="left", padx=5)
        self.save_button = tk.Button(button_frame, text="Зберегти результат", command=self.open_save_dialog)
        self.save_button.pack(side="left", padx=5)
        self.save_button.config(state='normal')
        tk.Button(button_frame, text="Очистити базу", command=self.clear_database).pack(side="left", padx=5)

        self.table_manager.create_tables()

    def open_act_form(self):
        self.logger.info("Opening ActForm")
        ActForm(self.root, self.data_processor, self.db_manager, self.table_manager.update_all)

    def open_payment_form(self):
        self.logger.info("Opening PaymentForm")
        PaymentForm(self.root, self.data_processor, self.db_manager, self.table_manager.update_all)

    def open_act_adjustment_form(self):
        self.logger.info("Opening ActAdjustmentForm")
        ActAdjustmentForm(self.root, self.db_manager, self.table_manager.update_all)

    def open_save_dialog(self):
        self.logger.info("Opening SaveTableDialog")
        SaveTableDialog(self.root, self.table_manager.save)

    def clear_database(self):
        self.logger.info("Clearing database")
        self.db_manager.clear_database()
        self.table_manager.update_all()
        self.logger.info("Database cleared successfully")
        messagebox.showinfo("Успіх", "База даних очищена!")

    def __del__(self):
        self.logger.info("Closing PaymentAnalyzerApp")
        self.logger_setup.close()