"""
Tests for GUI components module.

Tests StatusBar component with simplified mocking approach.
"""
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest


@pytest.fixture
def mock_gui_environment():
    """Mock entire GUI environment."""
    with patch("app.gui.components.statusbar.ctk") as mock_ctk, \
         patch("app.gui.components.statusbar.get_app_fonts") as mock_fonts:

        # Setup mock fonts
        mock_fonts.return_value = {"base": MagicMock()}

        # Setup mock CTk widgets
        mock_ctk.CTkFrame = MagicMock
        mock_ctk.CTkLabel = MagicMock

        yield {"ctk": mock_ctk, "fonts": mock_fonts}


class TestStatusBar:
    """Test StatusBar component."""

    def test_statusbar_initialization(self, mock_gui_environment: dict) -> None:
        """Test StatusBar can be initialized."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)

        # Verify object was created
        assert statusbar is not None
        assert hasattr(statusbar, "_tab_label")
        assert hasattr(statusbar, "_rows_label")
        assert hasattr(statusbar, "_filter_label")
        assert hasattr(statusbar, "_status_label")

    def test_update_context_with_active_tab(self, mock_gui_environment: dict) -> None:
        """Test updating active tab label."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)

        # Mock the label
        statusbar._tab_label = MagicMock()

        # Update context
        statusbar.update_context(active_tab="Акти")

        # Verify label was updated
        statusbar._tab_label.configure.assert_called_once_with(text="Таб: Акти")

    def test_update_context_with_row_count(self, mock_gui_environment: dict) -> None:
        """Test updating row count label."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._rows_label = MagicMock()

        statusbar.update_context(active_tab="Test", row_count=42)

        statusbar._rows_label.configure.assert_called_once_with(text="Рядків: 42")

    def test_update_context_with_zero_rows(self, mock_gui_environment: dict) -> None:
        """Test updating with zero rows."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._rows_label = MagicMock()

        statusbar.update_context(active_tab="Test", row_count=0)

        statusbar._rows_label.configure.assert_called_once_with(text="Рядків: 0")

    def test_update_context_with_filter_text(self, mock_gui_environment: dict) -> None:
        """Test updating filter label."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._filter_label = MagicMock()

        filter_text = "Фільтр: активний"
        statusbar.update_context(active_tab="Test", filter_text=filter_text)

        statusbar._filter_label.configure.assert_called_once_with(text=filter_text)

    def test_update_context_with_status_no_timestamp(self, mock_gui_environment: dict) -> None:
        """Test updating status without timestamp."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._status_label = MagicMock()

        status_text = "Готово"
        statusbar.update_context(active_tab="Test", status_text=status_text)

        statusbar._status_label.configure.assert_called_once_with(text="Готово")

    def test_update_context_with_status_and_timestamp(self, mock_gui_environment: dict) -> None:
        """Test updating status with timestamp."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._status_label = MagicMock()

        status_text = "Оновлено"
        timestamp = datetime(2024, 10, 15, 14, 30, 45)
        statusbar.update_context(
            active_tab="Test",
            status_text=status_text,
            updated_at=timestamp
        )

        statusbar._status_label.configure.assert_called_once_with(
            text="Оновлено о 14:30:45"
        )

    def test_update_context_with_all_parameters(self, mock_gui_environment: dict) -> None:
        """Test updating with all parameters."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._tab_label = MagicMock()
        statusbar._rows_label = MagicMock()
        statusbar._filter_label = MagicMock()
        statusbar._status_label = MagicMock()

        timestamp = datetime(2024, 10, 15, 14, 30, 45)
        statusbar.update_context(
            active_tab="Платежі",
            row_count=100,
            filter_text="Фільтр: компанія X",
            status_text="Завантажено",
            updated_at=timestamp
        )

        statusbar._tab_label.configure.assert_called_once()
        statusbar._rows_label.configure.assert_called_once()
        statusbar._filter_label.configure.assert_called_once()
        statusbar._status_label.configure.assert_called_once()

    def test_update_context_with_none_row_count_skipped(self, mock_gui_environment: dict) -> None:
        """Test that None row_count is skipped."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._rows_label = MagicMock()

        statusbar.update_context(active_tab="Test", row_count=None)

        # Should not be called because row_count is None
        statusbar._rows_label.configure.assert_not_called()

    def test_update_context_with_empty_filter_not_updated(self, mock_gui_environment: dict) -> None:
        """Test that empty filter is not updated."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._filter_label = MagicMock()

        statusbar.update_context(active_tab="Test", filter_text="")

        # Should not be called for empty string
        statusbar._filter_label.configure.assert_not_called()

    def test_update_context_with_empty_status_not_updated(self, mock_gui_environment: dict) -> None:
        """Test that empty status is not updated."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._status_label = MagicMock()

        statusbar.update_context(active_tab="Test", status_text="")

        # Should not be called for empty string
        statusbar._status_label.configure.assert_not_called()

    def test_update_context_partial_update(self, mock_gui_environment: dict) -> None:
        """Test partial update with only some parameters."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._tab_label = MagicMock()
        statusbar._rows_label = MagicMock()
        statusbar._filter_label = MagicMock()
        statusbar._status_label = MagicMock()

        # Only update tab and row count
        statusbar.update_context(active_tab="Акти", row_count=50)

        statusbar._tab_label.configure.assert_called_once()
        statusbar._rows_label.configure.assert_called_once()
        statusbar._filter_label.configure.assert_not_called()
        statusbar._status_label.configure.assert_not_called()

    def test_statusbar_timestamp_formatting(self, mock_gui_environment: dict) -> None:
        """Test timestamp formatting."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._status_label = MagicMock()

        # Test with single-digit hour/minute/second
        timestamp = datetime(2024, 1, 1, 9, 5, 3)
        statusbar.update_context(
            active_tab="Test",
            status_text="Done",
            updated_at=timestamp
        )

        # Should format as HH:MM:SS
        statusbar._status_label.configure.assert_called_once_with(text="Done о 09:05:03")

    def test_statusbar_multiple_updates(self, mock_gui_environment: dict) -> None:
        """Test multiple updates."""
        from app.gui.components.statusbar import StatusBar

        parent = MagicMock()
        statusbar = StatusBar(parent)
        statusbar._rows_label = MagicMock()

        # First update
        statusbar.update_context(active_tab="Акти", row_count=10)

        # Second update
        statusbar.update_context(active_tab="Акти", row_count=20)

        # Verify second update
        assert statusbar._rows_label.configure.call_count == 2
        last_call = statusbar._rows_label.configure.call_args_list[-1]
        assert last_call[1]["text"] == "Рядків: 20"
