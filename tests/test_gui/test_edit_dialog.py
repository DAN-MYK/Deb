"""
Tests for edit dialog module.

Tests EditDialog, EditField dataclass, and confirm_delete function.
"""
from unittest.mock import MagicMock, Mock, patch

import pytest


class TestEditField:
    """Test EditField dataclass."""

    def test_edit_field_creation_minimal(self) -> None:
        """Test creating EditField with minimal parameters."""
        from app.gui.dialogs.edit_dialog import EditField

        field = EditField(key="test_key", label="Test Label", value="test_value")

        assert field.key == "test_key"
        assert field.label == "Test Label"
        assert field.value == "test_value"
        assert field.placeholder == ""
        assert field.validator is None
        assert field.parser is None

    def test_edit_field_creation_full(self) -> None:
        """Test creating EditField with all parameters."""
        from app.gui.dialogs.edit_dialog import EditField

        validator = lambda x: None if x else "Required"
        parser = lambda x: int(x)

        field = EditField(
            key="amount",
            label="Amount",
            value="100",
            placeholder="Enter amount",
            validator=validator,
            parser=parser
        )

        assert field.key == "amount"
        assert field.label == "Amount"
        assert field.value == "100"
        assert field.placeholder == "Enter amount"
        assert field.validator == validator
        assert field.parser == parser

    def test_edit_field_validator_callable(self) -> None:
        """Test that validator is callable."""
        from app.gui.dialogs.edit_dialog import EditField

        def validator(value: str) -> str | None:
            return "Error" if not value else None

        field = EditField(key="test", label="Test", value="", validator=validator)

        assert field.validator("") == "Error"
        assert field.validator("valid") is None

    def test_edit_field_parser_callable(self) -> None:
        """Test that parser is callable."""
        from app.gui.dialogs.edit_dialog import EditField

        def parser(value: str) -> float:
            return float(value)

        field = EditField(key="price", label="Price", value="10.5", parser=parser)

        assert field.parser("10.5") == 10.5


