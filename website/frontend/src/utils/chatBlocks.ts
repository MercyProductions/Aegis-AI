export type ChatContentBlock =
  | {
      type: 'text';
      content: string;
    }
  | {
      type: 'code';
      content: string;
      language: string;
    };

export function parseChatContentBlocks(content: string): ChatContentBlock[] {
  const blocks: ChatContentBlock[] = [];
  const fencePattern = /```([a-zA-Z0-9_+#.-]*)?[^\n]*\n([\s\S]*?)```/g;
  let cursor = 0;
  let match: RegExpExecArray | null;

  while ((match = fencePattern.exec(content)) !== null) {
    const before = content.slice(cursor, match.index);
    pushTextBlock(blocks, before);
    blocks.push({
      type: 'code',
      language: (match[1] ?? '').trim(),
      content: trimCodeBlock(match[2] ?? '')
    });
    cursor = match.index + match[0].length;
  }

  pushTextBlock(blocks, content.slice(cursor));
  return blocks.length ? blocks : [{ type: 'text', content: content.trim() }];
}

function pushTextBlock(blocks: ChatContentBlock[], content: string) {
  const trimmed = content.trim();
  if (!trimmed) return;
  blocks.push({ type: 'text', content: trimmed });
}

function trimCodeBlock(content: string): string {
  return content.replace(/^\r?\n/, '').replace(/\r?\n$/, '');
}
