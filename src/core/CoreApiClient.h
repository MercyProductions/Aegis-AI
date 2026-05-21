#pragma once

#include "../AegisClient.h"

#include <string>
#include <vector>

namespace aegis {

class CoreApiClient {
public:
    explicit CoreApiClient(DesktopSettings settings);

    DesktopRuntimeStatus ProbeRuntime(
        const std::string& workspace_root,
        const HealthStatus* website_health = nullptr) const;
    DesktopRuntimeStatus CachedStatus() const;

    void RegisterClient(
        const std::string& workspace_root,
        const std::string& client_id,
        const std::string& client_type,
        const std::string& name,
        const std::string& version,
        const std::vector<std::string>& capabilities,
        const std::string& active_workflow_id = "") const;
    AegisCoreDashboardInfo GetDashboard(const std::string& workspace_root) const;
    AgentSupervisionInfo GetAgentSupervision(const std::string& workspace_root) const;
    QualityGateSnapshotInfo GetQualityGates(const std::string& workspace_root) const;
    ModelRegistrySnapshot GetModelRegistry(const std::string& workspace_root) const;

    ApplyResult ApplyChanges(
        const std::string& workspace_root,
        const std::vector<FileChange>& changes,
        bool dry_run = false) const;
    CheckpointListResult ListCheckpoints(const std::string& workspace_root, int limit = 50) const;
    RestoreResult RestoreCheckpoint(
        const std::string& workspace_root,
        const std::string& checkpoint_id,
        bool dry_run = false) const;
    AgentResponse RunValidation(
        const std::string& workspace_root,
        const std::vector<std::string>& command = {},
        int timeout_seconds = 120,
        bool dry_run = false) const;

    std::string CreateWorkflow(
        const std::string& workspace_root,
        const std::string& workflow_type,
        const std::string& objective,
        const std::vector<std::string>& context_files = {},
        const std::string& source_task_id = "") const;
    bool StepWorkflow(
        const std::string& workspace_root,
        const std::string& workflow_id,
        const std::string& action,
        const std::string& task_id = "",
        bool approval = false,
        const std::string& summary = "") const;

    std::vector<WorkspaceFile> ScanWorkspaceFiles(const std::string& workspace_root, int max_files = 160) const;

    void RecordWebsiteFallback(const std::string& operation, const std::string& detail) const;
    void RecordWebsiteSuccess(
        const std::string& operation,
        const std::string& detail = "",
        const std::string& checkpoint_id = "") const;

private:
    DesktopSettings settings_;

    std::string Endpoint(const std::string& path) const;
    std::string RequireJson(const HttpResponse& response, const std::string& action) const;
};

}
