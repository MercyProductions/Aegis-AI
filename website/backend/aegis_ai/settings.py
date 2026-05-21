# backend/settings.py
import shutil
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from dotenv import set_key
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
LEGACY_ENV_FILE = BACKEND_ROOT / ".env"
ENV_TEMPLATE = """AEGIS_ASSISTANT_NAME=Auralith Prime
AEGIS_ASSISTANT_MISSION=A local-first AI operating environment for coding, automation, research, orchestration, creative workflows, and intelligent task execution.
DEFAULT_MODE=build
DEFAULT_WORKSPACE=workspace
AEGIS_MODEL_API=ollama
AEGIS_MODEL_ENDPOINT=http://127.0.0.1:11434
AEGIS_MODEL_NAME=qwen2.5-coder:7b
AEGIS_CORE_API_URL=http://127.0.0.1:8788
AEGIS_CORE_DELEGATED_WORKFLOWS_ENABLED=true
AEGIS_CORE_REQUEST_TIMEOUT_SECONDS=8
AEGIS_LOCAL_API_TOKEN=
AEGIS_REQUIRE_LOCAL_API_TOKEN=false
AEGIS_CORE_LOCAL_TOKEN=
AEGIS_ALLOWED_ORIGINS=
AEGIS_MAX_REQUEST_BYTES=8000000
AEGIS_RATE_LIMIT_PER_MINUTE=600
AEGIS_PRIVACY_MODE=local_first
AEGIS_CLOUD_DISABLED=false
AEGIS_ROUTER_EXECUTION_ENABLED=true
AEGIS_ALLOW_EXPLICIT_WORKSPACE_PATHS=true
AEGIS_ADDITIONAL_WORKSPACE_ROOTS=
AEGIS_SHARED_WORKSPACE_MODE=false
AEGIS_FEEDBACK_CAPTURE_EXCERPTS=true
AEGIS_FEEDBACK_REDACTION_ENABLED=true
AEGIS_FEEDBACK_MAX_EXCERPT_CHARS=320
AEGIS_FEEDBACK_HASH_CONTENT=true
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
OPENROUTER_API_KEY=
PERPLEXITY_API_KEY=
XAI_API_KEY=
GROQ_API_KEY=
MISTRAL_API_KEY=
DEEPSEEK_API_KEY=
TOGETHER_API_KEY=
CEREBRAS_API_KEY=
FIREWORKS_API_KEY=
COHERE_API_KEY=
GEMINI_API_KEY=
HUGGINGFACE_API_KEY=
NVIDIA_API_KEY=
SAMBANOVA_API_KEY=
AEGIS_DATABASE_PATH=data/aegis.sqlite3
APPROVAL_TIER=guided
SANDBOX_PROFILE=standard
AEGIS_COMMAND_ALLOWLIST=python,py,node,npm,npx,pnpm,yarn,bun,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet,cmake,ctest,msbuild,ninja,make,gradle,gradlew,mvn,mvnw,javac,java,flutter,swift,powershell,pwsh,ruff,mypy,sqlfluff
AEGIS_COMMAND_TIMEOUT_SECONDS=120
AEGIS_AUTO_RUN_VALIDATION=false
AEGIS_MAX_WRITE_BYTES=1000000
AEGIS_MAX_CONTEXT_CHARS=128000
"""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    aegis_assistant_name: str = Field(default="Auralith Prime", alias="AEGIS_ASSISTANT_NAME")
    aegis_assistant_mission: str = Field(
        default="A local-first AI operating environment for coding, automation, research, orchestration, creative workflows, and intelligent task execution.",
        alias="AEGIS_ASSISTANT_MISSION",
    )
    default_mode: str = Field(default="build", alias="DEFAULT_MODE")
    default_workspace: str = Field(default="workspace", alias="DEFAULT_WORKSPACE")
    aegis_workspace_root: str = Field(default=str(PROJECT_ROOT.parent), alias="AEGIS_WORKSPACE_ROOT")
    aegis_allow_explicit_workspace_paths: bool = Field(default=True, alias="AEGIS_ALLOW_EXPLICIT_WORKSPACE_PATHS")
    aegis_additional_workspace_roots: str = Field(default="", alias="AEGIS_ADDITIONAL_WORKSPACE_ROOTS")
    aegis_model_api: str = Field(default="ollama", alias="AEGIS_MODEL_API")
    aegis_model_endpoint: str = Field(default="http://127.0.0.1:11434", alias="AEGIS_MODEL_ENDPOINT")
    aegis_model_name: str = Field(default="qwen2.5-coder:7b", alias="AEGIS_MODEL_NAME")
    aegis_core_api_url: str = Field(default="http://127.0.0.1:8788", alias="AEGIS_CORE_API_URL")
    aegis_core_delegated_workflows_enabled: bool = Field(default=True, alias="AEGIS_CORE_DELEGATED_WORKFLOWS_ENABLED")
    aegis_core_request_timeout_seconds: float = Field(default=8.0, alias="AEGIS_CORE_REQUEST_TIMEOUT_SECONDS")
    aegis_local_api_token: str = Field(default="", alias="AEGIS_LOCAL_API_TOKEN")
    aegis_require_local_api_token: bool = Field(default=False, alias="AEGIS_REQUIRE_LOCAL_API_TOKEN")
    aegis_core_local_token: str = Field(default="", alias="AEGIS_CORE_LOCAL_TOKEN")
    aegis_allowed_origins: str = Field(default="", alias="AEGIS_ALLOWED_ORIGINS")
    aegis_max_request_bytes: int = Field(default=8_000_000, alias="AEGIS_MAX_REQUEST_BYTES")
    aegis_rate_limit_per_minute: int = Field(default=600, alias="AEGIS_RATE_LIMIT_PER_MINUTE")
    aegis_privacy_mode: str = Field(default="local_first", alias="AEGIS_PRIVACY_MODE")
    aegis_cloud_disabled: bool = Field(default=False, alias="AEGIS_CLOUD_DISABLED")
    aegis_model_timeout_seconds: float = Field(default=120.0, alias="AEGIS_MODEL_TIMEOUT_SECONDS")
    aegis_model_temperature: float = Field(default=0.2, alias="AEGIS_MODEL_TEMPERATURE")
    aegis_router_execution_enabled: bool = Field(default=True, alias="AEGIS_ROUTER_EXECUTION_ENABLED")
    aegis_shared_workspace_mode: bool = Field(default=False, alias="AEGIS_SHARED_WORKSPACE_MODE")
    aegis_feedback_capture_excerpts: bool = Field(default=True, alias="AEGIS_FEEDBACK_CAPTURE_EXCERPTS")
    aegis_feedback_redaction_enabled: bool = Field(default=True, alias="AEGIS_FEEDBACK_REDACTION_ENABLED")
    aegis_feedback_max_excerpt_chars: int = Field(default=320, alias="AEGIS_FEEDBACK_MAX_EXCERPT_CHARS")
    aegis_feedback_hash_content: bool = Field(default=True, alias="AEGIS_FEEDBACK_HASH_CONTENT")
    aegis_database_path: str = Field(default="data/aegis.sqlite3", alias="AEGIS_DATABASE_PATH")
    approval_tier: str = Field(default="guided", alias="APPROVAL_TIER")
    sandbox_profile: str = Field(default="standard", alias="SANDBOX_PROFILE")
    aegis_command_allowlist: str = Field(
        default="python,py,node,npm,npx,pnpm,yarn,bun,pytest,uvicorn,tsc,vite,cargo,rustc,go,dotnet,cmake,ctest,msbuild,ninja,make,gradle,gradlew,mvn,mvnw,javac,java,flutter,swift,powershell,pwsh,ruff,mypy,sqlfluff",
        alias="AEGIS_COMMAND_ALLOWLIST",
    )
    aegis_command_timeout_seconds: int = Field(default=120, alias="AEGIS_COMMAND_TIMEOUT_SECONDS")
    aegis_auto_run_validation: bool = Field(default=False, alias="AEGIS_AUTO_RUN_VALIDATION")
    max_write_bytes: int = Field(default=1_000_000, alias="AEGIS_MAX_WRITE_BYTES")
    max_context_chars: int = Field(default=128_000, alias="AEGIS_MAX_CONTEXT_CHARS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()


def has_env_file() -> bool:
    return ENV_FILE.exists() or LEGACY_ENV_FILE.exists()


def ensure_env_file() -> None:
    if not ENV_FILE.exists():
        if LEGACY_ENV_FILE.exists():
            ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(LEGACY_ENV_FILE, ENV_FILE)
        else:
            ENV_FILE.write_text(ENV_TEMPLATE, encoding="utf-8")


def update_env(values: Mapping[str, str]) -> None:
    ensure_env_file()
    env_path = str(ENV_FILE)
    for key, value in values.items():
        set_key(env_path, key, value, quote_mode="auto")
