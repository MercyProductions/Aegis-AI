import { afterEach, describe, expect, it, vi } from 'vitest';
import { streamAgentMessage } from './api';
import type { AgentRequest, AgentResponse } from './types';

const originalFetch = globalThis.fetch;

afterEach(() => {
  vi.restoreAllMocks();
  globalThis.fetch = originalFetch;
});

describe('streamAgentMessage', () => {
  it('accepts a final SSE frame even when the stream closes without a trailing blank line', async () => {
    const finalResponse = createAgentResponse({ reply: 'finished without trailing separator' });
    const onFinal = vi.fn();

    mockStreamResponse([
      sseFrame('meta', { type: 'meta', stream_mode: 'test' }),
      `event: final\ndata: ${JSON.stringify({ type: 'final', response: finalResponse })}`
    ]);

    await expect(streamAgentMessage(createAgentRequest(), { onFinal })).resolves.toMatchObject({
      reply: 'finished without trailing separator'
    });
    expect(onFinal).toHaveBeenCalledWith(expect.objectContaining({ response: finalResponse }));
  });

  it('parses frames split across network chunks and emits deltas before final', async () => {
    const finalResponse = createAgentResponse({ reply: 'split chunks done' });
    const onDelta = vi.fn();

    mockStreamResponse([
      'event: delta\ndata: {"type":"delta","delta":"split"',
      ',"source":"direct"}\n\n',
      `event: final\ndata: ${JSON.stringify({ type: 'final', response: finalResponse })}`
    ]);

    await expect(streamAgentMessage(createAgentRequest(), { onDelta })).resolves.toMatchObject({
      reply: 'split chunks done'
    });
    expect(onDelta).toHaveBeenCalledWith(expect.objectContaining({ delta: 'split' }));
  });

  it('surfaces an unterminated SSE error frame instead of reporting a missing final response', async () => {
    mockStreamResponse(['event: error\ndata: {"type":"error","message":"provider disconnected"}']);

    await expect(streamAgentMessage(createAgentRequest())).rejects.toThrow('provider disconnected');
  });

  it('passes an abort signal through to the streaming fetch request', async () => {
    const abortController = new AbortController();
    const finalResponse = createAgentResponse({ reply: 'abort signal wired' });
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) =>
      new Response(createStreamBody([
        `event: final\ndata: ${JSON.stringify({ type: 'final', response: finalResponse })}`
      ]), {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' }
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    await expect(streamAgentMessage(createAgentRequest(), { signal: abortController.signal })).resolves.toMatchObject({
      reply: 'abort signal wired'
    });
    expect(fetchMock.mock.calls[0]?.[1]?.signal).toBe(abortController.signal);
  });

  it('rejects with AbortError when the provided signal is aborted', async () => {
    const abortController = new AbortController();
    vi.stubGlobal(
      'fetch',
      vi.fn(
        (_input: RequestInfo | URL, init?: RequestInit) =>
          new Promise<Response>((_resolve, reject) => {
            init?.signal?.addEventListener(
              'abort',
              () => reject(new DOMException('The operation was aborted.', 'AbortError')),
              { once: true }
            );
          })
      )
    );

    const result = streamAgentMessage(createAgentRequest(), { signal: abortController.signal });
    abortController.abort();

    await expect(result).rejects.toMatchObject({ name: 'AbortError' });
  });
});

function mockStreamResponse(chunks: string[]) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async () => new Response(createStreamBody(chunks), {
      status: 200,
      headers: { 'Content-Type': 'text/event-stream' }
    }))
  );
}

function createStreamBody(chunks: string[]) {
  const encoder = new TextEncoder();
  return new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk));
      }
      controller.close();
    }
  });
}

function sseFrame(event: string, payload: Record<string, unknown>) {
  return `event: ${event}\ndata: ${JSON.stringify(payload)}\n\n`;
}

function createAgentRequest(): AgentRequest {
  return {
    message: 'test',
    history: [],
    apply_changes: false,
    run_validation: false
  };
}

function createAgentResponse(overrides: Partial<AgentResponse> = {}): AgentResponse {
  return {
    task_id: 'stream-test',
    reply: 'done',
    plan: [],
    changes: [],
    applied: [],
    checkpoint: null,
    warnings: [],
    events: [],
    validation: null,
    validation_profile: null,
    task_plan: null,
    context_budget: null,
    model_attempts: [],
    assistant_name: 'Aegis AI',
    mode: 'chat',
    engine: 'Aegis Core',
    workspace_root: 'workspace',
    workspace_files: [],
    context_files: [],
    memory_hits: [],
    project_memory_hits: [],
    recent_tasks: [],
    repair_attempts: [],
    completion_quality: null,
    ...overrides
  };
}
