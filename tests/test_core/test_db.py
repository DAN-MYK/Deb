"""
Comprehensive tests for DatabaseManager module.

Tests cover database operations, validation, normalization,
error handling, and edge cases.
"""
import pytest
import sqlite3
from pathlib import Path
import tempfile
import shutil
from typing import Generator

from app.core.data.db import DatabaseManager, DatabaseError
from app.config.config import settings


@pytest.fixture
def temp_db_dir() -> Generator[str, None, None]:
    """Create temporary directory for test databases."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def db_manager(temp_db_dir: str, monkeypatch: pytest.MonkeyPatch) -> DatabaseManager:
    """Create DatabaseManager with temporary database."""
    monkeypatch.setattr("app.core.data.db.settings.data_dir", temp_db_dir)
    monkeypatch.setattr("app.config.config.settings.data_dir", temp_db_dir)
    manager = DatabaseManager()
    return manager


class TestDatabaseInitialization:
    """Test database initialization and setup."""
    
    def test_database_files_created(self, db_manager: DatabaseManager) -> None:
        """Test that database file is created on initialization."""
        assert db_manager.db_path.exists()
    
    def test_acts_table_schema(self, db_manager: DatabaseManager) -> None:
        """Test that acts table has correct schema."""
        with sqlite3.connect(str(db_manager.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(acts)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert "id" in columns
            assert "company" in columns
            assert "counterparty" in columns
            assert "period" in columns
            assert "amount" in columns
            assert "energy_volume" in columns
            assert "cost_without_vat" in columns
            assert "created_at" in columns
    
    def test_payments_table_schema(self, db_manager: DatabaseManager) -> None:
        """Test that payments table has correct schema."""
        with sqlite3.connect(str(db_manager.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(payments)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}
            
            assert "id" in columns
            assert "company" in columns
            assert "counterparty" in columns
            assert "period" in columns
            assert "amount" in columns
            assert "payment_date" in columns  # NEW: check payment_date column exists
            assert "created_at" in columns
    
    def test_payments_table_payment_date_index(self, db_manager: DatabaseManager) -> None:
        """Test that payment_date index exists."""
        with sqlite3.connect(str(db_manager.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA index_list(payments)")
            indexes = [row[1] for row in cursor.fetchall()]
            
            assert "idx_payments_payment_date" in indexes


class TestSaveAct:
    """Test saving acts to database."""
    
    def test_save_act_valid_data(self, db_manager: DatabaseManager) -> None:
        """Test saving act with valid data."""
        act_id = db_manager.save_act(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=100000.50
        )
        
        assert act_id > 0
        
        # Verify data was saved (id, company, counterparty, period, amount, ...)
        acts = db_manager.get_all_acts()
        assert len(acts) == 1
        assert acts[0][1] == "ПЕРВОМАЙСЬК"
        assert acts[0][2] == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        assert acts[0][3] == "12-2023"
        assert acts[0][4] == 100000.50
    
    def test_save_act_with_energy_fields(self, db_manager: DatabaseManager) -> None:
        """Test saving act with energy volume and cost without VAT."""
        act_id = db_manager.save_act(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=100000.50,
            energy_volume=50000.0,
            cost_without_vat=83333.75
        )
        
        assert act_id > 0
        
        # Verify energy fields were saved
        with sqlite3.connect(str(db_manager.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT energy_volume, cost_without_vat FROM acts WHERE id = ?",
                (act_id,)
            )
            result = cursor.fetchone()
            assert result[0] == 50000.0
            assert result[1] == 83333.75
    
    def test_save_act_negative_amount(self, db_manager: DatabaseManager) -> None:
        """Test that negative amounts are rejected."""
        with pytest.raises(ValueError, match="cannot be negative"):
            db_manager.save_act(
                company="TEST",
                counterparty="TEST",
                period="12-2023",
                amount=-1000.0
            )
    
    def test_save_act_zero_amount(self, db_manager: DatabaseManager) -> None:
        """Test that zero amounts are rejected."""
        with pytest.raises(ValueError, match="cannot be zero"):
            db_manager.save_act(
                company="TEST",
                counterparty="TEST",
                period="12-2023",
                amount=0.0
            )
    
    def test_save_act_none_amount(self, db_manager: DatabaseManager) -> None:
        """Test that None amounts are rejected."""
        with pytest.raises(ValueError, match="cannot be None"):
            db_manager.save_act(
                company="TEST",
                counterparty="TEST",
                period="12-2023",
                amount=None  # type: ignore
            )
    
    def test_save_act_string_amount(self, db_manager: DatabaseManager) -> None:
        """Test that string amounts are rejected."""
        with pytest.raises(ValueError, match="must be numeric"):
            db_manager.save_act(
                company="TEST",
                counterparty="TEST",
                period="12-2023",
                amount="1000"  # type: ignore
            )
    
    def test_save_act_excessive_amount(self, db_manager: DatabaseManager) -> None:
        """Test that amounts exceeding maximum are rejected."""
        with pytest.raises(ValueError, match="exceeds maximum"):
            db_manager.save_act(
                company="TEST",
                counterparty="TEST",
                period="12-2023",
                amount=2_000_000_000  # Exceeds pdf_amount_max
            )
    
    def test_save_act_empty_company(self, db_manager: DatabaseManager) -> None:
        """Test that empty company name is rejected."""
        with pytest.raises(ValueError, match="company cannot be empty"):
            db_manager.save_act(
                company="",
                counterparty="TEST",
                period="12-2023",
                amount=1000.0
            )
    
    def test_save_act_empty_counterparty(self, db_manager: DatabaseManager) -> None:
        """Test that empty counterparty name is rejected."""
        with pytest.raises(ValueError, match="counterparty cannot be empty"):
            db_manager.save_act(
                company="TEST",
                counterparty="",
                period="12-2023",
                amount=1000.0
            )
    
    def test_save_act_empty_period(self, db_manager: DatabaseManager) -> None:
        """Test that empty period is rejected."""
        with pytest.raises(ValueError, match="period cannot be empty"):
            db_manager.save_act(
                company="TEST",
                counterparty="TEST",
                period="",
                amount=1000.0
            )
    
    def test_save_act_whitespace_only_company(self, db_manager: DatabaseManager) -> None:
        """Test that whitespace-only company name is rejected."""
        with pytest.raises(ValueError, match="company cannot be"):
            db_manager.save_act(
                company="   ",
                counterparty="TEST",
                period="12-2023",
                amount=1000.0
            )
    
    def test_save_act_company_normalization(self, db_manager: DatabaseManager) -> None:
        """Test that company names are normalized."""
        act_id = db_manager.save_act(
            company="САН ПАУЕР ПЕРВОМАЙСЬК ТОВ",
            counterparty="TEST",
            period="12-2023",
            amount=1000.0
        )
        
        acts = db_manager.get_all_acts()
        assert acts[0][1] == "ПЕРВОМАЙСЬК"

    def test_save_act_counterparty_normalization(self, db_manager: DatabaseManager) -> None:
        """Test that counterparty names are normalized."""
        act_id = db_manager.save_act(
            company="TEST",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП",
            period="12-2023",
            amount=1000.0
        )

        acts = db_manager.get_all_acts()
        assert acts[0][2] == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"

    def test_save_act_period_normalization(self, db_manager: DatabaseManager) -> None:
        """Test that period format is normalized (dots to dashes)."""
        act_id = db_manager.save_act(
            company="TEST",
            counterparty="TEST",
            period="11.2023",
            amount=1000.0
        )

        acts = db_manager.get_all_acts()
        assert acts[0][3] == "11-2023"
    
    def test_save_act_negative_energy_volume(self, db_manager: DatabaseManager) -> None:
        """Test that negative energy volume is rejected."""
        with pytest.raises(ValueError, match="energy_volume cannot be negative"):
            db_manager.save_act(
                company="TEST",
                counterparty="TEST",
                period="12-2023",
                amount=1000.0,
                energy_volume=-100.0
            )
    
    def test_save_act_zero_energy_volume(self, db_manager: DatabaseManager) -> None:
        """Test that zero energy volume is rejected."""
        with pytest.raises(ValueError, match="energy_volume cannot be zero"):
            db_manager.save_act(
                company="TEST",
                counterparty="TEST",
                period="12-2023",
                amount=1000.0,
                energy_volume=0.0
            )


class TestSavePayment:
    """Test saving payments to database."""
    
    def test_save_payment_valid_data(self, db_manager: DatabaseManager) -> None:
        """Test saving payment with valid data."""
        payment_id = db_manager.save_payment(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=50000.0
        )
        
        assert payment_id > 0
        
        # Verify data was saved (id, company, counterparty, period, amount, ...)
        payments = db_manager.get_all_payments()
        assert len(payments) == 1
        assert payments[0][1] == "ПЕРВОМАЙСЬК"
        assert payments[0][2] == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        assert payments[0][3] == "12-2023"
        assert payments[0][4] == 50000.0
    
    def test_save_payment_with_payment_date(self, db_manager: DatabaseManager) -> None:
        """Test saving payment with payment_date."""
        payment_id = db_manager.save_payment(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=50000.0,
            payment_date="2023-12-15"
        )
        
        assert payment_id > 0
        
        # Verify payment_date was saved
        with sqlite3.connect(str(db_manager.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT payment_date FROM payments WHERE id = ?", (payment_id,))
            result = cursor.fetchone()
            assert result[0] == "2023-12-15"
    
    def test_save_payment_without_payment_date(self, db_manager: DatabaseManager) -> None:
        """Test saving payment without payment_date (backward compatibility)."""
        payment_id = db_manager.save_payment(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=50000.0
        )
        
        assert payment_id > 0
        
        # Verify payment_date is NULL
        with sqlite3.connect(str(db_manager.db_path)) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT payment_date FROM payments WHERE id = ?", (payment_id,))
            result = cursor.fetchone()
            assert result[0] is None
    
    def test_save_payment_invalid_payment_date_format(self, db_manager: DatabaseManager) -> None:
        """Test that invalid payment_date format is rejected."""
        with pytest.raises(ValueError, match="payment_date must be in format YYYY-MM-DD"):
            db_manager.save_payment(
                company="ПЕРВОМАЙСЬК",
                counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
                period="12-2023",
                amount=50000.0,
                payment_date="15-12-2023"  # Wrong format
            )
    
    def test_save_payment_invalid_payment_date_value(self, db_manager: DatabaseManager) -> None:
        """Test that invalid payment_date value is rejected."""
        with pytest.raises(ValueError, match="payment_date is not a valid date"):
            db_manager.save_payment(
                company="ПЕРВОМАЙСЬК",
                counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
                period="12-2023",
                amount=50000.0,
                payment_date="2023-13-45"  # Invalid date
            )
    
    def test_save_payment_multiple_same_period(self, db_manager: DatabaseManager) -> None:
        """Test that multiple payments for the same period are allowed."""
        payment_id1 = db_manager.save_payment(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=50000.0
        )
        
        payment_id2 = db_manager.save_payment(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=30000.0
        )
        
        assert payment_id1 > 0
        assert payment_id2 > 0
        assert payment_id1 != payment_id2
        
        payments = db_manager.get_all_payments()
        assert len(payments) == 2
    
    def test_save_payment_negative_amount(self, db_manager: DatabaseManager) -> None:
        """Test that negative payment amounts are rejected."""
        with pytest.raises(ValueError, match="cannot be negative"):
            db_manager.save_payment(
                company="TEST",
                counterparty="TEST",
                period="12-2023",
                amount=-500.0
            )
    
    def test_save_payment_normalization(self, db_manager: DatabaseManager) -> None:
        """Test that payment data is normalized."""
        payment_id = db_manager.save_payment(
            company="САН ПАУЕР ПЕРВОМАЙСЬК ТОВ",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП",
            period="11.2023",
            amount=1000.0
        )
        
        payments = db_manager.get_all_payments()
        assert payments[0][1] == "ПЕРВОМАЙСЬК"
        assert payments[0][2] == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        assert payments[0][3] == "11-2023"


class TestAdjustActs:
    """Test adjusting acts."""
    
    def test_adjust_acts_update_existing(self, db_manager: DatabaseManager) -> None:
        """Test adjusting existing act increases the amount."""
        # Create initial act
        db_manager.save_act(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=100000.0
        )
        
        # Adjust act
        updated, created = db_manager.adjust_acts(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            adjustment_amount=5000.0
        )
        
        assert updated == 1
        assert created is False
        
        # Verify amount was updated (id, company, counterparty, period, amount, ...)
        acts = db_manager.get_all_acts()
        assert len(acts) == 1
        assert acts[0][4] == 105000.0

    def test_adjust_acts_create_new(self, db_manager: DatabaseManager) -> None:
        """Test adjusting non-existent act creates new one."""
        updated, created = db_manager.adjust_acts(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            adjustment_amount=500.0
        )

        assert updated == 0
        assert created is True

        # Verify new act was created
        acts = db_manager.get_all_acts()
        assert len(acts) == 1
        assert acts[0][4] == 500.0
    
    def test_adjust_acts_negative_adjustment(self, db_manager: DatabaseManager) -> None:
        """Test that negative adjustments are allowed."""
        # Create initial act
        db_manager.save_act(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=100000.0
        )
        
        # Adjust with negative amount
        updated, created = db_manager.adjust_acts(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            adjustment_amount=-10000.0
        )
        
        assert updated == 1
        assert created is False
        
        # Verify amount was decreased
        acts = db_manager.get_all_acts()
        assert acts[0][4] == 90000.0
    
    def test_adjust_acts_multiple_acts_same_period(self, db_manager: DatabaseManager) -> None:
        """Test adjusting multiple acts for the same period."""
        # Create two acts for same period
        db_manager.save_act(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=100000.0
        )
        db_manager.save_act(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=50000.0
        )
        
        # Adjust both acts
        updated, created = db_manager.adjust_acts(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            adjustment_amount=5000.0
        )
        
        assert updated == 2
        assert created is False
        
        # Verify both amounts were updated
        acts = db_manager.get_all_acts()
        assert len(acts) == 2
        amounts = sorted([act[4] for act in acts])
        assert amounts == [55000.0, 105000.0]
    
    def test_adjust_acts_normalization(self, db_manager: DatabaseManager) -> None:
        """Test that adjust_acts normalizes company/counterparty names."""
        db_manager.save_act(
            company="ПЕРВОМАЙСЬК",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            period="12-2023",
            amount=100000.0
        )
        
        # Adjust using unnormalized names
        updated, created = db_manager.adjust_acts(
            company="САН ПАУЕР ПЕРВОМАЙСЬК ТОВ",
            counterparty="ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП",
            period="12.2023",
            adjustment_amount=5000.0
        )
        
        assert updated == 1
        assert created is False


class TestGetAllActs:
    """Test retrieving acts from database."""
    
    def test_get_all_acts_empty_database(self, db_manager: DatabaseManager) -> None:
        """Test getting acts from empty database."""
        acts = db_manager.get_all_acts()
        assert acts == []
    
    def test_get_all_acts_multiple_acts(self, db_manager: DatabaseManager) -> None:
        """Test getting multiple acts."""
        # Create multiple acts
        db_manager.save_act("ПЕРВОМАЙСЬК", "TEST1", "12-2023", 1000.0)
        db_manager.save_act("ФРІ-ЕНЕРДЖИ", "TEST2", "11-2023", 2000.0)
        db_manager.save_act("ПОРТ-СОЛАР", "TEST3", "10-2023", 3000.0)
        
        acts = db_manager.get_all_acts()
        assert len(acts) == 3
        
        # Verify all acts are present
        companies = {act[1] for act in acts}
        assert companies == {"ПЕРВОМАЙСЬК", "ФРІ-ЕНЕРДЖИ", "ПОРТ-СОЛАР"}
    
    def test_get_all_acts_ordered_by_created_at(self, db_manager: DatabaseManager) -> None:
        """Test that acts are ordered by created_at DESC (newest first)."""
        # Create acts in sequence - IDs will be 1, 2, 3
        db_manager.save_act("FIRST", "TEST", "12-2023", 1000.0)
        db_manager.save_act("SECOND", "TEST", "12-2023", 2000.0)
        db_manager.save_act("THIRD", "TEST", "12-2023", 3000.0)

        acts = db_manager.get_all_acts()

        # Highest ID should be first (most recently created)
        assert acts[0][0] > acts[1][0] > acts[2][0]
        assert acts[0][1] == "THIRD"
        assert acts[2][1] == "FIRST"


class TestGetAllPayments:
    """Test retrieving payments from database."""
    
    def test_get_all_payments_empty_database(self, db_manager: DatabaseManager) -> None:
        """Test getting payments from empty database."""
        payments = db_manager.get_all_payments()
        assert payments == []
    
    def test_get_all_payments_multiple_payments(self, db_manager: DatabaseManager) -> None:
        """Test getting multiple payments."""
        db_manager.save_payment("ПЕРВОМАЙСЬК", "TEST1", "12-2023", 1000.0)
        db_manager.save_payment("ФРІ-ЕНЕРДЖИ", "TEST2", "11-2023", 2000.0)
        
        payments = db_manager.get_all_payments()
        assert len(payments) == 2


class TestClearDatabase:
    """Test clearing database."""
    
    def test_clear_database_empty(self, db_manager: DatabaseManager) -> None:
        """Test clearing empty database."""
        db_manager.clear_database()
        
        acts = db_manager.get_all_acts()
        payments = db_manager.get_all_payments()
        
        assert acts == []
        assert payments == []
    
    def test_clear_database_with_data(self, db_manager: DatabaseManager) -> None:
        """Test clearing database with data."""
        # Add data
        db_manager.save_act("TEST", "TEST", "12-2023", 1000.0)
        db_manager.save_act("TEST", "TEST", "11-2023", 2000.0)
        db_manager.save_payment("TEST", "TEST", "12-2023", 500.0)
        
        # Verify data exists
        assert len(db_manager.get_all_acts()) == 2
        assert len(db_manager.get_all_payments()) == 1
        
        # Clear database
        db_manager.clear_database()
        
        # Verify all data is gone
        assert db_manager.get_all_acts() == []
        assert db_manager.get_all_payments() == []
    
    def test_clear_database_can_add_data_after(self, db_manager: DatabaseManager) -> None:
        """Test that data can be added after clearing database."""
        # Add and clear
        db_manager.save_act("TEST", "TEST", "12-2023", 1000.0)
        db_manager.clear_database()
        
        # Add new data
        act_id = db_manager.save_act("NEW", "NEW", "01-2024", 5000.0)
        
        assert act_id > 0
        acts = db_manager.get_all_acts()
        assert len(acts) == 1
        assert acts[0][1] == "NEW"


class TestContextManagers:
    """Test context manager behavior."""
    
    def test_context_manager_commits_on_success(self, db_manager: DatabaseManager) -> None:
        """Test that context manager commits on success."""
        with db_manager._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO acts (company, counterparty, period, amount)
                VALUES (?, ?, ?, ?)
            ''', ("TEST", "TEST", "12-2023", 1000.0))
        
        # Verify data was committed
        acts = db_manager.get_all_acts()
        assert len(acts) == 1
    
    def test_context_manager_rollback_on_error(self, db_manager: DatabaseManager) -> None:
        """Test that context manager rolls back on error."""
        try:
            with db_manager._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO acts (company, counterparty, period, amount)
                    VALUES (?, ?, ?, ?)
                ''', ("TEST", "TEST", "12-2023", 1000.0))
                
                # Force an error
                raise sqlite3.Error("Simulated error")
        except DatabaseError:
            pass
        
        # Verify data was not committed
        acts = db_manager.get_all_acts()
        assert len(acts) == 0


class TestEdgeCases:
    """Test edge cases and boundary conditions."""
    
    def test_save_act_with_large_decimal_amount(self, db_manager: DatabaseManager) -> None:
        """Test saving act with precise decimal amount."""
        act_id = db_manager.save_act(
            company="TEST",
            counterparty="TEST",
            period="12-2023",
            amount=123456.789
        )
        
        acts = db_manager.get_all_acts()
        assert acts[0][4] == pytest.approx(123456.789, rel=1e-6)

    def test_save_act_with_unicode_characters(self, db_manager: DatabaseManager) -> None:
        """Test saving act with unicode characters in names."""
        act_id = db_manager.save_act(
            company="КОМПАНІЯ З ЮНІКОД",
            counterparty="КОНТРАГЕНТ З ЮНІКОД",
            period="12-2023",
            amount=1000.0
        )

        acts = db_manager.get_all_acts()
        assert acts[0][1] == "КОМПАНІЯ З ЮНІКОД"
        assert acts[0][2] == "КОНТРАГЕНТ З ЮНІКОД"
    
    def test_save_act_period_boundary_months(self, db_manager: DatabaseManager) -> None:
        """Test saving acts with boundary month values."""
        # Month 01
        act_id1 = db_manager.save_act("TEST", "TEST", "01-2023", 1000.0)
        assert act_id1 > 0
        
        # Month 12
        act_id2 = db_manager.save_act("TEST", "TEST", "12-2023", 1000.0)
        assert act_id2 > 0
        
        acts = db_manager.get_all_acts()
        assert len(acts) == 2
    
    def test_save_multiple_acts_returns_unique_ids(self, db_manager: DatabaseManager) -> None:
        """Test that multiple acts receive unique IDs."""
        ids = []
        for i in range(5):
            act_id = db_manager.save_act(
                company=f"COMPANY{i}",
                counterparty="TEST",
                period="12-2023",
                amount=1000.0 * (i + 1)
            )
            ids.append(act_id)
        
        # All IDs should be unique
        assert len(set(ids)) == 5
        
        # IDs should be increasing
        assert ids == sorted(ids)
