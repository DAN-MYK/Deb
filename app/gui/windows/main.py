"""
Main application window module.

This module contains the main application window and its components.
It orchestrates the GUI, forms, and data processing operations.
Top menu: Головна | Документи | Банк | Звіти | Очистити базу, with dropdown sub-menus.
"""
# Standard library imports
import logging
from tkinter import messagebox
from typing import Any, List, Tuple

# Third-party imports
import customtkinter as ctk

# Local imports
from app.config.logging_config import get_logger
from app.core.data.db import DatabaseManager
from app.core.data.processor import DataProcessor
from app.gui.dialogs.edit_dialog import confirm_delete
from app.gui.dialogs.save_table import SaveTableDialog
from app.gui.forms.act import ActForm
from app.gui.forms.act_adjustment import ActAdjustmentForm
from app.gui.forms.payment import PaymentForm
from app.gui.components.statusbar import StatusBar
from app.gui.messages import MSG_CONFIRM_CLEAR_DB, MSG_DATABASE_CLEARED, TITLE_CONFIRM, TITLE_SUCCESS
from app.gui.styles import SPACING, apply_app_theme, button_variant_kwargs, get_app_fonts
from app.gui.windows.table_manager import TableManager


class PaymentAnalyzerApp:
    """
    Main application window for payment and acts analysis.
    
    This class manages the main window and coordinates all application
    components including forms, tables, and data operations.
    
    Attributes:
        root: Main window root widget
        logger: Logger instance for this module
        data_processor: DataProcessor for file processing
        db_manager: DatabaseManager for database operations
        table_manager: TableManager for table display and management
    
    Example:
        >>> root = ctk.CTk()
        >>> app = PaymentAnalyzerApp(root)
        >>> root.mainloop()
    """
    
    def __init__(self, root: ctk.CTk) -> None:
        """
        Initialize the main application window.

        Sets up the window, initializes all managers, creates widgets,
        and loads initial data into tables.

        Args:
            root: CustomTkinter root window instance
        """
        self.logger = get_logger(__name__)
        self.logger.info("Initializing PaymentAnalyzerApp")

        self.root = root
        apply_app_theme()
        self.root.title("Deb - Аналіз платежів та актів")
        self.root.geometry("1200x700")
        
        # Налаштування мінімального розміру вікна
        self.root.minsize(800, 500)
        
        self.data_processor = DataProcessor()
        self.db_manager = DatabaseManager()
        
        self.table_manager = TableManager(self.root, self.db_manager)
        
        self.create_widgets()
        self.table_manager.update_all()

    def create_widgets(self) -> None:
        """
        Create all GUI widgets: top menu bar, dropdown sub-menu, action bar, content, statusbar.
        """
        self.logger.info("Creating widgets for PaymentAnalyzerApp")
        fonts = get_app_fonts()

        # ----- Верхнє меню -----
        menu_bar = ctk.CTkFrame(self.root, fg_color="transparent")
        menu_bar.pack(pady=(10, 0), padx=20, fill="x")

        left_menu = ctk.CTkFrame(menu_bar, fg_color="transparent")
        left_menu.pack(side="left", fill="x")

        self._menu_buttons: List[Tuple[str, str, List[Tuple[str, str]]]] = [
            ("Головна", "home", []),
            ("Документи", "documents", [("Акти", "acts"), ("Акти коригування", "act_adjustment")]),
            ("Банк", "bank", [("Оплати", "payments")]),
            ("Звіти", "reports", [("Загальний звіт", "summary"), ("Підсумки по компаніях", "summary_by_company")]),
        ]

        for label, key, sub_items in self._menu_buttons:
            btn = ctk.CTkButton(
                left_menu,
                text=label,
                width=120,
                height=SPACING["button_height"],
                corner_radius=SPACING["corner_radius"],
                font=fonts["base"],
                fg_color="transparent",
                command=lambda k=key, s=sub_items: self._on_menu_click(k, s),
            )
            btn.pack(side="left", padx=4, pady=4)

        ctk.CTkButton(
            menu_bar,
            text="Очистити базу",
            width=140,
            height=SPACING["button_height"],
            corner_radius=SPACING["corner_radius"],
            font=fonts["base"],
            command=self.clear_database,
            **button_variant_kwargs("danger"),
        ).pack(side="right", padx=4, pady=4)

        # ----- Випадаюче підменю (зникає після вибору) -----
        self._dropdown_frame = ctk.CTkFrame(self.root, fg_color=("gray85", "gray25"))
        # спочатку не показуємо; pack буде викликано в _show_dropdown

        # ----- Панель дій (ДОДАТИ / Зберегти звіти) -----
        self._action_bar = ctk.CTkFrame(self.root, fg_color="transparent")
        self._action_bar.pack(pady=6, padx=20, fill="x")

        self._add_btn = ctk.CTkButton(
            self._action_bar,
            text="ДОДАТИ",
            width=140,
            height=SPACING["button_height"],
            corner_radius=SPACING["corner_radius"],
            font=fonts["base"],
            command=self._on_add_click,
            **button_variant_kwargs("success"),
        )

        self._save_reports_btn = ctk.CTkButton(
            self._action_bar,
            text="Зберегти звіти",
            width=160,
            height=SPACING["button_height"],
            corner_radius=SPACING["corner_radius"],
            font=fonts["base"],
            command=self.open_save_dialog,
            **button_variant_kwargs("success"),
        )

        # ----- Контент (таблиці) -----
        self.table_manager.create_tables()
        self._update_action_bar()
        self.statusbar = StatusBar(self.root)
        self.statusbar.pack(fill="x", padx=20, pady=(0, 10))
        self.table_manager.set_statusbar(self.statusbar)

    def open_act_form(self) -> None:
        """
        Open the form for adding acts.
        
        Creates a new ActForm window allowing the user to add acts
        either from a file (Excel/PDF) or manually.
        """
        self.logger.info("Opening ActForm")
        ActForm(self.root, self.data_processor, self.db_manager, self.table_manager.update_all)

    def open_payment_form(self) -> None:
        """
        Open the form for adding payments.
        
        Creates a new PaymentForm window allowing the user to add payments
        either from a file (Excel/PDF) or manually.
        """
        self.logger.info("Opening PaymentForm")
        PaymentForm(self.root, self.data_processor, self.db_manager, self.table_manager.update_all)

    def open_act_adjustment_form(self) -> None:
        """
        Open the form for adjusting acts.
        
        Creates a new ActAdjustmentForm window allowing the user to
        adjust act amounts for specific companies, counterparties, and periods.
        """
        self.logger.info("Opening ActAdjustmentForm")
        ActAdjustmentForm(self.root, self.db_manager, self.table_manager.update_all)

    def open_save_dialog(self) -> None:
        """
        Open the dialog for saving table data to Excel.
        
        Creates a SaveTableDialog allowing the user to select which
        table to export and specify the output filename.
        """
        self.logger.info("Opening SaveTableDialog")
        SaveTableDialog(self.root, self.table_manager.save)

    def clear_database(self) -> None:
        """
        Clear all data from the database.

        Prompts the user for confirmation, then clears both acts
        and payments databases. Updates all table displays after clearing.

        Warning:
            This operation cannot be undone!
        """
        if not confirm_delete(self.root, TITLE_CONFIRM, MSG_CONFIRM_CLEAR_DB):
            return
        self.logger.info("Clearing database")
        self.db_manager.clear_database()
        self.table_manager.update_all()
        self.logger.info("Database cleared successfully")
        messagebox.showinfo(TITLE_SUCCESS, MSG_DATABASE_CLEARED)

    def _on_menu_click(self, key: str, sub_items: List[Tuple[str, str]]) -> None:
        if not sub_items:
            # Головна — порожня сторінка
            self.table_manager.show_view("home")
            self._hide_dropdown()
            self._update_action_bar()
            return
        self._show_dropdown(sub_items)

    def _show_dropdown(self, sub_items: List[Tuple[str, str]]) -> None:
        for w in self._dropdown_frame.winfo_children():
            w.destroy()
        fonts = get_app_fonts()
        for label, view_key in sub_items:
            btn = ctk.CTkButton(
                self._dropdown_frame,
                text=label,
                width=200,
                height=32,
                corner_radius=6,
                font=fonts["base"],
                fg_color="transparent",
                command=lambda v=view_key: self._on_dropdown_choice(v),
            )
            btn.pack(pady=2, padx=8, fill="x")
        self._dropdown_frame.pack(pady=0, padx=20, fill="x")

    def _hide_dropdown(self) -> None:
        self._dropdown_frame.pack_forget()

    def _on_dropdown_choice(self, view_key: str) -> None:
        self.table_manager.show_view(view_key)
        self._hide_dropdown()
        self._update_action_bar()

    def _update_action_bar(self) -> None:
        for w in self._action_bar.winfo_children():
            w.pack_forget()
        view = self.table_manager.get_current_view()
        # ДОДАТИ — тільки в Документах (Акти, Акти коригування) та Банку (Оплати)
        if view in ("acts", "act_adjustment", "payments"):
            self._add_btn.pack(side="left", padx=4, pady=4)
        elif view in ("summary", "summary_by_company"):
            self._save_reports_btn.pack(side="left", padx=4, pady=4)

    def _on_add_click(self) -> None:
        view = self.table_manager.get_current_view()
        if view == "acts":
            self.open_act_form()
        elif view == "act_adjustment":
            self.open_act_adjustment_form()
        elif view == "payments":
            self.open_payment_form()
        else:
            self.open_act_form()