"""
Configuration module using pydantic-settings for environment-based configuration.
"""
import sys
from typing import List, Tuple
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from platformdirs import user_data_dir, user_log_dir


def is_frozen() -> bool:
    """
    Check if the application is running as a frozen executable (PyInstaller).
    
    Returns:
        True if running as frozen executable, False otherwise
    """
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')


def get_default_data_dir() -> str:
    """
    Get the default data directory based on execution context.
    
    In frozen mode (PyInstaller), uses platform-specific user data directory.
    In development mode, uses local 'data' directory.
    
    Returns:
        Path to data directory
    """
    if is_frozen():
        return user_data_dir("Deb", "MykhailoDan")
    return "data"


def get_default_log_dir() -> str:
    """
    Get the default log directory based on execution context.
    
    In frozen mode (PyInstaller), uses platform-specific user log directory.
    In development mode, uses local 'logs' directory.
    
    Returns:
        Path to log directory
    """
    if is_frozen():
        return user_log_dir("Deb", "MykhailoDan")
    return "logs"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables and .env file.
    
    All settings can be overridden via environment variables.
    
    In frozen mode (PyInstaller), data and logs are stored in platform-specific
    user directories. In development mode, they use local directories.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Database Configuration
    data_dir: str = Field(
        default_factory=get_default_data_dir,
        description="Directory for database files"
    )
    db_name: str = Field(
        default="deb.db",
        description="Database file name"
    )
    
    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    log_dir: str = Field(
        default_factory=get_default_log_dir,
        description="Directory for log files"
    )
    
    # PDF Processing Configuration
    pdf_bank_keywords: List[str] = Field(
        default=[
            "виписка",
            "банк",
            "рахунок",
            "statement",
            "банківська",
            "виписка по рахунку"
        ],
        description="Keywords to identify bank statement PDFs"
    )
    pdf_act_keywords: List[str] = Field(
        default=[
            "акт",
            "виконаних робіт",
            "наданих послуг",
            "надання послуг",
            "виконання робіт"
        ],
        description="Keywords to identify act PDFs"
    )
    pdf_max_pages: int = Field(
        default=50,
        description="Maximum number of pages to process in a PDF"
    )
    pdf_amount_max: float = Field(
        default=1_000_000_000,
        description="Maximum allowed amount value"
    )
    
    # OCR Configuration
    ocr_enabled: bool = Field(
        default=True,
        description="Enable OCR fallback for scanned PDFs"
    )
    ocr_language: str = Field(
        default="ukr+eng",
        description="OCR language(s) for Tesseract (e.g., 'ukr+eng', 'rus+eng')"
    )
    ocr_max_pages: int = Field(
        default=10,
        description="Maximum number of pages to process with OCR (resource intensive)"
    )
    ocr_dpi: int = Field(
        default=300,
        description="DPI for PDF to image conversion (higher = better quality but slower)"
    )
    
    # File Processing Configuration
    supported_extensions: Tuple[str, ...] = Field(
        default=(".xlsx", ".xlsm", ".xls", ".pdf"),
        description="Supported file extensions for import"
    )
    date_formats: List[str] = Field(
        default=[
            '%Y-%m-%d',
            '%d.%m.%Y %H:%M:%S',
            '%d.%m.%Y',
            '%Y-%m-%d %H:%M:%S',
        ],
        description="Date formats for parsing"
    )
    
    # UI Configuration
    appearance_mode: str = Field(
        default="dark",
        description="UI appearance mode (dark, light, system)"
    )
    color_theme: str = Field(
        default="blue",
        description="UI color theme"
    )
    
    @property
    def db_path(self) -> Path:
        """Get full path to database."""
        return Path(self.data_dir) / self.db_name
    
    @property
    def log_dir_path(self) -> Path:
        """Get full path to logs directory."""
        return Path(self.log_dir)


# Global settings instance
settings = Settings()
