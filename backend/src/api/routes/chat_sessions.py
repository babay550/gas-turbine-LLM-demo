"""会话持久化 — JSON 文件存储对话历史。"""

import json
import os
import uuid
from datetime import datetime

from fastapi import APIRouter

router = APIRouter()

_SESSIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "chat_sessions")
)


def _ensure_dir():
    os.makedirs(_SESSIONS_DIR, exist_ok=True)


def _session_path(session_id: str) -> str:
    return os.path.join(_SESSIONS_DIR, f"{session_id}.json")


def _read_session(session_id: str) -> dict | None:
    path = _session_path(session_id)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_session(data: dict):
    _ensure_dir()
    path = _session_path(data["id"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _summary(session: dict) -> dict:
    return {
        "id": session["id"],
        "title": session["title"],
        "created": session["created"],
        "updated": session["updated"],
        "message_count": len(session.get("messages", [])),
    }


@router.get("/sessions")
async def list_sessions():
    _ensure_dir()
    sessions = []
    for fname in os.listdir(_SESSIONS_DIR):
        if not fname.endswith(".json"):
            continue
        path = os.path.join(_SESSIONS_DIR, fname)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            sessions.append(_summary(data))
        except (json.JSONDecodeError, KeyError):
            continue
    sessions.sort(key=lambda s: s["updated"], reverse=True)
    return {"sessions": sessions, "total": len(sessions)}


@router.post("/sessions")
async def create_session():
    now = datetime.now().isoformat(timespec="seconds")
    session = {
        "id": uuid.uuid4().hex[:12],
        "title": "新对话",
        "created": now,
        "updated": now,
        "messages": [],
    }
    _write_session(session)
    return session


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    data = _read_session(session_id)
    if not data:
        return {"error": "Session not found"}
    return data


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    path = _session_path(session_id)
    if os.path.exists(path):
        os.remove(path)
    return {"success": True}


def append_message(session_id: str, role: str, content: str,
                   citations: list | None = None, debug_logs: list | None = None):
    """向指定会话追加一条消息（由 chat.py 调用）。"""
    session = _read_session(session_id)
    if not session:
        return
    now = datetime.now().isoformat(timespec="seconds")
    msg: dict = {"role": role, "content": content, "timestamp": now}
    if citations:
        msg["citations"] = citations
    if debug_logs:
        msg["debug_logs"] = debug_logs

    session["messages"].append(msg)
    session["updated"] = now

    # 第一条用户消息自动设 title
    if role == "user" and session["title"] == "新对话":
        session["title"] = content[:20] + ("..." if len(content) > 20 else "")

    _write_session(session)
