#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Міграція: додавання поля price_without_vat до таблиці acts.

Це поле зберігає ціну за одиницю електроенергії без ПДВ (грн/кВт·год).
Для існуючих записів, де є cost_without_vat та energy_volume,
поле автоматично обчислюється.

Usage:
    python migrate_add_price_field.py
"""

import logging
import sqlite3
from pathlib import Path

from app.config.logging_config import setup_logging

logger = logging.getLogger(__name__)


def migrate_price_field():
    """
    Додає поле price_without_vat до таблиці acts та обчислює його
    для існуючих записів.
    """
    setup_logging()

    logger.info("=" * 80)
    logger.info("Starting migration: add price_without_vat field")
    logger.info("=" * 80)

    # Database path
    db_path = Path(__file__).parent / "data" / "debts.db"

    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return False

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(acts)")
        columns = [row[1] for row in cursor.fetchall()]

        if 'price_without_vat' in columns:
            logger.info("Column price_without_vat already exists. Nothing to do.")
            return True

        # Add the column
        logger.info("Adding column price_without_vat...")
        cursor.execute("ALTER TABLE acts ADD COLUMN price_without_vat REAL")
        conn.commit()
        logger.info("✓ Column added successfully")

        # Calculate price_without_vat for existing records
        logger.info("Calculating price_without_vat for existing records...")
        cursor.execute("""
            UPDATE acts
            SET price_without_vat = cost_without_vat / energy_volume
            WHERE cost_without_vat IS NOT NULL
              AND energy_volume IS NOT NULL
              AND energy_volume > 0
        """)

        updated_count = cursor.rowcount
        conn.commit()

        logger.info(f"✓ Updated {updated_count} records with calculated price")

        # Show summary
        cursor.execute("SELECT COUNT(*) FROM acts WHERE price_without_vat IS NOT NULL")
        price_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM acts")
        total_count = cursor.fetchone()[0]

        logger.info("")
        logger.info("=" * 80)
        logger.info("MIGRATION SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Total acts in database: {total_count}")
        logger.info(f"Acts with price_without_vat: {price_count}")
        logger.info(f"Acts without price: {total_count - price_count}")
        logger.info("=" * 80)
        logger.info("✓ Migration completed successfully!")

        return True

    except Exception as e:
        logger.error(f"Migration failed: {e}", exc_info=True)
        conn.rollback()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    import sys
    success = migrate_price_field()
    sys.exit(0 if success else 1)
