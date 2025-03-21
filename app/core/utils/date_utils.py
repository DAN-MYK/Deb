import re
import pandas as pd
from datetime import datetime
from app.config.settings import DATE_FORMATS

def extract_month(text):
    if pd.isna(text):
        return None
    text = str(text).lower()
    # Шукаємо формат "mm.yyyy" або "mm-yyyy"
    match = re.search(r'(\d{2})[.-](\d{4})', text)
    if match:
        month, year = match.groups()
        return f"{month}-{year}"
    return None

def extract_month_from_date(date):
    if pd.isna(date):
        return None
    
    if isinstance(date, (datetime, pd.Timestamp)):
        date = date.to_pydatetime() if isinstance(date, pd.Timestamp) else date
        return f"{date.month:02d}-{date.year}"

    if isinstance(date, str):
        for date_format in DATE_FORMATS:
            try:
                parsed_date = datetime.strptime(date, date_format)
                return f"{parsed_date.month:02d}-{parsed_date.year}"
            except ValueError:
                continue
        
        raise ValueError(f"Не вдалося розпізнати формат дати: {date}")
    
    raise ValueError(f"Непідтримуваний тип дати: {type(date)}")