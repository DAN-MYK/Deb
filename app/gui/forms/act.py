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
        update_callback: Callable[[], None]
    ) -> None:
        """
        Initialize the act form.
        
        Args:
            root: Parent window widget
            data_processor: DataProcessor instance for file processing
            db_manager: DatabaseManager instance for database operations
            update_callback: Callback function to refresh tables after adding acts
        """
        self.data_processor = data_processor
        self.db_manager = db_manager
        self.update_callback = update_callback
        self.load_button: Optional[ctk.CTkButton] = None
        self.load_folder_button: Optional[ctk.CTkButton] = None
        self.status_label: Optional[ctk.CTkLabel] = None
        self.is_processing = False

        self.act_window = ctk.CTkToplevel(root)
        self.act_window.title("📄 Додати акт")
        self.act_window.geometry("650x700")
        
        # Центруємо вікно
        self.act_window.transient(root)
        self.act_window.grab_set()
        
        # Додаємо хоткей Ctrl+Enter для збереження
        self.act_window.bind('<Control-Return>', lambda event: self.save_act())

        self.create_widgets()

    def create_widgets(self) -> None:
        """
        Create all form widgets.
        
        Creates a tabbed interface with:
        - 1С tab: For file upload (Excel/PDF)
        - Manual tab: For manual data entry
        """
        # Основний контейнер
        main_frame = ctk.CTkFrame(self.act_window)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)
        
        # Заголовок
        title_label = ctk.CTkLabel(
            main_frame, 
            text="Додавання акту",
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
        
        info_text = """📋 Завантаження файлу або папки

Підтримувані формати:
• Excel (1С): .xlsx, .xls
• PDF: текстові документи з актами

📂 Завантаження папки:
• Обробляє всі PDF файли в папці та підпапках
• Автоматично знаходить акти купівлі-продажу

Excel файл має містити колонки:
• Дата, Сумма, Контрагент, Организация

PDF файл має містити:
• Номер та дату акту
• Дані про виконавця та замовника
• Загальну суму з ПДВ"""
        
        info_label = ctk.CTkLabel(
            info_frame,
            text=info_text,
            font=ctk.CTkFont(size=12),
            justify="left"
        )
        info_label.pack(pady=15, padx=15)
        
        # Контейнер для кнопок
        buttons_frame = ctk.CTkFrame(tab_1c, fg_color="transparent")
        buttons_frame.pack(pady=20)
        
        # Кнопка завантаження файлу
        self.load_button = ctk.CTkButton(
            buttons_frame,
            text="📂 Завантажити файл",
            command=self.load_file_1c,
            width=250,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#3498db",
            hover_color="#2980b9"
        )
        self.load_button.pack(pady=5)
        
        # Кнопка завантаження папки
        self.load_folder_button = ctk.CTkButton(
            buttons_frame,
            text="📁 Завантажити папку з актами",
            command=self.load_folder_1c,
            width=250,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#9b59b6",
            hover_color="#8e44ad"
        )
        self.load_folder_button.pack(pady=5)
        
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

        # Scrollable frame для більшої кількості полів
        scrollable_frame = ctk.CTkScrollableFrame(tab_manual, width=500, height=450)
        scrollable_frame.pack(pady=10, padx=10, fill="both", expand=True)

        # Компанія
        ctk.CTkLabel(
            scrollable_frame,
            text="Компанія (Организация):",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(10, 3), anchor="w", padx=20)
        self.company_entry = ctk.CTkEntry(scrollable_frame, width=400, height=35)
        self.company_entry.pack(pady=3, padx=20, fill="x")

        # Контрагент
        ctk.CTkLabel(
            scrollable_frame,
            text="Контрагент:",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(8, 3), anchor="w", padx=20)
        self.counterparty_entry = ctk.CTkEntry(scrollable_frame, width=400, height=35)
        self.counterparty_entry.pack(pady=3, padx=20, fill="x")

        # Період
        ctk.CTkLabel(
            scrollable_frame,
            text="Період (наприклад, 11.2019):",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(8, 3), anchor="w", padx=20)
        self.period_entry = ctk.CTkEntry(
            scrollable_frame,
            width=400,
            height=35,
            placeholder_text="11.2019"
        )
        self.period_entry.pack(pady=3, padx=20, fill="x")

        # Кількість (кВт/год)
        ctk.CTkLabel(
            scrollable_frame,
            text="Кількість (кВт/год):",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(8, 3), anchor="w", padx=20)
        self.energy_volume_entry = ctk.CTkEntry(
            scrollable_frame,
            width=400,
            height=35,
            placeholder_text="1500,00"
        )
        self.energy_volume_entry.pack(pady=3, padx=20, fill="x")
        # Bind для автообчислення ціни
        self.energy_volume_entry.bind('<KeyRelease>', self._calculate_price)

        # Фрейм для фінансової інформації
        finance_frame = ctk.CTkFrame(scrollable_frame, fg_color=("gray92", "gray18"))
        finance_frame.pack(pady=10, padx=20, fill="x")

        finance_label = ctk.CTkLabel(
            finance_frame,
            text="💰 Фінансова інформація",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        finance_label.pack(pady=(10, 5))

        # Сума з ПДВ
        ctk.CTkLabel(
            finance_frame,
            text="Сума з ПДВ:",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(8, 3), anchor="w", padx=20)
        self.amount_entry = ctk.CTkEntry(
            finance_frame,
            width=400,
            height=35,
            placeholder_text="1200,00"
        )
        self.amount_entry.pack(pady=3, padx=20, fill="x")
        # Bind для автообчислення суми без ПДВ
        self.amount_entry.bind('<KeyRelease>', self._calculate_cost_without_vat)

        # Сума без ПДВ
        ctk.CTkLabel(
            finance_frame,
            text="Сума без ПДВ (автообчислення: ÷ 1.2):",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(8, 3), anchor="w", padx=20)
        self.cost_without_vat_entry = ctk.CTkEntry(
            finance_frame,
            width=400,
            height=35,
            placeholder_text="1000,00"
        )
        self.cost_without_vat_entry.pack(pady=3, padx=20, fill="x")
        # Bind для автообчислення ціни
        self.cost_without_vat_entry.bind('<KeyRelease>', self._calculate_price)

        # Ціна без ПДВ
        ctk.CTkLabel(
            finance_frame,
            text="Ціна без ПДВ за одиницю (автообчислення):",
            font=ctk.CTkFont(size=13)
        ).pack(pady=(8, 3), anchor="w", padx=20)
        self.price_without_vat_entry = ctk.CTkEntry(
            finance_frame,
            width=400,
            height=35,
            placeholder_text="0,67"
        )
        self.price_without_vat_entry.pack(pady=(3, 10), padx=20, fill="x")

        # Підказка про автообчислення
        ctk.CTkLabel(
            scrollable_frame,
            text="ℹ️ Поля автоматично обчислюються, але можна редагувати",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(pady=(10, 5))

        # Підказка про хоткей
        ctk.CTkLabel(
            scrollable_frame,
            text="⌨️ Ctrl+Enter для швидкого збереження",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        ).pack(pady=5)

        # Кнопка збереження
        ctk.CTkButton(
            scrollable_frame,
            text="💾 Зберегти",
            command=self.save_act,
            width=250,
            height=45,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2ecc71",
            hover_color="#27ae60"
        ).pack(pady=(5, 20))

    def _calculate_cost_without_vat(self, event: Any = None) -> None:
        """Автообчислення суми без ПДВ зі суми з ПДВ (÷ 1.2)"""
        try:
            amount_str = self.amount_entry.get().strip().replace(',', '.')
            if amount_str:
                amount = float(amount_str)
                cost_without_vat = amount / 1.2
                self.cost_without_vat_entry.delete(0, 'end')
                self.cost_without_vat_entry.insert(0, f"{cost_without_vat:.2f}")
                # Також обчислити ціну
                self._calculate_price()
        except (ValueError, ZeroDivisionError):
            pass

    def _calculate_price(self, event: Any = None) -> None:
        """Автообчислення ціни без ПДВ (сума без ПДВ / кількість)"""
        try:
            cost_str = self.cost_without_vat_entry.get().strip().replace(',', '.')
            volume_str = self.energy_volume_entry.get().strip().replace(',', '.')

            if cost_str and volume_str:
                cost = float(cost_str)
                volume = float(volume_str)
                if volume > 0:
                    price = cost / volume
                    self.price_without_vat_entry.delete(0, 'end')
                    self.price_without_vat_entry.insert(0, f"{price:.4f}")
        except (ValueError, ZeroDivisionError):
            pass

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
        """Збереження акту, введеного вручну"""
        try:
            company = self.company_entry.get().strip()
            counterparty = self.counterparty_entry.get().strip()
            period = self.period_entry.get().strip()
            energy_volume_str = self.energy_volume_entry.get().strip().replace(',', '.')
            amount_str = self.amount_entry.get().strip().replace(',', '.')
            cost_without_vat_str = self.cost_without_vat_entry.get().strip().replace(',', '.')
            price_without_vat_str = self.price_without_vat_entry.get().strip().replace(',', '.')

            if not company or not counterparty or not period or not amount_str:
                raise ValueError("Компанія, контрагент, період та сума з ПДВ обов'язкові!")

            amount = float(amount_str)
            energy_volume = float(energy_volume_str) if energy_volume_str else None
            cost_without_vat = float(cost_without_vat_str) if cost_without_vat_str else None
            price_without_vat = float(price_without_vat_str) if price_without_vat_str else None

            self.db_manager.save_act(
                company, counterparty, period, amount,
                energy_volume=energy_volume,
                cost_without_vat=cost_without_vat,
                price_without_vat=price_without_vat,
            )
            messagebox.showinfo("Успіх", "Акт успішно збережено!")
            self.update_callback()
            self.act_window.destroy()
        except ValueError as e:
            messagebox.showerror("Помилка", str(e))
        except Exception as e:
            messagebox.showerror("Помилка", f"Не вдалося зберегти акт:\n{str(e)}")