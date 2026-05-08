export type ConnectionState = 'checking' | 'connected' | 'reconnecting' | 'offline' | 'failed';

export function connectionStateLabel(state: ConnectionState): string {
  switch (state) {
    case 'checking':
      return 'Checking';
    case 'connected':
      return 'Connected';
    case 'reconnecting':
      return 'Reconnecting';
    case 'failed':
      return 'Failed';
    case 'offline':
    default:
      return 'Offline';
  }
}

export function connectionStateDetail(state: ConnectionState): string {
  switch (state) {
    case 'connected':
      return 'queued prompts will send now';
    case 'checking':
      return 'waiting for backend health check';
    case 'reconnecting':
      return 'waiting for backend to reconnect';
    case 'failed':
      return 'backend responded but is not ready';
    case 'offline':
    default:
      return 'backend is offline';
  }
}

export function isLikelyConnectionError(message: string): boolean {
  const lower = message.toLowerCase();
  return [
    'failed to fetch',
    'networkerror',
    'network error',
    'load failed',
    'connection',
    'connect',
    'econnrefused',
    'timeout',
    'timed out',
    'backend',
    'server'
  ].some((fragment) => lower.includes(fragment));
}
