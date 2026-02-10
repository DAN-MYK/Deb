"""Acts table module."""
from typing import Any, List, Optional, Tuple
import logging
import os
import platform
import subprocess

from tkinter import Menu, messagebox

from app.config.logging_config import get_logger
from app.gui.dialogs.edit_dialog import confirm_delete
from app.gui.forms.act import ActForm
from app.gui.windows.table_formatter import TableFormatter
from app.gui.windows.tables.base_table import BaseTreeviewTable, FilterConfig


class ActsTable(BaseTreeviewTable):
    """Table for displaying acts data with sorting and filtering capabilities."""

    table_display_name = "Акти"
    columns = [
        "Компанія", "Контрагент", "Найменування", "Період",
        "Кількість", "Ціна", "Сума без ПДВ", "Сума з ПДВ",
    ]
    column_types = {
        "Період": "period",
        "Кількість": "number",
        "Ціна": "number",
        "Сума без ПДВ": "number",
        "Сума з ПДВ": "number",
    }
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
        self.logger.info("Initializing ActsTable")
        self.formatter: TableFormatter = TableFormatter()
        self.original_data: List[Tuple[str, str, str, float, Optional[float], Optional[str]]] = []

    def create(self) -> Any:
        self.logger.info("Creating ActsTable")
        tree = super().create()
        # Custom column widths to fit all data
        column_widths = {
            "Компанія": 170,
            "Контрагент": 170,
            "Найменування": 130,
            "Період": 90,
            "Кількість": 110,
            "Ціна": 100,
            "Сума без ПДВ": 130,
            "Сума з ПДВ": 130,
        }
        for col, width in column_widths.items():
            self.tree.column(col, width=width)
        self._setup_context_menu()
        self._setup_double_click()
        return tree
    
    def _setup_context_menu(self) -> None:
        """Налаштовує контекстне меню для таблиці."""
        self.context_menu = Menu(self.tree, tearoff=0)
        self.context_menu.add_command(label="📄 Відкрити PDF", command=self._open_pdf)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="✏️ Редагувати", command=self._edit_act)
        self.context_menu.add_command(label="🗑️ Видалити", command=self._delete_act)

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
            self._edit_act()
    
    def _show_context_menu(self, event: Any) -> None:
        """Показує контекстне меню при кліку правою кнопкою миші."""
        # Визначаємо рядок під курсором
        item = self.tree.identify_row(event.y)
        if item:
            # Вибираємо рядок
            self.tree.selection_set(item)
            # Показуємо меню
            self.context_menu.post(event.x_root, event.y_root)
    
    def _open_pdf(self) -> None:
        """Відкриває PDF файл для вибраного акту."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Увага", "Будь ласка, виберіть акт для відкриття PDF")
            return
        
        # Отримуємо перший вибраний елемент
        item = selection[0]
        tags = self.tree.item(item, 'tags')
        
        if not tags or not tags[0]:
            messagebox.showinfo("Інформація", "Для цього акту не збережено шлях до PDF файлу")
            return
        
        pdf_path = next((tag for tag in tags if tag not in ("odd", "even")), None)
        if not pdf_path:
            messagebox.showinfo("Інформація", "Для цього акту не збережено шлях до PDF файлу")
            return
        
        # Перевіряємо чи існує файл
        if not os.path.exists(pdf_path):
            messagebox.showerror(
                "Помилка",
                f"PDF файл не знайдено:\n{pdf_path}\n\nМожливо файл було переміщено або видалено."
            )
            return
        
        # Відкриваємо PDF файл системним переглядачем
        try:
            if platform.system() == 'Windows':
                os.startfile(pdf_path)
            elif platform.system() == 'Darwin':  # macOS
                subprocess.run(['open', pdf_path])
            else:  # Linux
                subprocess.run(['xdg-open', pdf_path])
            
            self.logger.info(f"Opened PDF file: {pdf_path}")
        except Exception as e:
            self.logger.error(f"Failed to open PDF: {str(e)}")
            messagebox.showerror("Помилка", f"Не вдалося відкрити PDF файл:\n{str(e)}")
    
    def _edit_act(self) -> None:
        """Редагує вибраний акт."""
        try:
            selection = self.tree.selection()
            if not selection:
                messagebox.showwarning("Увага", "Будь ласка, виберіть акт для редагування")
                return

            # Отримуємо дані вибраного елемента
            item = selection[0]
            values = self.tree.item(item)['values']

            if not values or len(values) < 8:
                messagebox.showerror("Помилка", "Не вдалося отримати дані акту")
                return

            old_company = values[0]
            old_counterparty = values[1]
            # values[2] = Найменування (завжди "Електроенергія")
            old_period = values[3]
            old_volume_str = values[4]  # Кількість (кВт/год)
            old_price_str = values[5]  # Ціна
            old_cost_str = values[6]  # Сума без ПДВ
            old_amount_str = values[7]  # Сума з ПДВ

            # Конвертуємо значення в числовий формат
            try:
                old_amount = float(str(old_amount_str).replace(' ', '').replace(',', '.'))
            except (ValueError, AttributeError) as e:
                self.logger.error(f"Error parsing amount: {e}")
                messagebox.showerror("Помилка", f"Не вдалося обробити суму акту: {old_amount_str}")
                return

            try:
                old_volume = float(str(old_volume_str).replace(' ', '').replace(',', '.')) if old_volume_str else None
            except (ValueError, AttributeError):
                old_volume = None

            try:
                old_cost = float(str(old_cost_str).replace(' ', '').replace(',', '.')) if old_cost_str else None
            except (ValueError, AttributeError):
                old_cost = None

            try:
                old_price = float(str(old_price_str).replace(' ', '').replace(',', '.')) if old_price_str else None
            except (ValueError, AttributeError):
                old_price = None

            # Формуємо дані для редагування
            act_data = {
                'company': old_company,
                'counterparty': old_counterparty,
                'period': old_period,
                'amount': old_amount,
                'energy_volume': old_volume,
                'cost_without_vat': old_cost,
                'price_without_vat': old_price,
            }

            # Відкриваємо форму редагування
            from app.core.data.processor import DataProcessor
            data_processor = DataProcessor()

            # Визначаємо callback для оновлення
            update_cb = self.update_callback if self.update_callback else self.update

            ActForm(
                self.parent,
                data_processor,
                self.db_manager,
                update_cb,
                edit_mode=True,
                act_data=act_data
            )
        except Exception as e:
            self.logger.error(f"Error in _edit_act: {e}", exc_info=True)
            messagebox.showerror("Помилка", f"Не вдалося відкрити форму редагування:\n{str(e)}")
    
    def _delete_act(self) -> None:
        """Видаляє вибраний акт з бази даних та таблиці."""
        selection = self.tree.selection()
        if not selection:
            messagebox.showwarning("Увага", "Будь ласка, виберіть акт для видалення")
            return
        
        # Отримуємо дані вибраного елемента
        item = selection[0]
        values = self.tree.item(item)['values']
        
        if not values or len(values) < 8:
            messagebox.showerror("Помилка", "Не вдалося отримати дані акту")
            return
        
        company = values[0]
        counterparty = values[1]
        # values[2] = Найменування (завжди "Електроенергія")
        period = values[3]
        # values[4] = Кількість, values[5] = Ціна, values[6] = Сума без ПДВ (розрахункові)
        amount_str = values[7]  # Сума з ПДВ
        
        # Конвертуємо суму назад в числовий формат
        try:
            amount = float(str(amount_str).replace(' ', '').replace(',', '.'))
        except (ValueError, AttributeError):
            messagebox.showerror("Помилка", "Не вдалося обробити суму акту")
            return
        
        # Підтвердження видалення
        if not confirm_delete(
            self.parent,
            "Підтвердження видалення",
            f"Ви впевнені, що хочете видалити цей акт?\n\n"
            f"Компанія: {company}\n"
            f"Контрагент: {counterparty}\n"
            f"Період: {period}\n"
            f"Сума з ПДВ: {amount_str}",
        ):
            return
        
        try:
            # Видаляємо з бази даних
            deleted_count = self.db_manager.delete_act(company, counterparty, period, amount)
            
            if deleted_count > 0:
                messagebox.showinfo("Успіх", f"Акт успішно видалено")
                self.logger.info(f"Deleted act: {company} - {counterparty} - {period}")
                # Оновлюємо таблицю та звіти
                if self.update_callback:
                    self.update_callback()
                else:
                    # Видаляємо з таблиці
                    self.tree.delete(item)
                    # Оновлюємо оригінальні дані
                    self.original_data = [act for act in self.original_data 
                                         if not (act[0] == company and act[1] == counterparty 
                                                and act[2] == period and act[3] == amount)]
            else:
                messagebox.showwarning("Увага", "Акт не знайдено в базі даних")
                
        except Exception as e:
            self.logger.error(f"Error deleting act: {str(e)}")
            messagebox.showerror("Помилка", f"Не вдалося видалити акт:\n{str(e)}")

    def update(self) -> None:
        """Update table with current acts data."""
        self.logger.info("Updating ActsTable")
        self.original_data = self.db_manager.get_all_acts()
        self.logger.info(f"Loaded {len(self.original_data)} acts")

        rows = []
        for company, counterparty, period, amount, energy_volume, pdf_path in self.original_data:
            name = "Електроенергія"
            # Сума без ПДВ = Сума / 1.2
            amount_without_vat = amount / 1.2 if amount else 0.0
            # Ціна = Сума без ПДВ / Кількість
            price = amount_without_vat / energy_volume if energy_volume else 0.0

            formatted_amount = self.formatter.format_number(amount)
            formatted_volume = self.formatter.format_number(energy_volume) if energy_volume else "0,00"
            formatted_price = self.formatter.format_number(price) if energy_volume else "0,00"
            formatted_without_vat = self.formatter.format_number(amount_without_vat)

            rows.append((
                company, counterparty, name, period,
                formatted_volume, formatted_price,
                formatted_without_vat, formatted_amount,
                pdf_path,
            ))

        self.set_rows(rows)

    def _get_row_tags(self, row: Tuple[Any, ...]) -> Optional[Tuple[str, ...]]:
        pdf_path = row[8] if len(row) > 8 else None
        if pdf_path:
            return (pdf_path,)
        return None