"""Payments table module - unified table for all payments."""
from typing import Any, Dict, List, Optional, Tuple
import logging

from tkinter import Menu, messagebox

from app.config.logging_config import get_logger
from app.gui.dialogs.edit_dialog import EditDialog, EditField, confirm_delete
from app.gui.windows.table_formatter import TableFormatter
from app.gui.windows.tables.base_table import BaseTreeviewTable, FilterConfig


class PaymentsTable(BaseTreeviewTable):
    """Unified table for displaying all payments with sorting and filtering capabilities."""

    table_display_name = "Оплати"
    columns = ["Компанія", "Контрагент", "Період", "Загальна сума"]
    column_types = {"Період": "period", "Загальна сума": "number"}
    filter_config = FilterConfig(columns=columns, show_advanced=False)

    def __init__(
        self,
        parent: Any,
        db_manager: Any,
        update_callback: Optional[Any] = None,
        state_callback: Optional[Any] = None,
    ) -> None:
        super().__init__(parent, db_manager, update_callback, state_callback)
        self.logger: logging.Logger = get_logger(__name__)
        self.logger.info("Initializing PaymentsTable")
        self.formatter: TableFormatter = TableFormatter()
        self.original_data: List[Tuple[str, str, str, float]] = []

    def create(self) -> Any:
        self.logger.info("Creating PaymentsTable")
        tree = super().create()
        self._setup_context_menu()
        self._setup_double_click()
        return tree
    
    def _setup_context_menu(self) -> None:
        """Налаштовує контекстне меню для таблиці."""
        self.context_menu = Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="✏️ Редагувати", command=self._edit_payment)
        self.context_menu.add_command(label="🗑️ Видалити", command=self._delete_payment)

        # Прив'язуємо контекстне меню до правої кнопки миші
        self.tree.bind("<Button-3>", self._show_context_menu)

    def _setup_double_click(self) -> None:
        """Налаштовує подвійний клік для редагування."""
        self.tree.bind("<Double-Button-1>", self._on_double_click)

    def _on_double_click(self, event: Any) -> None:
        """Обробляє подвійний клік по рядку таблиці."""
        # Визначаємо рядок під курсором
        item = self.tree.identify_row(event.y)
        if item:
            # Вибираємо рядок
            self.tree.selection_set(item)
            # Відкриваємо редагування
            self._edit_payment()
    
    def _show_context_menu(self, event: Any) -> None:
        """Показує контекстне меню при кліку правою кнопкою миші."""
        # Визначаємо рядок під курсором
        item = self.tree.identify_row(event.y)
        if item:
            # Вибираємо рядок
            self.tree.selection_set(item)
            # Показуємо меню
            self.context_menu.post(event.x_root, event.y_root)

    def update(self) -> None:
        """Update table with all payments from database."""
        self.logger.info("Updating PaymentsTable")
        
        # Отримуємо всі оплати з бази даних
        payments = self.db_manager.get_all_payments()
        self.logger.info(f"Loaded {len(payments)} payments")
        
        # Групуємо оплати по компанії, контрагенту та періоду
        payments_by_month: Dict[Tuple[str, str, str], float] = {}
        for payment in payments:
            company, counterparty, period, amount = payment
            key = (company, counterparty, period)
            if key in payments_by_month:
                payments_by_month[key] += amount
            else:
                payments_by_month[key] = amount
        
        self.original_data = [
            (company, counterparty, period, total_amount)
            for (company, counterparty, period), total_amount in payments_by_month.items()
        ]

        rows = []
        for company, counterparty, period, total_amount in self.original_data:
            formatted_amount = self.formatter.format_number(total_amount)
            rows.append((company, counterparty, period, formatted_amount))

        self.set_rows(rows)
    
    def _edit_payment(self) -> None:
        """Редагує вибрану оплату."""
        try:
            selection = self.tree.selection()
            if not selection:
                messagebox.showwarning("Увага", "Будь ласка, виберіть оплату для редагування")
                return

            # Отримуємо дані вибраного елемента
            item = selection[0]
            values = self.tree.item(item)['values']

            if not values or len(values) < 4:
                messagebox.showerror("Помилка", "Не вдалося отримати дані оплати")
                return

            old_company = values[0]
            old_counterparty = values[1]
            old_period = values[2]
            old_amount_str = values[3]

            # Конвертуємо суму назад в числовий формат
            try:
                old_amount = float(old_amount_str.replace(' ', '').replace(',', '.'))
            except (ValueError, AttributeError) as e:
                self.logger.error(f"Error parsing amount: {e}")
                messagebox.showerror("Помилка", f"Не вдалося обробити суму оплати: {old_amount_str}")
                return

            # Формуємо дані для редагування
            payment_data = {
                'company': old_company,
                'counterparty': old_counterparty,
                'period': old_period,
                'amount': old_amount,
                'payment_date': None,  # Немає в таблиці
                'purpose': None,  # Немає в таблиці
            }

            # Відкриваємо форму редагування
            from app.gui.forms.payment import PaymentForm
            from app.core.data.processor import DataProcessor
            data_processor = DataProcessor()

            # Визначаємо callback для оновлення
            update_cb = self.update_callback if self.update_callback else self.update

            PaymentForm(
                self.parent,
                data_processor,
                self.db_manager,
                update_cb,
                edit_mode=True,
                payment_data=payment_data
            )
        except Exception as e:
            self.logger.error(f"Error in _edit_payment: {e}", exc_info=True)
            messagebox.showerror("Помилка", f"Не вдалося відкрити форму редагування:\n{str(e)}")
    
    def _delete_payment(self) -> None:
        """Видаляє вибрану оплату з бази даних та таблиці."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Увага", "Будь ласка, виберіть оплату для видалення")
            return
        
        # Отримуємо дані вибраного елемента
        item = selection[0]
        values = self.tree.item(item)['values']
        
        if not values or len(values) < 4:
            messagebox.showerror("Помилка", "Не вдалося отримати дані оплати")
            return
        
        company = values[0]
        counterparty = values[1]
        period = values[2]
        amount_str = values[3]
        
        # Конвертуємо суму назад в числовий формат
        try:
            amount = float(amount_str.replace(' ', '').replace(',', '.'))
        except (ValueError, AttributeError):
            messagebox.showerror("Помилка", "Не вдалося обробити суму оплати")
            return
        
        # Підтвердження видалення
        if not confirm_delete(
            self.parent,
            "Підтвердження видалення",
            f"Ви впевнені, що хочете видалити цю оплату?\n\n"
            f"Компанія: {company}\n"
            f"Контрагент: {counterparty}\n"
            f"Період: {period}\n"
            f"Сума: {amount_str}",
        ):
            return
        
        try:
            # Видаляємо з бази даних
            deleted_count = self.db_manager.delete_payment(company, counterparty, period, amount)
            
            if deleted_count > 0:
                messagebox.showinfo("Успіх", f"Оплату успішно видалено")
                self.logger.info(f"Deleted payment: {company} - {counterparty} - {period}")
                # Оновлюємо таблицю та звіти
                if self.update_callback:
                    self.update_callback()
                else:
                    self.update()
            else:
                messagebox.showwarning("Увага", "Оплату не знайдено в базі даних")
                
        except Exception as e:
            self.logger.error(f"Error deleting payment: {str(e)}")
            messagebox.showerror("Помилка", f"Не вдалося видалити оплату:\n{str(e)}")

