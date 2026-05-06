import { describe, expect, it } from 'vitest';
import { parseChatContentBlocks } from './chatBlocks';

describe('chat content blocks', () => {
  it('keeps plain messages as text blocks', () => {
    expect(parseChatContentBlocks('  hello\nworld  ')).toEqual([{ type: 'text', content: 'hello\nworld' }]);
  });

  it('extracts fenced code blocks with language labels', () => {
    expect(
      parseChatContentBlocks(
        [
          'Use this function:',
          '',
          '```ts',
          'export function add(a: number, b: number) {',
          '  return a + b;',
          '}',
          '```',
          '',
          'Then import it.'
        ].join('\n')
      )
    ).toEqual([
      { type: 'text', content: 'Use this function:' },
      {
        type: 'code',
        language: 'ts',
        content: 'export function add(a: number, b: number) {\n  return a + b;\n}'
      },
      { type: 'text', content: 'Then import it.' }
    ]);
  });
});