class TestEditDialog:
    """Test EditDialog class."""

    @pytest.fixture(autouse=True)
    def mock_gui_modules(self):
        """Mock GUI-related modules."""
        with patch.dict("sys.modules", {
            "customtkinter": MagicMock(),
            "tkinter": MagicMock()
        }):
            yield

    @pytest.fixture
    def mock_parent(self):
        """Create mock parent widget."""
        return MagicMock()

    @pytest.fixture
    def simple_fields(self):
        """Create simple test fields."""
        from app.gui.dialogs.edit_dialog import EditField

        return [
            EditField(key="name", label="Name", value="Test Name"),
            EditField(key="amount", label="Amount", value="100.50")
        ]

    def test_edit_dialog_init(self, mock_parent: Mock, simple_fields: list) -> None:
        """Test EditDialog initialization."""
        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            from app.gui.dialogs.edit_dialog import EditDialog

            on_save = Mock()
            dialog = EditDialog(
                parent=mock_parent,
                title="Edit Test",
                fields=simple_fields,
                on_save=on_save
            )

            assert dialog.parent == mock_parent
            assert dialog.fields == simple_fields
            assert dialog.on_save == on_save
            assert len(dialog._entries) == 2
            assert len(dialog._errors) == 2

    def test_edit_dialog_creates_entries_for_fields(self, mock_parent: Mock, simple_fields: list) -> None:
        """Test that dialog creates entries for all fields."""
        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            from app.gui.dialogs.edit_dialog import EditDialog

            dialog = EditDialog(mock_parent, "Test", simple_fields, Mock())

            assert "name" in dialog._entries
            assert "amount" in dialog._entries

    def test_edit_dialog_creates_error_labels(self, mock_parent: Mock, simple_fields: list) -> None:
        """Test that dialog creates error labels for all fields."""
        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            from app.gui.dialogs.edit_dialog import EditDialog

            dialog = EditDialog(mock_parent, "Test", simple_fields, Mock())

            assert "name" in dialog._errors
            assert "amount" in dialog._errors

    def test_handle_save_with_valid_data(self, mock_parent: Mock) -> None:
        """Test successful save with valid data."""
        from app.gui.dialogs.edit_dialog import EditDialog, EditField

        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            fields = [
                EditField(key="name", label="Name", value="John"),
                EditField(key="age", label="Age", value="30", parser=int)
            ]

            on_save = Mock()
            dialog = EditDialog(mock_parent, "Test", fields, on_save)

            # Mock entry widgets
            dialog._entries["name"] = Mock()
            dialog._entries["name"].get.return_value = "John Doe"
            dialog._entries["age"] = Mock()
            dialog._entries["age"].get.return_value = "25"

            # Mock error labels
            dialog._errors["name"] = Mock()
            dialog._errors["age"] = Mock()

            # Mock dialog destroy
            dialog.dialog = Mock()

            dialog._handle_save()

            # Verify on_save was called with correct values
            on_save.assert_called_once()
            call_args = on_save.call_args[0][0]
            assert call_args["name"] == "John Doe"
            assert call_args["age"] == 25

            # Verify dialog was destroyed
            dialog.dialog.destroy.assert_called_once()

    def test_handle_save_with_validation_error(self, mock_parent: Mock) -> None:
        """Test save with validation error."""
        from app.gui.dialogs.edit_dialog import EditDialog, EditField

        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            def validate_name(value: str) -> str | None:
                return "Name is required" if not value.strip() else None

            fields = [
                EditField(key="name", label="Name", value="", validator=validate_name)
            ]

            on_save = Mock()
            dialog = EditDialog(mock_parent, "Test", fields, on_save)

            # Mock entry widget with empty value
            dialog._entries["name"] = Mock()
            dialog._entries["name"].get.return_value = "  "

            # Mock error label
            dialog._errors["name"] = Mock()

            # Mock dialog (should NOT be destroyed)
            dialog.dialog = Mock()

            dialog._handle_save()

            # Verify error was set
            dialog._errors["name"].configure.assert_called()
            error_text = dialog._errors["name"].configure.call_args[1]["text"]
            assert error_text == "Name is required"

            # Verify on_save was NOT called
            on_save.assert_not_called()

            # Verify dialog was NOT destroyed
            dialog.dialog.destroy.assert_not_called()

    def test_handle_save_with_parser_error(self, mock_parent: Mock) -> None:
        """Test save with parser error."""
        from app.gui.dialogs.edit_dialog import EditDialog, EditField

        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            fields = [
                EditField(key="amount", label="Amount", value="100", parser=float)
            ]

            on_save = Mock()
            dialog = EditDialog(mock_parent, "Test", fields, on_save)

            # Mock entry widget with invalid float value
            dialog._entries["amount"] = Mock()
            dialog._entries["amount"].get.return_value = "not_a_number"

            # Mock error label
            dialog._errors["amount"] = Mock()

            dialog.dialog = Mock()

            dialog._handle_save()

            # Verify error was set
            dialog._errors["amount"].configure.assert_called()
            error_text = dialog._errors["amount"].configure.call_args[1]["text"]
            assert "Невірне значення" in error_text

            # Verify on_save was NOT called
            on_save.assert_not_called()

    def test_handle_save_strips_whitespace(self, mock_parent: Mock) -> None:
        """Test that save strips whitespace from input."""
        from app.gui.dialogs.edit_dialog import EditDialog, EditField

        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            fields = [EditField(key="name", label="Name", value="Test")]

            on_save = Mock()
            dialog = EditDialog(mock_parent, "Test", fields, on_save)

            # Mock entry with leading/trailing whitespace
            dialog._entries["name"] = Mock()
            dialog._entries["name"].get.return_value = "  John Doe  "

            dialog._errors["name"] = Mock()
            dialog.dialog = Mock()

            dialog._handle_save()

            # Verify stripped value was used
            call_args = on_save.call_args[0][0]
            assert call_args["name"] == "John Doe"

    def test_handle_save_with_multiple_validation_errors(self, mock_parent: Mock) -> None:
        """Test save with multiple validation errors."""
        from app.gui.dialogs.edit_dialog import EditDialog, EditField

        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            def validate_required(value: str) -> str | None:
                return "Required" if not value.strip() else None

            fields = [
                EditField(key="name", label="Name", value="", validator=validate_required),
                EditField(key="email", label="Email", value="", validator=validate_required)
            ]

            on_save = Mock()
            dialog = EditDialog(mock_parent, "Test", fields, on_save)

            # Mock both entries with empty values
            dialog._entries["name"] = Mock()
            dialog._entries["name"].get.return_value = ""
            dialog._entries["email"] = Mock()
            dialog._entries["email"].get.return_value = ""

            # Mock error labels
            dialog._errors["name"] = Mock()
            dialog._errors["email"] = Mock()

            dialog.dialog = Mock()

            dialog._handle_save()

            # Verify both errors were set
            assert dialog._errors["name"].configure.called
            assert dialog._errors["email"].configure.called

            # Verify on_save was NOT called
            on_save.assert_not_called()

    def test_handle_save_clears_previous_errors(self, mock_parent: Mock) -> None:
        """Test that save clears previous error messages."""
        from app.gui.dialogs.edit_dialog import EditDialog, EditField

        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            fields = [EditField(key="name", label="Name", value="Test")]

            on_save = Mock()
            dialog = EditDialog(mock_parent, "Test", fields, on_save)

            dialog._entries["name"] = Mock()
            dialog._entries["name"].get.return_value = "Valid Name"

            dialog._errors["name"] = Mock()
            dialog.dialog = Mock()

            dialog._handle_save()

            # Verify error was cleared (set to empty string)
            dialog._errors["name"].configure.assert_called()
            error_text = dialog._errors["name"].configure.call_args[1]["text"]
            assert error_text == ""

    @patch("app.gui.dialogs.edit_dialog.messagebox")
    def test_handle_save_shows_error_on_save_exception(
        self, mock_messagebox: Mock, mock_parent: Mock
    ) -> None:
        """Test that save shows error dialog on exception."""
        from app.gui.dialogs.edit_dialog import EditDialog, EditField

        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            fields = [EditField(key="name", label="Name", value="Test")]

            # on_save raises exception
            on_save = Mock(side_effect=RuntimeError("Database error"))
            dialog = EditDialog(mock_parent, "Test", fields, on_save)

            dialog._entries["name"] = Mock()
            dialog._entries["name"].get.return_value = "Valid"

            dialog._errors["name"] = Mock()
            dialog.dialog = Mock()

            dialog._handle_save()

            # Verify error dialog was shown
            mock_messagebox.showerror.assert_called_once()
            assert "Database error" in str(mock_messagebox.showerror.call_args)

            # Verify dialog was NOT destroyed
            dialog.dialog.destroy.assert_not_called()

    def test_handle_save_with_no_parser(self, mock_parent: Mock) -> None:
        """Test save with field that has no parser (uses raw string)."""
        from app.gui.dialogs.edit_dialog import EditDialog, EditField

        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            fields = [EditField(key="description", label="Description", value="")]

            on_save = Mock()
            dialog = EditDialog(mock_parent, "Test", fields, on_save)

            dialog._entries["description"] = Mock()
            dialog._entries["description"].get.return_value = "Some description"

            dialog._errors["description"] = Mock()
            dialog.dialog = Mock()

            dialog._handle_save()

            # Verify raw string value was used (no parsing)
            call_args = on_save.call_args[0][0]
            assert call_args["description"] == "Some description"
            assert isinstance(call_args["description"], str)

    @patch("app.gui.dialogs.edit_dialog.logger")
    def test_handle_save_logs_parser_errors(
        self, mock_logger: Mock, mock_parent: Mock
    ) -> None:
        """Test that parser errors are logged."""
        from app.gui.dialogs.edit_dialog import EditDialog, EditField

        with patch("app.gui.dialogs.edit_dialog.get_app_fonts") as mock_fonts, \
             patch("app.gui.dialogs.edit_dialog.SPACING", {"button_height": 40, "button_height_lg": 45}):
            mock_fonts.return_value = {"base": MagicMock()}

            def bad_parser(value: str):
                raise AttributeError("Parser error")

            fields = [EditField(key="test", label="Test", value="", parser=bad_parser)]

            on_save = Mock()
            dialog = EditDialog(mock_parent, "Test", fields, on_save)

            dialog._entries["test"] = Mock()
            dialog._entries["test"].get.return_value = "value"

            dialog._errors["test"] = Mock()
            dialog.dialog = Mock()

            dialog._handle_save()

            # Verify error was logged
            mock_logger.error.assert_called_once()
            assert "Parser error" in str(mock_logger.error.call_args)


