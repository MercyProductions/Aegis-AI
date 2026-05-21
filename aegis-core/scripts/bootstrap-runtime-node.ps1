$ErrorActionPreference = 'Stop'

param(
    [string]$Workspace = (Get-Location).Path,
    [string]$CoreUrl = $(if ($env:AEGIS_CORE_BASE_URL) { $env:AEGIS_CORE_BASE_URL } else { 'http://127.0.0.1:8000' }),
    [string]$NodeId = $(if ($env:AEGIS_NODE_ID) { $env:AEGIS_NODE_ID } else { "$env:COMPUTERNAME-validation" }),
    [ValidateSet('trusted_remote', 'isolated_worker', 'validation', 'indexing', 'gpu_model')]
    [string]$NodeType = 'validation',
    [string]$Endpoint = $(if ($env:AEGIS_NODE_ENDPOINT) { $env:AEGIS_NODE_ENDPOINT } else { "local://$env:COMPUTERNAME" })
)

$Token = $env:AEGIS_DISTRIBUTED_NODE_TOKEN
if (-not $Token) {
    Write-Warning 'AEGIS_DISTRIBUTED_NODE_TOKEN is not set. Core will register this node as untrusted until approved.'
}

$Body = @{
    workspace = (Resolve-Path -LiteralPath $Workspace).Path
    node_id = $NodeId
    name = $NodeId
    node_type = $NodeType
    endpoint = $Endpoint
    auth_token = $Token
    capabilities = @('validation_execution', 'indexing', 'workspace_scan')
    permission_scopes = @('workspace_scan', 'validation_execution')
    supported_workflow_types = @('validate_project', 'repair_project', 'build_project', 'scan_workspace')
    max_parallel_workloads = 1
    isolation = @{
        subprocess = $true
        containers = 'supported_or_planned'
        workspace_mount = 'read_only_by_default'
        plugin_code = 'sandbox_required'
    }
    metadata = @{
        bootstrap_script = 'aegis-core/scripts/bootstrap-runtime-node.ps1'
        machine = $env:COMPUTERNAME
    }
} | ConvertTo-Json -Depth 8

Invoke-RestMethod -Method Post -Uri "$CoreUrl/v1/distributed-runtime/nodes/register" -ContentType 'application/json' -Body $Body
