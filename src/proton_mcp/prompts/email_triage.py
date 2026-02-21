"""Prompt template for multi-step email triage workflow."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config


def register_prompts(mcp: FastMCP, config: Config) -> None:
    """Register email triage prompts with the MCP server."""

    @mcp.prompt()
    def email_triage() -> str:
        """Guide the user through a multi-step email triage workflow."""
        return """I'll help you triage your inbox. Here's the workflow I'll follow:

## Step 1: Scan for Junk
First, I'll scan your recent emails for junk/spam using `filter_junk_emails`. This identifies suspicious emails using pattern-based detection.

## Step 2: Review Unsubscribe Opportunities
Next, I'll check for emails from mailing lists you might want to unsubscribe from using `bulk_find_unsubscribe_opportunities`. This finds emails with unsubscribe links.

## Step 3: Identify Frequent Senders
I'll use `get_mailing_list_senders` to identify frequent senders that may be mailing lists, so you can decide which ones to keep.

## Step 4: Apply Filter Rules
If you have existing filter rules, I'll apply them using `apply_filter_rules` to automatically organize matching emails.

## Step 5: Manual Review
Finally, I'll show you the remaining unprocessed emails for manual review, highlighting:
- Emails that need a response
- Emails that can be archived
- Emails from new senders

## Getting Started

Would you like me to:
1. **Full triage** - Run all steps above
2. **Junk cleanup only** - Just scan and remove junk
3. **Unsubscribe review** - Focus on mailing list cleanup
4. **Apply rules** - Just apply existing filter rules

Tell me which option you'd like, or describe your own custom triage workflow."""
