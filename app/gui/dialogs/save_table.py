import tkinter as tk
from tkinter import messagebox, ttk

class SaveTableDialog:
    def __init__(self, root, callback):
        self.root = root
        self.callback = callback

        self.dialog = tk.Toplevel(root)
        self.dialog.title("Вибір таблиці для збереження")
        self.dialog.geometry("300x150")

        self.create_widgets()

    def create_widgets(self):
        tk.Label(self.dialog, text="Виберіть таблицю для збереження:").pack(pady=10)

        self.table_var = tk.StringVar()
        tables = ["Акти", "Оплати (з бази)", "Оплати (з банку)", "Загальний звіт", "Підсумки по компанії та роках"]
        table_menu = ttk.Combobox(self.dialog, textvariable=self.table_var, values=tables, width=25)
        table_menu.pack(pady=5)
        table_menu.current(0)

        tk.Button(self.dialog, text="Зберегти", command=self.save).pack(pady=10)

    def save(self):
        selected_table = self.table_var.get()
        if not selected_table:
            messagebox.showerror("Помилка", "Виберіть таблицю для збереження!")
            return
        self.callback(selected_table)
        self.dialog.destroy()