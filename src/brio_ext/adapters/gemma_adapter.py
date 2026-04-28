"""Gemma 4 family prompt adapter.

Mirrors the chat template shipped with `google/gemma-4-*` models, which uses
turn markers `<|turn>...<turn|>` and a thinking channel `<|channel>...<channel|>`.
Tools and multimodal content are out of scope (BrioDocs does not use them with
this adapter), so this implementation handles only system / user / assistant
text turns.
"""

from __future__ import annotations

import re
from typing import Dict, List

from brio_ext.adapters import ChatAdapter, RenderedPrompt

_TURN_OPEN = "<|turn>"
_TURN_CLOSE = "<turn|>"
_CHANNEL_OPEN = "<|channel>"
_CHANNEL_CLOSE = "<channel|>"
_THINK = "<|think|>"

_THINKING_BLOCK_RE = re.compile(
    re.escape(_CHANNEL_OPEN) + r".*?" + re.escape(_CHANNEL_CLOSE),
    re.DOTALL,
)
# Strips globally, not just at the start of a response — if the model literally
# discusses the string `<|turn>model` (e.g. when asked about the chat template
# itself) the substring is eaten. Acceptable: BrioDocs prompts never ask about
# the template, so the collision is unreachable in practice.
_TURN_HEADER_RE = re.compile(
    re.escape(_TURN_OPEN) + r"(?:user|model|system|developer)\n?"
)


class Gemma4Adapter(ChatAdapter):
    """Render Esperanto messages into Gemma 4 turn-based prompts."""

    def can_handle(self, model_id: str) -> bool:
        lower = (model_id or "").lower()
        # Match only Gemma 4 — earlier and future Gemma generations use
        # different chat templates and need their own adapters.
        return "gemma-4" in lower or "gemma4" in lower

    def render(self, messages: List[Dict[str, str]], no_think: bool = False) -> RenderedPrompt:
        """
        Render messages into a Gemma 4 E4B prompt.

        Diverges from the chat template on one shape: when two non-tool
        assistant messages appear back-to-back, the template
        (chat_template.jinja lines 218-233) suppresses the
        ``<|turn>model\\n`` opener on the second one so the pair renders
        as a single continued model turn. This adapter emits a fresh
        opener for every assistant message instead. The continuation rule
        exists for tool-call flows (``assistant(tool_calls) ->
        tool(result) -> assistant(answer)``), which BrioDocs does not
        produce — every turn has exactly one assistant message and tools
        are not used. See
        ``test_consecutive_assistants_diverges_from_template`` for the
        byte-level difference.

        Args:
            messages: Conversation messages with ``role`` and ``content``
                keys. Must contain at least one message; ``content`` may
                be an empty string but not ``None``.
            no_think: When True, omit the ``<|think|>`` system marker so
                the model is not steered toward an extended reasoning
                phase.

        Returns:
            A ``RenderedPrompt`` with the prompt string and stop sequences.

        Raises:
            ValueError: If ``messages`` is empty, or any message has
                ``content`` set to ``None``. Both cases would also error
                inside the Jinja template (``messages[0]`` IndexError,
                ``| trim`` on ``None``); raising here produces a clearer
                signal at the call site.
            NotImplementedError: If any message has ``role == "tool"``.
                Tools are out of scope for this adapter (see the module
                docstring); silently dropping them would produce a
                corrupted assistant/tool/assistant turn sequence, so we
                fail loudly instead.
        """
        if not messages:
            raise ValueError("messages must contain at least one message")
        for i, msg in enumerate(messages):
            if msg.get("content") is None:
                raise ValueError(
                    f"messages[{i}] has content=None; pass an empty string "
                    f"for explicitly empty content"
                )

        thinking_enabled = not no_think
        parts: List[str] = []

        first_is_system = messages[0].get("role") in ("system", "developer")

        # Template opens a system turn whenever thinking is enabled or the first
        # message is system/developer (chat_template.jinja line 179).
        if thinking_enabled or first_is_system:
            parts.append(f"{_TURN_OPEN}system\n")
            if thinking_enabled:
                parts.append(f"{_THINK}\n")
            if first_is_system:
                parts.append(messages[0]["content"].strip())
            parts.append(f"{_TURN_CLOSE}\n")

        loop_messages = messages[1:] if first_is_system else messages
        for msg in loop_messages:
            role = msg.get("role")
            if role == "tool":
                raise NotImplementedError(
                    "Gemma 4 adapter does not support tool messages"
                )
            rendered_role = "model" if role == "assistant" else role
            content = msg["content"]
            if rendered_role == "model":
                content = self._strip_thinking_block(content)
            content = content.strip()

            parts.append(f"{_TURN_OPEN}{rendered_role}\n")
            parts.append(content)
            parts.append(f"{_TURN_CLOSE}\n")

        parts.append(f"{_TURN_OPEN}model\n")
        # Note: the Gemma 4 E4B template emits no further prefill. Some larger
        # variants (e.g. 26B-A4B-it) append `<|channel>thought\n<channel|>` to
        # signal "skip reasoning", but on E4B that prefill is interpreted as an
        # opening signal and triggers reasoning instead — clean_response below
        # strips any leaked reasoning before the first `<channel|>`.

        return {"prompt": "".join(parts), "stop": [_TURN_CLOSE]}

    def clean_response(self, text: str) -> str:
        # The E4B model often emits `<reasoning><channel|><answer>` even though
        # the prompt doesn't open a channel — the reasoning lives implicitly
        # before the closing `<channel|>`. Drop that prefix.
        if _CHANNEL_OPEN not in text and _CHANNEL_CLOSE in text:
            text = text.split(_CHANNEL_CLOSE, 1)[1]

        cleaned = _THINKING_BLOCK_RE.sub("", text)
        if _CHANNEL_OPEN in cleaned:
            cleaned = cleaned.split(_CHANNEL_OPEN)[0]
        cleaned = _TURN_HEADER_RE.sub("", cleaned)
        for marker in (_TURN_CLOSE, _CHANNEL_CLOSE, _THINK):
            cleaned = cleaned.replace(marker, "")
        return cleaned.strip()

    @staticmethod
    def _strip_thinking_block(text: str) -> str:
        result = _THINKING_BLOCK_RE.sub("", text)
        if _CHANNEL_OPEN in result:
            result = result.split(_CHANNEL_OPEN)[0]
        return result
