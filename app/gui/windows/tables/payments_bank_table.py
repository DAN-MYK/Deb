import tkinter as tk
from tkinter import ttk
from app.gui.windows.table_formatter import TableFormatter
from app.config.logging_config import setup_logging

class PaymentsBankTable:
    def __init__(self, parent, db_manager):
        self.logger_setup = setup_logging()
        self.logger = self.logger_setup.get_logger()  # Правильна ініціалізація логера
        self.logger.info("Initializing PaymentsBankTable")

        self.parent = parent
        self.db_manager = db_manager
        self.formatter = TableFormatter()
        self.frame = None
        self.tree = None
        self.monthly_summary = None

    def create(self):
        self.logger.info("Creating PaymentsBankTable")
        self.frame = ttk.Frame(self.parent)
        self.frame.pack(fill="both", expand=True)

        columns = ["Компанія", "Контрагент", "Місяць", "Кількість платежів", "Загальна сумма"]
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
        self.logger.info("Updating PaymentsBankTable")
        for item in self.tree.get_children():
            self.tree.delete(item)

        if self.monthly_summary is not None and not self.monthly_summary.empty:
            self.logger.info(f"Loaded {len(self.monthly_summary)} bank payments")
            for (company, counterparty, month), row in self.monthly_summary.iterrows():
                self.tree.insert("", "end", values=(
                    company, 
                    counterparty, 
                    month, 
                    int(row['кількість платежів']), 
                    self.formatter.format_number(row['SUM_PD_NOM'])
                ))
        else:
            self.logger.warning("No monthly summary data to display")

    def set_monthly_summary(self, monthly_summary):
        self.logger.info("Setting monthly summary for PaymentsBankTable")
        self.monthly_summary = monthly_summary

    def save(self):
        import pandas as pd
        from tkinter import filedialog

        self.logger.info("Saving PaymentsBankTable")
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
            initialfile="Оплати_з_банку_звіт"
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
                    self.logger.info(f"PaymentsBankTable saved successfully to {save_path}")
                except ImportError:
                    df.to_excel(save_path, index=False, engine='openpyxl')
                    self.logger.info(f"PaymentsBankTable saved successfully to {save_path} using openpyxl")
                tk.messagebox.showinfo("Успіх", f"Таблиця 'Оплати (з банку)' збережена: {save_path}")
            except Exception as e:
                self.logger.error(f"Error saving PaymentsBankTable: {str(e)}")
                tk.messagebox.showerror("Помилка", f"Не вдалося зберегти файл: {str(e)}")

    def __del__(self):
        self.logger.info("Closing PaymentsBankTable")
        self.logger_setup.close()