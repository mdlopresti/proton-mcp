"""Tests for SMTPClient."""

import smtplib
from email.mime.multipart import MIMEMultipart
from unittest.mock import MagicMock, patch

import pytest

from proton_mcp.clients.smtp import SMTPClient


class TestSMTPClientContextManager:
    """Test context manager connect/disconnect behavior."""

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_enter_connects_with_starttls_and_login(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        client = SMTPClient(mock_config)
        result = client.__enter__()

        mock_smtp_cls.assert_called_once_with(mock_config.smtp_host, mock_config.smtp_port)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(mock_config.email, mock_config.password)
        assert result is client

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_exit_quits_connection(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        with SMTPClient(mock_config) as client:
            pass

        mock_server.quit.assert_called_once()

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_context_manager_full_lifecycle(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        with SMTPClient(mock_config) as client:
            assert client._server is mock_server

        mock_smtp_cls.assert_called_once()
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_connection_failure_raises(self, mock_smtp_cls, mock_config):
        mock_smtp_cls.side_effect = OSError("Connection refused")

        client = SMTPClient(mock_config)
        with pytest.raises(OSError, match="Connection refused"):
            client.__enter__()

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_login_failure_raises(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")

        client = SMTPClient(mock_config)
        with pytest.raises(smtplib.SMTPAuthenticationError):
            client.__enter__()

    def test_exit_handles_no_connection_gracefully(self, mock_config):
        """__exit__ should not raise if connection was never established."""
        client = SMTPClient(mock_config)
        # _server is None, __exit__ should not raise
        client.__exit__(None, None, None)

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_exit_handles_already_disconnected(self, mock_smtp_cls, mock_config):
        """__exit__ should handle SMTPServerDisconnected gracefully."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server
        mock_server.quit.side_effect = smtplib.SMTPServerDisconnected("Already disconnected")

        with SMTPClient(mock_config):
            pass
        # Should not raise


class TestSMTPClientSendEmail:
    """Test send_email method."""

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_send_email_returns_true_on_success(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        with SMTPClient(mock_config) as client:
            result = client.send_email("recipient@example.com", "Test Subject", "Test body")

        assert result is True
        mock_server.send_message.assert_called_once()

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_send_email_constructs_correct_headers(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        with SMTPClient(mock_config) as client:
            client.send_email("recipient@example.com", "Test Subject", "Hello there")

        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["From"] == mock_config.email
        assert sent_msg["To"] == "recipient@example.com"
        assert sent_msg["Subject"] == "Test Subject"

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_send_email_with_reply_to_id_sets_headers(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        reply_id = "<original-message-id@proton.me>"

        with SMTPClient(mock_config) as client:
            client.send_email("recipient@example.com", "Re: Test", "Reply body", reply_to_id=reply_id)

        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["In-Reply-To"] == reply_id
        assert sent_msg["References"] == reply_id

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_send_email_without_reply_to_id_omits_headers(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        with SMTPClient(mock_config) as client:
            client.send_email("recipient@example.com", "Test Subject", "Body text")

        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["In-Reply-To"] is None
        assert sent_msg["References"] is None

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_send_email_attaches_plain_text_body(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        with SMTPClient(mock_config) as client:
            client.send_email("recipient@example.com", "Test Subject", "Hello world")

        sent_msg = mock_server.send_message.call_args[0][0]
        assert isinstance(sent_msg, MIMEMultipart)
        payload = sent_msg.get_payload()
        assert len(payload) == 1
        assert payload[0].get_content_type() == "text/plain"
        assert payload[0].get_payload() == "Hello world"

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_send_email_returns_false_on_smtp_failure(self, mock_smtp_cls, mock_config):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server
        mock_server.send_message.side_effect = smtplib.SMTPException("Send failed")

        with SMTPClient(mock_config) as client:
            result = client.send_email("recipient@example.com", "Test Subject", "Body")

        assert result is False

    @patch("proton_mcp.clients.smtp.smtplib.SMTP")
    def test_send_email_logs_error_on_failure(self, mock_smtp_cls, mock_config, caplog):
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server
        mock_server.send_message.side_effect = smtplib.SMTPException("Send failed")

        import logging

        with caplog.at_level(logging.ERROR, logger="proton_mcp.clients.smtp"):
            with SMTPClient(mock_config) as client:
                client.send_email("recipient@example.com", "Test", "Body")

        assert "Failed to send email" in caplog.text
        assert "Send failed" in caplog.text

    def test_send_email_without_connection_returns_false(self, mock_config):
        """send_email should return False if called without a connection."""
        client = SMTPClient(mock_config)
        result = client.send_email("recipient@example.com", "Test", "Body")
        assert result is False
