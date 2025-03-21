import tkinter as tk
from tkinter import filedialog, messagebox
from app.core.data.processor import DataProcessor
from app.core.data.db import DatabaseManager

class PaymentForm:
    def __init__(self, root, data_processor: DataProcessor, db_manager: DatabaseManager, update_callback):
        self.root = root
        self.data_processor = data_processor
        self.db_manager = db_manager
        self.update_callback = update_callback

        self.payment_window = tk.Toplevel(root)
        self.payment_window.title("Додати оплату")
        self.payment_window.geometry("400x300")

        self.create_widgets()

    def create_widgets(self):
        tk.Label(self.payment_window, text="Джерело даних:").pack(pady=5)
        self.source_var = tk.StringVar(value="Вручну")
        source_menu = tk.OptionMenu(self.payment_window, self.source_var, "1С", "Укргазбанк", "Ощадбанк", "Вручну")
        source_menu.pack()

        tk.Label(self.payment_window, text="Компанія: Организация").pack(pady=5)
        self.company_entry = tk.Entry(self.payment_window, width=40)
        self.company_entry.pack()

        tk.Label(self.payment_window, text="Контрагент:").pack(pady=5)
        self.counterparty_entry = tk.Entry(self.payment_window, width=40)
        self.counterparty_entry.pack()

        tk.Label(self.payment_window, text="Період (наприклад, 11.2019):").pack(pady=5)
        self.period_entry = tk.Entry(self.payment_window, width=40)
        self.period_entry.pack()

        tk.Label(self.payment_window, text="Сумма з ПДВ (наприклад, 1000,50):").pack(pady=5)
        self.amount_entry = tk.Entry(self.payment_window, width=40)
        self.amount_entry.pack()

        self.source_var.trace("w", lambda *args: self.toggle_fields())
        self.toggle_fields()

        tk.Button(self.payment_window, text="Завантажити файл", command=self.load_file).pack(pady=5)
        tk.Button(self.payment_window, text="Зберегти оплату", command=self.save_payment).pack(pady=5)

    def toggle_fields(self):
        state = 'disabled' if self.source_var.get() != "Вручну" else 'normal'
        self.company_entry.config(state=state)
        self.counterparty_entry.config(state=state)
        self.period_entry.config(state=state)
        self.amount_entry.config(state=state)

    def load_file(self):
        source = self.source_var.get()
        if source in ["1С", "Укргазбанк", "Ощадбанк"]:
            file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx *.xls")])
            if file_path:
                try:
                    if source == "1С":
                        self.data_processor.process_1c_payments(file_path, self.db_manager)
                        messagebox.showinfo("Успіх", "Оплати з 1С успішно збережено!")
                        self.update_callback()
                        self.payment_window.destroy()
                    else:
                        messagebox.showwarning("Попередження", "Обробка файлів Укргазбанк/Ощадбанк більше не підтримується.")
                except Exception as e:
                    messagebox.showerror("Помилка", f"Не вдалося завантажити файл: {str(e)}")

    def save_payment(self):
        if self.source_var.get() == "Вручну":
            try:
                company = self.company_entry.get()
                counterparty = self.counterparty_entry.get()
                period = self.period_entry.get()
                amount_str = self.amount_entry.get().replace(',', '.')  # Замінюємо кому на крапку
                amount = float(amount_str)

                if not company or not counterparty or not period:
                    raise ValueError("Усі поля мають бути заповнені!")

                self.db_manager.save_payment(company, counterparty, period, amount)
                messagebox.showinfo("Успіх", "Оплату успішно збережено!")
                self.update_callback()
                self.payment_window.destroy()
            except ValueError as e:
                messagebox.showerror("Помилка", str(e))