class TestConfirmDelete:
    """Test confirm_delete function."""

    @patch("app.gui.dialogs.edit_dialog.messagebox")
    def test_confirm_delete_returns_true_on_yes(self, mock_messagebox: Mock) -> None:
        """Test confirm_delete returns True when user clicks Yes."""
        from app.gui.dialogs.edit_dialog import confirm_delete

        mock_messagebox.askyesno.return_value = True

        result = confirm_delete(
            parent=MagicMock(),
            title="Confirm",
            message="Are you sure?"
        )

        assert result is True
        mock_messagebox.askyesno.assert_called_once()

    @patch("app.gui.dialogs.edit_dialog.messagebox")
    def test_confirm_delete_returns_false_on_no(self, mock_messagebox: Mock) -> None:
        """Test confirm_delete returns False when user clicks No."""
        from app.gui.dialogs.edit_dialog import confirm_delete

        mock_messagebox.askyesno.return_value = False

        result = confirm_delete(
            parent=MagicMock(),
            title="Confirm",
            message="Are you sure?"
        )

        assert result is False

    @patch("app.gui.dialogs.edit_dialog.messagebox")
    def test_confirm_delete_passes_correct_parameters(self, mock_messagebox: Mock) -> None:
        """Test that confirm_delete passes correct parameters to messagebox."""
        from app.gui.dialogs.edit_dialog import confirm_delete

        parent = MagicMock()
        title = "Delete Confirmation"
        message = "Delete this item?"

        confirm_delete(parent, title, message)

        mock_messagebox.askyesno.assert_called_once_with(title, message, parent=parent)
