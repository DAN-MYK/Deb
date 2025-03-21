import unittest
from unittest.mock import MagicMock, patch
from app.gui.windows.table_manager import TableManager
from app.gui.windows.tables.acts_table import ActsTable
from app.gui.windows.tables.payments_db_table import PaymentsDbTable
from app.gui.windows.tables.payments_bank_table import PaymentsBankTable
from app.gui.windows.tables.summary_table import SummaryTable
from app.gui.windows.tables.summary_by_company_table import SummaryByCompanyTable
from app.config.logging_config import setup_logging

class TestTableManager(unittest.TestCase):
    def setUp(self):
        # Ініціалізація логера
        self.logger_setup = setup_logging()
        self.logger = self.logger_setup.get_logger()

        # Мок для db_manager
        self.db_manager = MagicMock()
        # Мок для root (tkinter widget)
        self.root = MagicMock()
        # Мок для ttk.Notebook
        self.notebook_mock = MagicMock()

    def tearDown(self):
        # Закриваємо логер після кожного тесту
        self.logger_setup.close()

    @patch('app.gui.windows.table_manager.ttk')
    @patch('app.gui.windows.table_manager.ActsTable')
    @patch('app.gui.windows.table_manager.PaymentsDbTable')
    @patch('app.gui.windows.table_manager.PaymentsBankTable')
    @patch('app.gui.windows.table_manager.SummaryTable')
    @patch('app.gui.windows.table_manager.SummaryByCompanyTable')
    def test_table_manager_init(self, summary_by_company_mock, summary_mock, payments_bank_mock, payments_db_mock, acts_mock, ttk_mock):
        # Налаштування моків
        ttk_mock.Notebook.return_value = self.notebook_mock
        ttk_mock.Frame.return_value = MagicMock()
        acts_mock.return_value = MagicMock()
        payments_db_mock.return_value = MagicMock()
        payments_bank_mock.return_value = MagicMock()
        summary_mock.return_value = MagicMock()
        summary_by_company_mock.return_value = MagicMock()

        # Створюємо TableManager
        manager = TableManager(self.root, self.db_manager)

        # Перевіряємо, що таблиці ініціалізовані
        self.assertIn('acts', manager.tables)
        self.assertIn('payments_db', manager.tables)
        self.assertIn('payments_bank', manager.tables)
        self.assertIn('summary', manager.tables)
        self.assertIn('summary_by_company', manager.tables)

        # Перевіряємо, що вкладки додані
        # Очікуємо 4 виклики: 3 основні таблиці + 1 для summary_frame
        # Але через вкладки summary_notebook додається ще 2 виклики
        self.assertEqual(self.notebook_mock.add.call_count, 4)  # 3 основні + 1 для summary
        self.assertEqual(manager.summary_notebook.add.call_count, 2)  # 2 вкладки в summary_notebook

    def test_table_manager_create_tables(self):
        # Налаштування моків
        manager = TableManager(self.root, self.db_manager)
        manager.notebook = self.notebook_mock
        for table_name in manager.tables:
            manager.tables[table_name] = MagicMock()

        # Викликаємо create_tables
        manager.create_tables()

        # Перевіряємо, що pack викликано для notebook
        self.notebook_mock.pack.assert_called_once_with(pady=10, fill="both", expand=True)
        # Перевіряємо, що create викликано для кожної таблиці
        for table in manager.tables.values():
            table.create.assert_called_once()

    def test_table_manager_update_all(self):
        # Налаштування моків
        manager = TableManager(self.root, self.db_manager)
        for table_name in manager.tables:
            manager.tables[table_name] = MagicMock()

        # Викликаємо update_all
        manager.update_all()

        # Перевіряємо, що update викликано для кожної таблиці
        for table in manager.tables.values():
            table.update.assert_called_once()

    def test_table_manager_save(self):
        # Налаштування моків
        manager = TableManager(self.root, self.db_manager)
        manager.tables['acts'] = MagicMock()
        # Видаляємо неіснуючу таблицю, щоб уникнути помилки
        if 'invalid_table' in manager.tables:
            del manager.tables['invalid_table']

        # Викликаємо save для існуючої таблиці
        manager.save('acts')
        manager.tables['acts'].save.assert_called_once()

        # Викликаємо save для неіснуючої таблиці
        with patch('tkinter.messagebox.showerror') as showerror_mock:
            manager.save('invalid_table')
            showerror_mock.assert_called_once_with("Помилка", "Невідома таблиця!")

if __name__ == '__main__':
    unittest.main()