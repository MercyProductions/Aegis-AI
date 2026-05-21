from __future__ import annotations

from .adaptive_intelligence import register_adaptive_intelligence_routes
from .agent_bridge_execution import register_agent_bridge_execution_routes
from .agent_bridge_jobs import register_agent_bridge_job_routes
from .agent_bridge_streaming import register_agent_bridge_streaming_routes
from .agent_supervision import register_agent_supervision_routes
from .autonomous_engineering import register_autonomous_engineering_routes
from .autopilot import register_autopilot_routes
from .auth import register_auth_routes
from .chat import register_chat_routes
from .checkpoints import register_checkpoint_routes
from .collaboration import register_collaboration_routes
from .config import register_config_routes
from .distributed_runtime import register_distributed_runtime_routes
from .ecosystem import register_ecosystem_routes
from .files import register_file_routes
from .governance import register_governance_routes
from .history_tasks import register_history_task_routes
from .media import register_media_routes
from .model_registry import register_model_registry_routes
from .onboarding_settings import register_onboarding_settings_routes
from .provider_accounts import register_provider_account_routes
from .productization import register_productization_routes
from .project_builder import register_project_builder_routes
from .project_intelligence import register_project_intelligence_routes
from .quality_evaluation import register_quality_evaluation_routes
from .routing_apply import register_routing_apply_routes
from .runtime import register_runtime_routes
from .runtime_convergence import register_runtime_convergence_routes
from .telemetry import register_telemetry_routes
from .utility import register_utility_routes
from .validation import register_validation_routes
from .workspace_intelligence import register_workspace_intelligence_routes
from .workspace_profile import build_workspace_profile, register_workspace_profile_routes

__all__ = [
    "build_workspace_profile",
    "register_adaptive_intelligence_routes",
    "register_agent_bridge_execution_routes",
    "register_agent_bridge_job_routes",
    "register_agent_bridge_streaming_routes",
    "register_agent_supervision_routes",
    "register_autonomous_engineering_routes",
    "register_autopilot_routes",
    "register_auth_routes",
    "register_chat_routes",
    "register_checkpoint_routes",
    "register_collaboration_routes",
    "register_config_routes",
    "register_distributed_runtime_routes",
    "register_ecosystem_routes",
    "register_file_routes",
    "register_governance_routes",
    "register_history_task_routes",
    "register_media_routes",
    "register_model_registry_routes",
    "register_onboarding_settings_routes",
    "register_provider_account_routes",
    "register_productization_routes",
    "register_project_builder_routes",
    "register_project_intelligence_routes",
    "register_quality_evaluation_routes",
    "register_routing_apply_routes",
    "register_runtime_convergence_routes",
    "register_runtime_routes",
    "register_telemetry_routes",
    "register_utility_routes",
    "register_validation_routes",
    "register_workspace_intelligence_routes",
    "register_workspace_profile_routes",
]
