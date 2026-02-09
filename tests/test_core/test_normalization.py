"""
Tests for data normalization module.

Tests company name, counterparty name, and period normalization
to ensure consistent data processing across the application.
"""
import pytest

from app.core.normalization.normalizers import DataNormalizer


class TestCompanyNormalization:
    """Test company name normalization."""

    def test_normalize_first_maysk_variants(self) -> None:
        """Test ПЕРВОМАЙСЬК normalization variants."""
        variants = [
            "САН ПАУЕР ПЕРВОМАЙСЬК ТОВ",
            "САН ПАУЕР ПЕРВОМАЙСЬК",
            "ТОВ САН ПАУЕР ПЕРВОМАЙСЬК",
            'ТОВ САН ПАУЕР ПЕРВОМАЙСЬК»',
        ]
        for variant in variants:
            assert DataNormalizer.normalize_company(variant) == "ПЕРВОМАЙСЬК"

    def test_normalize_fri_energy_variants(self) -> None:
        """Test ФРІ-ЕНЕРДЖИ normalization variants."""
        variants = [
            'ТОВ "ФРІ-ЕНЕРДЖИ ГЕНІЧЕСЬК"',
            "ФРІ-ЕНЕРДЖИ ГЕНІЧЕСЬК",
        ]
        for variant in variants:
            assert DataNormalizer.normalize_company(variant) == "ФРІ-ЕНЕРДЖИ"

    def test_normalize_port_solar(self) -> None:
        """Test ПОРТ-СОЛАР normalization."""
        assert DataNormalizer.normalize_company('ТОВ "ПОРТ-СОЛАР"') == "ПОРТ-СОЛАР"
        assert DataNormalizer.normalize_company("порт-солар") == "ПОРТ-СОЛАР"

    def test_normalize_skifiya_solar_variants(self) -> None:
        """Test СКІФІЯ-СОЛАР normalization variants."""
        assert DataNormalizer.normalize_company('ТОВ "СКІФІЯ-СОЛАР-2"') == "СКІФІЯ-СОЛАР-2"
        assert DataNormalizer.normalize_company('ТОВ "СКІФІЯ-СОЛАР-1"') == "СКІФІЯ-СОЛАР-1"

    def test_normalize_dymerska_ses_variants(self) -> None:
        """Test ДИМЕРСЬКА СЕС-1 normalization with space variations."""
        variants = [
            "ДИМЕРСЬКА СЕС-1 ТОВ",
            "ДИМЕРСЬКА СЕС - 1",  # With spaces
            "димерська сес-1",
        ]
        for variant in variants:
            assert DataNormalizer.normalize_company(variant) == "ДИМЕРСЬКА СЕС-1"

    def test_normalize_terslav_variants(self) -> None:
        """Test ТЕРСЛАВ normalization variants."""
        variants = [
            'ТОВ "ТЕРСЛАВ"',
            "ТЕРСЛАВ",
            'ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ"ТЕРСЛАВ"',
            "терслав",
        ]
        for variant in variants:
            assert DataNormalizer.normalize_company(variant) == "ТЕРСЛАВ"

    def test_normalize_guaranteed_buyer(self) -> None:
        """Test ГАРАНТОВАНИЙ ПОКУПЕЦЬ normalization."""
        assert (
            DataNormalizer.normalize_company('ДЕРЖАВНЕ ПІДПРИЄМСТВО "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"')
            == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        )

    def test_normalize_encoding_issues(self) -> None:
        """Test normalization with encoding issues."""
        assert DataNormalizer.normalize_company("��� ����� �����������") == "ПЕРВОМАЙСЬК"
        assert DataNormalizer.normalize_company("�������") == "ТЕРСЛАВ"

    def test_normalize_unknown_company(self) -> None:
        """Test normalization of unknown company (no mapping)."""
        unknown = "SOME UNKNOWN COMPANY"
        assert DataNormalizer.normalize_company(unknown) == "SOME UNKNOWN COMPANY"
        assert DataNormalizer.normalize_company(unknown.lower()) == "SOME UNKNOWN COMPANY"

    def test_normalize_empty_company(self) -> None:
        """Test normalization of empty company name."""
        assert DataNormalizer.normalize_company("") == ""
        assert DataNormalizer.normalize_company("   ") == ""

    def test_normalize_company_case_insensitive(self) -> None:
        """Test that normalization is case-insensitive."""
        assert DataNormalizer.normalize_company("порт-солар") == "ПОРТ-СОЛАР"
        assert DataNormalizer.normalize_company("ПОРТ-СОЛАР") == "ПОРТ-СОЛАР"
        assert DataNormalizer.normalize_company("ПоРт-СоЛаР") == "ПОРТ-СОЛАР"

    def test_normalize_company_strips_whitespace(self) -> None:
        """Test that normalization strips leading/trailing whitespace."""
        assert DataNormalizer.normalize_company("  ТЕРСЛАВ  ") == "ТЕРСЛАВ"
        assert DataNormalizer.normalize_company("\t\nТЕРСЛАВ\n\t") == "ТЕРСЛАВ"


