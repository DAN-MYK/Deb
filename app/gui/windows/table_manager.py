import tkinter as tk
from tkinter import ttk
from app.gui.windows.tables.acts_table import ActsTable
from app.gui.windows.tables.payments_db_table import PaymentsDbTable
from app.gui.windows.tables.payments_bank_table import PaymentsBankTable
from app.gui.windows.tables.summary_table import SummaryTable
from app.gui.windows.tables.summary_by_company_table import SummaryByCompanyTable
from app.config.logging_config import setup_logging

class TableManager:
    def __init__(self, root, db_manager):
        self.logger_setup = setup_logging()
        self.logger = self.logger_setup.get_logger()
        self.logger.info("Initializing TableManager")

        self.root = root
        self.db_manager = db_manager
        self.notebook = ttk.Notebook(self.root)
        self.tables = {}

        # Мапінг між назвами таблиць у GUI та ключами в self.tables
        self.table_name_mapping = {
            "Акти": "acts",
            "Оплати (з бази)": "payments_db",
            "Оплати (з банку)": "payments_bank",
            "Загальний звіт": "summary",
            "Підсумки по компанії та роках": "summary_by_company"
        }

        self._initialize_tables()

    def _initialize_tables(self):
        self.logger.info("Initializing tables")
        # Спочатку створюємо таблиці, які додаються безпосередньо до основного notebook
        self.tables['acts'] = ActsTable(self.notebook, self.db_manager)
        self.tables['payments_db'] = PaymentsDbTable(self.notebook, self.db_manager)
        self.tables['payments_bank'] = PaymentsBankTable(self.notebook, self.db_manager)

        # Викликаємо create() для цих таблиць
        self.tables['acts'].create()
        self.tables['payments_db'].create()
        self.tables['payments_bank'].create()

        # Додаємо frame цих таблиць до основного notebook
        self.notebook.add(self.tables['acts'].frame, text="Акти")
        self.notebook.add(self.tables['payments_db'].frame, text="Оплати (з бази)")
        self.notebook.add(self.tables['payments_bank'].frame, text="Оплати (з банку)")

        # Загальний звіт із вкладками
        self.summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.summary_frame, text="Загальний звіт")
        
        self.summary_notebook = ttk.Notebook(self.summary_frame)
        self.summary_notebook.pack(pady=10, fill="both", expand=True)

        # Тепер створюємо таблиці для summary_notebook
        self.tables['summary'] = SummaryTable(self.summary_notebook, self.db_manager)
        self.tables['summary_by_company'] = SummaryByCompanyTable(self.summary_notebook, self.db_manager)

        # Викликаємо create() для цих таблиць
        self.tables['summary'].create()
        self.tables['summary_by_company'].create()

        # Додаємо frame до summary_notebook
        self.summary_notebook.add(self.tables['summary'].frame, text="Деталі")
        self.summary_notebook.add(self.tables['summary_by_company'].frame, text="Підсумки по компанії та роках")

    def create_tables(self):
        self.logger.info("Creating tables")
        self.notebook.pack(pady=10, fill="both", expand=True)

    def update_all(self):
        self.logger.info("Updating all tables")
        for table in self.tables.values():
            table.update()

    def save(self, table_name):
        self.logger.info(f"Saving table: {table_name}")
        # Перетворюємо назву таблиці з GUI на ключ у self.tables
        table_key = self.table_name_mapping.get(table_name, table_name)
        if table_key in self.tables:
            self.tables[table_key].save()
        else:
            self.logger.error(f"Unknown table: {table_name} (mapped to {table_key})")
            tk.messagebox.showerror("Помилка", "Невідома таблиця!")

    def __del__(self):
        self.logger.info("Closing TableManager")
        self.logger_setup.close()