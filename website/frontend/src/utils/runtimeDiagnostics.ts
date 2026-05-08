import type { AppConfig, HealthResponse, ValidationRecipe, WorkspaceProfileResponse } from '../types';
import type { ConnectionState } from './connection';

export type RuntimeDiagnosticStatus = 'ok' | 'warning' | 'error';
export type RuntimeDiagnosticActionKind = 'refresh' | 'setup_workspace' | 'run_validation';

export interface RuntimeDiagnosticAction {
  kind: RuntimeDiagnosticActionKind;
  label: string;
}

export interface RuntimeDiagnosticCheck {
  id: string;
  label: string;
  status: RuntimeDiagnosticStatus;
  detail: string;
  action?: RuntimeDiagnosticAction;
}

export interface RuntimeDiagnostics {
  status: RuntimeDiagnosticStatus;
  label: string;
  checks: RuntimeDiagnosticCheck[];
}

interface RuntimeDiagnosticsInput {
  health: HealthResponse | null;
  config: AppConfig | null;
  workspaceProfile: WorkspaceProfileResponse | null;
  validationRecipe: ValidationRecipe | null;
  connectionState: ConnectionState;
  workspaceRoot: string;
}

export function buildRuntimeDiagnostics(input: RuntimeDiagnosticsInput): RuntimeDiagnostics {
  const checks: RuntimeDiagnosticCheck[] = [
    buildBackendCheck(input.health, input.connectionState),
    buildModelCheck(input.health),
    buildConfigCheck(input.config),
    buildWorkspaceCheck(input.workspaceProfile, input.validationRecipe, input.workspaceRoot)
  ];
  const status = summarizeStatus(checks);
  return {
    status,
    label: runtimeDiagnosticsLabel(status, checks),
    checks
  };
}

function buildBackendCheck(health: HealthResponse | null, connectionState: ConnectionState): RuntimeDiagnosticCheck {
  if (!health) {
    return {
      id: 'backend',
      label: 'Backend',
      status: connectionState === 'checking' ? 'warning' : 'error',
      detail: connectionState === 'checking' ? 'Waiting for the first health check.' : 'No backend health snapshot is available.',
      action: { kind: 'refresh', label: 'Refresh' }
    };
  }
  if (health.ok && health.engine_ready) {
    return {
      id: 'backend',
      label: 'Backend',
      status: 'ok',
      detail: `${health.app || 'Aegis'} is ready.`
    };
  }
  return {
    id: 'backend',
    label: 'Backend',
    status: 'error',
    detail: health.engine_message || 'Backend responded but is not ready.',
    action: { kind: 'refresh', label: 'Refresh' }
  };
}

function buildModelCheck(health: HealthResponse | null): RuntimeDiagnosticCheck {
  if (!health) {
    return {
      id: 'model',
      label: 'Model',
      status: 'warning',
      detail: 'Model status has not loaded yet.',
      action: { kind: 'refresh', label: 'Refresh' }
    };
  }
  return {
    id: 'model',
    label: 'Model',
    status: health.model_ready ? 'ok' : 'error',
    detail:
      health.model_message ||
      (health.model_ready ? `${health.model_name || 'Configured model'} is reachable.` : 'Configured model is offline.'),
    action: health.model_ready ? undefined : { kind: 'refresh', label: 'Refresh' }
  };
}

function buildConfigCheck(config: AppConfig | null): RuntimeDiagnosticCheck {
  if (!config) {
    return {
      id: 'config',
      label: 'Config',
      status: 'warning',
      detail: 'Configuration has not loaded yet.'
    };
  }
  return {
    id: 'config',
    label: 'Config',
    status: config.default_workspace ? 'ok' : 'error',
    detail: config.default_workspace ? `Default workspace: ${config.default_workspace}` : 'Default workspace is empty.'
  };
}

function buildWorkspaceCheck(
  profile: WorkspaceProfileResponse | null,
  recipe: ValidationRecipe | null,
  workspaceRoot: string
): RuntimeDiagnosticCheck {
  if (!workspaceRoot.trim()) {
    return {
      id: 'workspace',
      label: 'Workspace',
      status: 'error',
      detail: 'No workspace root is selected.'
    };
  }
  if (!profile) {
    return {
      id: 'workspace',
      label: 'Workspace',
      status: 'warning',
      detail: 'Workspace readiness has not loaded yet.',
      action: { kind: 'refresh', label: 'Refresh' }
    };
  }

  const status = profile.readiness.status;
  const score = profile.readiness.score;
  const hasValidationCommand = Boolean(recipe?.command || profile.dependency_profile.validation_commands.length);
  if (status === 'ready') {
    return {
      id: 'workspace',
      label: 'Workspace',
      status: 'ok',
      detail: `Ready with score ${score}/100.`
    };
  }
  if (status === 'needs_repair') {
    return {
      id: 'workspace',
      label: 'Workspace',
      status: 'error',
      detail: profile.readiness.next_action || profile.readiness.summary || `Workspace needs repair (${score}/100).`,
      action: hasValidationCommand ? { kind: 'run_validation', label: 'Run validation' } : { kind: 'setup_workspace', label: 'Set up workspace' }
    };
  }
  if (shouldSetupWorkspace(profile, recipe)) {
    return {
      id: 'workspace',
      label: 'Workspace',
      status: 'warning',
      detail: profile.readiness.next_action || profile.readiness.summary || `Workspace needs attention (${score}/100).`,
      action: { kind: 'setup_workspace', label: 'Set up workspace' }
    };
  }
  if (status === 'needs_validation' && hasValidationCommand) {
    return {
      id: 'workspace',
      label: 'Workspace',
      status: 'warning',
      detail: profile.readiness.next_action || profile.readiness.summary || `Workspace needs validation (${score}/100).`,
      action: { kind: 'run_validation', label: 'Run validation' }
    };
  }
  return {
    id: 'workspace',
    label: 'Workspace',
    status: 'warning',
    detail: profile.readiness.next_action || profile.readiness.summary || `Workspace needs attention (${score}/100).`
  };
}

function summarizeStatus(checks: RuntimeDiagnosticCheck[]): RuntimeDiagnosticStatus {
  if (checks.some((check) => check.status === 'error')) return 'error';
  if (checks.some((check) => check.status === 'warning')) return 'warning';
  return 'ok';
}

function runtimeDiagnosticsLabel(status: RuntimeDiagnosticStatus, checks: RuntimeDiagnosticCheck[]): string {
  if (status === 'ok') return 'Runtime Healthy';
  if (status === 'error') return 'Runtime Issue detected';

  const warnings = checks.filter((check) => check.status === 'warning');
  if (warnings.length === 1 && warnings[0]?.id === 'workspace') return 'Workspace needs attention';
  return 'Runtime Needs attention';
}

function shouldSetupWorkspace(profile: WorkspaceProfileResponse, recipe: ValidationRecipe | null): boolean {
  if (!profile.has_manifest) return true;
  return !recipe?.command && profile.dependency_profile.validation_commands.length === 0;
}
