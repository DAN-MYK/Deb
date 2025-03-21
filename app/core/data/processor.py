import pandas as pd
import logging
from app.core.utils.date_utils import extract_month, extract_month_from_date
from app.config.settings import SUPPORTED_EXTENSIONS

class DataProcessor:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Initializing DataProcessor")

        # Словник для нормалізації компаній
        self.company_replacements = {
            "САН ПАУЕР ПЕРВОМАЙСЬК ТОВ": "ПЕРВОМАЙСЬК",
            'ТОВ "ФРІ-ЕНЕРДЖИ ГЕНІЧЕСЬК"': "ФРІ-ЕНЕРДЖИ",
            'ТОВ "ПОРТ-СОЛАР"': "ПОРТ-СОЛАР",
            'ТОВ "СКІФІЯ-СОЛАР-2"': "СКІФІЯ-СОЛАР-2",
            'ТОВ "СКІФІЯ-СОЛАР-1"': "СКІФІЯ-СОЛАР-1",
            "ДИМЕРСЬКА СЕС-1 ТОВ": "ДИМЕРСЬКА СЕС-1",
            'ТОВ "ТЕРСЛАВ"': "ТЕРСЛАВ"
        }

        # Словник для нормалізації контрагентів
        self.counterparty_replacements = {
            "ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП": "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        }

    def to_upper(self, value):
        """Переводить рядок у верхній регістр."""
        return value.upper() if isinstance(value, str) else value

    def normalize_company(self, company):
        company = self.to_upper(company)
        normalized = self.company_replacements.get(company, company)
        if normalized != company:
            self.logger.debug(f"Normalized company: {company} -> {normalized}")
        return normalized

    def normalize_counterparty(self, counterparty):
        counterparty = self.to_upper(counterparty)
        for original, replacement in self.counterparty_replacements.items():
            if original in counterparty:
                self.logger.debug(f"Normalized counterparty: {counterparty} -> {replacement}")
                return replacement
        return counterparty

    def load_excel(self, file_path):
        if not file_path.endswith(SUPPORTED_EXTENSIONS):
            self.logger.error(f"Unsupported file format: {file_path}. Supported formats: {', '.join(SUPPORTED_EXTENSIONS)}")
            raise ValueError(f"Непідтримуваний формат файлу: {file_path}. Підтримуються лише {', '.join(SUPPORTED_EXTENSIONS)}")

        try:
            if file_path.endswith('.xlsx') or file_path.endswith('.xlsm'):
                self.logger.debug(f"Loading {file_path} with openpyxl engine")
                return pd.read_excel(file_path, engine='openpyxl')
            elif file_path.endswith('.xls'):
                self.logger.debug(f"Loading {file_path} with xlrd engine")
                return pd.read_excel(file_path, engine='xlrd')
        except FileNotFoundError as e:
            self.logger.error(f"File not found: {file_path}")
            raise ValueError(f"Файл не знайдено: {file_path}") from e
        except Exception as e:
            self.logger.error(f"Failed to load file {file_path}: {str(e)}")
            raise ValueError(f"Не вдалося завантажити файл {file_path}: {str(e)}") from e

    def process_1c_acts(self, file_path, db_manager):
        df = self.load_excel(file_path)
        required_columns = ['Дата', 'Сумма', 'Контрагент', 'Организация']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            raise ValueError(f"Не знайдено колонки: {', '.join(missing_columns)}")

        # Векторизована обробка
        df['period'] = df['Дата'].apply(extract_month_from_date)
        df['amount'] = pd.to_numeric(df['Сумма'], errors='coerce')
        df['counterparty'] = df['Контрагент'].apply(self.normalize_counterparty)
        df['company'] = df['Организация'].apply(self.normalize_company)

        # Перевіряємо на помилки
        invalid_rows = df[df['period'].isna() | df['amount'].isna()]
        if not invalid_rows.empty:
            self.logger.error(f"Invalid rows detected: {invalid_rows}")
            raise ValueError("Деякі рядки мають некоректні значення для дати або суми")

        processed_count = 0
        for _, row in df.iterrows():
            db_manager.save_act(row['company'], row['counterparty'], row['period'], row['amount'])
            processed_count += 1

        self.logger.info(f"Processed {processed_count} acts from {file_path}")

    def process_1c_payments(self, file_path, db_manager):
        df = self.load_excel(file_path)
        required_columns = ['Комментарий', 'Сумма документа', 'Контрагент', 'Организация']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            raise ValueError(f"Не знайдено колонки: {', '.join(missing_columns)}")

        # Векторизована обробка
        df['period'] = df['Комментарий'].apply(extract_month)
        df['amount'] = pd.to_numeric(df['Сумма документа'], errors='coerce')
        df['counterparty'] = df['Контрагент'].apply(self.normalize_counterparty)
        df['company'] = df['Организация'].apply(self.normalize_company)

        # Перевіряємо на помилки
        invalid_rows = df[df['period'].isna() | df['amount'].isna()]
        if not invalid_rows.empty:
            self.logger.error(f"Invalid rows detected: {invalid_rows}")
            raise ValueError("Деякі рядки мають некоректні значення для періоду або суми")

        processed_count = 0
        for _, row in df.iterrows():
            db_manager.save_payment(row['company'], row['counterparty'], row['period'], row['amount'])
            processed_count += 1

        self.logger.info(f"Processed {processed_count} payments from {file_path}")

    def process_bank_payments(self, df):
        required_columns = ['NAME', 'NAME_KOR', 'PURPOSE', 'SUM_PD_NOM']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            raise ValueError(f"Не знайдено колонки: {', '.join(missing_columns)}")

        # Векторизована обробка
        df['місяць'] = df['PURPOSE'].apply(extract_month)
        df = df.dropna(subset=['місяць'])
        
        if df.empty:
            self.logger.warning("No valid rows after filtering by 'місяць'")
            return pd.DataFrame()

        # Нормалізуємо компанії та контрагентів
        df['NAME'] = df['NAME'].map(self.normalize_company)
        df['NAME_KOR'] = df['NAME_KOR'].map(self.normalize_counterparty)
        
        monthly_summary = df.groupby(['NAME', 'NAME_KOR', 'місяць']).agg({
            'SUM_PD_NOM': 'sum',
            'NAME_KOR': 'count'
        }).rename(columns={'NAME_KOR': 'кількість платежів'})
        
        self.logger.info(f"Processed {len(monthly_summary)} bank payment summaries")
        return monthly_summary.sort_index()