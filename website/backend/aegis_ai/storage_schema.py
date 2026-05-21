from __future__ import annotations

import sqlite3


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row["name"] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    if not existing:
        return
    for name, ddl in columns.items():
        if name not in existing:
            conn.execute(f"alter table {table} add column {name} {ddl}")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    row = conn.execute("select name from sqlite_master where type = 'table' and name = ?", (table,)).fetchone()
    return row is not None


def ensure_task_columns(conn: sqlite3.Connection) -> None:
    columns: dict[str, str] = {
        "updated_at": "text",
        "completed_at": "text",
        "project_id": "text not null default ''",
        "parent_task_id": "text",
        "title": "text not null default ''",
        "user_goal": "text not null default ''",
        "priority": "integer not null default 0",
        "assigned_agent_role": "text not null default ''",
        "related_files_json": "text not null default '[]'",
        "validation_commands_json": "text not null default '[]'",
        "checkpoints_json": "text not null default '[]'",
        "error_summary": "text not null default ''",
        "final_summary": "text not null default ''",
    }
    _ensure_columns(conn, "tasks", columns)
    conn.execute("update tasks set updated_at = coalesce(updated_at, created_at) where updated_at is null or updated_at = ''")
    conn.execute("update tasks set completed_at = coalesce(completed_at, finished_at) where completed_at is null and finished_at is not null")
    conn.execute("update tasks set project_id = workspace_root where project_id = ''")
    conn.execute("update tasks set user_goal = message where user_goal = ''")
    conn.execute("update tasks set title = substr(message, 1, 80) where title = ''")


