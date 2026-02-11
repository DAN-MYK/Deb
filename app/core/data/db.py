"""
Database manager module with context managers and transaction support.
"""
# Standard library imports
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Local imports
from app.config.config import settings
from app.core.errors.exceptions import DatabaseError
from app.core.normalization import DataNormalizer
from app.core.validation.validators import DataValidator

logger = logging.getLogger("deb.db")


def calculate_file_hash(file_path: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Calculate MD5 hash and size of a file.

    Args:
        file_path: Path to the file

    Returns:
        Tuple of (md5_hash, file_size) or (None, None) if file not found
    """
    import hashlib
    from pathlib import Path

    try:
        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return None, None

        # Calculate MD5 hash
        md5_hash = hashlib.md5()
        file_size = path.stat().st_size

        # Read file in chunks to handle large files
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                md5_hash.update(chunk)

        return md5_hash.hexdigest(), file_size
    except Exception as e:
        logger.warning(f"Failed to calculate file hash for {file_path}: {e}")
        return None, None


class DatabaseManager:
    """
    Database manager with context managers and transaction support.
    
    Provides safe database operations with automatic connection management,
    transaction handling, and proper error recovery.
    """
    
    def __init__(self) -> None:
        """Initialize database manager and create database files."""
        self.db_path = Path(settings.data_dir) / settings.db_name
        self._ensure_data_dir()
        self._init_databases()
        self._migrate_from_separate_dbs()
    
    def _ensure_data_dir(self) -> None:
        """Create data directory if it doesn't exist."""
        data_dir = Path(settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def _get_connection(self) -> Iterator[sqlite3.Connection]:
        """
        Context manager for database connection.

        Yields:
            Connection to the database

        Raises:
            DatabaseError: If connection or transaction fails
        """
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise DatabaseError(f"Database operation failed: {e}") from e
        finally:
            if conn:
                conn.close()
    
    def _init_databases(self) -> None:
        """Initialize database schemas and indexes in a single database."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Initialize acts table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS acts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    counterparty TEXT NOT NULL,
                    period TEXT NOT NULL,
                    amount REAL NOT NULL,
                    energy_volume REAL,
                    cost_without_vat REAL,
                    price_without_vat REAL,
                    pdf_path TEXT,
                    file_hash TEXT,
                    file_size INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Check if pdf_path column exists (for existing databases)
            cursor.execute("PRAGMA table_info(acts)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'pdf_path' not in columns:
                logger.info("Adding pdf_path column to existing acts table")
                cursor.execute("ALTER TABLE acts ADD COLUMN pdf_path TEXT")

            if 'price_without_vat' not in columns:
                logger.info("Adding price_without_vat column to existing acts table")
                cursor.execute("ALTER TABLE acts ADD COLUMN price_without_vat REAL")

            if 'file_hash' not in columns:
                logger.info("Adding file_hash column to existing acts table")
                cursor.execute("ALTER TABLE acts ADD COLUMN file_hash TEXT")

            if 'file_size' not in columns:
                logger.info("Adding file_size column to existing acts table")
                cursor.execute("ALTER TABLE acts ADD COLUMN file_size INTEGER")

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_acts_period ON acts(period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_acts_company ON acts(company)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_acts_company_period ON acts(company, period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_acts_counterparty ON acts(counterparty)')

            # Initialize payments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS payments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    counterparty TEXT NOT NULL,
                    period TEXT NOT NULL,
                    amount REAL NOT NULL,
                    payment_date TEXT,
                    purpose TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            cursor.execute('DROP INDEX IF EXISTS unique_payment')

            cursor.execute("PRAGMA table_info(payments)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'payment_date' not in columns:
                logger.info("Adding payment_date column to existing payments table")
                cursor.execute("ALTER TABLE payments ADD COLUMN payment_date TEXT")

            if 'purpose' not in columns:
                logger.info("Adding purpose column to existing payments table")
                cursor.execute("ALTER TABLE payments ADD COLUMN purpose TEXT")

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_period ON payments(period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_company ON payments(company)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_company_period ON payments(company, period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_counterparty ON payments(counterparty)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_payment_date ON payments(payment_date)')

            # Initialize act adjustments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS act_adjustments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    counterparty TEXT NOT NULL,
                    period TEXT NOT NULL,
                    adjustment_amount REAL NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    version TEXT,
                    adjustment_date TEXT,
                    contract_number TEXT,
                    adjustment_amount_with_vat REAL,
                    energy_volume REAL,
                    price_per_kwh REAL,
                    vat_amount REAL,
                    resource_code TEXT,
                    facility_name TEXT,
                    pdf_path TEXT,
                    file_hash TEXT,
                    file_size INTEGER,
                    original_energy REAL,
                    original_amount REAL,
                    corrected_energy REAL,
                    corrected_amount REAL
                )
            ''')

            cursor.execute("PRAGMA table_info(act_adjustments)")
            columns = [row[1] for row in cursor.fetchall()]

            new_columns = {
                'version': 'TEXT',
                'adjustment_date': 'TEXT',
                'contract_number': 'TEXT',
                'adjustment_amount_with_vat': 'REAL',
                'energy_volume': 'REAL',
                'price_per_kwh': 'REAL',
                'vat_amount': 'REAL',
                'resource_code': 'TEXT',
                'facility_name': 'TEXT',
                'pdf_path': 'TEXT',
                'file_hash': 'TEXT',
                'file_size': 'INTEGER',
                'original_energy': 'REAL',
                'original_amount': 'REAL',
                'corrected_energy': 'REAL',
                'corrected_amount': 'REAL',
            }

            for column_name, column_type in new_columns.items():
                if column_name not in columns:
                    logger.info(f"Adding {column_name} column to act_adjustments table")
                    cursor.execute(f"ALTER TABLE act_adjustments ADD COLUMN {column_name} {column_type}")

            cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_period ON act_adjustments(period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_company ON act_adjustments(company)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_company_period ON act_adjustments(company, period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_counterparty ON act_adjustments(counterparty)')

            logger.info("Database initialized with all tables and indexes")

    def _migrate_from_separate_dbs(self) -> None:
        """Migrate data from old separate database files into the single deb.db.

        Checks for acts.db, payments.db, act_adjustments.db in the data directory.
        If they contain data and deb.db doesn't have that data yet, copies it over
        using ATTACH DATABASE. Old files are renamed to .db.bak afterwards.
        """
        data_dir = Path(settings.data_dir)
        old_dbs = [
            ("acts.db", "acts", "acts"),
            ("payments.db", "payments", "payments"),
            ("act_adjustments.db", "act_adjustments", "act_adjustments"),
        ]

        for old_filename, table_name, _alias in old_dbs:
            old_path = data_dir / old_filename
            if not old_path.exists():
                continue
            # Skip if old file IS the new deb.db (same file)
            if old_path.resolve() == self.db_path.resolve():
                continue

            try:
                # Check if old DB has data
                old_conn = sqlite3.connect(str(old_path))
                try:
                    old_cursor = old_conn.cursor()
                    old_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    old_count = old_cursor.fetchone()[0]
                finally:
                    old_conn.close()

                if old_count == 0:
                    # No data to migrate, just rename
                    backup_path = old_path.with_suffix('.db.bak')
                    old_path.rename(backup_path)
                    logger.info(f"Renamed empty {old_filename} to {backup_path.name}")
                    continue

                # Check if deb.db already has data in this table
                with self._get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    new_count = cursor.fetchone()[0]

                if new_count > 0:
                    # deb.db already has data, skip migration
                    logger.info(
                        f"Skipping migration of {old_filename}: "
                        f"deb.db already has {new_count} rows in {table_name}"
                    )
                    continue

                # Migrate data using ATTACH DATABASE
                conn = sqlite3.connect(str(self.db_path))
                try:
                    alias = f"old_{table_name}"
                    conn.execute(f"ATTACH DATABASE ? AS {alias}", (str(old_path),))
                    conn.execute(f"INSERT INTO {table_name} SELECT * FROM {alias}.{table_name}")
                    conn.commit()
                    conn.execute(f"DETACH DATABASE {alias}")

                    # Verify migration
                    cursor = conn.cursor()
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    migrated_count = cursor.fetchone()[0]
                    logger.info(
                        f"Migrated {migrated_count} rows from {old_filename} to deb.db ({table_name})"
                    )
                finally:
                    conn.close()

                # Rename old file to .bak
                backup_path = old_path.with_suffix('.db.bak')
                if backup_path.exists():
                    backup_path.unlink()
                old_path.rename(backup_path)
                logger.info(f"Renamed {old_filename} to {backup_path.name}")

            except Exception as e:
                logger.warning(f"Failed to migrate {old_filename}: {e}")

    def check_act_exists(self, pdf_path: str, file_hash: Optional[str] = None) -> Optional[int]:
        """
        Check if an act from this PDF has already been imported.

        Args:
            pdf_path: Path to the PDF file
            file_hash: Optional MD5 hash of the file (will be calculated if not provided)

        Returns:
            Act ID if exists, None otherwise
        """
        if not pdf_path:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Primary check: by file hash (most reliable)
            if file_hash is None:
                file_hash, _ = calculate_file_hash(pdf_path)

            if file_hash:
                cursor.execute('SELECT id FROM acts WHERE file_hash = ?', (file_hash,))
                result = cursor.fetchone()
                if result:
                    logger.info(f"Found duplicate PDF by hash: ID {result[0]}")
                    return result[0]

            # Fallback: check by exact path match
            from pathlib import Path
            try:
                absolute_path = str(Path(pdf_path).resolve())
                cursor.execute('SELECT id FROM acts WHERE pdf_path = ?', (absolute_path,))
                result = cursor.fetchone()
                if result:
                    logger.info(f"Found duplicate PDF by path: ID {result[0]}")
                    return result[0]
            except Exception as e:
                logger.debug(f"Path comparison failed: {e}")

            return None

    def save_act(
        self,
        company: str,
        counterparty: str,
        period: str,
        amount: float,
        energy_volume: Optional[float] = None,
        cost_without_vat: Optional[float] = None,
        price_without_vat: Optional[float] = None,
        pdf_path: Optional[str] = None
    ) -> int:
        """
        Save act to database with validation and normalization.

        Args:
            company: Company name (will be normalized)
            counterparty: Counterparty name (will be normalized)
            period: Period in format MM-YYYY or MM.YYYY
            amount: Act amount in UAH (must be positive)
            energy_volume: Optional energy volume in kWh
            cost_without_vat: Optional cost without VAT in UAH
            price_without_vat: Optional price per unit without VAT in UAH
            pdf_path: Optional path to source PDF file

        Returns:
            ID of the saved act

        Raises:
            ValueError: If data validation fails
            DatabaseError: If database operation fails
        """
        # Validate inputs
        DataValidator.validate_string(company, "company")
        DataValidator.validate_string(counterparty, "counterparty")
        DataValidator.validate_amount(amount, "amount")
        
        if energy_volume is not None:
            DataValidator.validate_energy_volume(energy_volume, "energy_volume")
        
        if cost_without_vat is not None:
            DataValidator.validate_amount(cost_without_vat, "cost_without_vat")

        if price_without_vat is not None:
            DataValidator.validate_amount(price_without_vat, "price_without_vat")

        # Normalize first (period needs normalization before validation)
        company = DataNormalizer.normalize_company(company)
        counterparty = DataNormalizer.normalize_counterparty(counterparty)
        period = DataNormalizer.normalize_period(period)

        # Validate period after normalization
        DataValidator.validate_period(period)

        # Calculate file hash and normalize PDF path
        file_hash = None
        file_size = None
        if pdf_path:
            from pathlib import Path
            import unicodedata

            try:
                # Normalize to absolute path with proper Unicode handling
                pdf_path = str(Path(pdf_path).resolve())
                pdf_path = unicodedata.normalize('NFC', pdf_path)

                # Calculate file hash for duplicate detection
                file_hash, file_size = calculate_file_hash(pdf_path)
            except Exception as e:
                logger.error(f"Failed to process PDF path: {e}")
                raise ValueError(f"Некоректний шлях до PDF файлу: {pdf_path}")

            # Check for duplicate PDF import (using hash)
            existing_id = self.check_act_exists(pdf_path, file_hash)
            if existing_id:
                logger.warning(f"Act from PDF already exists with ID {existing_id}: {pdf_path}")
                raise ValueError(f"Цей PDF файл вже було завантажено раніше (ID: {existing_id})")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO acts (company, counterparty, period, amount, energy_volume,
                                 cost_without_vat, price_without_vat, pdf_path, file_hash, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (company, counterparty, period, amount, energy_volume, cost_without_vat,
                  price_without_vat, pdf_path, file_hash, file_size))
            act_id = cursor.lastrowid
            if act_id is None:
                raise DatabaseError("Failed to get ID of saved act")
            logger.info(f"Act saved with ID: {act_id} (PDF: {pdf_path or 'N/A'})")
            return act_id

    def save_payment(
        self,
        company: str,
        counterparty: str,
        period: str,
        amount: float,
        payment_date: Optional[str] = None,
        purpose: Optional[str] = None
    ) -> int:
        """
        Save payment to database with validation and normalization.
        
        Multiple payments for the same period are allowed.
        
        Args:
            company: Company name (will be normalized)
            counterparty: Counterparty name (will be normalized)
            period: Period in format MM-YYYY or MM.YYYY
            amount: Payment amount in UAH (must be positive)
            payment_date: Optional payment date in YYYY-MM-DD format
            
        Returns:
            ID of the saved payment
            
        Raises:
            ValueError: If data validation fails
            DatabaseError: If database operation fails
        """
        # Validate inputs
        DataValidator.validate_string(company, "company")
        DataValidator.validate_string(counterparty, "counterparty")
        DataValidator.validate_amount(amount, "amount")
        
        # Validate payment_date if provided
        if payment_date is not None:
            DataValidator.validate_date(payment_date, "payment_date")
        
        # Normalize first (period needs normalization before validation)
        company = DataNormalizer.normalize_company(company)
        counterparty = DataNormalizer.normalize_counterparty(counterparty)
        period = DataNormalizer.normalize_period(period)
        
        # Validate period after normalization
        DataValidator.validate_period(period)

        # Check for duplicate payment (by date and amount)
        if payment_date is not None:
            existing_id = self.check_payment_exists(payment_date, amount)
            if existing_id:
                logger.warning(f"Payment with same date and amount already exists with ID {existing_id}")
                raise ValueError(f"Оплата з такою датою ({payment_date}) та сумою ({amount:.2f} грн) вже існує (ID: {existing_id})")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO payments (company, counterparty, period, amount, payment_date, purpose)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (company, counterparty, period, amount, payment_date, purpose))
            payment_id = cursor.lastrowid
            if payment_id is None:
                raise DatabaseError("Failed to get ID of saved payment")
            logger.info(f"Payment saved with ID: {payment_id}")
            return payment_id

    def _save_batch_generic(
        self,
        records: List[Tuple],
        table_name: str,
        is_payment: bool = False
    ) -> int:
        """
        Generic method for batch saving records (acts or payments).

        Args:
            records: List of tuples to save
            table_name: Table name ('acts' or 'payments')
            is_payment: True for payments, False for acts

        Returns:
            Number of records successfully inserted

        Raises:
            ValueError: If any record fails validation
            DatabaseError: If database operation fails
        """
        if not records:
            logger.warning(f"save_{table_name}_batch called with empty list")
            return 0

        # Validate and normalize all records first
        normalized_records = []
        for idx, record in enumerate(records):
            try:
                if is_payment:
                    company = record[0]
                    counterparty = record[1]
                    period = record[2]
                    amount = record[3]
                    payment_date = record[4] if len(record) > 4 else None
                    purpose = record[5] if len(record) > 5 else None

                    # Validate
                    DataValidator.validate_string(company, "company")
                    DataValidator.validate_string(counterparty, "counterparty")
                    DataValidator.validate_amount(amount, "amount")

                    if payment_date is not None:
                        DataValidator.validate_date(payment_date, "payment_date")

                    # Normalize
                    normalized_company = DataNormalizer.normalize_company(company)
                    normalized_counterparty = DataNormalizer.normalize_counterparty(counterparty)
                    normalized_period = DataNormalizer.normalize_period(period)

                    # Validate period after normalization
                    DataValidator.validate_period(normalized_period)

                    normalized_records.append((
                        normalized_company,
                        normalized_counterparty,
                        normalized_period,
                        amount,
                        payment_date,
                        purpose
                    ))
                else:
                    company, counterparty, period, amount, energy_volume, cost_without_vat = record

                    # Validate
                    DataValidator.validate_string(company, "company")
                    DataValidator.validate_string(counterparty, "counterparty")
                    DataValidator.validate_amount(amount, "amount")

                    if energy_volume is not None:
                        DataValidator.validate_energy_volume(energy_volume, "energy_volume")

                    if cost_without_vat is not None:
                        DataValidator.validate_amount(cost_without_vat, "cost_without_vat")

                    # Normalize
                    normalized_company = DataNormalizer.normalize_company(company)
                    normalized_counterparty = DataNormalizer.normalize_counterparty(counterparty)
                    normalized_period = DataNormalizer.normalize_period(period)

                    # Validate period after normalization
                    DataValidator.validate_period(normalized_period)

                    normalized_records.append((
                        normalized_company,
                        normalized_counterparty,
                        normalized_period,
                        amount,
                        energy_volume,
                        cost_without_vat
                    ))

            except (ValueError, TypeError) as e:
                logger.error(f"Validation failed for {table_name} #{idx + 1}: {e}")
                raise ValueError(f"{table_name.capitalize()} #{idx + 1} validation failed: {e}") from e

        # Perform bulk insert in single transaction
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if is_payment:
                cursor.executemany('''
                    INSERT INTO payments (company, counterparty, period, amount, payment_date, purpose)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', normalized_records)
            else:
                cursor.executemany('''
                    INSERT INTO acts (company, counterparty, period, amount, energy_volume, cost_without_vat)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', normalized_records)

            rows_inserted = cursor.rowcount
            logger.info(f"Batch inserted {rows_inserted} {table_name}")
            return rows_inserted

    def save_acts_batch(
        self,
        acts: List[Tuple[str, str, str, float, Optional[float], Optional[float]]]
    ) -> int:
        """
        Save multiple acts to database in a single transaction using bulk insert.

        This is significantly faster than saving acts one by one for large datasets.
        All acts are validated and normalized before insertion. If any act fails
        validation, the entire batch is rolled back.

        Args:
            acts: List of tuples (company, counterparty, period, amount, energy_volume, cost_without_vat)

        Returns:
            Number of acts successfully inserted

        Raises:
            ValueError: If any act fails validation
            DatabaseError: If database operation fails
        """
        return self._save_batch_generic(acts, 'acts', is_payment=False)

    def save_payments_batch(
        self,
        payments: List[Tuple[str, str, str, float, Optional[str], Optional[str]]]
    ) -> int:
        """
        Save multiple payments to database in a single transaction using bulk insert.

        This is significantly faster than saving payments one by one for large datasets.
        All payments are validated and normalized before insertion. If any payment fails
        validation, the entire batch is rolled back.

        Args:
            payments: List of tuples (company, counterparty, period, amount, payment_date, purpose).
                      payment_date and purpose are optional (can be None).
                      payment_date should be in YYYY-MM-DD format.

        Returns:
            Number of payments successfully inserted

        Raises:
            ValueError: If any payment fails validation
            DatabaseError: If database operation fails
        """
        return self._save_batch_generic(payments, 'payments', is_payment=True)

    def adjust_acts(
        self,
        company: str,
        counterparty: str,
        period: str,
        adjustment_amount: float
    ) -> Tuple[int, bool]:
        """
        Adjust acts for a specific period.
        
        If acts exist for the period, updates their amounts.
        If no acts exist, creates a new act with the adjustment amount.
        
        Args:
            company: Company name (will be normalized)
            counterparty: Counterparty name (will be normalized)
            period: Period in format MM-YYYY or MM.YYYY
            adjustment_amount: Amount to add to existing acts
            
        Returns:
            Tuple of (number_of_updated_acts, was_created)
            - number_of_updated_acts: Number of acts that were updated
            - was_created: True if new act was created, False if existing acts were updated
            
        Raises:
            ValueError: If data validation fails
            DatabaseError: If database operation fails
        """
        # Validate inputs
        DataValidator.validate_string(company, "company")
        DataValidator.validate_string(counterparty, "counterparty")
        
        # Note: adjustment_amount can be negative, so we don't validate it as a positive amount
        if adjustment_amount is None or not isinstance(adjustment_amount, (int, float)):
            raise ValueError(f"adjustment_amount must be numeric, got {type(adjustment_amount)}")
        
        # Normalize
        company = DataNormalizer.normalize_company(company)
        counterparty = DataNormalizer.normalize_counterparty(counterparty)
        period = DataNormalizer.normalize_period(period)
        
        # Validate period after normalization
        DataValidator.validate_period(period)
        
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Get all acts for the specified period
            cursor.execute('''
                SELECT id, amount 
                FROM acts 
                WHERE company = ? AND counterparty = ? AND period = ?
            ''', (company, counterparty, period))
            acts = cursor.fetchall()
            
            if not acts:
                # No acts found - create new act with adjustment amount
                cursor.execute('''
                    INSERT INTO acts (company, counterparty, period, amount)
                    VALUES (?, ?, ?, ?)
                ''', (company, counterparty, period, adjustment_amount))
                logger.info(f"Created new act with adjustment amount: {adjustment_amount}")
                return 0, True  # 0 acts updated, new act created
            else:
                # Update amounts for all acts in the period
                for act_id, amount in acts:
                    new_amount = amount + adjustment_amount
                    cursor.execute('''
                        UPDATE acts 
                        SET amount = ? 
                        WHERE id = ?
                    ''', (new_amount, act_id))
                
                logger.info(f"Updated {len(acts)} act(s) with adjustment: {adjustment_amount}")
                return len(acts), False  # Number of updated acts, not created

    def check_adjustment_exists(self, pdf_path: str, file_hash: Optional[str] = None) -> Optional[int]:
        """
        Check if an adjustment act from this PDF has already been imported.

        Args:
            pdf_path: Path to the PDF file
            file_hash: Optional MD5 hash of the file (will be calculated if not provided)

        Returns:
            Adjustment ID if exists, None otherwise
        """
        if not pdf_path:
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Primary check: by file hash (most reliable)
            if file_hash is None:
                file_hash, _ = calculate_file_hash(pdf_path)

            if file_hash:
                cursor.execute('SELECT id FROM act_adjustments WHERE file_hash = ?', (file_hash,))
                result = cursor.fetchone()
                if result:
                    logger.info(f"Found duplicate PDF by hash: ID {result[0]}")
                    return result[0]

            # Fallback: check by exact path match
            from pathlib import Path
            try:
                absolute_path = str(Path(pdf_path).resolve())
                cursor.execute('SELECT id FROM act_adjustments WHERE pdf_path = ?', (absolute_path,))
                result = cursor.fetchone()
                if result:
                    logger.info(f"Found duplicate PDF by path: ID {result[0]}")
                    return result[0]
            except Exception as e:
                logger.debug(f"Path comparison failed: {e}")

            return None

    def check_payment_exists(self, payment_date: Optional[str], amount: float) -> Optional[int]:
        """
        Check if a payment with the same date and amount already exists.

        Args:
            payment_date: Payment date in YYYY-MM-DD format (can be None)
            amount: Payment amount in UAH

        Returns:
            Payment ID if exists, None otherwise
        """
        # Both payment_date and amount must match for it to be a duplicate
        if payment_date is None:
            # If no payment_date, we can't reliably detect duplicates
            # (could be multiple payments with NULL date and same amount)
            return None

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM payments WHERE payment_date = ? AND amount = ?',
                (payment_date, amount)
            )
            result = cursor.fetchone()
            if result:
                logger.info(f"Found duplicate payment by date and amount: ID {result[0]}")
                return result[0]

            return None

    def save_act_adjustment(
        self,
        company: str,
        counterparty: str,
        period: str,
        adjustment_amount: float,
        description: Optional[str] = None,
        version: Optional[str] = None,
        adjustment_date: Optional[str] = None,
        contract_number: Optional[str] = None,
        adjustment_amount_with_vat: Optional[float] = None,
        energy_volume: Optional[float] = None,
        price_per_kwh: Optional[float] = None,
        vat_amount: Optional[float] = None,
        resource_code: Optional[str] = None,
        facility_name: Optional[str] = None,
        pdf_path: Optional[str] = None,
        original_energy: Optional[float] = None,
        original_amount: Optional[float] = None,
        corrected_energy: Optional[float] = None,
        corrected_amount: Optional[float] = None
    ) -> int:
        """
        Save act adjustment to database as a separate record.

        Act adjustments are stored independently from acts and are used
        to increase or decrease act amounts for specific periods without
        modifying the original acts.

        Args:
            company: Company name (will be normalized)
            counterparty: Counterparty name (will be normalized)
            period: Period in format MM-YYYY or MM.YYYY
            adjustment_amount: Amount to adjust (positive or negative)
            description: Optional description of the adjustment
            version: Optional version of the adjustment act ('old' or 'new')
            adjustment_date: Optional date of the adjustment act
            contract_number: Optional contract number
            adjustment_amount_with_vat: Optional adjustment amount with VAT
            energy_volume: Optional energy volume in kWh
            price_per_kwh: Optional price per kWh
            vat_amount: Optional VAT amount
            resource_code: Optional resource code (e.g., 62W...)
            facility_name: Optional facility name
            pdf_path: Optional path to source PDF file
            original_energy: Optional energy volume from first row (for two-row adjustments)
            original_amount: Optional amount with VAT from first row (for two-row adjustments)
            corrected_energy: Optional energy volume from second row (for two-row adjustments)
            corrected_amount: Optional amount with VAT from second row (for two-row adjustments)

        Returns:
            ID of the saved adjustment

        Raises:
            ValueError: If data validation fails
            DatabaseError: If database operation fails
        """
        # Validate inputs
        DataValidator.validate_string(company, "company")
        DataValidator.validate_string(counterparty, "counterparty")

        # Note: adjustment_amount can be negative, so we don't validate it as a positive amount
        if adjustment_amount is None or not isinstance(adjustment_amount, (int, float)):
            raise ValueError(f"adjustment_amount must be numeric, got {type(adjustment_amount)}")

        # Normalize
        company = DataNormalizer.normalize_company(company)
        counterparty = DataNormalizer.normalize_counterparty(counterparty)
        period = DataNormalizer.normalize_period(period)

        # Validate period after normalization
        DataValidator.validate_period(period)

        # Calculate file hash and normalize PDF path
        file_hash = None
        file_size = None
        if pdf_path:
            from pathlib import Path
            import unicodedata

            try:
                # Normalize to absolute path with proper Unicode handling
                pdf_path = str(Path(pdf_path).resolve())
                pdf_path = unicodedata.normalize('NFC', pdf_path)

                # Calculate file hash for duplicate detection
                file_hash, file_size = calculate_file_hash(pdf_path)
            except Exception as e:
                logger.error(f"Failed to process PDF path: {e}")
                raise ValueError(f"Некоректний шлях до PDF файлу: {pdf_path}")

            # Check for duplicate PDF import (using hash)
            existing_id = self.check_adjustment_exists(pdf_path, file_hash)
            if existing_id:
                logger.warning(f"Adjustment from PDF already exists with ID {existing_id}: {pdf_path}")
                raise ValueError(f"Цей PDF файл вже було завантажено раніше (ID: {existing_id})")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO act_adjustments (
                    company, counterparty, period, adjustment_amount, description,
                    version, adjustment_date, contract_number, adjustment_amount_with_vat,
                    energy_volume, price_per_kwh, vat_amount, resource_code, facility_name,
                    pdf_path, file_hash, file_size,
                    original_energy, original_amount, corrected_energy, corrected_amount
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                company, counterparty, period, adjustment_amount, description,
                version, adjustment_date, contract_number, adjustment_amount_with_vat,
                energy_volume, price_per_kwh, vat_amount, resource_code, facility_name,
                pdf_path, file_hash, file_size,
                original_energy, original_amount, corrected_energy, corrected_amount
            ))
            adjustment_id = cursor.lastrowid
            if adjustment_id is None:
                raise DatabaseError("Failed to get ID of saved adjustment")
            logger.info(f"Act adjustment saved with ID: {adjustment_id}, amount: {adjustment_amount}, version: {version}")
            return adjustment_id

    def get_all_act_adjustments(self) -> List[Tuple]:
        """
        Get all act adjustments from database with all fields.

        Returns:
            List of tuples (id, company, counterparty, period, adjustment_amount, description,
                          version, adjustment_date, contract_number, adjustment_amount_with_vat,
                          energy_volume, price_per_kwh, vat_amount, resource_code, facility_name, pdf_path,
                          original_energy, original_amount, corrected_energy, corrected_amount)
            Sorted by created_at DESC

        Raises:
            DatabaseError: If database operation fails
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, company, counterparty, period, adjustment_amount, description,
                       version, adjustment_date, contract_number, adjustment_amount_with_vat,
                       energy_volume, price_per_kwh, vat_amount, resource_code, facility_name, pdf_path,
                       original_energy, original_amount, corrected_energy, corrected_amount
                FROM act_adjustments
                ORDER BY created_at DESC, id DESC
            ''')
            adjustments = cursor.fetchall()
            logger.info(f"Retrieved {len(adjustments)} act adjustments from database")
            return adjustments

    def delete_act_adjustment(self, adjustment_id: int) -> int:
        """
        Delete a specific act adjustment from the database.

        Args:
            adjustment_id: ID of the adjustment to delete

        Returns:
            Number of adjustments deleted

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM act_adjustments WHERE id = ?', (adjustment_id,))
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} act adjustment(s) with ID: {adjustment_id}")
                return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Failed to delete act adjustment: {e}")
            raise DatabaseError(f"Failed to delete act adjustment: {e}") from e

    def update_act_adjustment(
        self,
        adjustment_id: int,
        company: str,
        counterparty: str,
        period: str,
        adjustment_amount: float,
        description: Optional[str] = None,
        adjustment_amount_with_vat: Optional[float] = None,
        energy_volume: Optional[float] = None
    ) -> int:
        """
        Update a specific act adjustment in the database.

        Args:
            adjustment_id: ID of the adjustment to update
            company: New company name (will be normalized)
            counterparty: New counterparty name (will be normalized)
            period: New period
            adjustment_amount: New adjustment amount (without VAT)
            description: New description
            adjustment_amount_with_vat: Adjustment amount with VAT (optional)
            energy_volume: Energy volume in kWh (optional)

        Returns:
            Number of adjustments updated

        Raises:
            ValueError: If data validation fails
            DatabaseError: If database operation fails
        """
        # Validate inputs
        DataValidator.validate_string(company, "company")
        DataValidator.validate_string(counterparty, "counterparty")

        if adjustment_amount is None or not isinstance(adjustment_amount, (int, float)):
            raise ValueError(f"adjustment_amount must be numeric, got {type(adjustment_amount)}")

        # Normalize
        company = DataNormalizer.normalize_company(company)
        counterparty = DataNormalizer.normalize_counterparty(counterparty)
        period = DataNormalizer.normalize_period(period)

        # Validate period after normalization
        DataValidator.validate_period(period)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE act_adjustments
                    SET company = ?, counterparty = ?, period = ?, adjustment_amount = ?,
                        description = ?, adjustment_amount_with_vat = ?, energy_volume = ?
                    WHERE id = ?
                ''', (company, counterparty, period, adjustment_amount, description,
                     adjustment_amount_with_vat, energy_volume, adjustment_id))
                updated_count = cursor.rowcount
                logger.info(f"Updated {updated_count} act adjustment(s)")
                return updated_count
        except sqlite3.Error as e:
            logger.error(f"Failed to update act adjustment: {e}")
            raise DatabaseError(f"Failed to update act adjustment: {e}") from e

    def get_all_acts(self) -> List[Tuple[int, str, str, str, float, Optional[float], Optional[str]]]:
        """
        Get all acts from database.

        Returns:
            List of tuples (id, company, counterparty, period, amount, energy_volume, pdf_path)

        Raises:
            DatabaseError: If database operation fails
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, company, counterparty, period, amount, energy_volume, pdf_path
                FROM acts
                ORDER BY created_at DESC, id DESC
            ''')
            acts = cursor.fetchall()
            logger.info(f"Retrieved {len(acts)} acts from database")
            return acts
    
    def get_all_payments(self) -> List[Tuple[int, str, str, str, float, Optional[str], Optional[str]]]:
        """
        Get all payments from database.

        Returns:
            List of tuples (id, company, counterparty, period, amount, payment_date, purpose)

        Raises:
            DatabaseError: If database operation fails
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, company, counterparty, period, amount, payment_date, purpose
                FROM payments
                ORDER BY created_at DESC, id DESC
            ''')
            payments = cursor.fetchall()
            logger.info(f"Retrieved {len(payments)} payments from database")
            return payments
    
    # Whitelists for safe dynamic SQL in _get_aggregated_data
    _ALLOWED_TABLES = frozenset({'acts', 'act_adjustments', 'payments'})
    _ALLOWED_COLUMNS = frozenset({
        'period', 'company', 'counterparty', 'amount', 'adjustment_amount',
        'SUBSTR(period, -4)',
    })

    def _get_aggregated_data(
        self, table_name: str, group_by_sql: str, amount_column: str = "amount"
    ) -> dict:
        """
        Get aggregated data from database with custom GROUP BY.

        Args:
            table_name: Name of table (must be in _ALLOWED_TABLES)
            group_by_sql: SQL for SELECT and GROUP BY (e.g., "period, company, counterparty")
            amount_column: Name of the amount column to sum (must be in _ALLOWED_COLUMNS)

        Returns:
            Dictionary with tuple keys and sum values

        Raises:
            ValueError: If table_name, amount_column, or group_by columns are not whitelisted
        """
        # Validate table name against whitelist
        if table_name not in self._ALLOWED_TABLES:
            raise ValueError(f"Table '{table_name}' is not allowed. Allowed: {self._ALLOWED_TABLES}")

        # Validate amount column against whitelist
        if amount_column not in self._ALLOWED_COLUMNS:
            raise ValueError(f"Column '{amount_column}' is not allowed. Allowed: {self._ALLOWED_COLUMNS}")

        # Validate each group_by column against whitelist
        group_by_parts = [part.strip() for part in group_by_sql.split(',')]
        for part in group_by_parts:
            if part not in self._ALLOWED_COLUMNS:
                raise ValueError(f"Column '{part}' is not allowed. Allowed: {self._ALLOWED_COLUMNS}")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f'''
                SELECT {group_by_sql}, SUM({amount_column}) as total_amount
                FROM {table_name}
                GROUP BY {group_by_sql}
            ''')
            return {tuple(row[:-1]): row[-1] for row in cursor.fetchall()}

    @staticmethod
    def _parse_period_for_sort(period: str) -> Tuple[str, str]:
        """
        Parse period string for sorting (MM-YYYY → (year, month)).

        Args:
            period: Period string in MM-YYYY format

        Returns:
            Tuple of (year, month) for sorting
        """
        parts = period.split('-')
        if len(parts) == 2:
            month, year = parts
            return (year, month)
        return (period, '')

    def get_summary_by_period(self) -> List[Tuple[str, str, str, float, float]]:
        """
        Get aggregated summary data by period, company, and counterparty.

        Uses SQL aggregation to efficiently compute sums without loading all records.
        This method performs a FULL OUTER JOIN between acts, adjustments and payments
        to include all combinations, even if one side has no data.

        Act adjustments are added to act amounts to get the final act total.

        Returns:
            List of tuples (period, company, counterparty, total_act_amount, total_payment_amount)
            Sorted by period (year DESC, month DESC), then company, then counterparty

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # Get aggregated data from all tables
            acts_data = self._get_aggregated_data(
                'acts', 'period, company, counterparty', 'amount'
            )
            adjustments_data = self._get_aggregated_data(
                'act_adjustments', 'period, company, counterparty', 'adjustment_amount'
            )
            payments_data = self._get_aggregated_data(
                'payments', 'period, company, counterparty', 'amount'
            )

            # Combine data (full outer join logic)
            all_keys = set(acts_data.keys()) | set(adjustments_data.keys()) | set(payments_data.keys())

            result = []
            for key in all_keys:
                period, company, counterparty = key
                act_amount = acts_data.get(key, 0.0)
                adjustment_amount = adjustments_data.get(key, 0.0)
                payment_amount = payments_data.get(key, 0.0)
                # Add adjustments to act amount for final total
                total_act_amount = act_amount + adjustment_amount
                result.append((period, company, counterparty, total_act_amount, payment_amount))

            # Sort by period (year DESC, month DESC), then company, counterparty
            result.sort(
                key=lambda row: self._parse_period_for_sort(row[0]) + (row[1], row[2]),
                reverse=True
            )

            logger.info(f"Retrieved {len(result)} summary records by period (including adjustments)")
            return result

        except sqlite3.Error as e:
            logger.error(f"Failed to get summary by period: {e}")
            raise DatabaseError(f"Failed to retrieve summary data: {e}") from e
    
    def get_summary_by_company(self) -> List[Tuple[str, str, float, float]]:
        """
        Get aggregated summary data by company and year.

        Uses SQL aggregation to efficiently compute sums grouped by company and year.
        Extracts year from period field and aggregates across all counterparties.
        Act adjustments are added to act amounts to get the final act total.

        Returns:
            List of tuples (company, year, total_act_amount, total_payment_amount)
            Sorted by year DESC, then company

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            # Get aggregated data from all tables (extract year from period)
            # Note: no alias in group_by_sql - SQLite does not allow aliases in GROUP BY
            acts_data = self._get_aggregated_data(
                'acts', 'company, SUBSTR(period, -4)', 'amount'
            )
            adjustments_data = self._get_aggregated_data(
                'act_adjustments', 'company, SUBSTR(period, -4)', 'adjustment_amount'
            )
            payments_data = self._get_aggregated_data(
                'payments', 'company, SUBSTR(period, -4)', 'amount'
            )

            # Combine data (full outer join logic)
            all_keys = set(acts_data.keys()) | set(adjustments_data.keys()) | set(payments_data.keys())

            result = []
            for key in all_keys:
                company, year = key
                act_amount = acts_data.get(key, 0.0)
                adjustment_amount = adjustments_data.get(key, 0.0)
                payment_amount = payments_data.get(key, 0.0)
                # Add adjustments to act amount for final total
                total_act_amount = act_amount + adjustment_amount
                result.append((company, year, total_act_amount, payment_amount))

            # Sort by year DESC, then company
            result.sort(key=lambda x: (x[1], x[0]), reverse=True)

            logger.info(f"Retrieved {len(result)} summary records by company (including adjustments)")
            return result

        except sqlite3.Error as e:
            logger.error(f"Failed to get summary by company: {e}")
            raise DatabaseError(f"Failed to retrieve summary data: {e}") from e
    
    def get_payments_monthly_summary(self) -> List[Tuple[str, str, str, int, float]]:
        """
        Get monthly payment summary grouped by company, counterparty, and period.
        
        Returns aggregated payment data showing total amounts and payment counts
        for each company-counterparty-period combination.
        
        Returns:
            List of tuples (company, counterparty, period, payment_count, total_amount)
            Sorted by period, company, counterparty
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT 
                        company,
                        counterparty,
                        period,
                        COUNT(*) as payment_count,
                        SUM(amount) as total_amount
                    FROM payments
                    GROUP BY company, counterparty, period
                    ORDER BY period, company, counterparty
                ''')
                results = cursor.fetchall()
                logger.info(f"Retrieved {len(results)} monthly payment summary records")
                return results
                
        except sqlite3.Error as e:
            logger.error(f"Failed to get monthly payment summary: {e}")
            raise DatabaseError(f"Failed to retrieve monthly payment summary: {e}") from e

    def get_period_details(
        self,
        period: str,
        company: str,
        counterparty: str
    ) -> Dict[str, Any]:
        """
        Get detailed information for a specific period, company, and counterparty.

        Returns acts, adjustments, payments, and totals for the given combination.

        Args:
            period: Period in format MM-YYYY
            company: Company name
            counterparty: Counterparty name

        Returns:
            Dictionary with keys:
                - acts: List of tuples (created_at, amount, id, pdf_path)
                - adjustments: List of tuples (adjustment_date, adjustment_amount, id, pdf_path)
                - payments: List of tuples (payment_date, amount, id)
                - total_act_amount: Sum of all acts
                - total_adjustment_amount: Sum of all adjustments
                - total_payment_amount: Sum of all payments
                - final_act_amount: Total act amount including adjustments

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Get acts
                cursor.execute('''
                    SELECT created_at, amount, id, pdf_path
                    FROM acts
                    WHERE period = ? AND company = ? AND counterparty = ?
                    ORDER BY created_at
                ''', (period, company, counterparty))
                acts = cursor.fetchall()
                total_act_amount = sum(row[1] for row in acts)

                # Get adjustments
                cursor.execute('''
                    SELECT adjustment_date, adjustment_amount, id, pdf_path
                    FROM act_adjustments
                    WHERE period = ? AND company = ? AND counterparty = ?
                    ORDER BY adjustment_date
                ''', (period, company, counterparty))
                adjustments = cursor.fetchall()
                total_adjustment_amount = sum(row[1] for row in adjustments)

                # Get payments
                cursor.execute('''
                    SELECT payment_date, amount, id
                    FROM payments
                    WHERE period = ? AND company = ? AND counterparty = ?
                    ORDER BY payment_date
                ''', (period, company, counterparty))
                payments = cursor.fetchall()
                total_payment_amount = sum(row[1] for row in payments)

            # Calculate final amount
            final_act_amount = total_act_amount + total_adjustment_amount

            logger.info(
                f"Retrieved period details for {period}/{company}/{counterparty}: "
                f"{len(acts)} acts, {len(adjustments)} adjustments, {len(payments)} payments"
            )

            return {
                'acts': acts,
                'adjustments': adjustments,
                'payments': payments,
                'total_act_amount': total_act_amount,
                'total_adjustment_amount': total_adjustment_amount,
                'total_payment_amount': total_payment_amount,
                'final_act_amount': final_act_amount,
            }

        except sqlite3.Error as e:
            logger.error(f"Failed to get period details: {e}")
            raise DatabaseError(f"Failed to retrieve period details: {e}") from e

    def delete_act(self, act_id: int) -> int:
        """
        Delete a specific act from the database by ID.

        Args:
            act_id: ID of the act to delete

        Returns:
            Number of acts deleted (0 or 1)

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM acts WHERE id = ?', (act_id,))
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} act(s) with ID: {act_id}")
                return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Failed to delete act: {e}")
            raise DatabaseError(f"Failed to delete act: {e}") from e
    
    def delete_payment(self, payment_id: int) -> int:
        """
        Delete a specific payment from the database by ID.

        Args:
            payment_id: ID of the payment to delete

        Returns:
            Number of payments deleted (0 or 1)

        Raises:
            DatabaseError: If database operation fails
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM payments WHERE id = ?', (payment_id,))
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} payment(s) with ID: {payment_id}")
                return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Failed to delete payment: {e}")
            raise DatabaseError(f"Failed to delete payment: {e}") from e
    
    def update_act(
        self,
        act_id: int,
        new_company: str,
        new_counterparty: str,
        new_period: str,
        new_amount: float,
        energy_volume: Optional[float] = None,
        cost_without_vat: Optional[float] = None,
        price_without_vat: Optional[float] = None,
    ) -> int:
        """
        Update a specific act in the database by ID.

        Args:
            act_id: ID of the act to update
            new_company: New company name (will be normalized)
            new_counterparty: New counterparty name (will be normalized)
            new_period: New period
            new_amount: New amount
            energy_volume: Optional energy volume in kWh
            cost_without_vat: Optional cost without VAT
            price_without_vat: Optional price per unit without VAT

        Returns:
            Number of acts updated (0 or 1)

        Raises:
            ValueError: If data validation fails
            DatabaseError: If database operation fails
        """
        # Validate new inputs
        DataValidator.validate_string(new_company, "company")
        DataValidator.validate_string(new_counterparty, "counterparty")
        DataValidator.validate_amount(new_amount, "amount")

        if energy_volume is not None:
            DataValidator.validate_energy_volume(energy_volume, "energy_volume")

        if cost_without_vat is not None:
            DataValidator.validate_amount(cost_without_vat, "cost_without_vat")

        if price_without_vat is not None:
            DataValidator.validate_amount(price_without_vat, "price_without_vat")

        # Normalize new values
        new_company = DataNormalizer.normalize_company(new_company)
        new_counterparty = DataNormalizer.normalize_counterparty(new_counterparty)
        new_period = DataNormalizer.normalize_period(new_period)

        # Validate period after normalization
        DataValidator.validate_period(new_period)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE acts
                    SET company = ?, counterparty = ?, period = ?, amount = ?,
                        energy_volume = ?, cost_without_vat = ?, price_without_vat = ?
                    WHERE id = ?
                ''', (new_company, new_counterparty, new_period, new_amount, energy_volume,
                     cost_without_vat, price_without_vat, act_id))
                updated_count = cursor.rowcount
                logger.info(f"Updated {updated_count} act(s) with ID: {act_id}")
                return updated_count
        except sqlite3.Error as e:
            logger.error(f"Failed to update act: {e}")
            raise DatabaseError(f"Failed to update act: {e}") from e
    
    def update_payment(
        self,
        payment_id: int,
        new_company: str,
        new_counterparty: str,
        new_period: str,
        new_amount: float,
        payment_date: Optional[str] = None,
        purpose: Optional[str] = None
    ) -> int:
        """
        Update a specific payment in the database by ID.

        Args:
            payment_id: ID of the payment to update
            new_company: New company name (will be normalized)
            new_counterparty: New counterparty name (will be normalized)
            new_period: New period
            new_amount: New amount
            payment_date: Optional payment date in YYYY-MM-DD format
            purpose: Optional payment purpose description

        Returns:
            Number of payments updated (0 or 1)

        Raises:
            ValueError: If data validation fails
            DatabaseError: If database operation fails
        """
        # Validate new inputs
        DataValidator.validate_string(new_company, "company")
        DataValidator.validate_string(new_counterparty, "counterparty")
        DataValidator.validate_amount(new_amount, "amount")

        # Normalize new values
        new_company = DataNormalizer.normalize_company(new_company)
        new_counterparty = DataNormalizer.normalize_counterparty(new_counterparty)
        new_period = DataNormalizer.normalize_period(new_period)

        # Validate period after normalization
        DataValidator.validate_period(new_period)

        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE payments
                    SET company = ?, counterparty = ?, period = ?, amount = ?,
                        payment_date = ?, purpose = ?
                    WHERE id = ?
                ''', (new_company, new_counterparty, new_period, new_amount, payment_date, purpose,
                     payment_id))
                updated_count = cursor.rowcount
                logger.info(f"Updated {updated_count} payment(s) with ID: {payment_id}")
                return updated_count
        except sqlite3.Error as e:
            logger.error(f"Failed to update payment: {e}")
            raise DatabaseError(f"Failed to update payment: {e}") from e
    
    def clear_database(self) -> None:
        """
        Clear all data from acts, act adjustments, and payments databases.

        Warning: This operation cannot be undone!

        Raises:
            DatabaseError: If database operation fails
        """
        logger.warning("Clearing all database data")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM acts')
            acts_deleted = cursor.rowcount
            cursor.execute('DELETE FROM act_adjustments')
            adjustments_deleted = cursor.rowcount
            cursor.execute('DELETE FROM payments')
            payments_deleted = cursor.rowcount
            logger.info(f"Deleted {acts_deleted} acts, {adjustments_deleted} adjustments, {payments_deleted} payments")

        logger.info("Database cleared successfully")

    def get_unique_companies(self) -> List[str]:
        """
        Отримати список унікальних компаній з бази даних актів.

        Returns:
            Відсортований список унікальних назв компаній

        Raises:
            DatabaseError: Якщо операція не вдалася
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT company FROM acts ORDER BY company')
            return [row[0] for row in cursor.fetchall()]

    def get_unique_counterparties(self) -> List[str]:
        """
        Отримати список унікальних контрагентів з бази даних актів.

        Returns:
            Відсортований список унікальних назв контрагентів

        Raises:
            DatabaseError: Якщо операція не вдалася
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT counterparty FROM acts ORDER BY counterparty')
            return [row[0] for row in cursor.fetchall()]