"""
Data processor module for handling various file formats.

This module provides the DataProcessor class which handles processing
of Excel files (from 1C and bank statements) and PDF files (acts).
It coordinates validation, normalization, and database operations.

Example:
    >>> from app.core.data.processor import DataProcessor
    >>> from app.core.data.db import DatabaseManager
    >>> 
    >>> processor = DataProcessor()
    >>> db = DatabaseManager()
    >>> 
    >>> # Process Excel file with acts
    >>> count = processor.process_1c_acts("acts.xlsx", db)
    >>> print(f"Processed {count} acts")
    >>> 
    >>> # Process bank statement Excel file
    >>> count = processor.process_bank_statement_excel("statement.xlsx", db)
    >>> print(f"Processed {count} payments")
    >>> 
    >>> # Process PDF file (acts only)
    >>> count = processor.process_pdf_file("document.pdf", db)
    >>> print(f"Processed {count} records")
"""
# Standard library imports
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional, Tuple

# Third-party imports
import pandas as pd

# Local imports
from app.config.config import settings
from app.core.data.pdf_exceptions import (
    InvalidPDFDataError,
    PDFExtractionError,
    PDFParsingError,
    UnsupportedPDFFormatError,
)
from app.core.normalization import DataNormalizer
from app.core.pdf import ActExtractor, PDFExtractor
from app.core.utils.date_utils import (
    extract_month,
    extract_month_from_date,
    extract_period_from_purpose,
)

if TYPE_CHECKING:
    from app.core.data.db import DatabaseManager


# Bank configuration for generic payment parser
BANK_CONFIGS = {
    'ukrgasbank': {
        'amount_field': 'SUM_PD_NOM',
        'direction_field': 'DK',
        'direction_value': 1,
        'counterparty_field': 'NAME_KOR',
        'company_field': 'NAME',
        'date_field': 'DATA_VYP',
        'purpose_field': 'PURPOSE',
        'company_from_header': False,
    },
    'oschadbank': {
        'amount_field': 'Кредит',
        'direction_field': None,
        'counterparty_field': 'Найменування кореспондента',
        'date_field': 'Дата валютування',
        'purpose_field': 'Призначення платежу',
        'company_from_header': True,
    }
}


