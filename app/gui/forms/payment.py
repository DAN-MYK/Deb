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
        root: Parent window widget
        data_processor: DataProcessor for file processing
        db_manager: DatabaseManager for database operations
        update_callback: Callback to refresh tables after adding payments
        payment_window: The toplevel window widget
    
    Keyboard Shortcuts:
        Ctrl+Enter: Save payment (when in manual entry mode)
    
    Example:
        >>> form = PaymentForm(root, processor, db_manager, callback)
        # User interacts with the form to add payments
    """
    
    def __init__(
        self,
        root: Any,
        data_processor: DataProcessor,
        db_manager: DatabaseManager,
        update_callback: Callable[[], None]
    ) -> None:
        """
        Initialize the payment form.
        
        Args:
            root: Parent window widget
            data_processor: DataProcessor instance for file processing
            db_manager: DatabaseManager instance for database operations
            update_callback: Callback function to refresh tables after adding payments
        """
        self.root = root
        self.data_processor = data_processor
        self.db_manager = db_manager
        self.update_callback = update_callback
        self.load_button: Optional[ctk.CTkButton] = None
        self.status_label: Optional[ctk.CTkLabel] = None
        self.is_processing = False

        self.payment_window = ctk.CTkToplevel(root)
        self.payment_window.title("💰 Додати оплату")
        self.payment_window.geometry("650x650")
        self._is_destroyed = False
        
        # Центруємо вікно
        self.payment_window.transient(root)
        self.payment_window.grab_set()
        
        # Безпечне закриття вікна
        self.payment_window.protocol("WM_DELETE_WINDOW", self._on_close)
        
        # Додаємо хоткей Ctrl+Enter для збереження
        self.payment_window.bind('<Control-Return>', lambda event: self.save_payment())

        self.create_widgets()

    def create_widgets(self) -> None:
        """
        Create all form widgets.
        
        Creates a tabbed interface with:
        - 1С tab: For file upload (Excel — 1C or bank statements)
        - Manual tab: For manual data entry
        """
        # Основний контейнер
        main_frame = ctk.CTkFrame(self.payment_window)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Заголовок
        title_label = ctk.CTkLabel(
            main_frame, 
            text="Додавання оплати",
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.pack(pady=(10, 20))
        
        # Створюємо вкладки
        self.tabview = ctk.CTkTabview(main_frame, width=550, height=420)
        self.tabview.pack(pady=10, padx=10, fill="both", expand=True)
        
        # Додаємо вкладки
        self.tabview.add("1С")
        self.tabview.add("Вручну")
        
        # Вкладка 1С
        self.create_1c_tab()
        
        # Вкладка Вручну
        self.create_manual_tab()

    def create_1c_tab(self) -> None:
        """Створює вміст вкладки 1С"""
        tab_1c = self.tabview.tab("1С")
        
        # Інформаційний блок
        info_frame = ctk.CTkFrame(tab_1c, fg_color=("gray90", "gray20"))
        info_frame.pack(pady=20, padx=20, fill="x")
        
        info_text = """📋 Завантаження файлу оплат

Підтримувані джерела:
• 1С - оплати з програми 1С
• Банк - банківські виписки

Перед завантаженням виберіть джерело файлу,
щоб програма знала як його обробляти.

Excel файл 1С має містити колонки:
• Комментарий, Сумма документа, 
• Контрагент, Организация

