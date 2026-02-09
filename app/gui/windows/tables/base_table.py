"""
Base Treeview table with common UI, filtering, and sorting.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
import re

import customtkinter as ctk
from tkinter import ttk, messagebox, filedialog

from app.core.validation.file_validator import FileValidator
from app.gui.messages import MSG_SAVE_ERROR, MSG_SAVE_SUCCESS, TITLE_ERROR, TITLE_SUCCESS
from app.gui.styles import SPACING, get_app_fonts, get_treeview_row_colors

ColumnType = str


@dataclass
class FilterConfig:
    columns: Sequence[str]
    show_advanced: bool = False


class BaseTreeviewTable:
    """Base class for Treeview tables with filters, search, and sorting."""

    columns: Sequence[str] = ()
    column_types: Dict[str, ColumnType] = {}
    filter_config: FilterConfig = FilterConfig(columns=())
    default_column_width: int = 150
    table_display_name: str = ""

    def __init__(
        self,
        parent: Any,
        db_manager: Any,
        update_callback: Optional[Callable[[], None]] = None,
        state_callback: Optional[Callable[["BaseTreeviewTable"], None]] = None,
    ) -> None:
        self.parent = parent
        self.db_manager = db_manager
        self.update_callback = update_callback
        self.state_callback = state_callback

        self.frame: Optional[ctk.CTkFrame] = None
        self.tree: ttk.Treeview

        self.search_entry: Optional[ctk.CTkEntry] = None
        self.filter_entries: Dict[str, ctk.CTkEntry] = {}
        self._search_after_id: Optional[str] = None

        self.sort_column: Optional[str] = None
        self.sort_reverse: bool = False

        self._rows: List[Tuple[Any, ...]] = []
        self._default_rows: List[Tuple[Any, ...]] = []

    def create(self) -> ttk.Treeview:
        self.frame = ctk.CTkFrame(self.parent)
        self.frame.pack(fill="both", expand=True, padx=10, pady=10)

        self.frame.grid_columnconfigure(0, weight=1)
        self.frame.grid_rowconfigure(3, weight=1)

        toolbar = ctk.CTkFrame(self.frame, fg_color="transparent")
        toolbar.grid(row=0, column=0, sticky="ew", padx=5, pady=(5, 0))
        toolbar.grid_columnconfigure(1, weight=1)

        fonts = get_app_fonts()
        search_label = ctk.CTkLabel(toolbar, text="Пошук:", font=fonts["base"])
        search_label.grid(row=0, column=0, sticky="w", padx=(0, 8))

        self.search_entry = ctk.CTkEntry(toolbar, placeholder_text="Глобальний пошук...")
        self.search_entry.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        self.search_entry.bind("<KeyRelease>", self._schedule_filter)

        reset_filters_btn = ctk.CTkButton(
            toolbar,
            text="Скинути фільтри",
            width=140,
            height=SPACING["button_height"],
            command=self._clear_filters,
        )
        reset_filters_btn.grid(row=0, column=2, padx=(0, 8))

        reset_sort_btn = ctk.CTkButton(
            toolbar,
            text="Скинути сортування",
            width=160,
            height=SPACING["button_height"],
            command=self.reset_sorting,
        )
        reset_sort_btn.grid(row=0, column=3, padx=(0, 8))

        if self.filter_config.columns:
            toggle_text = "Розширені фільтри"
            self._toggle_filters_btn = ctk.CTkButton(
                toolbar,
                text=toggle_text,
                width=160,
                height=SPACING["button_height"],
                command=self._toggle_filters,
            )
            self._toggle_filters_btn.grid(row=0, column=4, padx=(0, 8))

        hint_label = ctk.CTkLabel(
            self.frame,
            text="ПКМ — меню, клік по заголовку — сортування",
            font=ctk.CTkFont(size=11),
            text_color="gray",
        )
        hint_label.grid(row=1, column=0, sticky="w", padx=8, pady=(4, 6))

        self._filters_frame = ctk.CTkFrame(self.frame)
        self._filters_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=(0, 8))
        self._filters_frame.grid_columnconfigure(0, weight=1)

        if self.filter_config.columns:
            self._build_advanced_filters(self._filters_frame)
            if not self.filter_config.show_advanced:
                self._filters_frame.grid_remove()
        else:
            self._filters_frame.grid_remove()

        tree_frame = ctk.CTkFrame(self.frame)
        tree_frame.grid(row=3, column=0, sticky="nsew", padx=5, pady=(0, 5))
        tree_frame.grid_columnconfigure(0, weight=1)
        tree_frame.grid_rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(tree_frame, columns=list(self.columns), show="headings")
        for col in self.columns:
            self.tree.heading(col, text=col, command=lambda c=col: self._sort_by_column(c))
            self.tree.column(col, width=self.default_column_width, anchor="center")

        scrollbar_y = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(tree_frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")

        zebra = get_treeview_row_colors()
        self.tree.tag_configure("odd", background=zebra["odd"])
        self.tree.tag_configure("even", background=zebra["even"])

        return self.tree

    def set_rows(self, rows: Iterable[Tuple[Any, ...]]) -> None:
        self._rows = list(rows)
        self._default_rows = list(rows)
        self._apply_filters()

    def get_visible_row_count(self) -> int:
        return len(self.tree.get_children())

    def get_search_value(self) -> str:
        if not self.search_entry:
            return ""
        return self.search_entry.get().strip()

    def set_search_value(self, value: str) -> None:
        if not self.search_entry:
            return
        self.search_entry.delete(0, "end")
        if value:
            self.search_entry.insert(0, value)
        self._apply_filters()

    def is_filtered(self) -> bool:
        if self.get_search_value():
            return True
        for entry in self.filter_entries.values():
            if entry.get().strip():
                return True
        return False

    def get_filter_state_text(self) -> str:
        return "Фільтр: активний" if self.is_filtered() else "Фільтр: немає"

    def reset_sorting(self) -> None:
        self.sort_column = None
        self.sort_reverse = False
        self._rows = list(self._default_rows)
        self._apply_filters()

    def _build_advanced_filters(self, parent: ctk.CTkFrame) -> None:
        fonts = get_app_fonts()
        for idx, col in enumerate(self.filter_config.columns):
            label = ctk.CTkLabel(parent, text=f"{col}:", font=fonts["base"])
            label.grid(row=0, column=idx * 2, padx=5, pady=5, sticky="e")

            entry = ctk.CTkEntry(parent, placeholder_text="Фільтр...")
            entry.grid(row=0, column=idx * 2 + 1, padx=5, pady=5, sticky="ew")
            entry.bind("<KeyRelease>", self._schedule_filter)
            self.filter_entries[col] = entry

        for i in range(len(self.filter_config.columns) * 2):
            parent.grid_columnconfigure(i, weight=1)

    def _toggle_filters(self) -> None:
        if self._filters_frame.winfo_ismapped():
            self._filters_frame.grid_remove()
            self._toggle_filters_btn.configure(text="Розширені фільтри")
        else:
            self._filters_frame.grid()
            self._toggle_filters_btn.configure(text="Приховати фільтри")

    def _schedule_filter(self, event: Optional[Any] = None) -> None:
        if not self.frame:
            return
        if self._search_after_id:
            self.frame.after_cancel(self._search_after_id)
        self._search_after_id = self.frame.after(200, self._apply_filters)

    def _apply_filters(self) -> None:
        rows = list(self._rows)
        search_value = self.get_search_value().lower()
        if search_value:
            rows = [row for row in rows if search_value in self._row_to_search_text(row)]

        for col, entry in self.filter_entries.items():
            filter_value = entry.get().strip().lower()
            if filter_value:
                col_index = self._column_index(col)
                rows = [row for row in rows if filter_value in str(row[col_index]).lower()]

        if self.sort_column:
            col = self.sort_column
            rows.sort(
                key=lambda r: self._parse_sort_value(r[self._column_index(col)], col),
                reverse=self.sort_reverse,
            )

        self.render_rows(rows)

        if self.state_callback:
            self.state_callback(self)

    def render_rows(self, rows: Iterable[Tuple[Any, ...]]) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

        for index, row in enumerate(rows):
            values = list(row[: len(self.columns)])
            tag = "even" if index % 2 == 0 else "odd"
            row_tags = self._get_row_tags(row)
            if row_tags:
                if isinstance(row_tags, str):
                    tags = (row_tags, tag)
                else:
                    tags = tuple(row_tags) + (tag,)
            else:
                tags = (tag,)
            self.tree.insert("", "end", values=values, tags=tags)

    def _get_row_tags(self, row: Tuple[Any, ...]) -> Optional[Tuple[str, ...]]:
        return None

    def _row_to_search_text(self, row: Tuple[Any, ...]) -> str:
        return " ".join(str(value).lower() for value in row[: len(self.columns)])

    def _sort_by_column(self, col: str) -> None:
        if self.sort_column == col:
            self.sort_reverse = not self.sort_reverse
        else:
            self.sort_column = col
            self.sort_reverse = False

        self._apply_filters()

        for column in self.columns:
            heading_text = column
            if column == col:
                heading_text += " ↓" if self.sort_reverse else " ↑"
            self.tree.heading(column, text=heading_text)

    def _parse_sort_value(self, value: Any, col: str) -> Any:
        col_type = self.column_types.get(col, "text")
        if col_type == "number":
            return _to_number(value)
        if col_type == "percent":
            return _to_percent(value)
        if col_type == "year":
            return _to_year(value)
        if col_type == "period":
            return _to_period(value)
        return str(value).lower()

    def save(self) -> None:
        """Save table data to an Excel file."""
        import pandas as pd

        table_name = self.table_display_name or self.__class__.__name__
        logger = logging.getLogger(self.__class__.__module__)
        logger.info(f"Saving {self.__class__.__name__}")

        columns = [self.tree.heading(col)['text'] for col in self.tree['columns']]
        data = []
        for item in self.tree.get_children():
            values = self.tree.item(item)['values']
            formatted_values = []
            for value in values:
                if isinstance(value, str) and value.replace(' ', '').replace(',', '').replace('-', '').replace('.', '').replace(' ', '').replace('%', '').isdigit():
                    try:
                        value = float(value.replace(' ', '').replace(',', '.').replace('%', ''))
                    except ValueError:
                        pass
                formatted_values.append(value)
            data.append(formatted_values)

        df = pd.DataFrame(data, columns=columns)

        save_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=f"{table_name}_звіт"
        )
        if save_path:
            # Validate save path
            try:
                FileValidator.validate_save_path(save_path)
            except (FileNotFoundError, PermissionError) as e:
                messagebox.showerror("Помилка валідації", str(e))
                return

            try:
                try:
                    writer = pd.ExcelWriter(save_path, engine='xlsxwriter')
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
                    workbook = writer.book
                    worksheet = writer.sheets['Sheet1']

                    number_format = workbook.add_format({'num_format': '# ##0,00'})
                    percentage_format = workbook.add_format({'num_format': '0.00%'})
                    for col_num, col_name in enumerate(df.columns):
                        if "Сума" in col_name or "Заборгованість" in col_name or "Кількість" in col_name:
                            worksheet.set_column(col_num, col_num, None, number_format)
                        elif "Відсоток" in col_name:
                            worksheet.set_column(col_num, col_num, None, percentage_format)

                    writer.close()
                    logger.info(f"{self.__class__.__name__} saved successfully to {save_path}")
                except ImportError:
                    df.to_excel(save_path, index=False, engine='openpyxl')
                    logger.info(f"{self.__class__.__name__} saved successfully to {save_path} using openpyxl")
                messagebox.showinfo(TITLE_SUCCESS, MSG_SAVE_SUCCESS.format(table_name=table_name, path=save_path))
            except (OSError, PermissionError, ValueError, TypeError, RuntimeError) as e:
                logger.error(f"Error saving {self.__class__.__name__}: {str(e)}")
                messagebox.showerror(TITLE_ERROR, MSG_SAVE_ERROR.format(detail=str(e)))

    def _clear_filters(self) -> None:
        if self.search_entry:
            self.search_entry.delete(0, "end")
        for entry in self.filter_entries.values():
            entry.delete(0, "end")
        self._apply_filters()

    def _column_index(self, col: str) -> int:
        return list(self.columns).index(col)


def _to_number(value: Any) -> float:
    if value is None:
        return 0.0
    text = str(value).replace(" ", "").replace(",", ".").replace("%", "")
    try:
        return float(text)
    except ValueError:
        return 0.0


def _to_percent(value: Any) -> float:
    return _to_number(value)


def _to_year(value: Any) -> int:
    try:
        return int(str(value))
    except ValueError:
        return 0


def _to_period(value: Any) -> Tuple[int, int]:
    text = str(value)
    match = re.match(r"(\d{2})[-./](\d{4})", text)
    if not match:
        return (0, 0)
    month, year = match.groups()
    return (int(year), int(month))
