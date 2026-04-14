"""Tests for agent tool utility functions."""

import pytest
from app.agent.tools import normalize_phone, escape_ilike


class TestNormalizePhone:
    """Phone number normalization."""

    def test_strips_symbols(self):
        assert normalize_phone("+52 55 1234-5678") == "525512345678"
        assert normalize_phone("(555) 123-4567") == "5551234567"

    def test_handles_empty(self):
        assert normalize_phone("") == ""

    def test_handles_only_symbols(self):
        assert normalize_phone("+--()") == ""

    def test_already_clean(self):
        assert normalize_phone("5551234567") == "5551234567"

    def test_handles_spaces(self):
        assert normalize_phone("55 1234 5678") == "5512345678"


class TestEscapeIlike:
    """ILIKE special character escaping."""

    def test_escapes_percent(self):
        assert escape_ilike("100%") == "100\\%"

    def test_escapes_underscore(self):
        assert escape_ilike("first_name") == "first\\_name"

    def test_escapes_backslash(self):
        assert escape_ilike("path\\to") == "path\\\\to"

    def test_escapes_all_together(self):
        assert escape_ilike("100%_val\\x") == "100\\%\\_val\\\\x"

    def test_no_special_chars(self):
        assert escape_ilike("normal text") == "normal text"

    def test_empty_string(self):
        assert escape_ilike("") == ""
