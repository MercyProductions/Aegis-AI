// Shared task and workflow synchronization helpers.

const { coreEnvelopeData } = require('./coreEnvelope.ts');

function extractWorkflowId(envelopeOrData) {
  const data = envelopeOrData && envelopeOrData.data ? coreEnvelopeData(envelopeOrData) : (envelopeOrData || {});
  const workflow = data.workflow || {};
  return workflow.id || data.workflow_id || '';
}

function extractWorkflowSummary(envelopeOrData) {
  const data = envelopeOrData && envelopeOrData.data ? coreEnvelopeData(envelopeOrData) : (envelopeOrData || {});
  const workflow = data.workflow || {};
  return {
    id: workflow.id || data.workflow_id || '',
    workflowType: workflow.workflow_type || '',
    status: workflow.status || '',
    progress: typeof workflow.progress === 'number' ? workflow.progress : 0,
    activeTaskId: workflow.active_task_id || '',
    updatedAt: workflow.updated_at || workflow.created_at || ''
  };
}

function extractEditingJob(envelopeOrData) {
  const data = envelopeOrData && envelopeOrData.data ? coreEnvelopeData(envelopeOrData) : (envelopeOrData || {});
  return {
    jobId: data.job_id || '',
    taskId: data.task_id || '',
    projectId: data.project_id || '',
    activityId: data.activity_id || '',
    checkpointId: data.checkpoint_id || (data.checkpoint && data.checkpoint.id) || ''
  };
}

function summarizeWorkflowEvent(event) {
  const payload = event && event.data && typeof event.data === 'object' ? event.data : event;
  if (!payload || typeof payload !== 'object') {
    return {
      id: '',
      event: 'workflow.event',
      workflowId: '',
      summary: String(payload || ''),
      at: ''
    };
  }
  return {
    id: payload.id || '',
    event: payload.event || payload.kind || 'workflow.event',
    workflowId: payload.workflow_id || '',
    workflowType: payload.workflow_type || '',
    summary: payload.summary || payload.message || '',
    at: payload.at || payload.created_at || payload.timestamp || ''
  };
}

function recentEventsFromDashboard(envelopeOrData) {
  const data = envelopeOrData && envelopeOrData.data ? coreEnvelopeData(envelopeOrData) : (envelopeOrData || {});
  const events = []
    .concat(Array.isArray(data.recent_operations) ? data.recent_operations : [])
    .concat(Array.isArray(data.workspace_activity_feed) ? data.workspace_activity_feed : []);
  return events.map(summarizeWorkflowEvent).filter((item) => item.event || item.summary).slice(0, 30);
}

module.exports = {
  extractWorkflowId,
  extractWorkflowSummary,
  extractEditingJob,
  summarizeWorkflowEvent,
  recentEventsFromDashboard
};
