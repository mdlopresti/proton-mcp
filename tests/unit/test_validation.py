"""Tests for proton_mcp.utils.validation module."""

import pytest

from proton_mcp.utils.validation import (
    quote_mailbox,
    validate_email_id,
    validate_folder_name,
)


# ---------------------------------------------------------------------------
# validate_email_id
# ---------------------------------------------------------------------------


class TestValidateEmailId:
    def test_single_numeric_id(self):
        assert validate_email_id("123") == "123"

    def test_single_digit(self):
        assert validate_email_id("1") == "1"

    def test_large_numeric_id(self):
        assert validate_email_id("999999999") == "999999999"

    def test_comma_separated_ids(self):
        assert validate_email_id("1,2,3") == "1,2,3"

    def test_comma_separated_with_spaces(self):
        assert validate_email_id("1, 2, 3") == "1, 2, 3"

    def test_strips_leading_trailing_whitespace(self):
        assert validate_email_id("  42  ") == "42"

    def test_strips_whitespace_comma_list(self):
        assert validate_email_id("  1,2,3  ") == "1,2,3"

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id("   ")

    def test_rejects_alpha_characters(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id("abc")

    def test_rejects_mixed_alpha_numeric(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id("12a3")

    def test_rejects_trailing_comma(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id("1,2,")

    def test_rejects_leading_comma(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id(",1,2")

    def test_rejects_double_comma(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id("1,,2")

    def test_rejects_negative_id(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id("-1")

    def test_rejects_special_characters(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id("1;DROP TABLE")

    def test_rejects_float(self):
        with pytest.raises(ValueError, match="Invalid email ID format"):
            validate_email_id("1.5")


# ---------------------------------------------------------------------------
# validate_folder_name
# ---------------------------------------------------------------------------


class TestValidateFolderName:
    def test_simple_name(self):
        assert validate_folder_name("INBOX") == "INBOX"

    def test_lowercase_name(self):
        assert validate_folder_name("archive") == "archive"

    def test_name_with_hyphen(self):
        assert validate_folder_name("my-folder") == "my-folder"

    def test_name_with_underscore(self):
        assert validate_folder_name("my_folder") == "my_folder"

    def test_name_with_dot(self):
        assert validate_folder_name("mail.archive") == "mail.archive"

    def test_nested_folder_with_slash(self):
        assert validate_folder_name("INBOX/subfolder") == "INBOX/subfolder"

    def test_name_with_space(self):
        assert validate_folder_name("My Folder") == "My Folder"

    def test_name_with_numbers(self):
        assert validate_folder_name("folder123") == "folder123"

    def test_strips_whitespace(self):
        assert validate_folder_name("  Drafts  ") == "Drafts"

    def test_rejects_empty_string(self):
        with pytest.raises(ValueError, match="Folder name cannot be empty"):
            validate_folder_name("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(ValueError, match="Folder name cannot be empty"):
            validate_folder_name("   ")

    def test_rejects_path_traversal_double_dot(self):
        with pytest.raises(ValueError, match="Directory traversal not allowed"):
            validate_folder_name("../etc/passwd")

    def test_rejects_path_traversal_mid_path(self):
        with pytest.raises(ValueError, match="Directory traversal not allowed"):
            validate_folder_name("folder/../secret")

    def test_rejects_path_traversal_trailing(self):
        with pytest.raises(ValueError, match="Directory traversal not allowed"):
            validate_folder_name("folder/..")

    def test_rejects_special_characters_semicolon(self):
        with pytest.raises(ValueError, match="Invalid folder name"):
            validate_folder_name("folder;rm -rf")

    def test_rejects_special_characters_backtick(self):
        with pytest.raises(ValueError, match="Invalid folder name"):
            validate_folder_name("folder`cmd`")

    def test_rejects_pipe(self):
        with pytest.raises(ValueError, match="Invalid folder name"):
            validate_folder_name("folder|pipe")

    def test_rejects_angle_brackets(self):
        with pytest.raises(ValueError, match="Invalid folder name"):
            validate_folder_name("<script>")

    def test_rejects_dollar_sign(self):
        with pytest.raises(ValueError, match="Invalid folder name"):
            validate_folder_name("$HOME")


# ---------------------------------------------------------------------------
# quote_mailbox
# ---------------------------------------------------------------------------


class TestQuoteMailbox:
    def test_simple_name_no_quoting(self):
        assert quote_mailbox("INBOX") == "INBOX"

    def test_name_with_space_gets_quoted(self):
        assert quote_mailbox("My Folder") == '"My Folder"'

    def test_name_with_backslash_gets_quoted(self):
        assert quote_mailbox("folder\\sub") == '"folder\\\\sub"'

    def test_name_with_space_and_backslash(self):
        assert quote_mailbox("My Folder\\sub") == '"My Folder\\\\sub"'

    def test_name_with_double_quote_in_space_name(self):
        # If name has space AND a double-quote character, both need escaping
        assert quote_mailbox('My "Folder"') == '"My \\"Folder\\""'

    def test_plain_alpha_numeric(self):
        assert quote_mailbox("Archive2024") == "Archive2024"

    def test_dot_separated_no_quoting(self):
        assert quote_mailbox("INBOX.Sent") == "INBOX.Sent"

    def test_empty_string(self):
        assert quote_mailbox("") == ""
