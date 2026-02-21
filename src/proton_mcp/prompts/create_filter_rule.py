"""Prompt template for creating email filter rules."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config


def register_prompts(mcp: FastMCP, config: Config) -> None:
    """Register filter rule creation prompts with the MCP server."""

    @mcp.prompt()
    def create_filter_rule() -> str:
        """Guide the user through creating an email filter rule with examples."""
        return """I'll help you create an email filter rule. Filter rules automatically process incoming emails based on conditions you specify.

## Available Conditions

| Condition | Description | Example Value |
|-----------|-------------|---------------|
| `from` | Match sender (contains) | `"newsletter@example.com"` |
| `to` | Match recipient (contains) | `"team@company.com"` |
| `subject_contains` | Subject contains text | `"sale"` |
| `subject_equals` | Subject matches exactly | `"Weekly Report"` |
| `body_contains` | Body contains text | `"unsubscribe"` |
| `sender_domain` | Match sender domain | `"github.com"` |
| `has_attachments` | Has attachments | `true` |
| `older_than_days` | Email age in days | `30` |
| `newer_than_days` | Email is newer than N days | `7` |

## Available Actions

| Action | Description | Example Value |
|--------|-------------|---------------|
| `move_to_folder` | Move to folder | `"Newsletter"` |
| `mark_as_read` | Mark as read | `true` |
| `mark_as_important` | Flag as important | `true` |
| `delete` | Delete the email | `true` |

## Common Rule Examples

**GitHub Notifications:**
```
Name: "GitHub Notifications"
Conditions: {"sender_domain": "github.com"}
Actions: {"move_to_folder": "GitHub", "mark_as_read": true}
```

**Marketing Emails:**
```
Name: "Marketing Emails"
Conditions: {"body_contains": "unsubscribe"}
Actions: {"move_to_folder": "Marketing"}
```

**Important Client:**
```
Name: "Important Client"
Conditions: {"from": "client@importantcompany.com"}
Actions: {"move_to_folder": "VIP", "mark_as_important": true}
```

**Old Newsletter Cleanup:**
```
Name: "Old Newsletters"
Conditions: {"sender_domain": "newsletter.com", "older_than_days": 30}
Actions: {"delete": true}
```

## How to Create

Tell me the following:
1. **Rule name** - A descriptive name for the rule
2. **Conditions** - What emails should match (you can combine multiple conditions)
3. **Actions** - What to do with matching emails

I'll use the `create_filter_rule` tool to create it for you."""
