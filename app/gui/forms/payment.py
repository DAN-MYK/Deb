"""
Payment form module.

This module provides a form for adding payments to the database,
either from files (Excel — 1C or bank statements) or through manual input.
"""
# Standard library imports
import logging
from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

logger = logging.getLogger("deb.gui.forms.payment")

# Third-party imports
import customtkinter as ctk

# Local imports
from app.core.data.db import DatabaseManager
from app.core.data.processor import DataProcessor
from app.core.validation.file_validator import FileValidator
from app.gui.utils.async_worker import run_in_thread


class PaymentForm:
    """
    Form for adding payments from file or manually.

    Provides a tabbed interface with two modes:
    1. File upload (1С) - Import payments from Excel or PDF files
    2. Manual entry - Add payments manually through input fields

    Attributes:
        data_processor: DataProcessor for file processing
        db_manager: DatabaseManager for database operations
        update_callback: Callback to refresh tables after adding payments
        payment_window: The toplevel window widget

    Example:
        >>> form = PaymentForm(root, processor, db_manager, callback)
        # User interacts with the form to add payments
    """

    def __init__(
        self,
        root: Any,
        data_processor: DataProcessor,
        db_manager: DatabaseManager,
        update_callback: Callable[[], None],
        edit_mode: bool = False,
        payment_data: Optional[dict] = None
    ) -> None:
        """
        Initialize the payment form.

        Args:
            root: Parent window widget
            data_processor: DataProcessor instance for file processing
            db_manager: DatabaseManager instance for database operations
            update_callback: Callback function to refresh tables after adding payments
            edit_mode: True if editing existing payment, False if creating new
            payment_data: Existing payment data for edit mode (dict with keys: company,
                         counterparty, period, amount, payment_date, purpose)
        """
        self.data_processor = data_processor
        self.db_manager = db_manager
        self.update_callback = update_callback
        self.edit_mode = edit_mode
        self.payment_data = payment_data or {}
        self.load_button: Optional[ctk.CTkButton] = None
        self.status_label: Optional[ctk.CTkLabel] = None
        self.is_processing = False

        self.payment_window = ctk.CTkToplevel(root)
        self.payment_window.title("Редагувати оплату" if edit_mode else "Додати оплату")
        self.payment_window.geometry("750x600")

        # Центруємо вікно
        self.payment_window.transient(root)
        self.payment_window.grab_set()

        # Додаємо хоткеї
        self.payment_window.bind('<Control-Return>', lambda event: self.save_payment())
        self.payment_window.bind('<Escape>', lambda event: self.payment_window.destroy())

        self.create_widgets()

    def create_widgets(self) -> None:
        """Create all form widgets."""
        # Основний контейнер
        main_frame = ctk.CTkFrame(self.payment_window, fg_color="transparent")
        main_frame.pack(pady=10, padx=15, fill="both", expand=True)

        if self.edit_mode:
            # В режимі редагування показуємо тільки форму без вкладок
            self.create_manual_tab(main_frame, show_tabs=False)
        else:
            # В режимі створення показуємо вкладки
            self.tabview = ctk.CTkTabview(main_frame)
            self.tabview.pack(fill="both", expand=True)

            # Додаємо вкладки
            self.tabview.add("📂 Завантажити файл")
            self.tabview.add("✍️ Ввести вручну")

            # Вкладка завантаження
            self.create_file_tab()

            # Вкладка ручного введення
            self.create_manual_tab()

    def create_file_tab(self) -> None:
        """Створює вкладку завантаження файлів."""
        tab = self.tabview.tab("📂 Завантажити файл")

        # Верхня панель з описом
        info_frame = ctk.CTkFrame(tab, fg_color=("gray95", "gray17"), corner_radius=8)
        info_frame.pack(pady=10, padx=15, fill="x")

        info_text = """📋 Підтримувані джерела:

• 1С - оплати з програми 1С (Excel)
• Банк - банківські виписки (Ощадбанк, Укргазбанк)

Excel файл має містити відповідні колонки залежно від джерела."""

        ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=ctk.CTkFont(size=12),
            justify="left",
            anchor="w"
        ).pack(pady=10, padx=15, fill="x")

        # Основний контейнер для кнопок
        content_frame = ctk.CTkFrame(tab, fg_color="transparent")
        content_frame.pack(pady=10, fill="both", expand=True)

        # Центруємо контент
        center_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.4, anchor="center")

        # Кнопка завантаження файлу
        self.load_button = ctk.CTkButton(
            center_frame,
            text="📂 Завантажити файл",
            command=self.load_file_1c,
            width=280,
            height=38,
            font=ctk.CTkFont(size=13),
            fg_color=("#3498db", "#2980b9"),
            hover_color=("#2980b9", "#21618c")
        )
        self.load_button.pack(pady=10)

        # Статус
        self.status_label = ctk.CTkLabel(
            tab,
            text="",
            font=ctk.CTkFont(size=12),
            text_color=("#3498db", "#5dade2")
        )
        self.status_label.pack(side="bottom", pady=10)

    def create_manual_tab(self, parent: Optional[Any] = None, show_tabs: bool = True) -> None:
        """Створює вкладку ручного введення."""
        if show_tabs:
            tab = self.tabview.tab("✍️ Ввести вручну")
        elif parent is not None:
            tab = parent
        else:
            raise ValueError("Parent must be provided when show_tabs=False")

        # Контейнер для форми
        form_container = ctk.CTkFrame(tab, fg_color="transparent")
        form_container.pack(pady=5, padx=15, fill="both", expand=True)

        # ═══════════════════════════════════════════════════════════
        # СЕКЦІЯ 1: Основна інформація
        # ═══════════════════════════════════════════════════════════
        basic_frame = ctk.CTkFrame(form_container, corner_radius=8,
                                   fg_color=("gray95", "gray17"))
        basic_frame.pack(pady=(0, 10), fill="x")

        ctk.CTkLabel(
            basic_frame,
            text="📋 Основна інформація",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        ).pack(pady=(10, 6), padx=15, fill="x")

        # Отримуємо списки для випадаючих списків
        companies = self.db_manager.get_unique_companies()
        counterparties = self.db_manager.get_unique_counterparties()

        # Компанія
        self._create_combobox_field(
            basic_frame, "Компанія *", "company_entry",
            values=companies if companies else [""],
            placeholder="ТОВ 'Компанія'",
            tooltip="Ваша організація"
        )

        # Контрагент
        self._create_combobox_field(
            basic_frame, "Контрагент *", "counterparty_entry",
            values=counterparties if counterparties else [""],
            placeholder="ТОВ 'Клієнт'",
            tooltip="Платник"
        )

        # Період
        self._create_field(
            basic_frame, "Період *", "period_entry",
            placeholder="11.2024 або 11-2024",
            tooltip="Період оплати (місяць.рік)"
        )

        # ═══════════════════════════════════════════════════════════
        # СЕКЦІЯ 2: Деталі оплати (2 колонки)
        # ═══════════════════════════════════════════════════════════
        data_frame = ctk.CTkFrame(form_container, corner_radius=8,
                                  fg_color=("gray95", "gray17"))
        data_frame.pack(pady=(0, 10), fill="x")

        ctk.CTkLabel(
            data_frame,
            text="💰 Деталі оплати",
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w"
        ).pack(pady=(10, 6), padx=15, fill="x")

        # Контейнер для 2-колонкового layout
        cols_frame = ctk.CTkFrame(data_frame, fg_color="transparent")
        cols_frame.pack(padx=15, pady=(0, 10), fill="x")

        # Ліва колонка
        left_col = ctk.CTkFrame(cols_frame, fg_color="transparent")
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 8))

        # Права колонка
        right_col = ctk.CTkFrame(cols_frame, fg_color="transparent")
        right_col.pack(side="right", fill="both", expand=True, padx=(8, 0))

        # === Ліва колонка ===

        # Сума
        self._create_compact_field(
            left_col, "Сума, грн *", "amount_entry",
            placeholder="1200.00",
            tooltip="Сума оплати (обов'язково)"
        )

        # Дата оплати
        self._create_compact_field(
            left_col, "Дата оплати", "payment_date_entry",
            placeholder="2024-11-15",
            tooltip="Дата здійснення оплати (YYYY-MM-DD)"
        )

        # === Права колонка ===

        # Призначення платежу
        container = ctk.CTkFrame(right_col, fg_color="transparent")
        container.pack(pady=5, fill="both", expand=True)

        label_widget = ctk.CTkLabel(
            container,
            text="Призначення платежу",
            font=ctk.CTkFont(size=11),
            anchor="w"
        )
        label_widget.pack(anchor="w", pady=(0, 3))

        # Використовуємо textbox для довшого тексту
        self.purpose_entry = ctk.CTkTextbox(
            container,
            height=80,
            font=ctk.CTkFont(size=12)
        )
        self.purpose_entry.pack(fill="both", expand=True)

        # Заповнюємо значенням в режимі редагування
        if self.edit_mode and 'purpose' in self.payment_data and self.payment_data['purpose']:
            self.purpose_entry.insert("1.0", self.payment_data['purpose'])

        # Tooltip
        self._add_tooltip(self.purpose_entry, "Опис призначення платежу")

        # ═══════════════════════════════════════════════════════════
        # СЕКЦІЯ 3: Підказки та дії
        # ═══════════════════════════════════════════════════════════

        # Підказки
        hints_frame = ctk.CTkFrame(form_container, fg_color="transparent")
        hints_frame.pack(pady=(6, 0), fill="x")

        hint_text = "💡 Поля позначені * обов'язкові"
        ctk.CTkLabel(
            hints_frame,
            text=hint_text,
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w"
        ).pack(side="left")

        # Кнопки
        buttons_frame = ctk.CTkFrame(form_container, fg_color="transparent")
        buttons_frame.pack(pady=(12, 5), fill="x")

        # Кнопка скасування
        ctk.CTkButton(
            buttons_frame,
            text="Скасувати (Esc)",
            command=self.payment_window.destroy,
            width=140,
            height=38,
            font=ctk.CTkFont(size=12),
            fg_color="transparent",
            border_width=1,
            border_color=("gray70", "gray30"),
            hover_color=("gray90", "gray25")
        ).pack(side="left", padx=(0, 10))

        # Кнопка збереження
        save_btn = ctk.CTkButton(
            buttons_frame,
            text="💾 Зберегти (Ctrl+Enter)",
            command=self.save_payment,
            width=200,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#2ecc71", "#27ae60"),
            hover_color=("#27ae60", "#229954")
        )
        save_btn.pack(side="right")

        # Автофокус на перше поле
        self.payment_window.after(100, lambda: self.company_entry.focus())

    def _create_field(
        self,
        parent: Any,
        label: str,
        attr_name: str,
        placeholder: str = "",
        tooltip: str = ""
    ) -> None:
        """Створює поле з label."""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(pady=5, padx=15, fill="x")

        # Label
        label_widget = ctk.CTkLabel(
            container,
            text=label,
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        label_widget.pack(anchor="w", pady=(0, 4))

        # Entry
        entry = ctk.CTkEntry(
            container,
            placeholder_text=placeholder,
            height=34,
            font=ctk.CTkFont(size=12)
        )
        entry.pack(fill="x")
        setattr(self, attr_name, entry)

        # Заповнюємо значенням в режимі редагування
        if self.edit_mode and attr_name == 'period_entry' and 'period' in self.payment_data:
            entry.insert(0, self.payment_data['period'])

        # Tooltip (опціонально)
        if tooltip:
            self._add_tooltip(entry, tooltip)

    def _create_combobox_field(
        self,
        parent: Any,
        label: str,
        attr_name: str,
        values: list,
        placeholder: str = "",
        tooltip: str = ""
    ) -> None:
        """Створює випадаючий список з label."""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(pady=5, padx=15, fill="x")

        # Label
        label_widget = ctk.CTkLabel(
            container,
            text=label,
            font=ctk.CTkFont(size=12),
            anchor="w"
        )
        label_widget.pack(anchor="w", pady=(0, 4))

        # ComboBox
        combobox = ctk.CTkComboBox(
            container,
            values=values,
            height=34,
            font=ctk.CTkFont(size=12)
        )
        combobox.set("")  # Порожнє значення за замовчуванням
        combobox.pack(fill="x")
        setattr(self, attr_name, combobox)

        # Заповнюємо значенням в режимі редагування
        if self.edit_mode and attr_name in ['company_entry', 'counterparty_entry']:
            field_key = attr_name.replace('_entry', '')
            if field_key in self.payment_data:
                combobox.set(self.payment_data[field_key])

        # Tooltip (опціонально)
        if tooltip:
            self._add_tooltip(combobox, tooltip)

    def _create_compact_field(
        self,
        parent: Any,
        label: str,
        attr_name: str,
        placeholder: str = "",
        tooltip: str = ""
    ) -> None:
        """Створює компактне поле для 2-колонкового layout."""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(pady=5, fill="x")

        # Label
        label_widget = ctk.CTkLabel(
            container,
            text=label,
            font=ctk.CTkFont(size=11),
            anchor="w"
        )
        label_widget.pack(anchor="w", pady=(0, 3))

        # Entry
        entry = ctk.CTkEntry(
            container,
            placeholder_text=placeholder,
            height=32,
            font=ctk.CTkFont(size=12)
        )
        entry.pack(fill="x")
        setattr(self, attr_name, entry)

        # Заповнюємо значенням в режимі редагування
        if self.edit_mode:
            field_map = {
                'amount_entry': 'amount',
                'payment_date_entry': 'payment_date'
            }
            if attr_name in field_map and field_map[attr_name] in self.payment_data:
                value = self.payment_data[field_map[attr_name]]
                if value is not None:
                    # Для суми форматуємо з комою
                    if attr_name == 'amount_entry':
                        entry.insert(0, str(value).replace('.', ','))
                    else:
                        entry.insert(0, str(value))

        # Tooltip
        if tooltip:
            self._add_tooltip(entry, tooltip)

    def _add_tooltip(self, widget: Any, text: str) -> None:
        """Додає tooltip до віджета."""
        def on_enter(event):
            tooltip = ctk.CTkToplevel()
            tooltip.wm_overrideredirect(True)
            tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")

            label = ctk.CTkLabel(
                tooltip,
                text=text,
                font=ctk.CTkFont(size=10),
                fg_color=("gray85", "gray25"),
                corner_radius=4,
                padx=8,
                pady=4
            )
            label.pack()

            widget._tooltip = tooltip

        def on_leave(event):
            if hasattr(widget, '_tooltip'):
                widget._tooltip.destroy()
                delattr(widget, '_tooltip')

        widget.bind('<Enter>', on_enter)
        widget.bind('<Leave>', on_leave)

    def load_file_1c(self) -> None:
        """Завантаження файлу оплат (1С або банківська виписка)"""
        if self.is_processing:
            return

        # Спочатку питаємо користувача про джерело файлу
        choice_dialog = ctk.CTkToplevel(self.payment_window)
        choice_dialog.title("Виберіть джерело файлу")
        choice_dialog.geometry("400x200")
        choice_dialog.transient(self.payment_window)
        choice_dialog.grab_set()

        # Центруємо діалог
        choice_dialog.update_idletasks()
        x = self.payment_window.winfo_x() + (self.payment_window.winfo_width() // 2) - (choice_dialog.winfo_width() // 2)
        y = self.payment_window.winfo_y() + (self.payment_window.winfo_height() // 2) - (choice_dialog.winfo_height() // 2)
        choice_dialog.geometry(f"+{x}+{y}")

        selected_source = [None]  # Використовуємо список для мутабельності

        def select_source(source: str) -> None:
            selected_source[0] = source
            choice_dialog.destroy()

        # Заголовок
        label_frame = ctk.CTkFrame(choice_dialog, fg_color="transparent")
        label_frame.pack(pady=20, fill="both", expand=True)

        ctk.CTkLabel(
            label_frame,
            text="Оберіть джерело файлу з оплатами:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=10)

        # Кнопки вибору
        buttons_frame = ctk.CTkFrame(choice_dialog, fg_color="transparent")
        buttons_frame.pack(pady=10, fill="both", expand=True)

        ctk.CTkButton(
            buttons_frame,
            text="📊 1С (Excel з програми 1С)",
            command=lambda: select_source("1c"),
            width=300,
            height=40,
            font=ctk.CTkFont(size=13),
            fg_color="#3498db",
            hover_color="#2980b9"
        ).pack(pady=5)

        ctk.CTkButton(
            buttons_frame,
            text="🏦 Банк (банківська виписка)",
            command=lambda: select_source("bank"),
            width=300,
            height=40,
            font=ctk.CTkFont(size=13),
            fg_color="#9b59b6",
            hover_color="#8e44ad"
        ).pack(pady=5)

        # Чекаємо поки користувач зробить вибір
        self.payment_window.wait_window(choice_dialog)

        # Якщо користувач закрив діалог без вибору
        if selected_source[0] is None:
            return

        source_type = selected_source[0]

        # Тепер вибираємо файл
        file_path = filedialog.askopenfilename(
            title=f"Виберіть файл ({'1С' if source_type == '1c' else 'банківська виписка'})",
            filetypes=[
                ("Excel files", "*.xlsx *.xls *.xlsm"),
            ]
        )
        if not file_path:
            return

        # Validate file
        try:
            FileValidator.validate_file_path(
                file_path,
                allowed_extensions=['.xlsx', '.xls', '.xlsm']
            )
        except (FileNotFoundError, ValueError, PermissionError) as e:
            messagebox.showerror("Помилка валідації", str(e))
            return

        # Disable button and show status
        self.is_processing = True
        if self.load_button:
            self.load_button.configure(state="disabled")
        if self.status_label:
            self.status_label.configure(text="⏳ Обробка файлу...")

        # Define the processing task
        def process_file() -> tuple:
            """Process file based on selected source type."""
            if source_type == "1c":
                count = self.data_processor.process_1c_payments(
                    file_path, self.db_manager
                )
                return count, "1С"
            else:  # bank
                count = self.data_processor.process_bank_statement_excel(
                    file_path, self.db_manager
                )
                return count, "Банк"

        # Define completion callback
        def on_complete(result: tuple) -> None:
            """Handle successful completion"""
            count, file_type = result
            self.is_processing = False

            if self.load_button:
                self.load_button.configure(state="normal")
            if self.status_label:
                self.status_label.configure(text="")

            message = f"✅ Файл успішно оброблено!\n\n"
            message += f"💰 Оплат додано: {count}\n"
            message += f"📎 Тип файлу: {file_type}"

            messagebox.showinfo("Успіх", message)
            self.update_callback()
            self.payment_window.destroy()

        # Define error callback
        def on_error(error: Exception) -> None:
            """Handle processing error"""
            self.is_processing = False

            if self.load_button:
                self.load_button.configure(state="normal")
            if self.status_label:
                self.status_label.configure(text="❌ Помилка обробки")

            messagebox.showerror("Помилка", f"Не вдалося обробити файл:\n{str(error)}")

        # Run processing in background thread
        run_in_thread(
            task=process_file,
            on_complete=on_complete,
            on_error=on_error
        )

    def save_payment(self) -> None:
        """Збереження або оновлення оплати."""
        try:
            company = self.company_entry.get().strip()
            counterparty = self.counterparty_entry.get().strip()
            period = self.period_entry.get().strip()
            amount_str = self.amount_entry.get().strip().replace(',', '.')
            payment_date = self.payment_date_entry.get().strip() or None
            purpose = self.purpose_entry.get("1.0", "end-1c").strip() or None

            if not company or not counterparty or not period or not amount_str:
                raise ValueError("Заповніть обов'язкові поля, позначені *")

            amount = float(amount_str)

            if self.edit_mode:
                # Оновлюємо існуючу оплату
                updated_count = self.db_manager.update_payment(
                    self.payment_data['company'],
                    self.payment_data['counterparty'],
                    self.payment_data['period'],
                    self.payment_data['amount'],
                    company,
                    counterparty,
                    period,
                    amount
                )
                if updated_count > 0:
                    messagebox.showinfo("Успіх", "✅ Оплату успішно оновлено!")
                else:
                    messagebox.showwarning("Увага", "Оплату не знайдено для оновлення")
            else:
                # Створюємо нову оплату
                self.db_manager.save_payment(
                    company, counterparty, period, amount,
                    payment_date=payment_date,
                    purpose=purpose
                )
                messagebox.showinfo("Успіх", "✅ Оплату успішно збережено!")

            self.update_callback()
            self.payment_window.destroy()
        except ValueError as e:
            messagebox.showerror("Помилка", str(e))
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося зберегти оплату:\n{str(e)}")
