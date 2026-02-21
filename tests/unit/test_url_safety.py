"""Tests for proton_mcp.utils.url_safety module."""

import pytest

from proton_mcp.utils.url_safety import is_safe_url


class TestIsSafeUrl:
    # --- Valid / safe URLs ---

    def test_https_public_url(self):
        assert is_safe_url("https://example.com/unsubscribe") is True

    def test_http_public_url(self):
        assert is_safe_url("http://example.com/page") is True

    def test_https_with_path_and_query(self):
        assert is_safe_url("https://newsletter.example.com/unsub?id=123&token=abc") is True

    def test_public_ip_address(self):
        assert is_safe_url("http://8.8.8.8/path") is True

    # --- Blocked schemes ---

    def test_ftp_blocked(self):
        assert is_safe_url("ftp://example.com/file") is False

    def test_file_scheme_blocked(self):
        assert is_safe_url("file:///etc/passwd") is False

    def test_javascript_scheme_blocked(self):
        assert is_safe_url("javascript:alert(1)") is False

    def test_data_scheme_blocked(self):
        assert is_safe_url("data:text/html,<h1>Hi</h1>") is False

    def test_empty_scheme_blocked(self):
        assert is_safe_url("://example.com") is False

    # --- Localhost ---

    def test_localhost_blocked(self):
        assert is_safe_url("http://localhost/path") is False

    def test_localhost_localdomain_blocked(self):
        assert is_safe_url("http://localhost.localdomain/path") is False

    def test_localhost_with_port_blocked(self):
        assert is_safe_url("http://localhost:8080/path") is False

    # --- Loopback IPs ---

    def test_ipv4_loopback_blocked(self):
        assert is_safe_url("http://127.0.0.1/path") is False

    def test_ipv4_loopback_alt_blocked(self):
        assert is_safe_url("http://127.0.0.2/path") is False

    def test_ipv6_loopback_blocked(self):
        assert is_safe_url("http://[::1]/path") is False

    # --- Private IPs ---

    def test_10_x_private_blocked(self):
        assert is_safe_url("http://10.0.0.1/path") is False

    def test_172_16_private_blocked(self):
        assert is_safe_url("http://172.16.0.1/path") is False

    def test_172_31_private_blocked(self):
        assert is_safe_url("http://172.31.255.255/path") is False

    def test_192_168_private_blocked(self):
        assert is_safe_url("http://192.168.1.1/path") is False

    def test_192_168_0_private_blocked(self):
        assert is_safe_url("http://192.168.0.100/admin") is False

    # --- Link-local ---

    def test_ipv4_link_local_blocked(self):
        assert is_safe_url("http://169.254.1.1/path") is False

    def test_ipv6_link_local_blocked(self):
        assert is_safe_url("http://[fe80::1]/path") is False

    # --- Reserved ---

    def test_reserved_ip_0_0_0_0(self):
        assert is_safe_url("http://0.0.0.0/path") is False

    def test_reserved_ip_240(self):
        assert is_safe_url("http://240.0.0.1/path") is False

    # --- Edge cases ---

    def test_empty_string(self):
        assert is_safe_url("") is False

    def test_no_hostname(self):
        assert is_safe_url("http:///path") is False

    def test_garbage_input(self):
        assert is_safe_url("not a url at all") is False

    def test_hostname_that_looks_like_ip_but_isnt(self):
        # A hostname like "10.0.0.1.example.com" is a valid DNS name,
        # not an IP, so it should be allowed
        assert is_safe_url("http://10.0.0.1.example.com/path") is True

    def test_public_ipv6_allowed(self):
        # 2001:db8:: is documentation range but not private/link-local/loopback
        # Actually 2001:db8:: is reserved for documentation, so let's use a real public
        assert is_safe_url("http://[2607:f8b0:4004:800::200e]/path") is True
