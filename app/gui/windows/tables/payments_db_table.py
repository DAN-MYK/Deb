import tkinter as tk
from tkinter import ttk
from app.gui.windows.table_formatter import TableFormatter
from app.config.logging_config import setup_logging

class PaymentsDbTable:
    def __init__(self, parent, db_manager):
        self.logger_setup = setup_logging()
        self.logger = self.logger_setup.get_logger()  # Правильна ініціалізація логера
        self.logger.info("Initializing PaymentsDbTable")

        self.parent = parent
        self.db_manager = db_manager
        self.formatter = TableFormatter()
        self.frame = None
        self.tree = None

    def create(self):
        self.logger.info("Creating PaymentsDbTable")
        self.frame = ttk.Frame(self.parent)
        self.frame.pack(fill="both", expand=True)

        columns = ["Компанія", "Контрагент", "Період", "Загальна сумма"]
        self.tree = ttk.Treeview(self.frame, columns=columns, show="headings")
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=150, anchor="center")

        scrollbar_y = ttk.Scrollbar(self.frame, orient="vertical", command=self.tree.yview)
        scrollbar_x = ttk.Scrollbar(self.frame, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.tree.pack(side="left", fill="both", expand=True)
        scrollbar_y.pack(side="right", fill="y")
        scrollbar_x.pack(side="bottom", fill="x")

    def update(self):
        self.logger.info("Updating PaymentsDbTable")
        for item in self.tree.get_children():
            self.tree.delete(item)

        payments = self.db_manager.get_all_payments()
        self.logger.info(f"Loaded {len(payments)} payments")
        payments_by_month = {}
        for payment in payments:
            company, counterparty, period, amount = payment
            key = (company, counterparty, period)
            if key in payments_by_month:
                payments_by_month[key] += amount
            else:
                payments_by_month[key] = amount

        for (company, counterparty, period), total_amount in payments_by_month.items():
            self.tree.insert("", "end", values=(company, counterparty, period, self.formatter.format_number(total_amount)))

    def save(self):
        import pandas as pd
        from tkinter import filedialog

        self.logger.info("Saving PaymentsDbTable")
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
            initialfile="Оплати_з_бази_звіт"
        )
        if save_path:
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
                    self.logger.info(f"PaymentsDbTable saved successfully to {save_path}")
                except ImportError:
                    df.to_excel(save_path, index=False, engine='openpyxl')
                    self.logger.info(f"PaymentsDbTable saved successfully to {save_path} using openpyxl")
                tk.messagebox.showinfo("Успіх", f"Таблиця 'Оплати (з бази)' збережена: {save_path}")
            except Exception as e:
                self.logger.error(f"Error saving PaymentsDbTable: {str(e)}")
                tk.messagebox.showerror("Помилка", f"Не вдалося зберегти файл: {str(e)}")

    def __del__(self):
        self.logger.info("Closing PaymentsDbTable")
        self.logger_setup.close()