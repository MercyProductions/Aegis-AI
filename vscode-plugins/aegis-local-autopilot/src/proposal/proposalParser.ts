// Proposal parsing and normalization logic for Aegis Local Autopilot.
// Extracted from extension.js Phase-1 modularization.

const path = require('path');
const { parseJsonText } = require('../utils/fsSafe.ts');
const { normalizeLineEndings } = require('../utils/pathSafe.ts');
const { sanitizeMemoryText } = require('../utils/errors.ts');
const { normalizeConfidenceScore } = require('./proposalSafety.ts');

/**
 * Main entry point for parsing model output into a Proposal object.
 */
function parseProposal(raw, target, objective) {
  let parsed;
  try {
    parsed = parseJsonText(extractJson(raw));
  } catch (error) {
    parsed = proposalObjectFromInstructionalCodeBlocks(raw, objective) || {
      summary: 'Model returned non-JSON output; saved as notes.',
      risk: 'medium',
      notes: [raw],
      fileEdits: [],
      commands: [],
      tests: []
    };
  }

  let fileEdits = Array.isArray(parsed.fileEdits) ? parsed.fileEdits : [];
  let commands = Array.isArray(parsed.commands) ? parsed.commands : [];
  let tests = Array.isArray(parsed.tests) ? parsed.tests : [];

  if (!fileEdits.length) {
    const inferred = proposalObjectFromInstructionalCodeBlocks(raw, objective);
    if (inferred && Array.isArray(inferred.fileEdits) && inferred.fileEdits.length) {
      parsed = Object.assign({}, parsed, {
        summary: parsed.summary || inferred.summary,
        risk: parsed.risk || inferred.risk,
        confidenceScore: parsed.confidenceScore === undefined ? inferred.confidenceScore : parsed.confidenceScore,
        approachRationale: parsed.approachRationale || inferred.approachRationale,
        notes: [
          ...(Array.isArray(parsed.notes) ? parsed.notes.map(String) : []),
          ...(Array.isArray(inferred.notes) ? inferred.notes.map(String) : [])
        ].slice(0, 12),
        fileEdits: inferred.fileEdits,
        commands: commands.length ? commands : inferred.commands,
        tests: tests.length ? tests : inferred.tests,
        impactAnalysis: parsed.impactAnalysis || inferred.impactAnalysis,
        stages: parsed.stages || inferred.stages
      });
      fileEdits = inferred.fileEdits;
      commands = Array.isArray(parsed.commands) ? parsed.commands : [];
      tests = Array.isArray(parsed.tests) ? parsed.tests : [];
    }
  }

  const proposal = {
    objective,
    createdAt: new Date().toISOString(),
    workspace: target.root,
    targetRoot: target.root,
    targetLabel: target.label,
    workspaceRoot: target.workspaceRoot || target.root,
    summary: String(parsed.summary || '').trim(),
    risk: String(parsed.risk || 'medium').trim(),
    confidenceScore: normalizeConfidenceScore(parsed.confidenceScore),
    approachRationale: sanitizeMemoryText(String(parsed.approachRationale || parsed.rationale || '').trim()),
    notes: Array.isArray(parsed.notes) ? parsed.notes.map(String) : [],
    fileEdits: fileEdits
      .filter((edit) => edit && typeof edit.path === 'string' && typeof edit.content === 'string')
      .map((edit) => {
        const originalPath = String(edit.path || '');
        const normalizedPath = originalPath.replace(/\\/g, '/').replace(/^\/+/, '');
        return {
          path: normalizedPath,
          originalPath: originalPath !== normalizedPath ? originalPath : '',
          reason: String(edit.reason || ''),
          content: normalizeLineEndings(edit.content)
        };
      }),
    commands: commands
      .filter((command) => command && typeof command.command === 'string')
      .map((command) => ({
        command: command.command,
        reason: String(command.reason || '')
      })),
    tests: tests.map(String),
    impactAnalysis: normalizeModelImpactAnalysis(parsed.impactAnalysis),
    stages: normalizeModelStages(parsed.stages)
  };
  proposal.stages = normalizeProposalStages(proposal, proposal.impactAnalysis);
  return proposal;
}

/**
 * Extracts JSON block from markdown text.
 */
function extractJson(text) {
  const match = text.match(/```(?:json)?\s*([\s\S]*?)```/) || text.match(/\{[\s\S]*\}/);
  return match ? match[1] || match[0] : text;
}

/**
 * Extracts all fenced code blocks from markdown text.
 */
function extractFencedCodeBlocks(text) {
  const blocks = [];
  const regex = /```([A-Za-z0-9+#-]*)\s*([^\n]*)\n([\s\S]*?)```/g;
  let match;
  while ((match = regex.exec(text)) !== null) {
    blocks.push({
      language: (match[1] || '').trim().toLowerCase(),
      info: (match[2] || '').trim(),
      content: match[3],
      index: match.index
    });
  }
  return blocks;
}

/**
 * Heuristics to decide if we should infer file edits from loose code blocks.
 */
function shouldInferFileEditsFromCodeBlocks(raw, objective, blocks) {
  const lowerObjective = String(objective || '').toLowerCase();
  if (lowerObjective.includes('explain') || lowerObjective.includes('how to') || lowerObjective.includes('roadmap')) {
    return false;
  }
  if (blocks.length > 5) {
    return false;
  }
  return true;
}

/**
 * Attempts to infer the file path for a code block based on surrounding text.
 */
