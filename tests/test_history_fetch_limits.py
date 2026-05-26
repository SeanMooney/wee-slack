from __future__ import annotations

from typing import Any, Mapping

import pytest

from slack.slack_api import SlackApi
from slack.slack_message import SlackMessage
from slack.task import create_task


def run_coroutine(coroutine):
    task = create_task(coroutine)
    return task.result()


@pytest.mark.parametrize(
    ("method_name", "expected_method", "expected_params"),
    [
        (
            "fetch_conversations_history",
            "conversations.history",
            {"limit": 50},
        ),
        (
            "fetch_conversations_history_after",
            "conversations.history",
            {"oldest": "123.456", "inclusive": True},
        ),
        (
            "fetch_conversations_replies",
            "conversations.replies",
            {"ts": "123.456"},
        ),
    ],
)
def test_history_fetches_use_workspace_history_fetch_count(
    workspace, channel_public, method_name, expected_method, expected_params
):
    workspace.config.history_fetch_count.value = 50
    api = SlackApi(workspace)
    fetch_calls = []

    async def mock_fetch(method, params={}):
        fetch_calls.append((method, params))
        return {"ok": True, "messages": []}

    api._fetch = mock_fetch

    if method_name == "fetch_conversations_history":
        run_coroutine(api.fetch_conversations_history(channel_public))
    elif method_name == "fetch_conversations_history_after":
        run_coroutine(
            api.fetch_conversations_history_after(channel_public, "123.456", True)
        )
    elif method_name == "fetch_conversations_replies":
        run_coroutine(api.fetch_conversations_replies(channel_public, "123.456"))
    else:
        raise AssertionError(f"Unknown method name: {method_name}")

    if method_name == "fetch_conversations_history":
        assert fetch_calls == [
            (expected_method, {"channel": channel_public.id, **expected_params})
        ]
    else:
        assert fetch_calls == [
            (
                expected_method,
                {"channel": channel_public.id, **expected_params, "limit": 50},
            )
        ]


def test_fetch_conversations_replies_uses_explicit_limit(workspace, channel_public):
    workspace.config.history_fetch_count.value = 50
    api = SlackApi(workspace)
    fetch_calls = []

    async def mock_fetch(method, params={}):
        fetch_calls.append((method, params))
        return {"ok": True, "messages": []}

    api._fetch = mock_fetch

    run_coroutine(api.fetch_conversations_replies(channel_public, "123.456", limit=11))

    assert fetch_calls == [
        (
            "conversations.replies",
            {"channel": channel_public.id, "ts": "123.456", "limit": 11},
        )
    ]


def test_fetch_inline_thread_replies_uses_thread_limits(channel_public):
    channel_public.workspace.config.threads_fetch_count.value = 2
    channel_public.workspace.config.thread_replies_fetch_count.value = 3

    messages = [
        SlackMessage(channel_public, _message_json("1000.000000", reply_count=1)),
        SlackMessage(channel_public, _message_json("1001.000000", reply_count=1)),
        SlackMessage(channel_public, _message_json("1002.000000", reply_count=1)),
        SlackMessage(channel_public, _message_json("1003.000000")),
    ]

    async def fetch_replies(thread_ts, limit=None):
        fetch_replies.calls.append((thread_ts, limit))
        parent_message = SlackMessage(channel_public, _message_json(thread_ts))
        return parent_message, []

    fetch_replies.calls = []
    channel_public.fetch_replies = fetch_replies

    run_coroutine(channel_public.fetch_inline_thread_replies(messages))

    assert fetch_replies.calls == [
        ("1000.000000", 4),
        ("1001.000000", 4),
    ]


def test_fetch_inline_thread_replies_skips_when_reply_limit_is_zero(channel_public):
    channel_public.workspace.config.threads_fetch_count.value = 2
    channel_public.workspace.config.thread_replies_fetch_count.value = 0
    messages = [
        SlackMessage(channel_public, _message_json("1000.000000", reply_count=1)),
    ]

    async def fetch_replies(thread_ts, limit=None):
        fetch_replies.calls.append((thread_ts, limit))
        parent_message = SlackMessage(channel_public, _message_json(thread_ts))
        return parent_message, []

    fetch_replies.calls = []
    channel_public.fetch_replies = fetch_replies

    run_coroutine(channel_public.fetch_inline_thread_replies(messages))

    assert fetch_replies.calls == []


def _message_json(ts: str, reply_count: int = 0) -> Mapping[str, Any]:
    message = {
        "type": "message",
        "text": f"message {ts}",
        "user": "U0D7ZA4Q7",
        "ts": ts,
    }
    if reply_count:
        message.update(
            {
                "reply_count": reply_count,
                "reply_users_count": 1,
                "latest_reply": ts,
                "reply_users": ["U0D7ZA4Q7"],
                "thread_ts": ts,
            }
        )
    return message
