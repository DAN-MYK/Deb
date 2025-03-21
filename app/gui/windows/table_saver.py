import pandas as pd
from tkinter import filedialog, messagebox
from app.config.logging_config import setup_logging

class TableSaver:
    def __init__(self):
        self.logger = setup_logging()
        self.logger.info("Initializing TableSaver")

    def save(self, tree, table_name):
        self.logger.info(f"Saving table: {table_name}")
        columns = [tree.heading(col)['text'] for col in tree['columns']]
        data = []
        for item in tree.get_children():
            values = tree.item(item)['values']
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
                    self.logger.info(f"Table '{table_name}' saved successfully to {save_path}")
                except ImportError:
                    df.to_excel(save_path, index=False, engine='openpyxl')
                    self.logger.info(f"Table '{table_name}' saved successfully to {save_path} using openpyxl")
                messagebox.showinfo("Успіх", f"Таблиця '{table_name}' збережена: {save_path}")
            except Exception as e:
                self.logger.error(f"Error saving table '{table_name}': {str(e)}")
                messagebox.showerror("Помилка", f"Не вдалося зберегти файл: {str(e)}")