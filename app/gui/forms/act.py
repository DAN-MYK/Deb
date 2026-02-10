"""
Act form module.

This module provides a form for adding acts to the database,
either from files (Excel/PDF) or through manual input.
"""
# Standard library imports
import logging
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Any, Callable, Optional

logger = logging.getLogger("deb.gui.forms.act")

# Third-party imports
import customtkinter as ctk

# Local imports
from app.core.data.db import DatabaseManager
from app.core.data.processor import DataProcessor
from app.core.validation.file_validator import FileValidator
from app.gui.utils.async_worker import run_in_thread


class ActForm:
    """
    Form for adding acts from file or manually.

    Provides a tabbed interface with two modes:
    1. File upload (1С) - Import acts from Excel or PDF files
    2. Manual entry - Add acts manually through input fields

    Attributes:
        data_processor: DataProcessor for file processing
        db_manager: DatabaseManager for database operations
        update_callback: Callback to refresh tables after adding acts
        act_window: The toplevel window widget

    Example:
        >>> form = ActForm(root, processor, db_manager, callback)
        # User interacts with the form to add acts
    """

    def __init__(
        self,
        root: Any,
        data_processor: DataProcessor,
        db_manager: DatabaseManager,
        update_callback: Callable[[], None],
        edit_mode: bool = False,
        act_data: Optional[dict] = None
    ) -> None:
        """
        Initialize the act form.

        Args:
            root: Parent window widget
            data_processor: DataProcessor instance for file processing
            db_manager: DatabaseManager instance for database operations
            update_callback: Callback function to refresh tables after adding acts
            edit_mode: True if editing existing act, False if creating new
            act_data: Existing act data for edit mode (dict with keys: company, counterparty,
                     period, amount, energy_volume, cost_without_vat, price_without_vat)
        """
        self.data_processor = data_processor
        self.db_manager = db_manager
        self.update_callback = update_callback
        self.edit_mode = edit_mode
        self.act_data = act_data or {}
        self.load_button: Optional[ctk.CTkButton] = None
        self.load_folder_button: Optional[ctk.CTkButton] = None
        self.status_label: Optional[ctk.CTkLabel] = None
        self.is_processing = False

        self.act_window = ctk.CTkToplevel(root)
        self.act_window.title("Редагувати акт" if edit_mode else "Додати акт")
        self.act_window.geometry("750x680")

        # Центруємо вікно
        self.act_window.transient(root)
        self.act_window.grab_set()

        # Додаємо хоткеї
        self.act_window.bind('<Control-Return>', lambda event: self.save_act())
        self.act_window.bind('<Escape>', lambda event: self.act_window.destroy())

        self.create_widgets()

    def create_widgets(self) -> None:
        """Create all form widgets."""
        # Основний контейнер
        main_frame = ctk.CTkFrame(self.act_window, fg_color="transparent")
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

        ctk.CTkLabel(
            info_frame,
            text="📋 Підтримувані формати: Excel (.xlsx, .xls) та PDF",
            font=ctk.CTkFont(size=13),
            anchor="w"
        ).pack(pady=8, padx=15, fill="x")

        # Основний контейнер для кнопок
        content_frame = ctk.CTkFrame(tab, fg_color="transparent")
        content_frame.pack(pady=10, fill="both", expand=True)

        # Центруємо контент
        center_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
        center_frame.place(relx=0.5, rely=0.4, anchor="center")

        # Кнопка завантаження файлу
        file_btn_frame = ctk.CTkFrame(center_frame, corner_radius=10,
                                      fg_color=("gray90", "gray20"))
        file_btn_frame.pack(pady=8, padx=20)

        ctk.CTkLabel(
            file_btn_frame,
            text="📄 Один файл",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(12, 4))

        ctk.CTkLabel(
            file_btn_frame,
            text="Завантажити Excel або PDF файл з актами",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(pady=(0, 8))

        self.load_button = ctk.CTkButton(
            file_btn_frame,
            text="Вибрати файл",
            command=self.load_file_1c,
            width=280,
            height=38,
            font=ctk.CTkFont(size=13),
            fg_color=("#3498db", "#2980b9"),
            hover_color=("#2980b9", "#21618c")
        )
        self.load_button.pack(pady=(0, 12), padx=20)

        # Кнопка завантаження папки
        folder_btn_frame = ctk.CTkFrame(center_frame, corner_radius=10,
                                        fg_color=("gray90", "gray20"))
        folder_btn_frame.pack(pady=8, padx=20)

        ctk.CTkLabel(
            folder_btn_frame,
            text="📁 Папка з актами",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=(12, 4))

        ctk.CTkLabel(
            folder_btn_frame,
            text="Обробити всі PDF файли в папці (включно з підпапками)",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(pady=(0, 8))

        self.load_folder_button = ctk.CTkButton(
            folder_btn_frame,
            text="Вибрати папку",
            command=self.load_folder_1c,
            width=280,
            height=38,
            font=ctk.CTkFont(size=13),
            fg_color=("#9b59b6", "#8e44ad"),
            hover_color=("#8e44ad", "#7d3c98")
        )
        self.load_folder_button.pack(pady=(0, 12), padx=20)

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
            tooltip="Ваша організація (виконавець)"
        )

        # Контрагент
        self._create_combobox_field(
            basic_frame, "Контрагент *", "counterparty_entry",
            values=counterparties if counterparties else [""],
            placeholder="ТОВ 'Клієнт'",
            tooltip="Замовник послуг"
        )

        # Період
        self._create_field(
            basic_frame, "Період *", "period_entry",
            placeholder="11.2024 або 11-2024",
            tooltip="Період надання послуг (місяць.рік)"
        )

        # ═══════════════════════════════════════════════════════════
        # СЕКЦІЯ 2: Обсяги та фінанси (2 колонки)
        # ═══════════════════════════════════════════════════════════
        data_frame = ctk.CTkFrame(form_container, corner_radius=8,
                                  fg_color=("gray95", "gray17"))
        data_frame.pack(pady=(0, 10), fill="x")

        ctk.CTkLabel(
            data_frame,
            text="📊 Обсяги та фінанси",
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

        # === Ліва колонка: Обсяги ===

        # Кількість
        self._create_compact_field(
            left_col, "Кількість, кВт·год", "energy_volume_entry",
            placeholder="1 500.00",
            tooltip="Обсяг електроенергії"
        )
        self.energy_volume_entry.bind('<KeyRelease>', self._on_volume_change)

        # Сума з ПДВ
        self._create_compact_field(
            left_col, "Сума з ПДВ, грн *", "amount_entry",
            placeholder="1 200.00",
            tooltip="Загальна сума з ПДВ (обов'язково)"
        )
        self.amount_entry.bind('<KeyRelease>', self._on_amount_change)

        # === Права колонка: Розрахунки ===

        # Сума без ПДВ
        self._create_compact_field(
            right_col, "Сума без ПДВ, грн", "cost_without_vat_entry",
            placeholder="1 000.00",
            tooltip="Автоматично: сума з ПДВ ÷ 1.2",
            is_calculated=True
        )
        self.cost_without_vat_entry.bind('<KeyRelease>', self._on_cost_change)

        # Ціна без ПДВ
        self._create_compact_field(
            right_col, "Ціна, грн/кВт·год", "price_without_vat_entry",
            placeholder="0.6667",
            tooltip="Автоматично: сума без ПДВ ÷ кількість",
            is_calculated=True
        )

        # ═══════════════════════════════════════════════════════════
        # СЕКЦІЯ 3: Підказки та дії
        # ═══════════════════════════════════════════════════════════

        # Підказки
        hints_frame = ctk.CTkFrame(form_container, fg_color="transparent")
        hints_frame.pack(pady=(6, 0), fill="x")

        hint_text = "💡 Поля позначені * обов'язкові  •  🧮 Розрахункові поля заповнюються автоматично"
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
            command=self.act_window.destroy,
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
            command=self.save_act,
            width=200,
            height=38,
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color=("#2ecc71", "#27ae60"),
            hover_color=("#27ae60", "#229954")
        )
        save_btn.pack(side="right")

        # Автофокус на перше поле
        self.act_window.after(100, lambda: self.company_entry.focus())

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
        if self.edit_mode and attr_name == 'period_entry' and 'period' in self.act_data:
            entry.insert(0, self.act_data['period'])

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
            if field_key in self.act_data:
                combobox.set(self.act_data[field_key])

        # Tooltip (опціонально)
        if tooltip:
            self._add_tooltip(combobox, tooltip)

    def _create_compact_field(
        self,
        parent: Any,
        label: str,
        attr_name: str,
        placeholder: str = "",
        tooltip: str = "",
        is_calculated: bool = False
    ) -> None:
        """Створює компактне поле для 2-колонкового layout."""
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(pady=5, fill="x")

        # Label з іконкою якщо розрахункове
        label_text = f"🧮 {label}" if is_calculated else label
        label_widget = ctk.CTkLabel(
            container,
            text=label_text,
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
                'energy_volume_entry': ('energy_volume', 2),
                'amount_entry': ('amount', 2),
                'cost_without_vat_entry': ('cost_without_vat', 2),
                'price_without_vat_entry': ('price_without_vat', 4)
            }
            if attr_name in field_map:
                field_key, decimals = field_map[attr_name]
                if field_key in self.act_data:
                    value = self.act_data[field_key]
                    if value is not None:
                        # Форматуємо число з пробілами та комою
                        formatted = self._format_number_display(float(value), decimals=decimals)
                        entry.insert(0, formatted)

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

    def _format_number_field(self, event: Any) -> None:
        """Форматує числове поле з розділювачами тисячних (пробіли)."""
        widget = event.widget

        # Отримуємо поточне значення та позицію курсору
        current_value = widget.get()
        cursor_pos = widget.index("insert")

        # Видаляємо всі пробіли для обробки
        clean_value = current_value.replace(' ', '')

        # Якщо порожнє або тільки роздільник - не форматуємо
        if not clean_value or clean_value in [',', '.']:
            return

        try:
            # Розділяємо на цілу та дробову частини
            if ',' in clean_value:
                parts = clean_value.split(',')
            elif '.' in clean_value:
                parts = clean_value.split('.')
            else:
                parts = [clean_value, '']

            integer_part = parts[0]
            decimal_part = parts[1] if len(parts) > 1 else ''

            # Форматуємо цілу частину з пробілами
            if integer_part:
                # Додаємо пробіли кожні 3 цифри справа наліво
                formatted_int = ''
                for i, digit in enumerate(reversed(integer_part)):
                    if i > 0 and i % 3 == 0:
                        formatted_int = ' ' + formatted_int
                    formatted_int = digit + formatted_int
            else:
                formatted_int = ''

            # Складаємо відформатоване значення
            if decimal_part or clean_value.endswith(',') or clean_value.endswith('.'):
                formatted_value = f"{formatted_int},{decimal_part}"
            else:
                formatted_value = formatted_int

            # Якщо значення змінилося - оновлюємо
            if formatted_value != current_value:
                # Обчислюємо нову позицію курсору
                spaces_before = current_value[:cursor_pos].count(' ')
                spaces_after = formatted_value[:cursor_pos].count(' ')
                new_cursor_pos = cursor_pos + (spaces_after - spaces_before)

                # Оновлюємо значення
                widget.delete(0, 'end')
                widget.insert(0, formatted_value)

                # Відновлюємо позицію курсору
                try:
                    widget.icursor(max(0, new_cursor_pos))
                except Exception:
                    pass

        except (ValueError, IndexError):
            # Якщо щось пішло не так - не форматуємо
            pass

    def _on_amount_change(self, event: Any = None) -> None:
        """Обробка зміни суми з ПДВ: форматування + розрахунок."""
        self._format_number_field(event)
        self._calculate_cost_without_vat()

    def _on_volume_change(self, event: Any = None) -> None:
        """Обробка зміни кількості: форматування + розрахунок."""
        self._format_number_field(event)
        self._calculate_price()

    def _on_cost_change(self, event: Any = None) -> None:
        """Обробка зміни суми без ПДВ: форматування + розрахунок."""
        self._format_number_field(event)
        self._calculate_price()

    def _calculate_cost_without_vat(self, event: Any = None) -> None:
        """Автообчислення суми без ПДВ."""
        try:
            amount_str = self.amount_entry.get().strip().replace(' ', '').replace(',', '.')
            if amount_str:
                amount = float(amount_str)
                cost_without_vat = amount / 1.2
                # Форматуємо з пробілами
                formatted = self._format_number_display(cost_without_vat, decimals=2)
                self.cost_without_vat_entry.delete(0, 'end')
                self.cost_without_vat_entry.insert(0, formatted)
                self._calculate_price()
        except (ValueError, ZeroDivisionError):
            pass

    def _calculate_price(self, event: Any = None) -> None:
        """Автообчислення ціни без ПДВ."""
        try:
            cost_str = self.cost_without_vat_entry.get().strip().replace(' ', '').replace(',', '.')
            volume_str = self.energy_volume_entry.get().strip().replace(' ', '').replace(',', '.')

            if cost_str and volume_str:
                cost = float(cost_str)
                volume = float(volume_str)
                if volume > 0:
                    price = cost / volume
                    # Форматуємо з пробілами (4 знаки після коми для ціни)
                    formatted = self._format_number_display(price, decimals=4)
                    self.price_without_vat_entry.delete(0, 'end')
                    self.price_without_vat_entry.insert(0, formatted)
        except (ValueError, ZeroDivisionError):
            pass

    def _format_number_display(self, number: float, decimals: int = 2) -> str:
        """Форматує число для відображення з пробілами як розділювачі тисячних."""
        # Форматуємо число
        formatted = f"{number:.{decimals}f}"
        # Розділяємо на цілу та дробову частини
        parts = formatted.split('.')
        integer_part = parts[0]
        decimal_part = parts[1] if len(parts) > 1 else ''

        # Додаємо пробіли до цілої частини
        formatted_int = ''
        for i, digit in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                formatted_int = ' ' + formatted_int
            formatted_int = digit + formatted_int

        # Повертаємо з комою як роздільник
        return f"{formatted_int},{decimal_part}" if decimal_part else formatted_int

    def load_file_1c(self) -> None:
        """Завантаження файлу з 1С або PDF"""
        if self.is_processing:
            return

        file_path = filedialog.askopenfilename(
            title="Виберіть файл",
            filetypes=[
                ("Supported files", "*.xlsx *.xls *.pdf"),
                ("Excel files", "*.xlsx *.xls"),
                ("PDF files", "*.pdf")
            ]
        )
        if not file_path:
            return

        # Validate file
        try:
            FileValidator.validate_file_path(
                file_path,
                allowed_extensions=['.xlsx', '.xls', '.xlsm', '.pdf']
            )
        except (FileNotFoundError, ValueError, PermissionError) as e:
            messagebox.showerror("Помилка валідації", str(e))
            return

        # Визначаємо тип файлу за розширенням
        file_extension = file_path.lower().split('.')[-1]

        # Disable buttons and show status
        self.is_processing = True
        if self.load_button:
            self.load_button.configure(state="disabled")
        if self.load_folder_button:
            self.load_folder_button.configure(state="disabled")
        if self.status_label:
            self.status_label.configure(text="⏳ Обробка файлу...")

        # Define the processing task
        def process_file() -> tuple:
            """Process file and return (count, file_type)"""
            if file_extension == 'pdf':
                count = self.data_processor.process_act_pdf(file_path, self.db_manager)
                return count, "PDF"
            elif file_extension in ['xlsx', 'xls', 'xlsm']:
                count = self.data_processor.process_1c_acts(file_path, self.db_manager)
                return count, "Excel"
            else:
                raise ValueError(f"Непідтримуваний формат файлу: {file_extension}")

        # Define completion callback
        def on_complete(result: tuple) -> None:
            """Handle successful completion"""
            count, file_type = result
            self.is_processing = False

            if self.load_button:
                self.load_button.configure(state="normal")
            if self.load_folder_button:
                self.load_folder_button.configure(state="normal")
            if self.status_label:
                self.status_label.configure(text="")

            message = f"✅ Файл успішно оброблено!\n\n"
            message += f"📄 Актів додано: {count}\n"
            message += f"📎 Тип файлу: {file_type}"

            messagebox.showinfo("Успіх", message)
            self.update_callback()
            self.act_window.destroy()

        # Define error callback
        def on_error(error: Exception) -> None:
            """Handle processing error"""
            self.is_processing = False

            if self.load_button:
                self.load_button.configure(state="normal")
            if self.load_folder_button:
                self.load_folder_button.configure(state="normal")
            if self.status_label:
                self.status_label.configure(text="❌ Помилка обробки")

            messagebox.showerror("Помилка", f"Не вдалося обробити файл:\n{str(error)}")

        # Run processing in background thread
        run_in_thread(
            task=process_file,
            on_complete=on_complete,
            on_error=on_error
        )

    def load_folder_1c(self) -> None:
        """Завантаження папки з PDF актами (рекурсивно)"""
        if self.is_processing:
            return

        folder_path = filedialog.askdirectory(
            title="Виберіть папку з актами"
        )
        if not folder_path:
            return

        # Validate directory
        try:
            FileValidator.validate_directory_path(folder_path)
        except (FileNotFoundError, ValueError, PermissionError) as e:
            messagebox.showerror("Помилка валідації", str(e))
            return

        folder = Path(folder_path)

        # Знаходимо всі PDF файли рекурсивно
        pdf_files = list(folder.rglob("*.pdf"))

        if not pdf_files:
            messagebox.showwarning(
                "Увага",
                f"У вибраній папці та її підпапках не знайдено жодного PDF файлу"
            )
            return

        # Питаємо підтвердження
        confirm = messagebox.askyesno(
            "Підтвердження",
            f"Знайдено {len(pdf_files)} PDF файл(ів) для обробки.\n\n"
            f"Продовжити обробку?"
        )

        if not confirm:
            return

        # Disable buttons and show status
        self.is_processing = True
        if self.load_button:
            self.load_button.configure(state="disabled")
        if self.load_folder_button:
            self.load_folder_button.configure(state="disabled")
        if self.status_label:
            self.status_label.configure(text=f"⏳ Обробка 0/{len(pdf_files)} файлів...")

        # Define the processing task
        def process_folder() -> tuple:
            """Process all PDF files in folder and return (success_count, failed_count, total)"""
            success_count = 0
            failed_count = 0
            total_acts = 0

            for idx, pdf_file in enumerate(pdf_files, 1):
                # Update status label
                if self.status_label:
                    relative_path = pdf_file.relative_to(folder)
                    self.status_label.configure(
                        text=f"⏳ Обробка {idx}/{len(pdf_files)}: {relative_path.name}"
                    )

                try:
                    # Process the PDF file
                    count = self.data_processor.process_act_pdf(str(pdf_file), self.db_manager)
                    total_acts += count
                    success_count += 1
                except (ValueError, OSError, PermissionError, FileNotFoundError) as e:
                    failed_count += 1
                    logger.error(
                        f"Error processing {pdf_file.name}: {type(e).__name__}: {e}"
                    )
                except Exception as e:
                    failed_count += 1
                    logger.critical(
                        f"Unexpected error processing {pdf_file.name}: {type(e).__name__}: {e}",
                        exc_info=True
                    )

            return success_count, failed_count, total_acts

        # Define completion callback
        def on_complete(result: tuple) -> None:
            """Handle successful completion"""
            success_count, failed_count, total_acts = result
            self.is_processing = False

            if self.load_button:
                self.load_button.configure(state="normal")
            if self.load_folder_button:
                self.load_folder_button.configure(state="normal")
            if self.status_label:
                self.status_label.configure(text="")

            message = f"✅ Обробка папки завершена!\n\n"
            message += f"📂 Всього файлів: {len(pdf_files)}\n"
            message += f"✅ Успішно оброблено: {success_count}\n"
            message += f"❌ Помилок: {failed_count}\n"
            message += f"📄 Актів додано до БД: {total_acts}"

            messagebox.showinfo("Успіх", message)
            self.update_callback()
            self.act_window.destroy()

        # Define error callback
        def on_error(error: Exception) -> None:
            """Handle processing error"""
            self.is_processing = False

            if self.load_button:
                self.load_button.configure(state="normal")
            if self.load_folder_button:
                self.load_folder_button.configure(state="normal")
            if self.status_label:
                self.status_label.configure(text="❌ Помилка обробки")

            messagebox.showerror("Помилка", f"Не вдалося обробити папку:\n{str(error)}")

        # Run processing in background thread
        run_in_thread(
            task=process_folder,
            on_complete=on_complete,
            on_error=on_error
        )

    def save_act(self) -> None:
        """Збереження або оновлення акту."""
        try:
            company = self.company_entry.get().strip()
            counterparty = self.counterparty_entry.get().strip()
            period = self.period_entry.get().strip()
            energy_volume_str = self.energy_volume_entry.get().strip().replace(' ', '').replace(',', '.')
            amount_str = self.amount_entry.get().strip().replace(' ', '').replace(',', '.')
            cost_without_vat_str = self.cost_without_vat_entry.get().strip().replace(' ', '').replace(',', '.')
            price_without_vat_str = self.price_without_vat_entry.get().strip().replace(' ', '').replace(',', '.')

            if not company or not counterparty or not period or not amount_str:
                raise ValueError("Заповніть обов'язкові поля, позначені *")

            amount = float(amount_str)
            energy_volume = float(energy_volume_str) if energy_volume_str else None
            cost_without_vat = float(cost_without_vat_str) if cost_without_vat_str else None
            price_without_vat = float(price_without_vat_str) if price_without_vat_str else None

            if self.edit_mode:
                # Оновлюємо існуючий акт
                updated_count = self.db_manager.update_act(
                    self.act_data['company'],
                    self.act_data['counterparty'],
                    self.act_data['period'],
                    self.act_data['amount'],
                    company,
                    counterparty,
                    period,
                    amount,
                    energy_volume=energy_volume,
                    cost_without_vat=cost_without_vat,
                    price_without_vat=price_without_vat
                )
                if updated_count > 0:
                    messagebox.showinfo("Успіх", "✅ Акт успішно оновлено!")
                else:
                    messagebox.showwarning("Увага", "Акт не знайдено для оновлення")
            else:
                # Створюємо новий акт
                self.db_manager.save_act(
                    company, counterparty, period, amount,
                    energy_volume=energy_volume,
                    cost_without_vat=cost_without_vat,
                    price_without_vat=price_without_vat,
                )
                messagebox.showinfo("Успіх", "✅ Акт успішно збережено!")

            self.update_callback()
            self.act_window.destroy()
        except ValueError as e:
            messagebox.showerror("Помилка", str(e))
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося зберегти акт:\n{str(e)}")