function inferCodeBlockPath(raw, block, objective, usedPaths, totalBlocks) {
  const before = raw.slice(Math.max(0, block.index - 250), block.index);
  const pathMatch = before.match(/(?:file|path|to|in|at|create|update|modify|edit)\s*[:*-]?\s*`?([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+)`?/i);
  if (pathMatch) {
    const p = pathMatch[1].replace(/\\/g, '/').replace(/^\/+/, '');
    if (!usedPaths.has(p.toLowerCase())) return p;
  }
  const infoMatch = block.info.match(/([A-Za-z0-9_./\\-]+\.[A-Za-z0-9]+)/);
  if (infoMatch) {
    const p = infoMatch[1].replace(/\\/g, '/').replace(/^\/+/, '');
    if (!usedPaths.has(p.toLowerCase())) return p;
  }
  return null;
}

/**
 * Fallback parser for non-JSON model output.
 */
function proposalObjectFromInstructionalCodeBlocks(raw, objective) {
  const blocks = extractFencedCodeBlocks(raw);
  if (!blocks.length || !shouldInferFileEditsFromCodeBlocks(raw, objective, blocks)) {
    return null;
  }

  const usedPaths = new Set();
  const fileEdits = [];
  for (const block of blocks) {
    const inferredPath = inferCodeBlockPath(raw, block, objective, usedPaths, blocks.length);
    if (!inferredPath) {
      continue;
    }
    usedPaths.add(inferredPath.toLowerCase());
    fileEdits.push({
      path: inferredPath,
      reason: 'Converted generated code into an Aegis file edit so the extension can create the file after approval.',
      content: normalizeLineEndings(block.content.replace(/\s+$/, '')) + '\n'
    });
  }

  if (!fileEdits.length) {
    return null;
  }

  return {
    summary: 'Inferred file edits from generated code blocks.',
    risk: 'medium',
    confidenceScore: 0.7,
    approachRationale: 'Model did not return JSON; Aegis extracted code blocks into file edits.',
    notes: [],
    fileEdits,
    commands: [],
    tests: []
  };
}

/**
 * Normalizes impact analysis data from model output.
 */
function normalizeModelImpactAnalysis(value) {
  if (!value || typeof value !== 'object') {
    return { riskScore: 0.5, summary: 'No impact analysis provided.', brokenPoints: [] };
  }
  return {
    riskScore: Number.isFinite(Number(value.riskScore)) ? Math.max(0, Math.min(1, Number(value.riskScore))) : 0.5,
    summary: String(value.summary || 'Impact analysis summary unavailable.').trim(),
    brokenPoints: Array.isArray(value.brokenPoints) ? value.brokenPoints.map(String).slice(0, 12) : []
  };
}

/**
 * Normalizes staging plan data from model output.
 */
function normalizeModelStages(value) {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .filter((s) => s && typeof s === 'object')
    .map((s) => ({
      name: String(s.name || s.title || 'Stage').trim(),
      goal: String(s.goal || s.objective || 'Complete this stage.').trim(),
      risk: String(s.risk || 'low').trim(),
      files: Array.isArray(s.files) ? s.files.map(String).slice(0, 20) : []
    }))
    .slice(0, 8);
}

/**
 * Ensures a proposal has a valid staging plan, even if the model didn't provide one.
 */
function normalizeProposalStages(proposal, impactAnalysis) {
  if (proposal.stages && proposal.stages.length) {
    return proposal.stages;
  }
  // Simple heuristic for default stages
  const edits = proposal.fileEdits || [];
  if (edits.length <= 1) {
    return [{ name: 'Single edit', goal: 'Apply the requested change.', risk: proposal.risk || 'low', files: edits.map((e) => e.path) }];
  }
  return [
    { name: 'Core changes', goal: 'Implement the primary logic.', risk: proposal.risk || 'medium', files: edits.slice(0, Math.ceil(edits.length / 2)).map((e) => e.path) },
    { name: 'Remaining edits', goal: 'Complete the implementation and tests.', risk: 'low', files: edits.slice(Math.ceil(edits.length / 2)).map((e) => e.path) }
  ];
}

/**
 * Converts a proposal object into a human-readable plan text.
 */
function proposalToPlanText(proposal) {
  const lines = [];
  lines.push(proposal.summary || 'No summary returned.');
  if (proposal.risk) {
    lines.push(`Risk: ${proposal.risk}`);
  }
  if (proposal.confidenceScore !== undefined) {
    lines.push(`Confidence: ${Math.round(normalizeConfidenceScore(proposal.confidenceScore) * 100)}%`);
  }
  if (proposal.approachRationale) {
    lines.push(`Approach: ${proposal.approachRationale}`);
  }
  if (proposal.notes && proposal.notes.length) {
    lines.push('');
    lines.push('Notes:');
    proposal.notes.slice(0, 8).forEach((note) => lines.push(`- ${note}`));
  }
  if (proposal.fileEdits && proposal.fileEdits.length) {
    lines.push('');
    lines.push('Proposed file changes:');
    proposal.fileEdits.forEach((edit) => lines.push(`- ${edit.path}${edit.reason ? `: ${edit.reason}` : ''}`));
  }
  if (proposal.commands && proposal.commands.length) {
    lines.push('');
    lines.push('Suggested commands:');
    proposal.commands.forEach((item) => lines.push(`- ${item.command}${item.reason ? `: ${item.reason}` : ''}`));
  }
  if (proposal.tests && proposal.tests.length) {
    lines.push('');
    lines.push('Validation notes:');
    proposal.tests.forEach((item) => lines.push(`- ${item}`));
  }
  return lines.join('\n');
}

module.exports = {
  parseProposal,
  extractJson,
  extractFencedCodeBlocks,
  proposalToPlanText,
  normalizeModelImpactAnalysis,
  normalizeModelStages,
  normalizeProposalStages
};
