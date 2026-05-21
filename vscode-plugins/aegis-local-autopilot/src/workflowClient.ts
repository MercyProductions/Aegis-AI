// Thin workflow facade over Aegis Core for VS Code command flows.

const { coreEnvelopeData } = require('./core/coreEnvelope.ts');
const { extractWorkflowId, extractWorkflowSummary } = require('./core/taskSync.ts');

function createWorkflowClient(coreClient, options = {}) {
  const sourceClient = options.sourceClient || 'vscode-extension';

  async function start(workspace, workflowType, objective, metadata = {}) {
    const envelope = await coreClient.createWorkflow(workspace, workflowType, objective, {
      sourceClient,
      contextFiles: metadata.contextFiles || [],
      metadata: Object.assign({}, metadata.metadata || {}, {
        vscode_command: metadata.command || '',
        model: metadata.model || '',
        safety_mode: metadata.safetyMode || ''
      })
    });
    return {
      envelope,
      data: coreEnvelopeData(envelope),
      id: extractWorkflowId(envelope),
      summary: extractWorkflowSummary(envelope)
    };
  }

  return {
    start,

    startChat(workspace, objective, metadata = {}) {
      return start(workspace, 'chat_request', objective, metadata);
    },

    startFeature(workspace, objective, metadata = {}) {
      return start(workspace, 'generate_feature', objective, metadata);
    },

    startValidation(workspace, objective, metadata = {}) {
      return start(workspace, 'validate_project', objective || 'Validate this VS Code workspace.', metadata);
    },

    startRepair(workspace, objective, metadata = {}) {
      return start(workspace, 'repair_project', objective || 'Repair the latest validation failure.', metadata);
    },

    continueRoadmap(workspace, objective, metadata = {}) {
      return start(workspace, 'continue_roadmap', objective || 'Continue from the shared project roadmap.', metadata);
    },

    scanWorkspace(workspace, objective, metadata = {}) {
      return start(workspace, 'scan_workspace', objective || 'Refresh workspace intelligence for VS Code.', metadata);
    },

    recordLog(workspace, workflowId, summary, payload = {}) {
      return coreClient.stepWorkflow(workspace, workflowId, {
        action: 'record_log',
        summary,
        payload
      });
    },

    completeTask(workspace, workflowId, taskId, summary, payload = {}) {
      return coreClient.stepWorkflow(workspace, workflowId, {
        action: 'complete_task',
        taskId,
        summary,
        payload
      });
    },

    failTask(workspace, workflowId, taskId, summary, payload = {}) {
      return coreClient.stepWorkflow(workspace, workflowId, {
        action: 'fail_task',
        taskId,
        summary,
        payload
      });
    },

    pause(workspace, workflowId, summary) {
      return coreClient.pauseWorkflow(workspace, workflowId, summary || 'Paused by VS Code.');
    },

    resume(workspace, workflowId, summary) {
      return coreClient.resumeWorkflow(workspace, workflowId, summary || 'Resumed by VS Code.');
    },

    cancel(workspace, workflowId, summary) {
      return coreClient.cancelWorkflow(workspace, workflowId, summary || 'Cancelled by VS Code.');
    },

    events(workspace, options = {}) {
      return coreClient.workflowEvents(workspace, options);
    }
  };
}

module.exports = {
  createWorkflowClient
};
