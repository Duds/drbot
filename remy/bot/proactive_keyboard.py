"""
Unified keyboard factory for proactive messages (US-proactive-button-consistency).

All proactive triggers (briefing, check-ins, reminders) attach action buttons
via make_proactive_keyboard. Standard actions: Done (dismiss), Snooze 1h, Snooze 4h.
"""

from __future__ import annotations

from enum import auto, Enum

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Callback data prefix and action codes (Telegram callback_data max 64 bytes)
_CB_PREFIX = "pa:"
_DISMISS = "D"
_SNOOZE_1H = "S1"
_SNOOZE_4H = "S4"


class ProactiveAction(Enum):
    """Standard proactive message actions."""

    DISMISS = auto()
    SNOOZE_1H = auto()
    SNOOZE_4H = auto()


_BUTTONS: dict[ProactiveAction, tuple[str, str]] = {
    ProactiveAction.DISMISS: ("✅ Done", _DISMISS),
    ProactiveAction.SNOOZE_1H: ("💤 Snooze 1h", _SNOOZE_1H),
    ProactiveAction.SNOOZE_4H: ("💤 Snooze 4h", _SNOOZE_4H),
}


def make_proactive_keyboard(
    actions: list[ProactiveAction],
    context_id: str | None = None,
) -> InlineKeyboardMarkup:
    """
    Build a standard proactive action keyboard.

    actions: list of ProactiveAction to show (e.g. [DISMISS, SNOOZE_1H]).
    context_id: optional token or id for callbacks (e.g. reminder token, "briefing:date").
    Callback data format: "pa:{code}:{context_id}" so handlers can route by code and context.
    """
    ctx = (context_id or "").strip()
    if len(ctx) > 50:
        ctx = ctx[:50]  # keep under 64 bytes with prefix
    row = []
    for action in actions:
        if action not in _BUTTONS:
            continue
        label, code = _BUTTONS[action]
        cb_data = f"{_CB_PREFIX}{code}:{ctx}"
        if len(cb_data) <= 64:
            row.append(InlineKeyboardButton(label, callback_data=cb_data))
    if not row:
        return InlineKeyboardMarkup([[]])
    return InlineKeyboardMarkup([row])


def parse_proactive_callback(callback_data: str) -> tuple[str, str] | None:
    """
    Parse callback_data from make_proactive_keyboard.
    Returns (action_code, context_id) or None if not a proactive action.
    """
    if not callback_data.startswith(_CB_PREFIX):
        return None
    rest = callback_data[len(_CB_PREFIX) :]
    if ":" not in rest:
        return (rest, "")
    code, _, ctx = rest.partition(":")
    return (code, ctx)
