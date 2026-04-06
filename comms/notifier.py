"""
notifier.py — external notification dispatcher.

Phase 1: no-op stub (all methods return immediately).
Phase 2: Slack incoming webhook + Microsoft Teams webhook.

Called by main.py after a ClarificationMessage is stored,
so the human gets a notification even if the UI is not open.
"""

import logging
import os
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

SLACK_WEBHOOK_URL  = os.getenv("SLACK_WEBHOOK_URL")
TEAMS_WEBHOOK_URL  = os.getenv("TEAMS_WEBHOOK_URL")


async def notify_clarification(
    agent_label: str,
    question: str,
    file: Optional[str],
    message_id: str,
    ui_url: str = "http://localhost:7000",
) -> None:
    """
    Notify the human that an agent needs a reply.
    Fires Slack and/or Teams webhooks if configured.
    """
    if SLACK_WEBHOOK_URL:
        await _slack(agent_label, question, file, message_id, ui_url)

    if TEAMS_WEBHOOK_URL:
        await _teams(agent_label, question, file, message_id, ui_url)

    if not SLACK_WEBHOOK_URL and not TEAMS_WEBHOOK_URL:
        logger.debug("[notifier] no webhooks configured — UI only")


async def _slack(agent_label: str, question: str, file: Optional[str],
                 message_id: str, ui_url: str) -> None:
    file_line = f"\n*File:* `{file}`" if file else ""
    payload = {
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f":robot_face: *{agent_label}* needs your input{file_line}\n"
                        f">  {question}"
                    ),
                },
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "Reply in UI"},
                        "url": f"{ui_url}?msg={message_id}",
                        "style": "primary",
                    }
                ],
            },
        ]
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(SLACK_WEBHOOK_URL, json=payload)
            r.raise_for_status()
        logger.info("[notifier] Slack notification sent")
    except Exception as e:
        logger.warning("[notifier] Slack notification failed: %s", e)


async def _teams(agent_label: str, question: str, file: Optional[str],
                 message_id: str, ui_url: str) -> None:
    file_line = f"  \n**File:** `{file}`" if file else ""
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "7F77DD",
        "summary": f"{agent_label} needs input",
        "sections": [
            {
                "activityTitle": f"**{agent_label}** needs your input",
                "activitySubtitle": file_line,
                "text": question,
            }
        ],
        "potentialAction": [
            {
                "@type": "OpenUri",
                "name": "Reply in UI",
                "targets": [{"os": "default", "uri": f"{ui_url}?msg={message_id}"}],
            }
        ],
    }
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.post(TEAMS_WEBHOOK_URL, json=payload)
            r.raise_for_status()
        logger.info("[notifier] Teams notification sent")
    except Exception as e:
        logger.warning("[notifier] Teams notification failed: %s", e)
