import os
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class PlannerConfig:
    ai_dir: Path
    tasknotes_dir: Path
    ollama_url: str
    ollama_model: str
    ollama_format: str
    ollama_num_ctx: int
    ollama_num_predict: int
    ollama_timeout_seconds: int
    timezone: ZoneInfo
    max_log_chars: int
    max_jsonl_events: int
    max_tasknotes: int
    max_tasknote_chars: int
    max_policy_chars: int
    max_control_chars: int
    max_context_chars: int

    @classmethod
    def from_env(cls):
        return cls(
            ai_dir=Path(os.environ.get("AI_DIR", "~/Sync/Perseverance.Gu/AI")).expanduser(),
            tasknotes_dir=Path(os.environ.get("TASKNOTES_DIR", "~/Sync/Perseverance.Gu/TaskNotes")).expanduser(),
            ollama_url=os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/"),
            ollama_model=os.environ.get("OLLAMA_MODEL", "gemma3:4b"),
            ollama_format=os.environ.get("OLLAMA_FORMAT", "json").strip().lower(),
            ollama_num_ctx=int(os.environ.get("OLLAMA_NUM_CTX", "4096")),
            ollama_num_predict=int(os.environ.get("OLLAMA_NUM_PREDICT", "900")),
            ollama_timeout_seconds=int(os.environ.get("OLLAMA_TIMEOUT_SECONDS", "600")),
            timezone=ZoneInfo(os.environ.get("LLM_PLANNER_TIMEZONE", "Europe/Paris")),
            max_log_chars=int(os.environ.get("MAX_LOG_CHARS", "800")),
            max_jsonl_events=int(os.environ.get("MAX_JSONL_EVENTS", "20")),
            max_tasknotes=int(os.environ.get("MAX_TASKNOTES", "5")),
            max_tasknote_chars=int(os.environ.get("MAX_TASKNOTE_CHARS", "700")),
            max_policy_chars=int(os.environ.get("MAX_POLICY_CHARS", "700")),
            max_control_chars=int(os.environ.get("MAX_CONTROL_CHARS", "1000")),
            max_context_chars=int(os.environ.get("MAX_CONTEXT_CHARS", "4500")),
        )

    @property
    def control_dir(self):
        return self.ai_dir / "control"

    @property
    def policy_dir(self):
        return self.ai_dir / "policy"

    @property
    def state_dir(self):
        return self.ai_dir / "state"

    @property
    def state_desktop_dir(self):
        return self.state_dir / "desktop"

    @property
    def state_phone_dir(self):
        return self.state_dir / "phone"

    @property
    def state_llm_dir(self):
        return self.state_dir / "llm"

    @property
    def context_dir(self):
        return self.ai_dir / "context"

    @property
    def reports_daily_dir(self):
        return self.ai_dir / "reports" / "daily"

    @property
    def proposed_tasks_dir(self):
        return self.ai_dir / "proposed-tasks"

    @property
    def outbox_to_phone_dir(self):
        return self.ai_dir / "outbox" / "to-phone"

    @property
    def events_desktop_dir(self):
        return self.ai_dir / "events" / "desktop"

    @property
    def events_phone_dir(self):
        return self.ai_dir / "events" / "phone"

    @property
    def logs_desktop_dir(self):
        return self.ai_dir / "logs" / "desktop"

    @property
    def logs_phone_dir(self):
        return self.ai_dir / "logs" / "phone"

    @property
    def anki_dir(self):
        return self.ai_dir / "anki"
