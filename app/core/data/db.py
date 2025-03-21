import sqlite3
import os
from app.config.settings import DATA_DIR

class DatabaseManager:
    def __init__(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        
        self.conn_acts = sqlite3.connect(os.path.join(DATA_DIR, "acts.db"))
        self.cursor_acts = self.conn_acts.cursor()
        self.conn_payments = sqlite3.connect(os.path.join(DATA_DIR, "payments.db"))
        self.cursor_payments = self.conn_payments.cursor()
        self.init_db()

    def init_db(self):
        self.cursor_acts.execute('''
            CREATE TABLE IF NOT EXISTS acts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                counterparty TEXT,
                period TEXT,
                amount REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.cursor_payments.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company TEXT,
                counterparty TEXT,
                period TEXT,
                amount REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.cursor_payments.execute('''
            CREATE UNIQUE INDEX IF NOT EXISTS unique_payment 
            ON payments (company, counterparty, period, amount)
        ''')

        self.conn_acts.commit()
        self.conn_payments.commit()

    def normalize_company(self, company):
        # Переводимо в верхній регістр
        company = company.upper()
        # Заміни для компаній
        replacements = {
            "САН ПАУЕР ПЕРВОМАЙСЬК ТОВ": "ПЕРВОМАЙСЬК",
            'ТОВ "ФРІ-ЕНЕРДЖИ ГЕНІЧЕСЬК"': "ФРІ-ЕНЕРДЖИ",
            'ТОВ "ПОРТ-СОЛАР"': "ПОРТ-СОЛАР",
            'ТОВ "СКІФІЯ-СОЛАР-2"': "СКІФІЯ-СОЛАР-2",
            'ТОВ "СКІФІЯ-СОЛАР-1"': "СКІФІЯ-СОЛАР-1",
            "ДИМЕРСЬКА СЕС-1 ТОВ": "ДИМЕРСЬКА СЕС-1",
            'ТОВ "ТЕРСЛАВ"': "ТЕРСЛАВ"
        }
        return replacements.get(company, company)

    def normalize_counterparty(self, counterparty):
        # Переводимо в верхній регістр
        counterparty = counterparty.upper()
        # Заміна для контрагента
        if "ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП" in counterparty:
            return "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        return counterparty

    def save_act(self, company, counterparty, period, amount):
        # Нормалізуємо company і counterparty перед збереженням
        company = self.normalize_company(company)
        counterparty = self.normalize_counterparty(counterparty)
        
        self.cursor_acts.execute('''
            INSERT INTO acts (company, counterparty, period, amount)
            VALUES (?, ?, ?, ?)
        ''', (company, counterparty, period, amount))
        self.conn_acts.commit()

    def save_payment(self, company, counterparty, period, amount):
        # Нормалізуємо company і counterparty перед збереженням
        company = self.normalize_company(company)
        counterparty = self.normalize_counterparty(counterparty)
        
        self.cursor_payments.execute('''
            INSERT INTO payments (company, counterparty, period, amount)
            VALUES (?, ?, ?, ?)
        ''', (company, counterparty, period, amount))
        self.conn_payments.commit()

    def adjust_acts(self, company, counterparty, period, adjustment_amount):
        # Нормалізуємо company і counterparty перед коригуванням
        company = self.normalize_company(company)
        counterparty = self.normalize_counterparty(counterparty)
        
        # Отримуємо всі акти за вказаним періодом, компанією та контрагентом
        self.cursor_acts.execute('''
            SELECT id, amount 
            FROM acts 
            WHERE company = ? AND counterparty = ? AND period = ?
        ''', (company, counterparty, period))
        acts = self.cursor_acts.fetchall()

        if not acts:
            # Якщо актів за періодом немає, додаємо новий запис із сумою коригування
            self.cursor_acts.execute('''
                INSERT INTO acts (company, counterparty, period, amount)
                VALUES (?, ?, ?, ?)
            ''', (company, counterparty, period, adjustment_amount))
        else:
            # Оновлюємо суму для всіх актів за періодом
            for act in acts:
                act_id, amount = act
                new_amount = amount + adjustment_amount
                self.cursor_acts.execute('''
                    UPDATE acts 
                    SET amount = ? 
                    WHERE id = ?
                ''', (new_amount, act_id))

        self.conn_acts.commit()

    def get_all_acts(self):
        self.cursor_acts.execute('''
            SELECT company, counterparty, period, amount 
            FROM acts
        ''')
        return self.cursor_acts.fetchall()

    def get_all_payments(self):
        self.cursor_payments.execute('''
            SELECT company, counterparty, period, amount 
            FROM payments
        ''')
        return self.cursor_payments.fetchall()

    def clear_database(self):
        self.cursor_acts.execute('DELETE FROM acts')
        self.cursor_payments.execute('DELETE FROM payments')
        self.conn_acts.commit()
        self.conn_payments.commit()

    def __del__(self):
        self.conn_acts.close()
        self.conn_payments.close()