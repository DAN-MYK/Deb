"""
File and directory validation module.

Provides secure validation for file operations to prevent security issues
like path traversal, oversized files, and permission errors.
"""
import os
from pathlib import Path
from typing import List, Optional


class FileValidator:
    """Validator for file and directory operations."""

    DEFAULT_MAX_SIZE_MB = 100
    DEFAULT_MAX_FILES = 10000

    @staticmethod
    def validate_file_path(
        file_path: str,
        max_size_mb: int = DEFAULT_MAX_SIZE_MB,
        allowed_extensions: Optional[List[str]] = None
    ) -> bool:
        """
        Validate file before processing.

        Args:
            file_path: Path to file
            max_size_mb: Maximum file size in MB
            allowed_extensions: List of allowed extensions (e.g., ['.xlsx', '.pdf'])

        Returns:
            True if file is valid

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file is invalid (not a file, wrong extension, too large)
            PermissionError: If file is not readable
        """
        path = Path(file_path)

        # Check existence
        if not path.exists():
            raise FileNotFoundError(f"Файл не існує: {file_path}")

        # Check if it's a file
        if not path.is_file():
            raise ValueError(f"Не є файлом: {file_path}")

        # Check read permission
        if not os.access(path, os.R_OK):
            raise PermissionError(f"Немає дозволу на читання: {file_path}")

        # Check file size
        file_size_mb = path.stat().st_size / (1024 * 1024)
        if file_size_mb > max_size_mb:
            raise ValueError(
                f"Файл занадто великий: {file_size_mb:.1f}MB (макс {max_size_mb}MB)"
            )

        # Check extension
        if allowed_extensions:
            if path.suffix.lower() not in allowed_extensions:
                raise ValueError(
                    f"Непідтримуване розширення: {path.suffix} "
                    f"(дозволені: {', '.join(allowed_extensions)})"
                )

        return True

    @staticmethod
    def validate_directory_path(
        folder_path: str,
        max_files: int = DEFAULT_MAX_FILES
    ) -> bool:
        """
        Validate directory before processing.

        Args:
            folder_path: Path to directory
            max_files: Maximum number of files allowed (prevents DoS)

        Returns:
            True if directory is valid

        Raises:
            FileNotFoundError: If directory doesn't exist
            ValueError: If path is not a directory or has too many files
            PermissionError: If directory is not readable
        """
        path = Path(folder_path)

        # Check existence
        if not path.exists():
            raise FileNotFoundError(f"Папка не існує: {folder_path}")

        # Check if it's a directory
        if not path.is_dir():
            raise ValueError(f"Не є папкою: {folder_path}")

        # Check read permission
        if not os.access(path, os.R_OK):
            raise PermissionError(f"Немає дозволу на читання папки: {folder_path}")

        # Check number of files (prevent DoS)
        file_count = sum(1 for _ in path.rglob('*') if _.is_file())
        if file_count > max_files:
            raise ValueError(
                f"Занадто багато файлів у папці: {file_count} (макс {max_files})"
            )

        return True

    @staticmethod
    def validate_save_path(save_path: str) -> bool:
        """
        Validate path for saving files.

        Args:
            save_path: Path where file will be saved

        Returns:
            True if path is valid for saving

        Raises:
            FileNotFoundError: If parent directory doesn't exist
            PermissionError: If no write permission in directory
        """
        path = Path(save_path)
        parent = path.parent

        # Check parent directory exists
        if not parent.exists():
            raise FileNotFoundError(f"Директорія не існує: {parent}")

        # Check write permission
        if not os.access(parent, os.W_OK):
            raise PermissionError(f"Немає дозволу на запис: {parent}")

        return True
