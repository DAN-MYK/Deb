import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
from app.gui.windows.tables.acts_table import ActsTable
from app.gui.windows.tables.payments_db_table import PaymentsDbTable
from app.gui.windows.tables.payments_bank_table import PaymentsBankTable
from app.gui.windows.tables.summary_table import SummaryTable
from app.gui.windows.tables.summary_by_company_table import SummaryByCompanyTable
from app.gui.windows.table_formatter import TableFormatter
from app.config.logging_config import setup_logging

class TestTables(unittest.TestCase):
    def setUp(self):
        # Ініціалізація логера
        self.logger_setup = setup_logging()
        self.logger = self.logger_setup.get_logger()

        # Мок для db_manager
        self.db_manager = MagicMock()
        # Мок для parent (tkinter widget)
        self.parent = MagicMock()
        # Мок для tkinter.Treeview
        self.tree_mock = MagicMock()
        # Мок для filedialog
        self.filedialog_mock = MagicMock()
        # Налаштування formatter
        self.formatter = TableFormatter()

    def tearDown(self):
        # Закриваємо логер після кожного тесту
        self.logger_setup.close()

    @patch('app.gui.windows.tables.acts_table.ttk')
    def test_acts_table_create(self, ttk_mock):
        # Налаштування моків
        ttk_mock.Frame.return_value = MagicMock()
        ttk_mock.Treeview.return_value = self.tree_mock
        ttk_mock.Scrollbar.return_value = MagicMock()

        # Створюємо ActsTable
        table = ActsTable(self.parent, self.db_manager)
        table.create()

        # Перевіряємо, що Treeview створено з правильними стовпцями
        ttk_mock.Treeview.assert_called_once_with(table.frame, columns=["Компанія", "Контрагент", "Період", "Сумма з ПДВ"], show="headings")
        # Перевіряємо, що заголовки стовпців встановлені
        self.assertEqual(self.tree_mock.heading.call_count, 4)
        # Перевіряємо, що стовпці налаштовані
        self.assertEqual(self.tree_mock.column.call_count, 4)

    def test_acts_table_update(self):
        # Налаштування моків
        self.db_manager.get_all_acts.return_value = [
            ("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", 1000.0),
            ("ФРІ-ЕНЕРДЖИ", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "02-2023", 2000.0)
        ]
        table = ActsTable(self.parent, self.db_manager)
        table.tree = self.tree_mock

        # Викликаємо update
        table.update()

        # Перевіряємо, що старі дані видалені
        self.tree_mock.get_children.return_value = ["item1", "item2"]
        self.tree_mock.delete.assert_called()
        self.assertEqual(self.tree_mock.delete.call_count, 2)  # Двічі викликається для кожного елемента
        # Перевіряємо, що нові дані додані
        self.tree_mock.insert.assert_called()
        self.assertEqual(self.tree_mock.insert.call_count, 2)
        self.tree_mock.insert.assert_any_call("", "end", values=("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", "1 000,00"))

    @patch('app.gui.windows.tables.acts_table.filedialog')
    @patch('pandas')
    def test_acts_table_save(self, pd_mock, filedialog_mock):
        # Налаштування моків
        filedialog_mock.asksaveasfilename.return_value = "test_acts.xlsx"
        pd_mock.DataFrame.return_value = MagicMock()
        pd_mock.ExcelWriter.return_value = MagicMock()
        table = ActsTable(self.parent, self.db_manager)
        table.tree = self.tree_mock
        table.tree.get_children.return_value = ["item1"]
        table.tree.item.return_value = {'values': ["ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", "1 000,00"]}
        table.tree.heading.side_effect = lambda x: {'text': x}

        # Викликаємо save
        table.save()

        # Перевіряємо, що DataFrame створено
        pd_mock.DataFrame.assert_called_once()
        # Перевіряємо, що файл збережено
        pd_mock.ExcelWriter.assert_called_once_with("test_acts.xlsx", engine='xlsxwriter')

    @patch('app.gui.windows.tables.payments_db_table.ttk')
    def test_payments_db_table_create(self, ttk_mock):
        # Налаштування моків
        ttk_mock.Frame.return_value = MagicMock()
        ttk_mock.Treeview.return_value = self.tree_mock
        ttk_mock.Scrollbar.return_value = MagicMock()

        # Створюємо PaymentsDbTable
        table = PaymentsDbTable(self.parent, self.db_manager)
        table.create()

        # Перевіряємо, що Treeview створено з правильними стовпцями
        ttk_mock.Treeview.assert_called_once_with(table.frame, columns=["Компанія", "Контрагент", "Період", "Загальна сумма"], show="headings")
        self.assertEqual(self.tree_mock.heading.call_count, 4)
        self.assertEqual(self.tree_mock.column.call_count, 4)

    def test_payments_db_table_update(self):
        # Налаштування моків
        self.db_manager.get_all_payments.return_value = [
            ("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", 1000.0),
            ("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", 500.0)  # Такий самий ключ, сума додається
        ]
        table = PaymentsDbTable(self.parent, self.db_manager)
        table.tree = self.tree_mock

        # Викликаємо update
        table.update()

        # Перевіряємо, що старі дані видалені
        self.tree_mock.get_children.return_value = ["item1"]
        self.tree_mock.delete.assert_called()
        self.assertEqual(self.tree_mock.delete.call_count, 1)
        # Перевіряємо, що нові дані додані (сума 1500.0)
        self.tree_mock.insert.assert_called_once_with("", "end", values=("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", "1 500,00"))

    @patch('app.gui.windows.tables.payments_db_table.filedialog')
    @patch('pandas')
    def test_payments_db_table_save(self, pd_mock, filedialog_mock):
        # Налаштування моків
        filedialog_mock.asksaveasfilename.return_value = "test_payments_db.xlsx"
        pd_mock.DataFrame.return_value = MagicMock()
        pd_mock.ExcelWriter.return_value = MagicMock()
        table = PaymentsDbTable(self.parent, self.db_manager)
        table.tree = self.tree_mock
        table.tree.get_children.return_value = ["item1"]
        table.tree.item.return_value = {'values': ["ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", "1 500,00"]}
        table.tree.heading.side_effect = lambda x: {'text': x}

        # Викликаємо save
        table.save()

        # Перевіряємо, що DataFrame створено
        pd_mock.DataFrame.assert_called_once()
        # Перевіряємо, що файл збережено
        pd_mock.ExcelWriter.assert_called_once_with("test_payments_db.xlsx", engine='xlsxwriter')

    @patch('app.gui.windows.tables.payments_bank_table.ttk')
    def test_payments_bank_table_create(self, ttk_mock):
        # Налаштування моків
        ttk_mock.Frame.return_value = MagicMock()
        ttk_mock.Treeview.return_value = self.tree_mock
        ttk_mock.Scrollbar.return_value = MagicMock()

        # Створюємо PaymentsBankTable
        table = PaymentsBankTable(self.parent, self.db_manager)
        table.create()

        # Перевіряємо, що Treeview створено з правильними стовпцями
        ttk_mock.Treeview.assert_called_once_with(table.frame, columns=["Компанія", "Контрагент", "Місяць", "Кількість платежів", "Загальна сумма"], show="headings")
        self.assertEqual(self.tree_mock.heading.call_count, 5)
        self.assertEqual(self.tree_mock.column.call_count, 5)

    def test_payments_bank_table_update(self):
        # Налаштування моків
        monthly_summary = pd.DataFrame({
            'SUM_PD_NOM': [1000.0, 2000.0],
            'кількість платежів': [1, 2]
        }, index=pd.MultiIndex.from_tuples([
            ("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023"),
            ("ФРІ-ЕНЕРДЖИ", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "02-2023")
        ], names=["NAME", "NAME_KOR", "місяць"]))
        table = PaymentsBankTable(self.parent, self.db_manager)
        table.tree = self.tree_mock
        table.monthly_summary = monthly_summary

        # Викликаємо update
        table.update()

        # Перевіряємо, що старі дані видалені
        self.tree_mock.get_children.return_value = ["item1", "item2"]
        self.tree_mock.delete.assert_called()
        self.assertEqual(self.tree_mock.delete.call_count, 2)
        # Перевіряємо, що нові дані додані
        self.tree_mock.insert.assert_called()
        self.assertEqual(self.tree_mock.insert.call_count, 2)
        self.tree_mock.insert.assert_any_call("", "end", values=("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", 1, "1 000,00"))

    @patch('app.gui.windows.tables.payments_bank_table.filedialog')
    @patch('pandas')
    def test_payments_bank_table_save(self, pd_mock, filedialog_mock):
        # Налаштування моків
        filedialog_mock.asksaveasfilename.return_value = "test_payments_bank.xlsx"
        pd_mock.DataFrame.return_value = MagicMock()
        pd_mock.ExcelWriter.return_value = MagicMock()
        table = PaymentsBankTable(self.parent, self.db_manager)
        table.tree = self.tree_mock
        table.tree.get_children.return_value = ["item1"]
        table.tree.item.return_value = {'values': ["ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", 1, "1 000,00"]}
        table.tree.heading.side_effect = lambda x: {'text': x}

        # Викликаємо save
        table.save()

        # Перевіряємо, що DataFrame створено
        pd_mock.DataFrame.assert_called_once()
        # Перевіряємо, що файл збережено
        pd_mock.ExcelWriter.assert_called_once_with("test_payments_bank.xlsx", engine='xlsxwriter')

    @patch('app.gui.windows.tables.summary_table.ttk')
    def test_summary_table_create(self, ttk_mock):
        # Налаштування моків
        ttk_mock.Frame.return_value = MagicMock()
        ttk_mock.Treeview.return_value = self.tree_mock
        ttk_mock.Scrollbar.return_value = MagicMock()

        # Створюємо SummaryTable
        table = SummaryTable(self.parent, self.db_manager)
        table.create()

        # Перевіряємо, що Treeview створено з правильними стовпцями
        ttk_mock.Treeview.assert_called_once_with(table.frame, columns=["Період", "Компанія", "Контрагент", "Сума Акту", "Сума Оплати", "Заборгованість", "Відсоток оплат", "Відсоток заборгованості"], show="headings")
        self.assertEqual(self.tree_mock.heading.call_count, 8)
        self.assertEqual(self.tree_mock.column.call_count, 8)

    def test_summary_table_update(self):
        # Налаштування моків
        self.db_manager.get_all_acts.return_value = [
            ("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", 1000.0)
        ]
        self.db_manager.get_all_payments.return_value = [
            ("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", 600.0)
        ]
        table = SummaryTable(self.parent, self.db_manager)
        table.tree = self.tree_mock

        # Викликаємо update
        table.update()

        # Перевіряємо, що старі дані видалені
        self.tree_mock.get_children.return_value = ["item1"]
        self.tree_mock.delete.assert_called()
        self.assertEqual(self.tree_mock.delete.call_count, 1)
        # Перевіряємо, що нові дані додані
        self.tree_mock.insert.assert_called_once_with("", "end", values=(
            "01-2023", "ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "1 000,00", "600,00", "400,00", "60.00%", "40.00%"
        ))

    @patch('app.gui.windows.tables.summary_table.filedialog')
    @patch('pandas')
    def test_summary_table_save(self, pd_mock, filedialog_mock):
        # Налаштування моків
        filedialog_mock.asksaveasfilename.return_value = "test_summary.xlsx"
        pd_mock.DataFrame.return_value = MagicMock()
        pd_mock.ExcelWriter.return_value = MagicMock()
        table = SummaryTable(self.parent, self.db_manager)
        table.tree = self.tree_mock
        table.tree.get_children.return_value = ["item1"]
        table.tree.item.return_value = {'values': ["01-2023", "ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "1 000,00", "600,00", "400,00", "60.00%", "40.00%"]}
        table.tree.heading.side_effect = lambda x: {'text': x}

        # Викликаємо save
        table.save()

        # Перевіряємо, що DataFrame створено
        pd_mock.DataFrame.assert_called_once()
        # Перевіряємо, що файл збережено
        pd_mock.ExcelWriter.assert_called_once_with("test_summary.xlsx", engine='xlsxwriter')

    @patch('app.gui.windows.tables.summary_by_company_table.ttk')
    def test_summary_by_company_table_create(self, ttk_mock):
        # Налаштування моків
        ttk_mock.Frame.return_value = MagicMock()
        ttk_mock.Treeview.return_value = self.tree_mock
        ttk_mock.Scrollbar.return_value = MagicMock()

        # Створюємо SummaryByCompanyTable
        table = SummaryByCompanyTable(self.parent, self.db_manager)
        table.create()

        # Перевіряємо, що Treeview створено з правильними стовпцями
        ttk_mock.Treeview.assert_called_once_with(table.frame, columns=["Компанія", "Рік", "Сума Акту", "Сума Оплати", "Заборгованість", "Відсоток оплат", "Відсоток заборгованості"], show="headings")
        self.assertEqual(self.tree_mock.heading.call_count, 7)
        self.assertEqual(self.tree_mock.column.call_count, 7)

    def test_summary_by_company_table_update(self):
        # Налаштування моків
        self.db_manager.get_all_acts.return_value = [
            ("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", 1000.0)
        ]
        self.db_manager.get_all_payments.return_value = [
            ("ПЕРВОМАЙСЬК", "ГАРАНТОВАНИЙ ПОКУПЕЦЬ", "01-2023", 600.0)
        ]
        table = SummaryByCompanyTable(self.parent, self.db_manager)
        table.tree = self.tree_mock

        # Викликаємо update
        table.update()

        # Перевіряємо, що старі дані видалені
        self.tree_mock.get_children.return_value = ["item1"]
        self.tree_mock.delete.assert_called()
        self.assertEqual(self.tree_mock.delete.call_count, 1)
        # Перевіряємо, що нові дані додані
        self.tree_mock.insert.assert_called_once_with("", "end", values=(
            "ПЕРВОМАЙСЬК", "2023", "1 000,00", "600,00", "400,00", "60.00%", "40.00%"
        ))

    @patch('app.gui.windows.tables.summary_by_company_table.filedialog')
    @patch('pandas')
    def test_summary_by_company_table_save(self, pd_mock, filedialog_mock):
        # Налаштування моків
        filedialog_mock.asksaveasfilename.return_value = "test_summary_by_company.xlsx"
        pd_mock.DataFrame.return_value = MagicMock()
        pd_mock.ExcelWriter.return_value = MagicMock()
        table = SummaryByCompanyTable(self.parent, self.db_manager)
        table.tree = self.tree_mock
        table.tree.get_children.return_value = ["item1"]
        table.tree.item.return_value = {'values': ["ПЕРВОМАЙСЬК", "2023", "1 000,00", "600,00", "400,00", "60.00%", "40.00%"]}
        table.tree.heading.side_effect = lambda x: {'text': x}

        # Викликаємо save
        table.save()

        # Перевіряємо, що DataFrame створено
        pd_mock.DataFrame.assert_called_once()
        # Перевіряємо, що файл збережено
        pd_mock.ExcelWriter.assert_called_once_with("test_summary_by_company.xlsx", engine='xlsxwriter')

if __name__ == '__main__':
    unittest.main()