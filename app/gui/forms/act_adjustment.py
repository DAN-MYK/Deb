import tkinter as tk
from tkinter import messagebox, ttk
from app.core.data.db import DatabaseManager

class ActAdjustmentForm:
    def __init__(self, root, db_manager: DatabaseManager, update_callback):
        self.root = root
        self.db_manager = db_manager
        self.update_callback = update_callback

        self.adjust_window = tk.Toplevel(root)
        self.adjust_window.title("Коригування актів")
        self.adjust_window.geometry("400x300")

        self.create_widgets()

    def create_widgets(self):
        acts = self.db_manager.get_all_acts()
        companies = sorted(set(act[0] for act in acts))
        counterparties = sorted(set(act[1] for act in acts))

        tk.Label(self.adjust_window, text="Компанія:").pack(pady=5)
        self.company_var = tk.StringVar()
        self.company_menu = ttk.Combobox(self.adjust_window, textvariable=self.company_var, values=companies, width=37)
        self.company_menu.pack()

        tk.Label(self.adjust_window, text="Контрагент:").pack(pady=5)
        self.counterparty_var = tk.StringVar()
        self.counterparty_menu = ttk.Combobox(self.adjust_window, textvariable=self.counterparty_var, values=counterparties, width=37)
        self.counterparty_menu.pack()

        tk.Label(self.adjust_window, text="Період (наприклад, 11.2019):").pack(pady=5)
        self.period_entry = tk.Entry(self.adjust_window, width=40)
        self.period_entry.pack()

        tk.Label(self.adjust_window, text="Сума (додатне значення додає, від’ємне віднімає, наприклад, 1000,50):").pack(pady=5)
        self.amount_entry = tk.Entry(self.adjust_window, width=40)
        self.amount_entry.pack()

        tk.Button(self.adjust_window, text="Зберегти", command=self.save_adjustment).pack(pady=20)

    def save_adjustment(self):
        try:
            company = self.company_var.get()
            counterparty = self.counterparty_var.get()
            period = self.period_entry.get()
            amount_str = self.amount_entry.get().replace(',', '.')  # Замінюємо кому на крапку
            amount = float(amount_str)

            if not company or not counterparty or not period:
                raise ValueError("Усі поля мають бути заповнені!")

            self.db_manager.adjust_acts(company, counterparty, period, amount)
            self.update_callback()
            messagebox.showinfo("Успіх", "Акти успішно скориговані!")
            self.adjust_window.destroy()
        except ValueError as e:
            messagebox.showerror("Помилка", str(e))