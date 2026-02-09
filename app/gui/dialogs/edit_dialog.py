"""
Reusable edit dialog with inline validation.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import customtkinter as ctk
from tkinter import messagebox

from app.gui.styles import SPACING, button_variant_kwargs, get_app_fonts

logger = logging.getLogger("deb.gui.dialogs.edit")


@dataclass
class EditField:
    key: str
    label: str
    value: str
    placeholder: str = ""
    validator: Optional[Callable[[str], Optional[str]]] = None
    parser: Optional[Callable[[str], Any]] = None


class EditDialog:
    """Modal dialog to edit row data with validation."""

    def __init__(
        self,
        parent: Any,
        title: str,
        fields: list[EditField],
        on_save: Callable[[Dict[str, Any]], None],
    ) -> None:
        self.parent = parent
        self.fields = fields
        self.on_save = on_save

        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("520x500")
        self.dialog.transient(parent)
        self.dialog.grab_set()

        self._entries: Dict[str, ctk.CTkEntry] = {}
        self._errors: Dict[str, ctk.CTkLabel] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        fonts = get_app_fonts()
        main_frame = ctk.CTkFrame(self.dialog)
        main_frame.pack(pady=20, padx=20, fill="both", expand=True)

        for idx, field in enumerate(self.fields):
            label = ctk.CTkLabel(main_frame, text=f"{field.label}:", font=fonts["base"])
            label.pack(pady=(10 if idx > 0 else 0, 4), anchor="w")

            entry = ctk.CTkEntry(
                main_frame,
                width=450,
                height=SPACING["button_height"],
                placeholder_text=field.placeholder,
            )
            if field.value:
                entry.insert(0, field.value)
            entry.pack(pady=(0, 2), fill="x")
            self._entries[field.key] = entry

            error_label = ctk.CTkLabel(main_frame, text="", font=ctk.CTkFont(size=11), text_color="red")
            error_label.pack(pady=(0, 4), anchor="w")
            self._errors[field.key] = error_label

        button_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        button_frame.pack(pady=20)

        ctk.CTkButton(
            button_frame,
            text="💾 Зберегти",
            width=200,
            height=SPACING["button_height_lg"],
            font=fonts["base"],
            command=self._handle_save,
            **button_variant_kwargs("success"),
        ).pack(side="left", padx=5)

        ctk.CTkButton(
            button_frame,
            text="❌ Скасувати",
            width=200,
            height=SPACING["button_height_lg"],
            font=fonts["base"],
            command=self.dialog.destroy,
            **button_variant_kwargs("secondary"),
        ).pack(side="left", padx=5)

    def _handle_save(self) -> None:
        values: Dict[str, Any] = {}
        has_errors = False

        for field in self.fields:
            raw = self._entries[field.key].get().strip()
            error = field.validator(raw) if field.validator else None
            self._errors[field.key].configure(text=error or "")
            if error:
                has_errors = True
                continue
            try:
                values[field.key] = field.parser(raw) if field.parser else raw
            except ValueError as e:
                self._errors[field.key].configure(text=f"Невірне значення: {str(e)}")
                has_errors = True
            except (TypeError, AttributeError) as e:
                logger.error(f"Parser error for field {field.key}: {e}")
                self._errors[field.key].configure(text="Невірний тип значення")
                has_errors = True

        if has_errors:
            return

        try:
            self.on_save(values)
            self.dialog.destroy()
        except Exception as exc:
            messagebox.showerror("Помилка", f"Не вдалося зберегти зміни:\n{exc}")


def confirm_delete(parent: Any, title: str, message: str) -> bool:
    """Consistent delete confirmation prompt."""
    return messagebox.askyesno(title, message, parent=parent)
