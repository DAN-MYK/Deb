#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Універсальний скрипт для очищення бази даних.
Дозволяє видаляти окремо акти, акти коригування та оплати.
"""

import sys
import sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

DB_PATH = Path("data/deb.db")


def get_db_stats():
    """Отримує статистику по всіх таблицях."""
    stats = {}

    if not DB_PATH.exists():
        return {'acts': None, 'adjustments': None, 'payments': None}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM acts")
        stats['acts'] = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        stats['acts'] = None

    try:
        cursor.execute("SELECT COUNT(*) FROM act_adjustments")
        stats['adjustments'] = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        stats['adjustments'] = None

    try:
        cursor.execute("SELECT COUNT(*) FROM payments")
        stats['payments'] = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        stats['payments'] = None

    conn.close()
    return stats


def delete_acts():
    """Видаляє всі акти."""
    if not DB_PATH.exists():
        print("\n❌ База даних не знайдена!")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM acts")
    count = cursor.fetchone()[0]

    if count == 0:
        print("\n✅ Таблиця актів вже порожня!")
        conn.close()
        return True

    cursor.execute("""
        SELECT id, company, period, amount
        FROM acts
        ORDER BY id DESC
        LIMIT 3
    """)
    records = cursor.fetchall()

    print(f"\n📋 Останні 3 записи (з {count}):")
    print("-" * 70)
    for rec in records:
        print(f"  ID {rec[0]:4} | {rec[1]:30} | {rec[2]:10} | {rec[3]:12.2f} грн")
    print("-" * 70)

    print(f"\n⚠️  УВАГА! Буде видалено {count} актів!")
    confirmation = input("Підтвердіть видалення (введіть 'ТАК'): ").strip()

    if confirmation != "ТАК":
        print("❌ Видалення скасовано")
        conn.close()
        return False

    try:
        cursor.execute("DELETE FROM acts")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='acts'")
        conn.commit()
        print(f"✅ Видалено {count} актів")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Помилка: {e}")
        conn.rollback()
        conn.close()
        return False


def delete_adjustments():
    """Видаляє всі акти коригування."""
    if not DB_PATH.exists():
        print("\n❌ База даних не знайдена!")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM act_adjustments")
    count = cursor.fetchone()[0]

    if count == 0:
        print("\n✅ Таблиця актів коригування вже порожня!")
        conn.close()
        return True

    cursor.execute("""
        SELECT id, company, period, adjustment_amount_with_vat
        FROM act_adjustments
        ORDER BY id DESC
        LIMIT 3
    """)
    records = cursor.fetchall()

    print(f"\n📋 Останні 3 записи (з {count}):")
    print("-" * 70)
    for rec in records:
        print(f"  ID {rec[0]:4} | {rec[1]:30} | {rec[2]:10} | {rec[3]:+12.2f} грн")
    print("-" * 70)

    print(f"\n⚠️  УВАГА! Буде видалено {count} актів коригування!")
    confirmation = input("Підтвердіть видалення (введіть 'ТАК'): ").strip()

    if confirmation != "ТАК":
        print("❌ Видалення скасовано")
        conn.close()
        return False

    try:
        cursor.execute("DELETE FROM act_adjustments")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='act_adjustments'")
        conn.commit()
        print(f"✅ Видалено {count} актів коригування")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Помилка: {e}")
        conn.rollback()
        conn.close()
        return False


def delete_payments():
    """Видаляє всі оплати."""
    if not DB_PATH.exists():
        print("\n❌ База даних не знайдена!")
        return False

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM payments")
    count = cursor.fetchone()[0]

    if count == 0:
        print("\n✅ Таблиця оплат вже порожня!")
        conn.close()
        return True

    cursor.execute("""
        SELECT id, company, period, amount, payment_date
        FROM payments
        ORDER BY id DESC
        LIMIT 3
    """)
    records = cursor.fetchall()

    print(f"\n📋 Останні 3 записи (з {count}):")
    print("-" * 70)
    for rec in records:
        date = rec[4] if rec[4] else "N/A"
        print(f"  ID {rec[0]:4} | {rec[1]:30} | {rec[2]:10} | {rec[3]:12.2f} грн | {date}")
    print("-" * 70)

    print(f"\n⚠️  УВАГА! Буде видалено {count} оплат!")
    confirmation = input("Підтвердіть видалення (введіть 'ТАК'): ").strip()

    if confirmation != "ТАК":
        print("❌ Видалення скасовано")
        conn.close()
        return False

    try:
        cursor.execute("DELETE FROM payments")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='payments'")
        conn.commit()
        print(f"✅ Видалено {count} оплат")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Помилка: {e}")
        conn.rollback()
        conn.close()
        return False


def delete_all():
    """Видаляє всі дані з усіх таблиць."""
    stats = get_db_stats()
    total = sum(v for v in stats.values() if v is not None)

    if total == 0:
        print("\n✅ Всі таблиці вже порожні!")
        return True

    print("\n⚠️  УВАГА! Буде видалено:")
    if stats['acts'] is not None:
        print(f"  • Актів: {stats['acts']}")
    if stats['adjustments'] is not None:
        print(f"  • Актів коригування: {stats['adjustments']}")
    if stats['payments'] is not None:
        print(f"  • Оплат: {stats['payments']}")
    print(f"\n  Всього: {total} записів")

    confirmation = input("\nПідтвердіть видалення ВСІХ даних (введіть 'ТАК'): ").strip()

    if confirmation != "ТАК":
        print("❌ Видалення скасовано")
        return False

    success = True

    if stats['acts'] and stats['acts'] > 0:
        print("\n🗑️ Видалення актів...")
        if not delete_acts():
            success = False

    if stats['adjustments'] and stats['adjustments'] > 0:
        print("\n🗑️ Видалення актів коригування...")
        if not delete_adjustments():
            success = False

    if stats['payments'] and stats['payments'] > 0:
        print("\n🗑️ Видалення оплат...")
        if not delete_payments():
            success = False

    return success


def main():
    """Головна функція з меню."""
    print("=" * 80)
    print("ОЧИЩЕННЯ БАЗИ ДАНИХ")
    print("=" * 80)

    stats = get_db_stats()

    print("\n📊 ПОТОЧНА СТАТИСТИКА:")
    print("-" * 80)

    if stats['acts'] is not None:
        print(f"  1. Акти:                  {stats['acts']:6} записів")
    else:
        print(f"  1. Акти:                  ❌ таблиця не знайдена")

    if stats['adjustments'] is not None:
        print(f"  2. Акти коригування:      {stats['adjustments']:6} записів")
    else:
        print(f"  2. Акти коригування:      ❌ таблиця не знайдена")

    if stats['payments'] is not None:
        print(f"  3. Оплати:                {stats['payments']:6} записів")
    else:
        print(f"  3. Оплати:                ❌ таблиця не знайдена")

    total = sum(v for v in stats.values() if v is not None)
    print("-" * 80)
    print(f"  Всього:                   {total:6} записів")
    print("-" * 80)

    if total == 0:
        print("\n✅ Всі таблиці порожні!")
        return

    print("\n📋 ЩО ВИДАЛИТИ?")
    print("-" * 80)
    print("  1 - Тільки акти")
    print("  2 - Тільки акти коригування")
    print("  3 - Тільки оплати")
    print("  4 - ВСЕ (акти + коригування + оплати)")
    print("  0 - Скасувати")
    print("-" * 80)

    choice = input("\nВаш вибір (0-4): ").strip()

    print("\n" + "=" * 80)

    if choice == "1":
        delete_acts()
    elif choice == "2":
        delete_adjustments()
    elif choice == "3":
        delete_payments()
    elif choice == "4":
        delete_all()
    elif choice == "0":
        print("❌ Операцію скасовано")
    else:
        print("❌ Невірний вибір!")

    print("=" * 80)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Операцію перервано користувачем")
        sys.exit(1)