Банківська виписка:
• Ощадбанк або Укргазбанк
• Період витягується з призначення платежу"""
        
        info_label = ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        info_label.pack(pady=15, padx=15)
        
        # Кнопка завантаження
        self.load_button = ctk.CTkButton(
            tab_1c,
            text="📂 Завантажити файл",
            command=self.load_file_1c,
            width=250,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#3498db",
            hover_color="#2980b9"
        )
        self.load_button.pack(pady=20)
        
        # Статус label
        self.status_label = ctk.CTkLabel(
            tab_1c,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray"
        )
        self.status_label.pack(pady=5)

    def create_manual_tab(self) -> None:
        """Створює вміст вкладки Вручну"""
        tab_manual = self.tabview.tab("Вручну")
        
        # Компанія
        ctk.CTkLabel(
            tab_manual, 
            text="Компанія (Организация):", 
            font=ctk.CTkFont(size=13)
        ).pack(pady=(10, 3), anchor="w", padx=20)
        self.company_entry = ctk.CTkEntry(tab_manual, width=400, height=35)
        self.company_entry.pack(pady=3, padx=20, fill="x")

        # Контрагент
        ctk.CTkLabel(
            tab_manual, 
            text="Контрагент:", 
            font=ctk.CTkFont(size=13)
        ).pack(pady=(8, 3), anchor="w", padx=20)
        self.counterparty_entry = ctk.CTkEntry(tab_manual, width=400, height=35)
        self.counterparty_entry.pack(pady=3, padx=20, fill="x")

        # Період
        ctk.CTkLabel(
            tab_manual, 
            text="Період (наприклад, 11.2019):", 
            font=ctk.CTkFont(size=13)
        ).pack(pady=(8, 3), anchor="w", padx=20)
        self.period_entry = ctk.CTkEntry(
            tab_manual, 
            width=400, 
            height=35, 
            placeholder_text="11.2019"
        )
        self.period_entry.pack(pady=3, padx=20, fill="x")

        # Сума
        ctk.CTkLabel(
            tab_manual, 
            text="Сумма з ПДВ (наприклад, 1000,50):", 
            font=ctk.CTkFont(size=13)
        ).pack(pady=(8, 3), anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(
            tab_manual, 
            width=400, 
            height=35, 
            placeholder_text="1000,50"
        )
        self.amount_entry.pack(pady=3, padx=20, fill="x")
        
        # Підказка про хоткей
        ctk.CTkLabel(
            tab_manual,
            text="⌨️ Ctrl+Enter для швидкого збереження",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(pady=(15, 5))
        
        # Кнопка збереження
        ctk.CTkButton(
            tab_manual,
            text="💾 Зберегти",
            command=self.save_payment,
            width=250,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2ecc71",
            hover_color="#27ae60"
        ).pack(pady=(5, 20))

    def _on_close(self) -> None:
        """Safely close the payment window."""
        if self._is_destroyed:
            return
        self._is_destroyed = True
        try:
            self.payment_window.grab_release()
        except RuntimeError:
            # Window was already destroyed
            pass
        except Exception as e:
            logger.warning(f"Error releasing grab: {e}")

        try:
            self.payment_window.destroy()
        except RuntimeError:
            # Window was already destroyed
            pass
        except Exception as e:
            logger.warning(f"Error destroying window: {e}")

    def _is_window_alive(self) -> bool:
        """Check if the payment window still exists."""
        if self._is_destroyed:
            return False
        try:
            return self.payment_window.winfo_exists()
        except RuntimeError:
            # Window no longer exists
            return False
        except Exception as e:
            logger.warning(f"Error checking window existence: {e}")
            return False
    
    def load_file_1c(self) -> None:
        """Завантаження файлу оплат (1С або банківська виписка)"""
        if self.is_processing:
            return
        
        # Спочатку питаємо користувача про джерело файлу
        from tkinter import Toplevel, Label, Button, BOTH, TOP
        
        # Створюємо діалог вибору
        choice_dialog = Toplevel(self.payment_window)
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
        label_frame.pack(pady=20, fill=BOTH, expand=True)
        
        ctk.CTkLabel(
            label_frame,
            text="Оберіть джерело файлу з оплатами:",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(pady=10)
        
        # Кнопки вибору
        buttons_frame = ctk.CTkFrame(choice_dialog, fg_color="transparent")
        buttons_frame.pack(pady=10, fill=BOTH, expand=True)
        
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
            
            if self._is_window_alive():
                if self.load_button:
                    self.load_button.configure(state="normal")
                if self.status_label:
                    self.status_label.configure(text="")
            
            message = f"✅ Файл успішно оброблено!\n\n"
            message += f"💰 Оплат додано: {count}\n"
            message += f"📎 Тип файлу: {file_type}"
            
            messagebox.showinfo("Успіх", message)
            self.update_callback()
            self._on_close()
        
        # Define error callback
        def on_error(error: Exception) -> None:
            """Handle processing error"""
            self.is_processing = False
            
            if self._is_window_alive():
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
        """Збереження оплати, введеної вручну"""
        try:
            company = self.company_entry.get().strip()
            counterparty = self.counterparty_entry.get().strip()
            period = self.period_entry.get().strip()
            amount_str = self.amount_entry.get().strip().replace(',', '.')
            
            if not company or not counterparty or not period or not amount_str:
                raise ValueError("Усі поля мають бути заповнені!")
            
            amount = float(amount_str)

            self.db_manager.save_payment(company, counterparty, period, amount)
            messagebox.showinfo("Успіх", "Оплату успішно збережено!")
            self.update_callback()
            self._on_close()
        except ValueError as e:
            messagebox.showerror("Помилка", str(e))
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося зберегти оплату:\n{str(e)}")