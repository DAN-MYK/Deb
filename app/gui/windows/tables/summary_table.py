import tkinter as tk
from tkinter import ttk
from app.gui.windows.table_formatter import TableFormatter
from app.config.logging_config import setup_logging

class SummaryTable:
    def __init__(self, parent, db_manager):
        self.logger_setup = setup_logging()
        self.logger = self.logger_setup.get_logger()
        self.logger.info("Initializing SummaryTable")

        self.parent = parent
        self.db_manager = db_manager
        self.formatter = TableFormatter()
        self.frame = None
        self.tree = None

    def create(self):
        self.logger.info("Creating SummaryTable")
        self.frame = ttk.Frame(self.parent)
        self.frame.pack(fill="both", expand=True)

        columns = ["Період", "Компанія", "Контрагент", "Сума Акту", "Сума Оплати", 
                   "Заборгованість", "Відсоток оплат", "Відсоток заборгованості"]
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
        self.logger.info("Updating SummaryTable")
        for item in self.tree.get_children():
            self.tree.delete(item)

        acts = self.db_manager.get_all_acts()
        payments = self.db_manager.get_all_payments()
        self.logger.info(f"Loaded {len(acts)} acts and {len(payments)} payments")
        self.logger.info(f"Acts: {acts}")
        self.logger.info(f"Payments: {payments}")

        summary_data = {}
        for act in acts:
            company, counterparty, period, amount = act
            key = (period, company, counterparty)
            if key not in summary_data:
                summary_data[key] = {'act_amount': 0, 'payment_amount': 0}
            summary_data[key]['act_amount'] += amount
            self.logger.info(f"Added act to summary_data: {key}, amount: {amount}")

        for payment in payments:
            company, counterparty, period, amount = payment
            key = (period, company, counterparty)
            if key not in summary_data:
                summary_data[key] = {'act_amount': 0, 'payment_amount': 0}
            summary_data[key]['payment_amount'] += amount
            self.logger.info(f"Added payment to summary_data: {key}, amount: {amount}")

        self.logger.info(f"Summary data: {summary_data}")

        sorted_keys = sorted(summary_data.keys(), key=lambda x: (x[0].split('-')[1], x[0].split('-')[0]))

        for key in sorted_keys:
            period, company, counterparty = key
            act_amount = summary_data[key]['act_amount']
            payment_amount = summary_data[key]['payment_amount']
            debt = act_amount - payment_amount
            payment_percentage = (payment_amount / act_amount * 100) if act_amount != 0 else 0
            debt_percentage = (debt / act_amount * 100) if act_amount != 0 else 0
            self.logger.info(f"Inserting row: {period}, {company}, {counterparty}, act: {act_amount}, payment: {payment_amount}, debt: {debt}")
            self.tree.insert("", "end", values=(
                period,
                company,
                counterparty,
                self.formatter.format_number(act_amount) if act_amount != 0 else "",
                self.formatter.format_number(payment_amount) if payment_amount != 0 else "",
                self.formatter.format_number(debt) if debt != 0 else "",
                self.formatter.format_percentage(payment_percentage) if payment_percentage != 0 else "",
                self.formatter.format_percentage(debt_percentage) if debt_percentage != 0 else ""
            ))

    def save(self):
        import pandas as pd
        from tkinter import filedialog

        self.logger.info("Saving SummaryTable")
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
            initialfile="Загальний_звіт"
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
                    self.logger.info(f"SummaryTable saved successfully to {save_path}")
                except ImportError:
                    df.to_excel(save_path, index=False, engine='openpyxl')
                    self.logger.info(f"SummaryTable saved successfully to {save_path} using openpyxl")
                tk.messagebox.showinfo("Успіх", f"Таблиця 'Загальний звіт' збережена: {save_path}")
            except Exception as e:
                self.logger.error(f"Error saving SummaryTable: {str(e)}")
                tk.messagebox.showerror("Помилка", f"Не вдалося зберегти файл: {str(e)}")

    def __del__(self):
        self.logger.info("Closing SummaryTable")
        self.logger_setup.close()