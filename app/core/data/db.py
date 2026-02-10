"""
Database manager module with context managers and transaction support.
"""
# Standard library imports
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, List, Optional, Tuple

# Local imports
from app.config.config import settings
from app.core.errors.exceptions import DatabaseError
from app.core.normalization import DataNormalizer
from app.core.validation.validators import DataValidator

logger = logging.getLogger("deb.db")


class DatabaseManager:
    """
    Database manager with context managers and transaction support.
    
    Provides safe database operations with automatic connection management,
    transaction handling, and proper error recovery.
    """
    
    def __init__(self) -> None:
        """Initialize database manager and create database files."""
        self.acts_db_path = Path(settings.data_dir) / settings.acts_db_name
        self.payments_db_path = Path(settings.data_dir) / settings.payments_db_name
        self.adjustments_db_path = Path(settings.data_dir) / "act_adjustments.db"
        self._ensure_data_dir()
        self._init_databases()
    
    def _ensure_data_dir(self) -> None:
        """Create data directory if it doesn't exist."""
        data_dir = Path(settings.data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
    
    @contextmanager
    def _get_connection(self, db_path: Path, db_name: str) -> Iterator[sqlite3.Connection]:
        """
        Context manager for database connection.

        Args:
            db_path: Path to the database file
            db_name: Human-readable name for log messages

        Yields:
            Connection to the specified database

        Raises:
            DatabaseError: If connection or transaction fails
        """
        conn = None
        try:
            conn = sqlite3.connect(str(db_path))
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            if conn:
                conn.rollback()
            logger.error(f"{db_name} database error: {e}")
            raise DatabaseError(f"{db_name} database operation failed: {e}") from e
        finally:
            if conn:
                conn.close()

    @contextmanager
    def _get_acts_connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for acts database connection."""
        with self._get_connection(self.acts_db_path, "Acts") as conn:
            yield conn

    @contextmanager
    def _get_payments_connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for payments database connection."""
        with self._get_connection(self.payments_db_path, "Payments") as conn:
            yield conn

    @contextmanager
    def _get_adjustments_connection(self) -> Iterator[sqlite3.Connection]:
        """Context manager for act adjustments database connection."""
        with self._get_connection(self.adjustments_db_path, "ActAdjustments") as conn:
            yield conn
    
    def _init_databases(self) -> None:
        """Initialize database schemas and indexes."""
        # Initialize acts database
        with self._get_acts_connection() as conn:
            cursor = conn.cursor()
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Check if pdf_path column exists (for existing databases)
            cursor.execute("PRAGMA table_info(acts)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'pdf_path' not in columns:
                # Add pdf_path column if it doesn't exist (migration for existing databases)
                logger.info("Adding pdf_path column to existing acts table")
                cursor.execute("ALTER TABLE acts ADD COLUMN pdf_path TEXT")

            if 'price_without_vat' not in columns:
                # Add price_without_vat column if it doesn't exist (migration for existing databases)
                logger.info("Adding price_without_vat column to existing acts table")
                cursor.execute("ALTER TABLE acts ADD COLUMN price_without_vat REAL")
            
            # Create indexes for common query patterns
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_acts_period ON acts(period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_acts_company ON acts(company)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_acts_company_period ON acts(company, period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_acts_counterparty ON acts(counterparty)')
            
            logger.info("Acts database and indexes initialized")
        
        # Initialize payments database
        with self._get_payments_connection() as conn:
            cursor = conn.cursor()
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
            # Remove unique index if exists to allow multiple payments per period
            cursor.execute('DROP INDEX IF EXISTS unique_payment')
            
            # Check if payment_date column exists (for existing databases)
            cursor.execute("PRAGMA table_info(payments)")
            columns = [row[1] for row in cursor.fetchall()]
            
            if 'payment_date' not in columns:
                # Add payment_date column if it doesn't exist (migration for existing databases)
                logger.info("Adding payment_date column to existing payments table")
                cursor.execute("ALTER TABLE payments ADD COLUMN payment_date TEXT")

            if 'purpose' not in columns:
                # Add purpose column if it doesn't exist (migration for existing databases)
                logger.info("Adding purpose column to existing payments table")
                cursor.execute("ALTER TABLE payments ADD COLUMN purpose TEXT")
            
            # Create indexes for common query patterns
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_period ON payments(period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_company ON payments(company)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_company_period ON payments(company, period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_counterparty ON payments(counterparty)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_payments_payment_date ON payments(payment_date)')

            logger.info("Payments database and indexes initialized")

        # Initialize act adjustments database
        with self._get_adjustments_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS act_adjustments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    company TEXT NOT NULL,
                    counterparty TEXT NOT NULL,
                    period TEXT NOT NULL,
                    adjustment_amount REAL NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create indexes for common query patterns
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_period ON act_adjustments(period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_company ON act_adjustments(company)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_company_period ON act_adjustments(company, period)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_adjustments_counterparty ON act_adjustments(counterparty)')

            logger.info("Act adjustments database and indexes initialized")

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
        
        with self._get_acts_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO acts (company, counterparty, period, amount, energy_volume, cost_without_vat, price_without_vat, pdf_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (company, counterparty, period, amount, energy_volume, cost_without_vat, price_without_vat, pdf_path))
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
        
        with self._get_payments_connection() as conn:
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
                        payment_date
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

        # Determine connection method
        conn_method = self._get_payments_connection if is_payment else self._get_acts_connection

        # Perform bulk insert in single transaction
        with conn_method() as conn:
            cursor = conn.cursor()
            if is_payment:
                cursor.executemany('''
                    INSERT INTO payments (company, counterparty, period, amount, payment_date)
                    VALUES (?, ?, ?, ?, ?)
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
        payments: List[Tuple[str, str, str, float, Optional[str]]]
    ) -> int:
        """
        Save multiple payments to database in a single transaction using bulk insert.

        This is significantly faster than saving payments one by one for large datasets.
        All payments are validated and normalized before insertion. If any payment fails
        validation, the entire batch is rolled back.

        Args:
            payments: List of tuples (company, counterparty, period, amount, payment_date).
                      payment_date is optional (can be None) in YYYY-MM-DD format.

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
        
        with self._get_acts_connection() as conn:
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

    def save_act_adjustment(
        self,
        company: str,
        counterparty: str,
        period: str,
        adjustment_amount: float,
        description: Optional[str] = None
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

        with self._get_adjustments_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO act_adjustments (company, counterparty, period, adjustment_amount, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (company, counterparty, period, adjustment_amount, description))
            adjustment_id = cursor.lastrowid
            if adjustment_id is None:
                raise DatabaseError("Failed to get ID of saved adjustment")
            logger.info(f"Act adjustment saved with ID: {adjustment_id}, amount: {adjustment_amount}")
            return adjustment_id

    def get_all_act_adjustments(self) -> List[Tuple[int, str, str, str, float, Optional[str]]]:
        """
        Get all act adjustments from database.

        Returns:
            List of tuples (id, company, counterparty, period, adjustment_amount, description)
            Sorted by created_at DESC

        Raises:
            DatabaseError: If database operation fails
        """
        with self._get_adjustments_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, company, counterparty, period, adjustment_amount, description
                FROM act_adjustments
                ORDER BY created_at DESC
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
            with self._get_adjustments_connection() as conn:
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
        description: Optional[str] = None
    ) -> int:
        """
        Update a specific act adjustment in the database.

        Args:
            adjustment_id: ID of the adjustment to update
            company: New company name (will be normalized)
            counterparty: New counterparty name (will be normalized)
            period: New period
            adjustment_amount: New adjustment amount
            description: New description

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
            with self._get_adjustments_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE act_adjustments
                    SET company = ?, counterparty = ?, period = ?, adjustment_amount = ?, description = ?
                    WHERE id = ?
                ''', (company, counterparty, period, adjustment_amount, description, adjustment_id))
                updated_count = cursor.rowcount
                logger.info(f"Updated {updated_count} act adjustment(s)")
                return updated_count
        except sqlite3.Error as e:
            logger.error(f"Failed to update act adjustment: {e}")
            raise DatabaseError(f"Failed to update act adjustment: {e}") from e

    def get_all_acts(self) -> List[Tuple[str, str, str, float, Optional[float], Optional[str]]]:
        """
        Get all acts from database.
        
        Returns:
            List of tuples (company, counterparty, period, amount, energy_volume, pdf_path)
            
        Raises:
            DatabaseError: If database operation fails
        """
        with self._get_acts_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT company, counterparty, period, amount, energy_volume, pdf_path 
                FROM acts
                ORDER BY created_at DESC
            ''')
            acts = cursor.fetchall()
            logger.info(f"Retrieved {len(acts)} acts from database")
            return acts
    
    def get_all_payments(self) -> List[Tuple[str, str, str, float]]:
        """
        Get all payments from database.
        
        Returns:
            List of tuples (company, counterparty, period, amount)
            
        Raises:
            DatabaseError: If database operation fails
        """
        with self._get_payments_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT company, counterparty, period, amount 
                FROM payments
                ORDER BY created_at DESC
            ''')
            payments = cursor.fetchall()
            logger.info(f"Retrieved {len(payments)} payments from database")
            return payments
    
    def _get_aggregated_data(
        self, db_path: Path, table_name: str, group_by_sql: str, amount_column: str = "amount"
    ) -> dict:
        """
        Get aggregated data from database with custom GROUP BY.

        Args:
            db_path: Path to database file
            table_name: Name of table
            group_by_sql: SQL for SELECT and GROUP BY (e.g., "period, company, counterparty")
            amount_column: Name of the amount column to sum (default: "amount")

        Returns:
            Dictionary with tuple keys and sum values
        """
        with self._get_connection(db_path, table_name) as conn:
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
            # Get aggregated data from all databases
            acts_data = self._get_aggregated_data(
                self.acts_db_path, 'acts', 'period, company, counterparty', 'amount'
            )
            adjustments_data = self._get_aggregated_data(
                self.adjustments_db_path, 'act_adjustments', 'period, company, counterparty', 'adjustment_amount'
            )
            payments_data = self._get_aggregated_data(
                self.payments_db_path, 'payments', 'period, company, counterparty', 'amount'
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
            # Get aggregated data from all databases (extract year from period)
            # Note: no alias in group_by_sql - SQLite does not allow aliases in GROUP BY
            acts_data = self._get_aggregated_data(
                self.acts_db_path, 'acts', 'company, SUBSTR(period, -4)', 'amount'
            )
            adjustments_data = self._get_aggregated_data(
                self.adjustments_db_path, 'act_adjustments', 'company, SUBSTR(period, -4)', 'adjustment_amount'
            )
            payments_data = self._get_aggregated_data(
                self.payments_db_path, 'payments', 'company, SUBSTR(period, -4)', 'amount'
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
            with self._get_payments_connection() as conn:
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
    
    def delete_act(
        self,
        company: str,
        counterparty: str,
        period: str,
        amount: float
    ) -> int:
        """
        Delete a specific act from the database.
        
        Args:
            company: Company name
            counterparty: Counterparty name
            period: Period in format MM-YYYY
            amount: Act amount
            
        Returns:
            Number of acts deleted
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            with self._get_acts_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM acts 
                    WHERE company = ? AND counterparty = ? AND period = ? AND amount = ?
                ''', (company, counterparty, period, amount))
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} act(s): {company} - {counterparty} - {period}")
                return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Failed to delete act: {e}")
            raise DatabaseError(f"Failed to delete act: {e}") from e
    
    def delete_payment(
        self,
        company: str,
        counterparty: str,
        period: str,
        amount: float
    ) -> int:
        """
        Delete a specific payment from the database.
        
        Args:
            company: Company name
            counterparty: Counterparty name
            period: Period in format MM-YYYY
            amount: Payment amount
            
        Returns:
            Number of payments deleted
            
        Raises:
            DatabaseError: If database operation fails
        """
        try:
            with self._get_payments_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    DELETE FROM payments 
                    WHERE company = ? AND counterparty = ? AND period = ? AND amount = ?
                ''', (company, counterparty, period, amount))
                deleted_count = cursor.rowcount
                logger.info(f"Deleted {deleted_count} payment(s): {company} - {counterparty} - {period}")
                return deleted_count
        except sqlite3.Error as e:
            logger.error(f"Failed to delete payment: {e}")
            raise DatabaseError(f"Failed to delete payment: {e}") from e
    
    def update_act(
        self,
        old_company: str,
        old_counterparty: str,
        old_period: str,
        old_amount: float,
        new_company: str,
        new_counterparty: str,
        new_period: str,
        new_amount: float,
        energy_volume: Optional[float] = None,
        cost_without_vat: Optional[float] = None,
        price_without_vat: Optional[float] = None,
    ) -> int:
        """
        Update a specific act in the database.

        Args:
            old_company: Current company name
            old_counterparty: Current counterparty name
            old_period: Current period
            old_amount: Current amount
            new_company: New company name (will be normalized)
            new_counterparty: New counterparty name (will be normalized)
            new_period: New period
            new_amount: New amount
            energy_volume: Optional energy volume in kWh
            cost_without_vat: Optional cost without VAT
            price_without_vat: Optional price per unit without VAT

        Returns:
            Number of acts updated

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
            with self._get_acts_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE acts
                    SET company = ?, counterparty = ?, period = ?, amount = ?,
                        energy_volume = ?, cost_without_vat = ?, price_without_vat = ?
                    WHERE company = ? AND counterparty = ? AND period = ? AND amount = ?
                ''', (new_company, new_counterparty, new_period, new_amount, energy_volume,
                     cost_without_vat, price_without_vat,
                     old_company, old_counterparty, old_period, old_amount))
                updated_count = cursor.rowcount
                logger.info(f"Updated {updated_count} act(s)")
                return updated_count
        except sqlite3.Error as e:
            logger.error(f"Failed to update act: {e}")
            raise DatabaseError(f"Failed to update act: {e}") from e
    
    def update_payment(
        self,
        old_company: str,
        old_counterparty: str,
        old_period: str,
        old_amount: float,
        new_company: str,
        new_counterparty: str,
        new_period: str,
        new_amount: float,
        payment_date: Optional[str] = None,
        purpose: Optional[str] = None
    ) -> int:
        """
        Update a specific payment in the database.

        Args:
            old_company: Current company name
            old_counterparty: Current counterparty name
            old_period: Current period
            old_amount: Current amount
            new_company: New company name (will be normalized)
            new_counterparty: New counterparty name (will be normalized)
            new_period: New period
            new_amount: New amount
            payment_date: Optional payment date in YYYY-MM-DD format
            purpose: Optional payment purpose description

        Returns:
            Number of payments updated

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
            with self._get_payments_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    UPDATE payments
                    SET company = ?, counterparty = ?, period = ?, amount = ?,
                        payment_date = ?, purpose = ?
                    WHERE company = ? AND counterparty = ? AND period = ? AND amount = ?
                ''', (new_company, new_counterparty, new_period, new_amount, payment_date, purpose,
                     old_company, old_counterparty, old_period, old_amount))
                updated_count = cursor.rowcount
                logger.info(f"Updated {updated_count} payment(s)")
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

        with self._get_acts_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM acts')
            acts_deleted = cursor.rowcount
            logger.info(f"Deleted {acts_deleted} acts")

        with self._get_adjustments_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM act_adjustments')
            adjustments_deleted = cursor.rowcount
            logger.info(f"Deleted {adjustments_deleted} act adjustments")

        with self._get_payments_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM payments')
            payments_deleted = cursor.rowcount
            logger.info(f"Deleted {payments_deleted} payments")

        logger.info("Database cleared successfully")

    def get_unique_companies(self) -> List[str]:
        """
        Отримати список унікальних компаній з бази даних актів.

        Returns:
            Відсортований список унікальних назв компаній

        Raises:
            DatabaseError: Якщо операція не вдалася
        """
        with self._get_acts_connection() as conn:
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
        with self._get_acts_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT DISTINCT counterparty FROM acts ORDER BY counterparty')
            return [row[0] for row in cursor.fetchall()]