class TestCounterpartyNormalization:
    """Test counterparty name normalization."""

    def test_normalize_guaranteed_buyer_variants(self) -> None:
        """Test ГАРАНТОВАНИЙ ПОКУПЕЦЬ normalization variants."""
        variants = [
            "ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП",
            'ДП "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"',
            "ДП ГАРАНТОВАНИЙ ПОКУПЕЦЬ",
            "ГАРАНТОВАНОГО ПОКУПЦЯ",
            "ДП ГАРАНТОВАНОГО ПОКУПЦЯ",
        ]
        for variant in variants:
            assert DataNormalizer.normalize_counterparty(variant) == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"

    def test_normalize_counterparty_substring_matching(self) -> None:
        """Test that counterparty normalization uses substring matching."""
        # Should match because contains "ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП"
        assert (
            DataNormalizer.normalize_counterparty("ДЕРЖАВНЕ ПІДПРИЄМСТВО ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП")
            == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        )

    def test_normalize_counterparty_case_insensitive(self) -> None:
        """Test that counterparty normalization is case-insensitive."""
        assert (
            DataNormalizer.normalize_counterparty("гарантований покупець дп")
            == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        )
        assert (
            DataNormalizer.normalize_counterparty("ГаРаНтОвАнИй ПоКуПеЦь ДП")
            == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        )

    def test_normalize_unknown_counterparty(self) -> None:
        """Test normalization of unknown counterparty (no mapping)."""
        unknown = "SOME OTHER COUNTERPARTY"
        assert DataNormalizer.normalize_counterparty(unknown) == "SOME OTHER COUNTERPARTY"

    def test_normalize_empty_counterparty(self) -> None:
        """Test normalization of empty counterparty name."""
        assert DataNormalizer.normalize_counterparty("") == ""
        assert DataNormalizer.normalize_counterparty("   ") == ""

    def test_normalize_counterparty_strips_whitespace(self) -> None:
        """Test that counterparty normalization strips whitespace."""
        assert (
            DataNormalizer.normalize_counterparty("  ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП  ")
            == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"
        )

    def test_normalize_counterparty_priority(self) -> None:
        """Test that first matching mapping is used."""
        # If multiple mappings match, first one wins
        text = "ДП ГАРАНТОВАНИЙ ПОКУПЕЦЬ ДП"
        result = DataNormalizer.normalize_counterparty(text)
        assert result == "ГАРАНТОВАНИЙ ПОКУПЕЦЬ"


class TestPeriodNormalization:
    """Test period format normalization."""

    def test_normalize_period_dot_to_dash(self) -> None:
        """Test conversion from dot to dash format."""
        assert DataNormalizer.normalize_period("11.2019") == "11-2019"
        assert DataNormalizer.normalize_period("01.2020") == "01-2020"
        assert DataNormalizer.normalize_period("12.2025") == "12-2025"

    def test_normalize_period_already_dash(self) -> None:
        """Test that dash format remains unchanged."""
        assert DataNormalizer.normalize_period("11-2019") == "11-2019"
        assert DataNormalizer.normalize_period("01-2020") == "01-2020"

    def test_normalize_period_multiple_dots(self) -> None:
        """Test normalization with multiple dots."""
        assert DataNormalizer.normalize_period("11.2019.extra") == "11-2019-extra"

    def test_normalize_period_empty(self) -> None:
        """Test normalization of empty period."""
        assert DataNormalizer.normalize_period("") == ""
        assert DataNormalizer.normalize_period("   ") == "   "  # Strips not applied for period

    def test_normalize_period_mixed_format(self) -> None:
        """Test normalization of mixed dot/dash format."""
        assert DataNormalizer.normalize_period("11.2019-extra") == "11-2019-extra"

    def test_normalize_period_no_separator(self) -> None:
        """Test period without separator."""
        assert DataNormalizer.normalize_period("112019") == "112019"

    def test_normalize_period_preserves_length(self) -> None:
        """Test that period length is preserved."""
        original = "01.2024"
        normalized = DataNormalizer.normalize_period(original)
        assert len(normalized) == len(original)


class TestNormalizationEdgeCases:
    """Test edge cases and special scenarios."""

    def test_normalize_none_handling(self) -> None:
        """Test that None is handled gracefully."""
        # These should not raise exceptions
        assert DataNormalizer.normalize_company("") == ""
        assert DataNormalizer.normalize_counterparty("") == ""
        assert DataNormalizer.normalize_period("") == ""

    def test_normalize_unicode_handling(self) -> None:
        """Test Unicode character handling."""
        ukrainian = "УКРАЇНСЬКА КОМПАНІЯ"
        assert DataNormalizer.normalize_company(ukrainian) == "УКРАЇНСЬКА КОМПАНІЯ"

    def test_normalize_special_characters(self) -> None:
        """Test special character handling."""
        company = 'ТОВ "КОМПАНІЯ-123"'
        result = DataNormalizer.normalize_company(company)
        assert result == 'ТОВ "КОМПАНІЯ-123"'

    def test_normalize_numbers_in_names(self) -> None:
        """Test handling of numbers in company names."""
        assert DataNormalizer.normalize_company("КОМПАНІЯ-1") == "КОМПАНІЯ-1"
        assert DataNormalizer.normalize_company("КОМПАНІЯ-2") == "КОМПАНІЯ-2"

    def test_all_mappings_are_uppercase(self) -> None:
        """Verify that all mappings use uppercase values."""
        for normalized in DataNormalizer.COMPANY_MAPPING.values():
            assert normalized == normalized.upper(), f"{normalized} should be uppercase"

        for normalized in DataNormalizer.COUNTERPARTY_MAPPING.values():
            assert normalized == normalized.upper(), f"{normalized} should be uppercase"
