import tkinter as tk
from tkinter import ttk
from app.gui.windows.table_formatter import TableFormatter
from app.config.logging_config import setup_logging

class SummaryByCompanyTable:
    def __init__(self, parent, db_manager):
        self.logger_setup = setup_logging()
        self.logger = self.logger_setup.get_logger()
        self.logger.info("Initializing SummaryByCompanyTable")

        self.parent = parent
        self.db_manager = db_manager
        self.formatter = TableFormatter()
        self.frame = None
        self.tree = None

    def create(self):
        self.logger.info("Creating SummaryByCompanyTable")
        self.frame = ttk.Frame(self.parent)
        self.frame.pack(fill="both", expand=True)

        columns = ["Компанія", "Рік", "Сума Акту", "Сума Оплати", "Заборгованість", 
                   "Відсоток оплат", "Відсоток заборгованості"]
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
        self.logger.info("Updating SummaryByCompanyTable")
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

        summary_by_company = {}
        for key in summary_data:
            period, company, _ = key
            try:
                year = period.split('-')[1]  # Витягуємо рік із періоду
            except IndexError:
                self.logger.error(f"Invalid period format: {period}")
                continue
            company_year_key = (company, year)
            if company_year_key not in summary_by_company:
                summary_by_company[company_year_key] = {'act_amount': 0, 'payment_amount': 0}
            summary_by_company[company_year_key]['act_amount'] += summary_data[key]['act_amount']
            summary_by_company[company_year_key]['payment_amount'] += summary_data[key]['payment_amount']
            self.logger.info(f"Added to summary_by_company: {company_year_key}, act_amount: {summary_data[key]['act_amount']}, payment_amount: {summary_data[key]['payment_amount']}")

        self.logger.info(f"Summary by company: {summary_by_company}")

        sorted_company_keys = sorted(summary_by_company.keys(), key=lambda x: (x[1], x[0]))

        for key in sorted_company_keys:
            company, year = key
            act_amount = summary_by_company[key]['act_amount']
            payment_amount = summary_by_company[key]['payment_amount']
            debt = act_amount - payment_amount
            payment_percentage = (payment_amount / act_amount * 100) if act_amount != 0 else 0
            debt_percentage = (debt / act_amount * 100) if act_amount != 0 else 0
            self.logger.info(f"Inserting row: {company}, {year}, act: {act_amount}, payment: {payment_amount}, debt: {debt}")
            self.tree.insert("", "end", values=(
                company,
                year,
                self.formatter.format_number(act_amount) if act_amount != 0 else "",
                self.formatter.format_number(payment_amount) if payment_amount != 0 else "",
                self.formatter.format_number(debt) if debt != 0 else "",
                self.formatter.format_percentage(payment_percentage) if payment_percentage != 0 else "",
                self.formatter.format_percentage(debt_percentage) if debt_percentage != 0 else ""
            ))

    def save(self):
        import pandas as pd
        from tkinter import filedialog

        self.logger.info("Saving SummaryByCompanyTable")
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
            initialfile="Підсумки_по_компанії_та_роках_звіт"
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
                    self.logger.info(f"SummaryByCompanyTable saved successfully to {save_path}")
                except ImportError:
                    df.to_excel(save_path, index=False, engine='openpyxl')
                    self.logger.info(f"SummaryByCompanyTable saved successfully to {save_path} using openpyxl")
                tk.messagebox.showinfo("Успіх", f"Таблиця 'Підсумки по компанії та роках' збережена: {save_path}")
            except Exception as e:
                self.logger.error(f"Error saving SummaryByCompanyTable: {str(e)}")
                tk.messagebox.showerror("Помилка", f"Не вдалося зберегти файл: {str(e)}")

    def __del__(self):
        self.logger.info("Closing SummaryByCompanyTable")
        self.logger_setup.close()