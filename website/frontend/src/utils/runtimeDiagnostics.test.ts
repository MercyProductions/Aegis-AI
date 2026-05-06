import { describe, expect, it } from 'vitest';
import { buildRuntimeDiagnostics } from './runtimeDiagnostics';
import type { AppConfig, HealthResponse, WorkspaceProfileResponse } from '../types';

const health: HealthResponse = {
  ok: true,
  ready: true,
  status: 'ready',
  app: 'Aegis Coding AI',
  version: '0.3.0',
  engine: 'Aegis Core / qwen2.5-coder:7b',
  engine_ready: true,
  engine_message: 'ready',
  model_name: 'qwen2.5-coder:7b',
  model_api: 'ollama',
  model_endpoint: 'http://127.0.0.1:11434',
  model_ready: true,
  model_message: 'model ready',
  project_root: 'C:/project',
  workspace_root: 'C:/project/workspace',
  database_path: 'C:/project/data/aegis.sqlite3',
  env_exists: true
};

const config: AppConfig = {
  assistant_name: 'Aegis AI',
  assistant_mission: 'Build software',
  default_mode: 'build',
  modes: [],
  default_workspace: 'C:/project/workspace',
  engine: 'Aegis Core / qwen2.5-coder:7b',
  engine_ready: true,
  engine_message: 'ready',
  model_name: 'qwen2.5-coder:7b',
  model_endpoint: 'http://127.0.0.1:11434',
  model_api: 'ollama',
  model_ready: true,
  model_message: 'model ready',
  database_path: 'C:/project/data/aegis.sqlite3',
  command_allowlist: 'node,npm',
  command_timeout_seconds: 120,
  auto_run_validation: false,
  shared_workspace_mode: false,
  feedback_capture_excerpts: true,
  feedback_redaction_enabled: true,
  feedback_max_excerpt_chars: 320,
  feedback_hash_content: true,
  env_exists: true
};

const profile: WorkspaceProfileResponse = {
  workspace_root: 'C:/project/workspace',
  manifest: null,
  has_manifest: true,
  dependency_profile: {
    project_type: 'node',
    languages: ['JavaScript'],
    frameworks: [],
    package_managers: ['npm'],
    build_systems: ['Node.js'],
    config_files: ['package.json'],
    entry_points: [],
    test_files: [],
    install_commands: ['npm install'],
    validation_commands: ['npm test'],
    scripts: [],
    dependencies: [],
    dev_dependencies: [],
    database_tools: [],
    warnings: []
  },
  instruction_status: {},
  has_instruction_status: false,
  validation_plan: {},
  has_validation_plan: false,
  readiness: {
    status: 'ready',
    score: 90,
    summary: 'Ready',
    next_action: '',
    blockers: [],
    signals: []
  },
  recommendations: []
};

describe('runtime diagnostics', () => {
  it('reports healthy when backend, model, config, and workspace are ready', () => {
    const result = buildRuntimeDiagnostics({
      health,
      config,
      workspaceProfile: profile,
      validationRecipe: {
        command: 'npm test',
        label: 'npm test',
        source: 'manual',
        updated_at: '2026-05-05T00:00:00Z',
        notes: ''
      },
      connectionState: 'connected',
      workspaceRoot: 'C:/project/workspace'
    });

    expect(result.status).toBe('ok');
    expect(result.label).toBe('Runtime Healthy');
    expect(result.checks.every((check) => check.status === 'ok')).toBe(true);
  });

  it('promotes an offline model to an error', () => {
    const result = buildRuntimeDiagnostics({
      health: { ...health, model_ready: false, model_message: 'Ollama is offline' },
      config,
      workspaceProfile: profile,
      validationRecipe: null,
      connectionState: 'connected',
      workspaceRoot: 'C:/project/workspace'
    });

    expect(result.status).toBe('error');
    expect(result.checks.find((check) => check.id === 'model')).toMatchObject({
      status: 'error',
      detail: 'Ollama is offline'
    });
  });

  it('treats pending validation as a warning instead of a fatal error', () => {
    const result = buildRuntimeDiagnostics({
      health,
      config,
      workspaceProfile: {
        ...profile,
        readiness: {
          ...profile.readiness,
          status: 'needs_validation',
          score: 65,
          next_action: 'Run validation command: npm test'
        }
      },
      validationRecipe: {
        command: 'npm test',
        label: 'npm test',
        source: 'manual',
        updated_at: '2026-05-05T00:00:00Z',
        notes: ''
      },
      connectionState: 'connected',
      workspaceRoot: 'C:/project/workspace'
    });

    expect(result.status).toBe('warning');
    expect(result.label).toBe('Workspace needs attention');
    expect(result.checks.find((check) => check.id === 'workspace')).toMatchObject({
      status: 'warning',
      detail: 'Run validation command: npm test'
    });
  });

  it('reports missing health snapshots as an offline runtime problem', () => {
    const result = buildRuntimeDiagnostics({
      health: null,
      config,
      workspaceProfile: profile,
      validationRecipe: null,
      connectionState: 'offline',
      workspaceRoot: 'C:/project/workspace'
    });

    expect(result.status).toBe('error');
    expect(result.checks.find((check) => check.id === 'backend')?.status).toBe('error');
  });

  it('offers workspace setup when the workspace has no manifest or validator', () => {
    const result = buildRuntimeDiagnostics({
      health,
      config,
      workspaceProfile: {
        ...profile,
        has_manifest: false,
        dependency_profile: {
          ...profile.dependency_profile,
          validation_commands: []
        },
        readiness: {
          status: 'unconfigured',
          score: 25,
          summary: 'Not configured',
          next_action: 'Add or generate a project manifest with install and validation commands.',
          blockers: ['No .aegis/project.json manifest is present.'],
          signals: []
        }
      },
      validationRecipe: null,
      connectionState: 'connected',
      workspaceRoot: 'C:/project/workspace'
    });

    expect(result.checks.find((check) => check.id === 'workspace')?.action).toEqual({
      kind: 'setup_workspace',
      label: 'Set up workspace'
    });
  });

  it('offers validation when readiness is waiting on a configured validator', () => {
    const result = buildRuntimeDiagnostics({
      health,
      config,
      workspaceProfile: {
        ...profile,
        readiness: {
          status: 'needs_validation',
          score: 70,
          summary: 'Needs validation',
          next_action: 'Run validation command: npm test',
          blockers: [],
          signals: []
        }
      },
      validationRecipe: {
        command: 'npm test',
        label: 'npm test',
        source: 'manual',
        updated_at: '2026-05-05T00:00:00Z',
        notes: ''
      },
      connectionState: 'connected',
      workspaceRoot: 'C:/project/workspace'
    });

    expect(result.checks.find((check) => check.id === 'workspace')?.action).toEqual({
      kind: 'run_validation',
      label: 'Run validation'
    });
  });
});