def ensure_provider_account_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        create table if not exists provider_accounts (
            account_id text primary key,
            provider_id text not null,
            provider_label text not null,
            auth_mode text not null,
            status text not null,
            account_label text not null,
            subject_hash text not null,
            credential_ref text not null,
            credential_hint text not null,
            session_ref text not null,
            scopes_json text not null,
            quota_status text not null,
            expires_at text not null,
            created_at text not null,
            updated_at text not null,
            last_validated_at text not null,
            last_error text not null,
            metadata_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists provider_sessions (
            session_id text primary key,
            account_id text not null,
            provider_id text not null,
            auth_mode text not null,
            status text not null,
            credential_ref text not null,
            refresh_supported integer not null,
            expires_at text not null,
            created_at text not null,
            updated_at text not null,
            last_refresh_at text not null,
            last_refresh_error text not null,
            metadata_json text not null,
            foreign key(account_id) references provider_accounts(account_id)
        )
        """
    )
    conn.execute(
        """
        create table if not exists provider_cli_bridges (
            provider_id text primary key,
            cli_name text not null,
            binary_path text not null,
            version text not null,
            status text not null,
            auth_status text not null,
            probe_command text not null,
            supported_delegation_modes_json text not null,
            last_probe_at text not null,
            last_error text not null,
            metadata_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists routing_runs (
            id text primary key,
            created_at text not null,
            workspace_root text not null,
            task_id text not null,
            selected_provider_id text not null,
            selected_model text not null,
            selected_account_id text not null,
            policy_reason text not null,
            alternatives_json text not null,
            fallback_chain_json text not null,
            metadata_json text not null
        )
        """
    )
    _ensure_columns(
        conn,
        "model_attempt_telemetry",
        {
            "provider_account_id": "text not null default ''",
            "routing_run_id": "text not null default ''",
            "limit_class": "text not null default ''",
            "retry_after": "integer",
            "resumed_from_attempt_id": "text not null default ''",
        },
    )
    conn.execute("create index if not exists idx_provider_accounts_provider on provider_accounts(provider_id, status)")
    conn.execute("create index if not exists idx_provider_sessions_account on provider_sessions(account_id, status)")
    conn.execute("create index if not exists idx_routing_runs_workspace_created on routing_runs(workspace_root, created_at)")
    if _table_exists(conn, "model_attempt_telemetry"):
        conn.execute(
            "create index if not exists idx_model_attempt_routing_run on model_attempt_telemetry(routing_run_id, provider_account_id)"
        )


def ensure_release_migration_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        create table if not exists release_migrations (
            id text primary key,
            component_id text not null,
            schema_version text not null,
            applied_at text not null,
            status text not null,
            detail text not null,
            metadata_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists release_update_audit (
            id text primary key,
            component_id text not null,
            created_at text not null,
            from_version text not null,
            to_version text not null,
            status text not null,
            backup_path text not null,
            package_sha256 text not null,
            detail text not null,
            metadata_json text not null
        )
        """
    )
    conn.execute(
        "create index if not exists idx_release_migrations_component on release_migrations(component_id, schema_version, applied_at)"
    )
    conn.execute(
        "create index if not exists idx_release_update_audit_component on release_update_audit(component_id, created_at)"
    )


def initialize_event_store_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        create table if not exists tasks (
            id text primary key,
            created_at text not null,
            finished_at text,
            mode text not null,
            workspace_root text not null,
            message text not null,
            status text not null
        )
        """
    )
    ensure_task_columns(conn)
    conn.execute(
        """
        create table if not exists events (
            id integer primary key autoincrement,
            task_id text not null,
            created_at text not null,
            kind text not null,
            title text not null,
            status text not null,
            detail text not null,
            payload_json text not null,
            foreign key(task_id) references tasks(id)
        )
        """
    )
    conn.execute(
        """
        create table if not exists fix_memory (
            id text primary key,
            created_at text not null,
            project_root text not null,
            error_signature text not null,
            fix_summary text not null,
            evidence text not null,
            confidence real not null,
            category text not null default 'unknown'
        )
        """
    )
    conn.execute(
        """
        create table if not exists repair_attempts (
            id text primary key,
            task_id text not null,
            created_at text not null,
            attempt_number integer not null,
            category text not null,
            before_signature text not null,
            after_signature text not null,
            outcome text not null,
            checkpoint text,
            summary text not null,
            foreign key(task_id) references tasks(id)
        )
        """
    )
    conn.execute(
        """
        create table if not exists project_memory (
            id text primary key,
            created_at text not null,
            updated_at text not null,
            project_root text not null,
            category text not null,
            title text not null,
            detail text not null,
            source text not null,
            confidence real not null,
            fingerprint text not null,
            unique(project_root, fingerprint)
        )
        """
    )
    conn.execute(
        """
        create table if not exists project_intelligence (
            project_root text primary key,
            updated_at text not null,
            indexed_at text not null,
            status text not null,
            profile_json text not null,
            architecture_json text not null,
            file_importance_json text not null,
            snapshot_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists workspace_watch_snapshots (
            workspace_root text primary key,
            scanned_at text not null,
            fingerprint text not null,
            dependency_fingerprint text not null,
            snapshot_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists workspace_operations_snapshots (
            workspace_root text primary key,
            generated_at text not null,
            health_score integer not null,
            status text not null,
            snapshot_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists workspace_events (
            id text primary key,
            workspace_root text not null,
            created_at text not null,
            kind text not null,
            severity text not null,
            title text not null,
            detail text not null,
            path text not null,
            related_files_json text not null,
            metadata_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists workspace_recommendations (
            id text primary key,
            workspace_root text not null,
            created_at text not null,
            updated_at text not null,
            dismissed_at text not null,
            severity text not null,
            category text not null,
            title text not null,
            detail text not null,
            rationale text not null,
            status text not null,
            related_files_json text not null,
            related_tasks_json text not null,
            evidence_json text not null,
            fix_prompt text not null,
            fix_task_id text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists workspace_intelligence_job_runs (
            id text primary key,
            workspace_root text not null,
            job_id text not null,
            name text not null,
            kind text not null,
            schedule_label text not null,
            enabled integer not null,
            safe_by_default integer not null,
            last_run_at text not null,
            status text not null,
            summary text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists runtime_workers (
            worker_id text primary key,
            name text not null,
            kind text not null,
            endpoint text not null,
            status text not null,
            trust_state text not null,
            trust_scope text not null,
            registered_at text not null,
            last_heartbeat_at text not null,
            capabilities_json text not null,
            current_jobs integer not null,
            total_jobs integer not null,
            failed_jobs integer not null,
            average_latency_ms real not null,
            public_key_fingerprint text not null,
            permission_scopes_json text not null,
            isolation_level text not null,
            metadata_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists execution_queue (
            id text primary key,
            task_id text not null,
            workspace_root text not null,
            kind text not null,
            title text not null,
            user_goal text not null,
            status text not null,
            priority integer not null,
            created_at text not null,
            updated_at text not null,
            assigned_worker_id text not null,
            attempts integer not null,
            max_attempts integer not null,
            depends_on_json text not null,
            required_capabilities_json text not null,
            permission_scope text not null,
            sandbox_profile text not null,
            payload_json text not null,
            error_summary text not null,
            result_summary text not null,
            lease_expires_at text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists worker_audit_events (
            id text primary key,
            created_at text not null,
            worker_id text not null,
            job_id text not null,
            event_type text not null,
            status text not null,
            detail text not null,
            metadata_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists workspace_sync_manifests (
            id text primary key,
            workspace_root text not null,
            created_at text not null,
            encrypted integer not null,
            encryption_label text not null,
            included_sections_json text not null,
            manifest_hash text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists context_budget_telemetry (
            id text primary key,
            task_id text not null,
            created_at text not null,
            workspace_root text not null,
            intent text not null,
            route_role text not null,
            strategy text not null,
            privacy_mode text not null,
            max_context_tokens integer not null,
            estimated_context_tokens integer not null,
            estimated_file_tokens integer not null,
            reserve_response_tokens integer not null,
            selected_file_count integer not null,
            omitted_file_count integer not null,
            payload_json text not null,
            foreign key(task_id) references tasks(id)
        )
        """
    )
    conn.execute(
        """
        create table if not exists model_attempt_telemetry (
            id text primary key,
            task_id text not null,
            created_at text not null,
            workspace_root text not null,
            attempt_number integer not null,
            role text not null,
            provider_id text not null,
            provider_label text not null,
            provider_api text not null,
            model text not null,
            endpoint text not null,
            privacy_mode text not null,
            status text not null,
            retryable integer not null,
            input_tokens integer,
            output_tokens integer,
            estimated_cost_usd real,
            latency_ms integer,
            reason text not null,
            error text not null,
            metadata_json text not null,
            foreign key(task_id) references tasks(id)
        )
        """
    )
    conn.execute(
        """
        create table if not exists feedback_telemetry (
            id text primary key,
            created_at text not null,
            workspace_root text not null,
            task_id text not null,
            sentiment text not null,
            action text not null,
            target text not null,
            model_label text not null,
            route_role text not null,
            candidate_id text not null,
            content_hash text not null,
            context text not null,
            metadata_json text not null
        )
        """
    )
    ensure_provider_account_schema(conn)
    ensure_release_migration_schema(conn)
    conn.execute(
        """
        create table if not exists telemetry_snapshots (
            id text primary key,
            created_at text not null,
            updated_at text not null,
            workspace_root text not null,
            snapshot_key text not null,
            route_quality_limit integer not null,
            fallback_limit integer not null,
            feedback_limit integer not null,
            stale_after_seconds integer not null,
            route_quality_json text not null,
            fallback_inspector_json text not null,
            feedback_json text not null,
            task_count integer not null,
            model_attempt_count integer not null,
            feedback_count integer not null,
            reliability_score real not null,
            positive_feedback_rate real not null,
            unique(workspace_root, snapshot_key)
        )
        """
    )
    conn.execute(
        """
        create table if not exists adaptive_task_outcomes (
            id text primary key,
            task_id text not null unique,
            workspace_root text not null,
            created_at text not null,
            updated_at text not null,
            completed_at text not null,
            status text not null,
            success integer not null,
            outcome_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists adaptive_policy_profiles (
            id text primary key,
            name text not null,
            active integer not null,
            created_at text not null,
            updated_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists adaptive_policy_checkpoints (
            id text primary key,
            created_at text not null,
            reason text not null,
            active_profile_id text not null,
            profiles_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists adaptive_benchmark_reports (
            id text primary key,
            workspace_root text not null,
            created_at text not null,
            suite_id text not null,
            status text not null,
            baseline_score real not null,
            candidate_score real not null,
            regression_detected integer not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists adaptive_replay_results (
            id text primary key,
            workspace_root text not null,
            created_at text not null,
            source_task_id text not null,
            status text not null,
            previous_score real not null,
            replay_score real not null,
            regression_detected integer not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists plugin_manifests (
            id text primary key,
            name text not null,
            version text not null,
            api_version text not null,
            enabled integer not null,
            trusted integer not null,
            created_at text not null,
            updated_at text not null,
            capabilities_json text not null,
            permission_scopes_json text not null,
            manifest_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists enterprise_policy_profiles (
            id text primary key,
            name text not null,
            active integer not null,
            created_at text not null,
            updated_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists reliability_metric_snapshots (
            id text primary key,
            workspace_root text not null,
            created_at text not null,
            metric_count integer not null,
            degraded_count integer not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists ecosystem_packages (
            id text primary key,
            kind text not null,
            name text not null,
            version text not null,
            api_version text not null,
            enabled integer not null,
            trust_level text not null,
            installed_at text not null,
            updated_at text not null,
            update_channel text not null,
            manifest_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists ecosystem_workflows (
            id text primary key,
            name text not null,
            version text not null,
            api_version text not null,
            category text not null,
            enabled integer not null,
            created_at text not null,
            updated_at text not null,
            definition_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists shared_intelligence_profiles (
            id text primary key,
            kind text not null,
            name text not null,
            version text not null,
            imported_at text not null,
            updated_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists organization_policy_profiles (
            id text primary key,
            name text not null,
            active integer not null,
            created_at text not null,
            updated_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists knowledge_graph_snapshots (
            id text primary key,
            workspace_root text not null,
            generated_at text not null,
            node_count integer not null,
            edge_count integer not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists reproducibility_records (
            id text primary key,
            workspace_root text not null,
            task_id text not null,
            created_at text not null,
            deterministic_hash text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists ecosystem_audit_events (
            id text primary key,
            created_at text not null,
            actor text not null,
            action text not null,
            subject_id text not null,
            status text not null,
            detail text not null,
            metadata_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists autonomous_objectives (
            id text primary key,
            workspace_root text not null,
            title text not null,
            status text not null,
            priority integer not null,
            created_at text not null,
            updated_at text not null,
            completed_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists autonomous_phases (
            id text primary key,
            objective_id text not null,
            workspace_root text not null,
            kind text not null,
            status text not null,
            created_at text not null,
            updated_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists autonomous_approval_gates (
            id text primary key,
            objective_id text not null,
            workspace_root text not null,
            kind text not null,
            status text not null,
            created_at text not null,
            resolved_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists autonomous_agents (
            id text primary key,
            objective_id text not null,
            phase_id text not null,
            role text not null,
            status text not null,
            updated_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists autonomous_verification (
            id text primary key,
            objective_id text not null,
            phase_id text not null,
            kind text not null,
            status text not null,
            created_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists autonomous_simulations (
            id text primary key,
            objective_id text not null,
            workspace_root text not null,
            created_at text not null,
            risk real not null,
            impact text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists autonomous_refactor_plans (
            id text primary key,
            objective_id text not null,
            kind text not null,
            status text not null,
            updated_at text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        """
        create table if not exists autonomous_explanations (
            id text primary key,
            objective_id text not null,
            created_at text not null,
            category text not null,
            payload_json text not null
        )
        """
    )
    conn.execute(
        "create index if not exists idx_context_budget_workspace_created on context_budget_telemetry(workspace_root, created_at)"
    )
    conn.execute(
        "create index if not exists idx_model_attempt_workspace_created on model_attempt_telemetry(workspace_root, created_at)"
    )
    conn.execute(
        "create index if not exists idx_feedback_workspace_created on feedback_telemetry(workspace_root, created_at)"
    )
    conn.execute(
        "create index if not exists idx_feedback_task on feedback_telemetry(task_id)"
    )
    conn.execute(
        "create index if not exists idx_telemetry_snapshots_workspace_updated on telemetry_snapshots(workspace_root, updated_at)"
    )
    conn.execute(
        "create index if not exists idx_adaptive_outcomes_workspace_updated on adaptive_task_outcomes(workspace_root, updated_at)"
    )
    conn.execute(
        "create index if not exists idx_adaptive_profiles_active on adaptive_policy_profiles(active, updated_at)"
    )
    conn.execute(
        "create index if not exists idx_adaptive_checkpoints_created on adaptive_policy_checkpoints(created_at)"
    )
    conn.execute(
        "create index if not exists idx_adaptive_benchmarks_workspace_suite on adaptive_benchmark_reports(workspace_root, suite_id, created_at)"
    )
    conn.execute(
        "create index if not exists idx_adaptive_replay_workspace_task on adaptive_replay_results(workspace_root, source_task_id, created_at)"
    )
    conn.execute(
        "create index if not exists idx_workspace_events_root_created on workspace_events(workspace_root, created_at)"
    )
    conn.execute(
        "create index if not exists idx_workspace_recommendations_root_status on workspace_recommendations(workspace_root, status, updated_at)"
    )
    conn.execute(
        "create index if not exists idx_workspace_job_runs_root_job on workspace_intelligence_job_runs(workspace_root, job_id, last_run_at)"
    )
    conn.execute(
        "create index if not exists idx_runtime_workers_status on runtime_workers(status, trust_state, kind)"
    )
    conn.execute(
        "create index if not exists idx_execution_queue_root_status_priority on execution_queue(workspace_root, status, priority, created_at)"
    )
    conn.execute(
        "create index if not exists idx_execution_queue_worker_status on execution_queue(assigned_worker_id, status, updated_at)"
    )
    conn.execute(
        "create index if not exists idx_worker_audit_worker_created on worker_audit_events(worker_id, created_at)"
    )
    conn.execute(
        "create index if not exists idx_worker_audit_job_created on worker_audit_events(job_id, created_at)"
    )
    conn.execute(
        "create index if not exists idx_workspace_sync_root_created on workspace_sync_manifests(workspace_root, created_at)"
    )
    conn.execute(
        "create index if not exists idx_plugin_manifests_enabled on plugin_manifests(enabled, trusted, name)"
    )
    conn.execute(
        "create index if not exists idx_enterprise_policy_active on enterprise_policy_profiles(active, updated_at)"
    )
    conn.execute(
        "create index if not exists idx_reliability_snapshots_root_created on reliability_metric_snapshots(workspace_root, created_at)"
    )
    conn.execute(
        "create index if not exists idx_ecosystem_packages_kind_enabled on ecosystem_packages(kind, enabled, trust_level)"
    )
    conn.execute(
        "create index if not exists idx_ecosystem_workflows_enabled_category on ecosystem_workflows(enabled, category, name)"
    )
    conn.execute(
        "create index if not exists idx_shared_profiles_kind_updated on shared_intelligence_profiles(kind, updated_at)"
    )
    conn.execute(
        "create index if not exists idx_org_policy_active_updated on organization_policy_profiles(active, updated_at)"
    )
    conn.execute(
        "create index if not exists idx_knowledge_graph_root_generated on knowledge_graph_snapshots(workspace_root, generated_at)"
    )
    conn.execute(
        "create index if not exists idx_reproducibility_root_task_created on reproducibility_records(workspace_root, task_id, created_at)"
    )
    conn.execute(
        "create index if not exists idx_ecosystem_audit_created on ecosystem_audit_events(created_at)"
    )
    conn.execute(
        "create index if not exists idx_autonomous_objectives_root_status on autonomous_objectives(workspace_root, status, updated_at)"
    )
    conn.execute(
        "create index if not exists idx_autonomous_phases_objective on autonomous_phases(objective_id, kind, status)"
    )
    conn.execute(
        "create index if not exists idx_autonomous_gates_root_status on autonomous_approval_gates(workspace_root, status, created_at)"
    )
    conn.execute(
        "create index if not exists idx_autonomous_agents_objective on autonomous_agents(objective_id, role, status)"
    )
    conn.execute(
        "create index if not exists idx_autonomous_verification_objective on autonomous_verification(objective_id, kind, status)"
    )
    conn.execute(
        "create index if not exists idx_autonomous_simulations_objective on autonomous_simulations(objective_id, created_at)"
    )
    conn.execute(
        "create index if not exists idx_autonomous_refactor_objective on autonomous_refactor_plans(objective_id, kind, status)"
    )
    conn.execute(
        "create index if not exists idx_autonomous_explanations_objective on autonomous_explanations(objective_id, created_at)"
    )
    ensure_fix_memory_category_column(conn)


def ensure_fix_memory_category_column(conn: sqlite3.Connection) -> None:
    columns = {
        str(row["name"])
        for row in conn.execute("pragma table_info(fix_memory)").fetchall()
        if row["name"]
    }
    if "category" not in columns:
        conn.execute("alter table fix_memory add column category text not null default 'unknown'")
