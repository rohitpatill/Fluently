"""Core chat flow: rebuild history, assemble prompt, run tool-calling loop, persist."""

import json

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage

from .. import repo
from ..models import Conversation, Message
from ..prompts import OPENER_INSTRUCTION, TITLE_SYSTEM
from . import prompt_builder
from .agent_tools import build_tools
from .llm_service import get_chat_model, get_utility_model
from .model_service import resolve_for_user

MAX_TOOL_ITERATIONS = 6


def _history_messages(conversation: Conversation) -> list:
    """Rebuild the LangChain message array from stored messages, including past tool calls
    (AIMessage with tool_calls + matching ToolMessages) so the model keeps full transparency."""
    out = []
    for m in conversation.messages:
        if m.role == "user":
            out.append(HumanMessage(content=m.content))
        else:
            if m.tool_calls:
                for tc in m.tool_calls:
                    out.append(
                        AIMessage(
                            content="",
                            tool_calls=[{"name": tc["name"], "args": tc["args"], "id": tc["id"], "type": "tool_call"}],
                        )
                    )
                    out.append(ToolMessage(content=tc["output"], tool_call_id=tc["id"]))
            out.append(AIMessage(content=m.content))
    return out


def _next_seq(conversation: Conversation) -> int:
    return (conversation.messages[-1].seq + 1) if conversation.messages else 1


def run_agent_turn(
    conversation: Conversation,
    user_content: str | None,
    provider: str | None = None,
    model_name: str | None = None,
    extra_instruction: str | None = None,
) -> Message:
    """One full turn: optional user message -> agent loop with tools -> stored assistant message.
    If user_content is None, the model opens the conversation itself (opener flow)."""

    # ensure we have the current message list to compute seq + rebuild history
    repo.load_messages(conversation)

    if user_content is not None:
        user_msg = Message(
            conversation_id=conversation.id, seq=_next_seq(conversation),
            role="user", content=user_content, user_id=conversation.user_id,
        )
        repo.insert_message(user_msg)
        conversation.messages.append(user_msg)

    system = prompt_builder.build_system_prompt(conversation)

    messages: list = [SystemMessage(content=system)] + _history_messages(conversation)

    # An extra instruction (e.g. the opener directive) is delivered as a HumanMessage, NOT
    # appended to the system prompt. This keeps `contents` non-empty on the opener flow
    # (user_content=None, no history) — Gemini (google_genai) rejects a system-only request
    # with `ValueError: contents are required.`
    if extra_instruction:
        messages.append(HumanMessage(content=extra_instruction))

    # Resolve THIS user's chosen model + key (Swift/Sage). Governs every call this turn.
    resolved = resolve_for_user(conversation.user_id)

    tools = build_tools(current_conversation_id=conversation.id, user_id=conversation.user_id)
    tool_map = {t.name: t for t in tools}
    llm = get_chat_model(
        provider or resolved.provider,
        model_name or resolved.model,
        api_key=resolved.api_key,
    ).bind_tools(tools)

    executed_tool_calls: list[dict] = []
    response = llm.invoke(messages)

    iterations = 0
    while getattr(response, "tool_calls", None) and iterations < MAX_TOOL_ITERATIONS:
        iterations += 1
        messages.append(response)
        for tc in response.tool_calls:
            tool_fn = tool_map.get(tc["name"])
            if tool_fn is None:
                output = f"Unknown tool: {tc['name']}"
            else:
                try:
                    output = tool_fn.invoke(tc["args"])
                except Exception as e:  # tool errors go back to the model, never crash the turn
                    output = f"Tool error: {e}"
            output = output if isinstance(output, str) else json.dumps(output)
            executed_tool_calls.append({"id": tc["id"], "name": tc["name"], "args": tc["args"], "output": output})
            messages.append(ToolMessage(content=output, tool_call_id=tc["id"]))
        response = llm.invoke(messages)

    content = response.content if isinstance(response.content, str) else _flatten_content(response.content)

    assistant_msg = Message(
        conversation_id=conversation.id,
        seq=_next_seq(conversation),
        role="assistant",
        content=content,
        tool_calls=executed_tool_calls,
        user_id=conversation.user_id,
    )
    repo.insert_message(assistant_msg)
    conversation.messages.append(assistant_msg)
    repo.touch_conversation(conversation.id)

    _maybe_set_title(conversation, resolved)
    return assistant_msg


def generate_opener(conversation: Conversation) -> Message:
    return run_agent_turn(conversation, user_content=None, extra_instruction=OPENER_INSTRUCTION)


def _flatten_content(blocks) -> str:
    parts = []
    for b in blocks:
        if isinstance(b, str):
            parts.append(b)
        elif isinstance(b, dict) and b.get("type") == "text":
            parts.append(b.get("text", ""))
    return "".join(parts)


def _maybe_set_title(conversation: Conversation, resolved) -> None:
    """Auto-title after the first exchange."""
    if conversation.title != "New conversation" or len(conversation.messages) < 2:
        return
    try:
        transcript = "\n".join(f"{m.role}: {m.content[:300]}" for m in conversation.messages[:4])
        llm = get_utility_model(resolved.provider, resolved.model, api_key=resolved.api_key, temperature=0.3)
        raw = llm.invoke([SystemMessage(content=TITLE_SYSTEM), HumanMessage(content=transcript)]).content
        title = raw if isinstance(raw, str) else _flatten_content(raw)  # Gemini returns block lists
        if title.strip():
            conversation.title = title.strip().strip('"')[:200]
            repo.save_conversation(conversation)
    except Exception:
        pass  # a failed title must never break the chat