class DataProcessor:
    """
    Data processor for handling Excel and PDF files.
    
    Processes financial documents from various sources:
    - Excel files from 1C (acts and payments)
    - Excel bank statements (Oschadbank, Ukrgasbank)
    - PDF files (acts only)
    - Combined Excel files with multiple sheets
    
    The processor automatically handles:
    - Data validation and normalization
    - Period extraction from dates and text
    - Company and counterparty name standardization
    - Bank format auto-detection
    - Error handling and logging
    
    Attributes:
        logger: Logger instance for this processor
        pdf_extractor: Base PDF extractor for document type detection
        act_extractor: Specialized extractor for act documents
    
    Example:
        >>> processor = DataProcessor()
        >>> db = DatabaseManager()
        >>> 
        >>> # Process Excel file
        >>> try:
        ...     count = processor.process_1c_acts("acts.xlsx", db)
        ...     print(f"Successfully processed {count} acts")
        ... except ValueError as e:
        ...     print(f"Error: {e}")
    """
    
    def __init__(self) -> None:
        """
        Initialize data processor with PDF extractors.
        
        Creates and configures all necessary extractors for processing
        different types of documents.
        """
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.logger.info("Initializing DataProcessor")
        self.pdf_extractor: PDFExtractor = PDFExtractor(self.logger)
        self.act_extractor: ActExtractor = ActExtractor(self.logger)

    def load_excel(self, file_path: str) -> pd.DataFrame:
        """
        Load Excel file into pandas DataFrame.
        
        Supports multiple Excel formats (.xlsx, .xls, .xlsm) and automatically
        selects the appropriate engine for reading.
        
        Args:
            file_path: Path to Excel file. Must have .xlsx, .xls, or .xlsm extension.
            
        Returns:
            DataFrame with loaded data from the Excel file.
            
        Raises:
            ValueError: If file format is unsupported, file is not found, or loading fails.
        
        Example:
            >>> processor = DataProcessor()
            >>> df = processor.load_excel("data.xlsx")
            >>> print(df.head())
        """
        if not file_path.endswith(settings.supported_extensions):
            self.logger.error(f"Unsupported file format: {file_path}. Supported formats: {', '.join(settings.supported_extensions)}")
            raise ValueError(f"Непідтримуваний формат файлу: {file_path}. Підтримуються лише {', '.join(settings.supported_extensions)}")

        try:
            if file_path.endswith('.xlsx') or file_path.endswith('.xlsm'):
                return pd.read_excel(file_path, engine='openpyxl')
            elif file_path.endswith('.xls'):
                return pd.read_excel(file_path, engine='xlrd')
            else:
                raise ValueError(f"Unsupported file extension: {file_path}")
        except FileNotFoundError as e:
            self.logger.error(f"File not found: {file_path}")
            raise ValueError(f"Файл не знайдено: {file_path}") from e
        except (ValueError, OSError, PermissionError, KeyError, TypeError, AttributeError) as e:
            self.logger.error(f"Failed to load file {file_path}: {str(e)}")
            raise ValueError(f"Не вдалося завантажити файл {file_path}: {str(e)}") from e
        except Exception as e:
            self.logger.exception("Unexpected error loading file %s", file_path)
            raise ValueError(f"Не вдалося завантажити файл {file_path}: {str(e)}") from e

    def process_1c_acts(self, file_path: str, db_manager: "DatabaseManager") -> int:
        """
        Process acts from 1C Excel file.
        
        Reads acts data from Excel file exported from 1C, validates and normalizes
        the data, then saves it to the database. The function expects specific
        column names and formats as exported by 1C.
        
        Required Excel columns:
            - Дата: Act date in DD.MM.YYYY format
            - Сумма: Amount with VAT (numeric)
            - Контрагент: Counterparty name (will be normalized)
            - Организация: Company/organization name (will be normalized)
        
        Args:
            file_path: Path to Excel file containing acts data.
            db_manager: DatabaseManager instance for saving acts to database.
            
        Returns:
            Number of successfully processed acts.
            
        Raises:
            ValueError: If required columns are missing, data is invalid,
                       or file cannot be loaded.
        
        Example:
            >>> processor = DataProcessor()
            >>> db = DatabaseManager()
            >>> count = processor.process_1c_acts("acts_january.xlsx", db)
            >>> print(f"Imported {count} acts from 1C")
        """
        df = self.load_excel(file_path)
        required_columns = ['Дата', 'Сумма', 'Контрагент', 'Организация']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            raise ValueError(f"Не знайдено колонки: {', '.join(missing_columns)}")

        # Векторизована обробка
        df['period'] = df['Дата'].apply(extract_month_from_date)
        df['amount'] = pd.to_numeric(df['Сумма'], errors='coerce')
        df['counterparty'] = df['Контрагент'].apply(DataNormalizer.normalize_counterparty)
        df['company'] = df['Организация'].apply(DataNormalizer.normalize_company)

        # Перевіряємо на помилки
        invalid_rows = df[df['period'].isna() | df['amount'].isna()]
        if not invalid_rows.empty:
            self.logger.error(f"Invalid rows detected: {invalid_rows}")
            raise ValueError("Деякі рядки мають некоректні значення для дати або суми")

        # Prepare batch data for bulk insert - фільтруємо тільки ГП
        acts_batch = [
            (row['company'], row['counterparty'], row['period'], row['amount'], None, None)
            for _, row in df.iterrows()
            if row['counterparty'] == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        ]
        
        total_rows = len(df)
        filtered_count = len(acts_batch)
        skipped_count = total_rows - filtered_count
        
        if skipped_count > 0:
            self.logger.info(f"Skipped {skipped_count} acts with other counterparties (only Guaranteed Buyer accepted)")
        
        # Use batch insert for better performance
        processed_count = db_manager.save_acts_batch(acts_batch)
        self.logger.info(f"Processed {processed_count} acts from {file_path} (Guaranteed Buyer only)")
        
        return processed_count

    def process_1c_payments(self, file_path: str, db_manager: "DatabaseManager") -> int:
        """
        Process payments from 1C Excel file.
        
        Reads payment data from Excel file exported from 1C, extracts periods
        from comments, validates and normalizes the data, then saves it to
        the database.
        
        Required Excel columns:
            - Комментарий: Comment containing period info (e.g., "Оплата за 11.2019")
            - Сумма документа: Payment amount (numeric)
            - Контрагент: Counterparty name (will be normalized)
            - Организация: Company/organization name (will be normalized)
        
        Args:
            file_path: Path to Excel file containing payments data.
            db_manager: DatabaseManager instance for saving payments to database.
            
        Returns:
            Number of successfully processed payments.
            
        Raises:
            ValueError: If required columns are missing, data is invalid,
                       period cannot be extracted from comments, or file cannot be loaded.
        
        Example:
            >>> processor = DataProcessor()
            >>> db = DatabaseManager()
            >>> count = processor.process_1c_payments("payments_january.xlsx", db)
            >>> print(f"Imported {count} payments from 1C")
        """
        df = self.load_excel(file_path)
        required_columns = ['Комментарий', 'Сумма документа', 'Контрагент', 'Организация']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            self.logger.error(f"Missing required columns: {missing_columns}")
            self.logger.error(f"Available columns: {df.columns.tolist()}")
            raise ValueError(f"Не знайдено колонки: {', '.join(missing_columns)}")

        # Векторизована обробка
        df['period'] = df['Комментарий'].apply(extract_month)
        df['amount'] = pd.to_numeric(df['Сумма документа'], errors='coerce')
        df['counterparty'] = df['Контрагент'].apply(DataNormalizer.normalize_counterparty)
        df['company'] = df['Организация'].apply(DataNormalizer.normalize_company)
        
        # Fallback: якщо є колонка "Дата" і період не витягнувся з коментарів - спробуємо з дати
        if 'Дата' in df.columns and df['period'].isna().any():
            null_count = df['period'].isna().sum()
            self.logger.info(f"Found {null_count} rows with period=None from comments, trying 'Дата' as fallback")
            df.loc[df['period'].isna(), 'period'] = df.loc[df['period'].isna(), 'Дата'].apply(extract_month_from_date)
            recovered_count = null_count - df['period'].isna().sum()
            if recovered_count > 0:
                self.logger.info(f"Recovered {recovered_count} periods from 'Дата' column")

        # Перевіряємо на помилки
        invalid_rows = df[df['period'].isna() | df['amount'].isna()]
        if not invalid_rows.empty:
            self.logger.error(f"Invalid rows detected ({len(invalid_rows)} rows):")
            self.logger.error(f"{invalid_rows.head(5)}")
            # Логуємо приклади для діагностики
            if 'Комментарий' in df.columns:
                sample_comments = df[df['period'].isna()]['Комментарий'].head(3).tolist()
                self.logger.error(f"Sample comments with null periods: {sample_comments}")
            if 'Дата' in df.columns:
                sample_dates = df[df['period'].isna()]['Дата'].head(3).tolist()
                self.logger.error(f"Sample dates with null periods: {sample_dates}")
            raise ValueError(f"Деякі рядки мають некоректні значення для періоду або суми ({len(invalid_rows)} з {len(df)} рядків)")

        # Prepare batch data for bulk insert - фільтруємо тільки ГП
        payments_batch: List[Tuple[str, str, str, float, Optional[str]]] = [
            (row['company'], row['counterparty'], row['period'], row['amount'], None)
            for _, row in df.iterrows()
            if row['counterparty'] == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        ]
        
        total_rows = len(df)
        filtered_count = len(payments_batch)
        skipped_count = total_rows - filtered_count
        
        if skipped_count > 0:
            self.logger.info(f"Skipped {skipped_count} payments with other counterparties (only Guaranteed Buyer accepted)")
        
        # Use batch insert for better performance
        processed_count = db_manager.save_payments_batch(payments_batch)
        self.logger.info(f"Processed {processed_count} payments from {file_path} (Guaranteed Buyer only)")
        
        return processed_count

    def process_bank_payments(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Process bank payments from DataFrame.
        
        Args:
            df: DataFrame with bank payment data
            
        Returns:
            DataFrame with monthly payment summaries
            
        Raises:
            ValueError: If required columns are missing
        """
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
        df['NAME'] = df['NAME'].map(DataNormalizer.normalize_company)
        df['NAME_KOR'] = df['NAME_KOR'].map(DataNormalizer.normalize_counterparty)
        
        monthly_summary = df.groupby(['NAME', 'NAME_KOR', 'місяць']).agg({
            'SUM_PD_NOM': 'sum',
            'NAME_KOR': 'count'
        }).rename(columns={'NAME_KOR': 'кількість платежів'})
        
        self.logger.info(f"Processed {len(monthly_summary)} bank payment summaries")
        return monthly_summary.sort_index()

    # ==================== Bank Statement Excel Processing ====================

    def _try_process_ukrgasbank(
        self, file_path: str, db_manager: "DatabaseManager"
    ) -> Optional[int]:
        """
        Attempt to process file as Ukrgasbank format.

        Returns:
            Number of processed payments, or None if format doesn't match.

        Raises:
            ValueError: If format matches but data is invalid.
        """
        ukr_columns = {'NAME', 'NAME_KOR', 'PURPOSE', 'SUM_PD_NOM', 'DK', 'DATA_VYP'}
        try:
            df = self._load_excel_with_header(file_path, header=0)
            if not ukr_columns.issubset(set(df.columns)):
                return None

            self.logger.info("Detected Ukrgasbank Excel format")
            payments = self._parse_ukrgasbank_payments(df)
            return self._save_bank_payments(payments, db_manager, "Укргазбанк")
        except ValueError:
            # Re-raise ValueError (e.g., "no payments") — format was detected
            raise
        except (KeyError, TypeError, OSError, AttributeError) as e:
            self.logger.debug(f"Not Ukrgasbank format: {e}")
            return None

    def _try_process_oschadbank(
        self, file_path: str, db_manager: "DatabaseManager"
    ) -> Optional[int]:
        """
        Attempt to process file as Oschadbank format.

        Returns:
            Number of processed payments, or None if format doesn't match.

        Raises:
            ValueError: If format matches but data is invalid.
        """
        oschad_columns = {
            'Дебет', 'Кредит', 'Найменування кореспондента',
            'Призначення платежу', 'Дата валютування',
        }
        try:
            # Read raw to extract company name from row 0
            df_raw = self._load_excel_with_header(file_path, header=None)
            company_name = self._extract_oschadbank_company(df_raw)

            # Read with header at row 3
            df = self._load_excel_with_header(file_path, header=3)
            if not oschad_columns.issubset(set(df.columns)):
                return None

            self.logger.info("Detected Oschadbank Excel format")
            payments = self._parse_oschadbank_payments(df, company_name)
            return self._save_bank_payments(payments, db_manager, "Ощадбанк")
        except ValueError:
            # Re-raise ValueError (e.g., "no payments") — format was detected
            raise
        except (KeyError, TypeError, OSError, AttributeError) as e:
            self.logger.debug(f"Not Oschadbank format: {e}")
            return None

    def process_bank_statement_excel(
        self, file_path: str, db_manager: "DatabaseManager"
    ) -> int:
        """
        Process bank statement from Excel file (.xlsx or .xls).

        Auto-detects the bank format (Oschadbank or Ukrgasbank) based on
        column names and processes payments accordingly.

        Supported formats:
            - Oschadbank (.xlsx): Header at row 3, columns include
              'Дебет', 'Кредит', 'Найменування кореспондента',
              'Призначення платежу', 'Дата валютування'
            - Ukrgasbank (.xls): Header at row 0, columns include
              'NAME', 'NAME_KOR', 'SUM_PD_NOM', 'PURPOSE', 'DATA_VYP', 'DK'

        Args:
            file_path: Path to the Excel bank statement file.
            db_manager: DatabaseManager instance for saving payments.

        Returns:
            Number of successfully processed payments.

        Raises:
            ValueError: If bank format cannot be detected, file cannot be loaded,
                       or no payments are found.

        Example:
            >>> processor = DataProcessor()
            >>> db = DatabaseManager()
            >>> count = processor.process_bank_statement_excel("bank_statement.xlsx", db)
            >>> print(f"Imported {count} payments from bank statement")
        """
        self.logger.info(f"Processing bank statement Excel: {file_path}")

        # Try Ukrgasbank format first
        result = self._try_process_ukrgasbank(file_path, db_manager)
        if result is not None:
            return result

        # Try Oschadbank format
        result = self._try_process_oschadbank(file_path, db_manager)
        if result is not None:
            return result

        raise ValueError(
            "Не вдалося визначити формат банківської виписки.\n"
            "Підтримуються формати Ощадбанку (.xlsx) та Укргазбанку (.xls)."
        )

    def _load_excel_with_header(
        self, file_path: str, header: Optional[int] = 0
    ) -> pd.DataFrame:
        """
        Load Excel file with a specified header row.
        
        Args:
            file_path: Path to Excel file.
            header: Row number to use as column names (None for no header).
            
        Returns:
            DataFrame with loaded data.
            
        Raises:
            ValueError: If file format is unsupported or loading fails.
        """
        try:
            if file_path.endswith('.xlsx') or file_path.endswith('.xlsm'):
                return pd.read_excel(file_path, engine='openpyxl', header=header)
            elif file_path.endswith('.xls'):
                return pd.read_excel(file_path, engine='xlrd', header=header)
            else:
                raise ValueError(f"Непідтримуваний формат файлу: {file_path}")
        except FileNotFoundError as e:
            raise ValueError(f"Файл не знайдено: {file_path}") from e
        except ValueError:
            raise
        except (OSError, PermissionError, KeyError, TypeError, AttributeError) as e:
            raise ValueError(
                f"Не вдалося завантажити файл {file_path}: {str(e)}"
            ) from e
        except Exception as e:
            self.logger.exception("Unexpected error loading Excel %s", file_path)
            raise ValueError(
                f"Не вдалося завантажити файл {file_path}: {str(e)}"
            ) from e

    @staticmethod
    def _parse_bank_amount(value: Any) -> float:
        """
        Parse bank statement amount from various formats.
        
        Handles space-separated thousands, comma decimals, and
        non-breaking space separators.
        
        Args:
            value: Raw amount value (string or numeric).
            
        Returns:
            Parsed float amount, or 0.0 if unparseable.
        """
        if pd.isna(value):
            return 0.0
        s = str(value).replace('\xa0', '').replace(' ', '').replace(',', '.')
        try:
            return float(s)
        except ValueError:
            return 0.0

    @staticmethod
    def _parse_bank_date(value: Any) -> Optional[str]:
        """
        Parse bank statement date to YYYY-MM-DD format.
        
        Supports formats: DD.MM.YYYY, DD-MM-YYYY, DD/MM/YYYY.
        
        Args:
            value: Raw date value.
            
        Returns:
            Date string in YYYY-MM-DD format, or None if unparseable.
        """
        if pd.isna(value):
            return None
        date_str = str(value).strip()
        # Take only the date part (before any time component)
        date_str = date_str.split(' ')[0]
        for fmt in ('%d.%m.%Y', '%d-%m-%Y', '%d/%m/%Y', '%Y-%m-%d'):
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except ValueError:
                continue
        return None

    def _extract_oschadbank_company(self, df_raw: pd.DataFrame) -> str:
        """
        Extract company name from Oschadbank Excel header area (row 0).
        
        The first cell typically contains the full company name with
        legal form and MFO code, e.g.:
        'ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ"ТЕРСЛАВ", МФО 300465'
        
        Args:
            df_raw: Raw DataFrame loaded without header.
            
        Returns:
            Company name string (may need normalization).
        """
        if df_raw.empty:
            return "Не визначено"
        raw_name = str(df_raw.iloc[0, 0])
        # Remove MFO suffix if present
        if ', МФО' in raw_name:
            raw_name = raw_name.split(', МФО')[0]
        return raw_name.strip()

    def _parse_bank_payments_generic(
        self,
        df: pd.DataFrame,
        bank_format: str,
        company_name: Optional[str] = None
    ) -> List[Tuple[str, str, str, float, Optional[str]]]:
        """
        Generic parser for bank payments (works for Ukrgasbank and Oschadbank).

        Only incoming (credit) payments to Guaranteed Buyer are extracted.
        Outgoing (debit) payments and payments to other counterparties are skipped.

        Args:
            df: DataFrame with bank statement data
            bank_format: Bank format identifier ('ukrgasbank' or 'oschadbank')
            company_name: Company name for header-based formats (Oschadbank)

        Returns:
            List of (company, counterparty, period, amount, payment_date) tuples.

        Raises:
            ValueError: If bank_format is not recognized
        """
        config = BANK_CONFIGS.get(bank_format)
        if not config:
            raise ValueError(f"Unknown bank format: {bank_format}")

        payments: List[Tuple[str, str, str, float, Optional[str]]] = []
        skipped = 0
        skipped_not_gb = 0

        for _, row in df.iterrows():
            try:
                # Check direction if applicable (Ukrgasbank has DK field)
                if config['direction_field']:
                    direction = row.get(config['direction_field'])
                    if pd.notna(direction):
                        try:
                            direction_value = int(direction)
                        except (ValueError, TypeError):
                            direction_value = None
                        if direction_value is not None and direction_value != config['direction_value']:
                            skipped += 1
                            continue

                # Parse amount
                amount = self._parse_bank_amount(row.get(config['amount_field']))
                if amount <= 0:
                    skipped += 1
                    continue

                # Extract period
                purpose = str(row.get(config['purpose_field'], ''))
                payment_date = self._parse_bank_date(row.get(config['date_field']))
                period = extract_period_from_purpose(purpose, payment_date)

                if not period:
                    skipped += 1
                    continue

                # Get company name
                if config['company_from_header']:
                    company = DataNormalizer.normalize_company(company_name or 'Не визначено')
                else:
                    company = DataNormalizer.normalize_company(
                        str(row.get(config['company_field'], 'Не визначено'))
                    )

                # Get counterparty
                counterparty = DataNormalizer.normalize_counterparty(
                    str(row.get(config['counterparty_field'], 'Не визначено'))
                )

                # Filter: only Guaranteed Buyer payments
                if counterparty != "ГАРАНТОВАНИЙ ПОКУПЕЦЬ":
                    skipped_not_gb += 1
                    continue

                payments.append((company, counterparty, period, amount, payment_date))

            except (ValueError, TypeError, KeyError, AttributeError) as e:
                self.logger.warning(f"Skipping {bank_format} row: {e}")
                skipped += 1

        self.logger.info(
            f"Parsed {len(payments)} {bank_format} payments to Guaranteed Buyer, "
            f"skipped {skipped} rows (invalid/outgoing), {skipped_not_gb} payments to other counterparties"
        )
        return payments

    def _parse_ukrgasbank_payments(
        self, df: pd.DataFrame
    ) -> List[Tuple[str, str, str, float, Optional[str]]]:
        """
        Parse Ukrgasbank Excel into payment tuples (incoming only, Guaranteed Buyer only).

        Only incoming (credit) payments to Guaranteed Buyer are extracted (DK=1).
        Outgoing (debit) payments and payments to other counterparties are skipped.

        Ukrgasbank format columns:
            - NAME: Company name (account holder)
            - NAME_KOR: Counterparty name
            - SUM_PD_NOM: Payment amount
            - PURPOSE: Payment purpose text
            - DATA_VYP: Statement date (DD-MM-YYYY)
            - DK: Direction (1=credit/incoming, 2=debit/outgoing)

        Args:
            df: DataFrame with Ukrgasbank column structure.

        Returns:
            List of (company, counterparty, period, amount, payment_date) tuples.
        """
        return self._parse_bank_payments_generic(df, 'ukrgasbank')

    def _parse_oschadbank_payments(
        self, df: pd.DataFrame, company_name: str
    ) -> List[Tuple[str, str, str, float, Optional[str]]]:
        """
        Parse Oschadbank Excel into payment tuples (incoming only, Guaranteed Buyer only).

        Only incoming (credit) payments to Guaranteed Buyer are extracted.
        Outgoing (debit) payments and payments to other counterparties are skipped.

        Oschadbank format columns (header at row 3):
            - Найменування кореспондента: Counterparty name
            - Дебет: Debit amount (outgoing) — skipped
            - Кредит: Credit amount (incoming) — processed
            - Призначення платежу: Payment purpose text
            - Дата валютування: Value date (DD.MM.YYYY)

        Company name is extracted from the file header area (row 0).

        Args:
            df: DataFrame with Oschadbank column structure.
            company_name: Company name from header area.

        Returns:
            List of (company, counterparty, period, amount, payment_date) tuples.
        """
        return self._parse_bank_payments_generic(df, 'oschadbank', company_name)

    def _save_bank_payments(
        self,
        payments: List[Tuple[str, str, str, float, Optional[str]]],
        db_manager: "DatabaseManager",
        bank_name: str,
    ) -> int:
        """
        Save parsed bank payments to database.
        
        Args:
            payments: List of (company, counterparty, period, amount, payment_date) tuples.
            db_manager: DatabaseManager instance.
            bank_name: Bank name for logging.
            
        Returns:
            Number of successfully saved payments.
            
        Raises:
            ValueError: If no incoming payments were found.
        """
        if not payments:
            raise ValueError(
                f"Не знайдено жодного вхідного платежу у виписці {bank_name}.\n"
                "Переконайтеся, що файл містить коректні дані\n"
                "та містить вхідні (кредитові) операції."
            )

        processed_count = db_manager.save_payments_batch(payments)
        self.logger.info(
            f"Saved {processed_count} incoming payments from {bank_name} bank statement"
        )
        return processed_count

    # ==================== Combined Excel Processing ====================

    def process_combined_excel(self, file_path: str, db_manager: "DatabaseManager") -> Tuple[int, int]:
        """
        Обробляє комбінований Excel файл з актами та оплатами.
        Файл повинен містити два аркуші: "Акти" та "Оплати"
        
        Args:
            file_path: Path to Excel file
            db_manager: Database manager instance
            
        Returns:
            tuple: (кількість оброблених актів, кількість оброблених оплат)
            
        Raises:
            ValueError: If sheets are not found or processing fails
        """
        self.logger.info(f"Processing combined Excel file: {file_path}")
        
        try:
            # Завантажуємо всі аркуші
            excel_file = pd.ExcelFile(file_path)
            sheet_names = excel_file.sheet_names
            self.logger.info(f"Available sheets: {sheet_names}")
            
            acts_count = 0
            payments_count = 0
            
            # Шукаємо аркуш з актами
            acts_sheet = None
            for name in sheet_names:
                if 'акт' in name.lower():
                    acts_sheet = name
                    break
            
            # Шукаємо аркуш з оплатами
            payments_sheet = None
            for name in sheet_names:
                if 'оплат' in name.lower() or 'платеж' in name.lower():
                    payments_sheet = name
                    break
            
            # Обробка актів
            if acts_sheet:
                self.logger.info(f"Processing acts from sheet: {acts_sheet}")
                df_acts = pd.read_excel(file_path, sheet_name=acts_sheet)
                acts_count = self._process_acts_dataframe(df_acts, db_manager)
                self.logger.info(f"Processed {acts_count} acts")
            else:
                self.logger.warning("No sheet with acts found. Looking for default sheet name 'Акти'")
                try:
                    df_acts = pd.read_excel(file_path, sheet_name='Акти')
                    acts_count = self._process_acts_dataframe(df_acts, db_manager)
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Could not find acts sheet: {str(e)}")
            
            # Обробка оплат
            if payments_sheet:
                self.logger.info(f"Processing payments from sheet: {payments_sheet}")
                df_payments = pd.read_excel(file_path, sheet_name=payments_sheet)
                payments_count = self._process_payments_dataframe(df_payments, db_manager)
                self.logger.info(f"Processed {payments_count} payments")
            else:
                self.logger.warning("No sheet with payments found. Looking for default sheet name 'Оплати'")
                try:
                    df_payments = pd.read_excel(file_path, sheet_name='Оплати')
                    payments_count = self._process_payments_dataframe(df_payments, db_manager)
                except (ValueError, KeyError) as e:
                    self.logger.warning(f"Could not find payments sheet: {str(e)}")
            
            if acts_count == 0 and payments_count == 0:
                raise ValueError(
                    "Не вдалося знайти жодного аркуша з актами або оплатами.\n"
                    "Переконайтеся, що файл містить аркуші з назвами 'Акти' та 'Оплати' "
                    "або їх варіації."
                )
            
            return acts_count, payments_count

        except (ValueError, OSError, KeyError, TypeError, AttributeError) as e:
            self.logger.error(f"Failed to process combined Excel file: {str(e)}")
            raise
        except Exception as e:
            self.logger.exception("Unexpected error processing combined Excel %s", file_path)
            raise

    def _process_acts_dataframe(self, df: pd.DataFrame, db_manager: "DatabaseManager") -> int:
        """
        Обробляє DataFrame з актами.
        
        Args:
            df: DataFrame with acts data
            db_manager: Database manager instance
            
        Returns:
            Number of processed acts
        """
        required_columns = ['Дата', 'Сумма', 'Контрагент', 'Организация']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            self.logger.error(f"Missing required columns in acts sheet: {missing_columns}")
            raise ValueError(f"Не знайдено колонки в аркуші актів: {', '.join(missing_columns)}")

        # Векторизована обробка
        df['period'] = df['Дата'].apply(extract_month_from_date)
        df['amount'] = pd.to_numeric(df['Сумма'], errors='coerce')
        df['counterparty'] = df['Контрагент'].apply(DataNormalizer.normalize_counterparty)
        df['company'] = df['Организация'].apply(DataNormalizer.normalize_company)

        # Перевіряємо на помилки
        invalid_rows = df[df['period'].isna() | df['amount'].isna()]
        if not invalid_rows.empty:
            self.logger.error(f"Invalid rows detected in acts: {invalid_rows}")
            raise ValueError("Деякі рядки в актах мають некоректні значення для дати або суми")

        # Prepare batch data for bulk insert - фільтруємо тільки ГП
        acts_batch = [
            (row['company'], row['counterparty'], row['period'], row['amount'], None, None)
            for _, row in df.iterrows()
            if row['counterparty'] == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        ]
        
        total_rows = len(df)
        filtered_count = len(acts_batch)
        skipped_count = total_rows - filtered_count
        
        if skipped_count > 0:
            self.logger.info(f"Skipped {skipped_count} acts with other counterparties (only Guaranteed Buyer accepted)")
        
        # Use batch insert for better performance
        processed_count = db_manager.save_acts_batch(acts_batch)
        return processed_count

    def _process_payments_dataframe(self, df: pd.DataFrame, db_manager: "DatabaseManager") -> int:
        """
        Обробляє DataFrame з оплатами.
        
        Args:
            df: DataFrame with payments data
            db_manager: Database manager instance
            
        Returns:
            Number of processed payments
        """
        required_columns = ['Комментарий', 'Сумма документа', 'Контрагент', 'Организация']
        
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            self.logger.error(f"Missing required columns in payments sheet: {missing_columns}")
            raise ValueError(f"Не знайдено колонки в аркуші оплат: {', '.join(missing_columns)}")

        # Векторизована обробка
        df['period'] = df['Комментарий'].apply(extract_month)
        df['amount'] = pd.to_numeric(df['Сумма документа'], errors='coerce')
        df['counterparty'] = df['Контрагент'].apply(DataNormalizer.normalize_counterparty)
        df['company'] = df['Организация'].apply(DataNormalizer.normalize_company)

        # Перевіряємо на помилки
        invalid_rows = df[df['period'].isna() | df['amount'].isna()]
        if not invalid_rows.empty:
            self.logger.error(f"Invalid rows detected in payments: {invalid_rows}")
            raise ValueError("Деякі рядки в оплатах мають некоректні значення для періоду або суми")

        # Prepare batch data for bulk insert - фільтруємо тільки ГП
        payments_batch: List[Tuple[str, str, str, float, Optional[str]]] = [
            (row['company'], row['counterparty'], row['period'], row['amount'], None)
            for _, row in df.iterrows()
            if row['counterparty'] == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        ]
        
        total_rows = len(df)
        filtered_count = len(payments_batch)
        skipped_count = total_rows - filtered_count
        
        if skipped_count > 0:
            self.logger.info(f"Skipped {skipped_count} payments with other counterparties (only Guaranteed Buyer accepted)")
        
        # Use batch insert for better performance
        processed_count = db_manager.save_payments_batch(payments_batch)
        return processed_count

    def process_pdf_file(self, file_path: str, db_manager: "DatabaseManager") -> int:
        """
        Обробляє PDF файл з актом виконаних робіт.
        
        Args:
            file_path: Шлях до PDF файлу
            db_manager: Екземпляр DatabaseManager для збереження даних
            
        Returns:
            int: Кількість оброблених записів
            
        Raises:
            ValueError: Якщо файл не є PDF або неможливо визначити тип
            PDFExtractionError: Якщо виникла помилка при обробці PDF
        """
        self.logger.info(f"Processing PDF file: {file_path}")
        
        # Перевіряємо розширення файлу
        if not file_path.lower().endswith('.pdf'):
            self.logger.error(f"File is not a PDF: {file_path}")
            raise ValueError(f"Файл не є PDF: {file_path}")
        
        try:
            # Створюємо базовий екстрактор для визначення типу
            extractor = PDFExtractor()
            
            # Валідуємо PDF файл
            is_valid, validation_message = extractor.validate_pdf_file(file_path)
            if not is_valid:
                self.logger.error(f"PDF validation failed: {validation_message}")
                raise ValueError(f"PDF файл не придатний для обробки: {validation_message}")
            
            # Обробляємо як акт
            return self.process_act_pdf(file_path, db_manager)
                
        except (PDFExtractionError, UnsupportedPDFFormatError, InvalidPDFDataError, PDFParsingError) as e:
            # Зберігаємо проблемний PDF для аналізу
            if hasattr(e, 'save_problematic_file'):
                saved_path = e.save_problematic_file()
                if saved_path:
                    self.logger.info(f"Problematic PDF saved for analysis: {saved_path}")
            
            # Пробрасываем PDF-специфичные ошибки как ValueError для единообразия
            self.logger.error(f"PDF processing error: {str(e)}")
            raise ValueError(str(e)) from e
        except (ValueError, OSError, TypeError, AttributeError, RuntimeError) as e:
            self.logger.error(f"Unexpected error processing PDF: {str(e)}")
            raise ValueError(f"Не вдалося обробити PDF файл: {str(e)}") from e
        except Exception as e:
            self.logger.exception("Unexpected error processing PDF %s", file_path)
            raise ValueError(f"Не вдалося обробити PDF файл: {str(e)}") from e

    def process_act_pdf(self, file_path: str, db_manager: "DatabaseManager") -> int:
        """
        Обробляє акт виконаних робіт з PDF файлу.
        
        Args:
            file_path: Шлях до PDF файлу
            db_manager: Екземпляр DatabaseManager для збереження даних
            
        Returns:
            int: Кількість оброблених актів (завжди 1 для одного акту)
            
        Raises:
            ValueError: Якщо не вдалося витягнути або зберегти дані
        """
        self.logger.info(f"Processing act PDF: {file_path}")
        
        try:
            # Створюємо екстрактор для актів
            extractor = ActExtractor()
            
            # Витягуємо дані акту
            act_data = extractor.extract_act_data(file_path)
            
            self.logger.info(f"Extracted act data: {act_data}")
            
            # Валідація обов'язкових полів
            if not act_data.get('amount') or act_data['amount'] <= 0:
                raise InvalidPDFDataError("Некоректна сума акту")
            
            if not act_data.get('period'):
                raise InvalidPDFDataError("Не вдалося визначити період акту")
            
            # Отримуємо дані з act_data
            executor = act_data.get('executor', 'Не визначено')
            customer = act_data.get('customer', 'Не визначено')
            
            # Нормалізуємо дані
            executor = DataNormalizer.normalize_company(executor)
            customer = DataNormalizer.normalize_counterparty(customer)
            
            # Зберігаємо в базу даних (з абсолютним шляхом до PDF)
            import os
            abs_pdf_path = os.path.abspath(file_path)
            
            # Calculate price_without_vat if we have both cost and volume
            price_without_vat = None
            if act_data.get('cost_without_vat') and act_data.get('energy_volume'):
                try:
                    price_without_vat = act_data['cost_without_vat'] / act_data['energy_volume']
                except ZeroDivisionError:
                    pass

            db_manager.save_act(
                company=executor,
                counterparty=customer,
                period=act_data['period'],
                amount=act_data['amount'],
                energy_volume=act_data.get('energy_volume'),
                cost_without_vat=act_data.get('cost_without_vat'),
                price_without_vat=price_without_vat,
                pdf_path=abs_pdf_path
            )
            
            self.logger.info(
                f"Successfully saved act: {executor} -> {customer}, "
                f"{act_data['period']}, {act_data['amount']}"
            )
            
            # Повертаємо 1, оскільки обробили один акт
            return 1
            
        except (InvalidPDFDataError, PDFExtractionError) as e:
            # Зберігаємо проблемний PDF для аналізу
            if hasattr(e, 'save_problematic_file'):
                saved_path = e.save_problematic_file()
                if saved_path:
                    self.logger.info(f"Problematic act PDF saved: {saved_path}")
            
            self.logger.error(f"Failed to process act PDF: {str(e)}")
            raise ValueError(str(e)) from e
        except (ValueError, OSError, TypeError, AttributeError, RuntimeError) as e:
            self.logger.error(f"Unexpected error processing act PDF: {str(e)}")
            raise ValueError(f"Не вдалося обробити акт: {str(e)}") from e
        except Exception as e:
            self.logger.exception("Unexpected error processing act PDF %s", file_path)
            raise ValueError(f"Не вдалося обробити акт: {str(e)}") from e