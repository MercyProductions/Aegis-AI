// frontend/src/components/MemoryEditor.tsx
import React, { useState, useEffect } from 'react';
import {
  Trash2,
  Plus,
  Pin,
  PinOff,
  Search,
  Save,
  X,
  Zap
} from 'lucide-react';
import type { CSSProperties } from 'react';

interface MemoryNote {
  id: string;
  title: string;
  content: string;
  category: 'fix' | 'pattern' | 'insight' | 'bug' | 'feature';
  created_at: string;
  pinned: boolean;
  tags: string[];
  confidence: number;
}

interface MemoryEditorProps {
  workspaceRoot: string;
  onClose: () => void;
  palette: any;
}

const API_BASE = (import.meta.env.VITE_API_BASE ?? 'http://127.0.0.1:8787').replace(/\/+$/, '');

export function MemoryEditor({ workspaceRoot, onClose, palette }: MemoryEditorProps) {
  const [notes, setNotes] = useState<MemoryNote[]>([]);
  const [selectedNote, setSelectedNote] = useState<MemoryNote | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [newNote, setNewNote] = useState({ title: '', content: '', category: 'insight' });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadNotes();
  }, [workspaceRoot]);

  async function loadNotes() {
    try {
      setLoading(true);
      setError('');
      const response = await fetch(`${API_BASE}/api/memory?workspace_root=${encodeURIComponent(workspaceRoot)}`);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const data = await response.json();
      setNotes(data.notes || []);
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to load notes');
    } finally {
      setLoading(false);
    }
  }

  async function createNote() {
    if (!newNote.title.trim()) return;

    try {
      setError('');
      const response = await fetch(`${API_BASE}/api/memory?workspace_root=${encodeURIComponent(workspaceRoot)}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          title: newNote.title,
          content: newNote.content,
          category: newNote.category,
          tags: [],
          related_files: []
        })
      });

      if (response.ok) {
        setNewNote({ title: '', content: '', category: 'insight' });
        setIsCreating(false);
        await loadNotes();
      } else {
        throw new Error(await response.text());
      }
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to create note');
    }
  }

  async function deleteNote(noteId: string) {
    if (!confirm('Delete this note?')) return;

    try {
      setError('');
      const response = await fetch(`${API_BASE}/api/memory/${noteId}?workspace_root=${encodeURIComponent(workspaceRoot)}`, {
        method: 'DELETE'
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      setSelectedNote(null);
      await loadNotes();
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to delete note');
    }
  }

  async function togglePin(noteId: string) {
    try {
      const note = notes.find(n => n.id === noteId);
      if (!note) return;

      setError('');
      const response = await fetch(`${API_BASE}/api/memory/${noteId}?workspace_root=${encodeURIComponent(workspaceRoot)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pinned: !note.pinned })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }

      await loadNotes();
    } catch (error) {
      setError(error instanceof Error ? error.message : 'Failed to update note');
    }
  }

  const filteredNotes = notes.filter(note =>
    note.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
    note.content.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const styles = {
    modal: {
      position: 'fixed' as const,
      inset: 0,
      background: 'rgba(0, 0, 0, 0.5)',
      backdropFilter: 'blur(4px)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000
    },
    container: {
      background: palette.shell,
      borderRadius: 16,
      border: `1px solid ${palette.shellBorder}`,
      width: '90%',
      maxWidth: 900,
      maxHeight: '90vh',
      display: 'flex',
      flexDirection: 'column' as const,
      overflow: 'hidden'
    },
    header: {
      padding: 20,
      borderBottom: `1px solid ${palette.shellBorder}`,
      display: 'flex',
      justifyContent: 'space-between',
      alignItems: 'center'
    },
    title: {
      fontSize: 20,
      fontWeight: 700,
      color: palette.text
    },
    body: {
      display: 'grid',
      gridTemplateColumns: '300px 1fr',
      flex: 1,
      overflow: 'hidden'
    },
    listPanel: {
      borderRight: `1px solid ${palette.shellBorder}`,
      overflow: 'auto',
      display: 'flex',
      flexDirection: 'column' as const
    },
    searchBox: {
      padding: 12,
      borderBottom: `1px solid ${palette.shellBorder}`
    },
    searchInput: {
      width: '100%',
      padding: '8px 12px',
      borderRadius: 8,
      border: `1px solid ${palette.shellBorder}`,
      background: palette.cardAlt,
      color: palette.text,
      fontSize: 14
    },
    noteList: {
      flex: 1,
      overflow: 'auto'
    },
    noteItem: {
      padding: 12,
      borderBottom: `1px solid ${palette.shellBorder}`,
      cursor: 'pointer',
      transition: 'background 0.2s'
    },
    noteItemActive: {
      background: palette.accentSoft
    },
    noteTitle: {
      fontSize: 14,
      fontWeight: 600,
      color: palette.text,
      marginBottom: 4
    },
    noteCategory: {
      fontSize: 12,
      color: palette.muted,
      display: 'inline-block',
      background: palette.bg,
      padding: '2px 6px',
      borderRadius: 4
    },
    detailPanel: {
      padding: 20,
      overflow: 'auto',
      display: 'flex',
      flexDirection: 'column' as const
    },
    detailTitle: {
      fontSize: 18,
      fontWeight: 700,
      color: palette.text,
      marginBottom: 12
    },
    detailContent: {
      fontSize: 14,
      color: palette.text,
      lineHeight: 1.6,
      marginBottom: 16,
      flex: 1,
      whiteSpace: 'pre-wrap' as const,
      wordBreak: 'break-word' as const
    },
    buttonGroup: {
      display: 'flex',
      gap: 8
    },
    button: {
      padding: '8px 12px',
      borderRadius: 8,
      border: 'none',
      background: palette.accent,
      color: '#fff',
      cursor: 'pointer',
      fontSize: 14,
      fontWeight: 600,
      display: 'flex',
      alignItems: 'center',
      gap: 6
    },
    secondaryButton: {
      background: palette.cardAlt,
      border: `1px solid ${palette.shellBorder}`,
      color: palette.text
    },
    errorMsg: {
      padding: '0 20px 16px',
      color: palette.bad,
      fontSize: 12
    }
  };

  return (
    <div style={styles.modal} onClick={onClose}>
      <div style={styles.container} onClick={(e) => e.stopPropagation()}>
        <div style={styles.header}>
          <div style={styles.title}>Memory Editor</div>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: palette.text }}
          >
            <X size={24} />
          </button>
        </div>

        {error ? <div style={styles.errorMsg}>{error}</div> : null}

        <div style={styles.body}>
          <div style={styles.listPanel}>
            <div style={styles.searchBox}>
              <input
                type="text"
                placeholder="Search notes..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                style={styles.searchInput}
              />
            </div>

            <div style={styles.noteList}>
              {loading ? (
                <div style={{ padding: 12, color: palette.muted }}>Loading...</div>
              ) : filteredNotes.length === 0 ? (
                <div style={{ padding: 12, color: palette.muted }}>No notes</div>
              ) : (
                filteredNotes.map((note) => (
                  <div
                    key={note.id}
                    style={{
                      ...styles.noteItem,
                      ...(selectedNote?.id === note.id ? styles.noteItemActive : {})
                    }}
                    onClick={() => setSelectedNote(note)}
                  >
                    <div style={styles.noteTitle}>
                      {note.pinned && <Pin size={12} style={{ marginRight: 4 }} />}
                      {note.title}
                    </div>
                    <div style={styles.noteCategory}>{note.category}</div>
                  </div>
                ))
              )}
            </div>

            <button
              onClick={() => setIsCreating(true)}
              style={{ ...styles.button, margin: 12, justifyContent: 'center' }}
            >
              <Plus size={16} />
              New Note
            </button>
          </div>

          <div style={styles.detailPanel}>
            {isCreating ? (
              <div>
                <input
                  type="text"
                  placeholder="Note title..."
                  value={newNote.title}
                  onChange={(e) => setNewNote({ ...newNote, title: e.target.value })}
                  style={{ ...styles.searchInput, marginBottom: 12 }}
                />
                <select
                  value={newNote.category}
                  onChange={(e) => setNewNote({ ...newNote, category: e.target.value })}
                  style={{ ...styles.searchInput, marginBottom: 12 }}
                >
                  <option value="insight">Insight</option>
                  <option value="fix">Fix</option>
                  <option value="pattern">Pattern</option>
                  <option value="bug">Bug</option>
                  <option value="feature">Feature</option>
                </select>
                <textarea
                  placeholder="Note content..."
                  value={newNote.content}
                  onChange={(e) => setNewNote({ ...newNote, content: e.target.value })}
                  style={{ ...styles.searchInput, marginBottom: 12, minHeight: 150, resize: 'none' }}
                />
                <div style={styles.buttonGroup}>
                  <button onClick={createNote} style={styles.button}>
                    <Save size={16} />
                    Save Note
                  </button>
                  <button
                    onClick={() => setIsCreating(false)}
                    style={{ ...styles.button, ...styles.secondaryButton }}
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : selectedNote ? (
              <>
                <div style={styles.detailTitle}>{selectedNote.title}</div>
                <div style={{ marginBottom: 12, display: 'flex', gap: 8 }}>
                  <span style={styles.noteCategory}>{selectedNote.category}</span>
                  <span style={{ fontSize: 12, color: palette.muted }}>
                    Confidence: {(selectedNote.confidence * 100).toFixed(0)}%
                  </span>
                </div>
                <div style={styles.detailContent}>{selectedNote.content}</div>
                <div style={styles.buttonGroup}>
                  <button
                    onClick={() => togglePin(selectedNote.id)}
                    style={{ ...styles.button, ...styles.secondaryButton }}
                  >
                    {selectedNote.pinned ? <PinOff size={16} /> : <Pin size={16} />}
                    {selectedNote.pinned ? 'Unpin' : 'Pin'}
                  </button>
                  <button
                    onClick={() => deleteNote(selectedNote.id)}
                    style={{ ...styles.button, ...styles.secondaryButton }}
                  >
                    <Trash2 size={16} />
                    Delete
                  </button>
                </div>
              </>
            ) : (
              <div style={{ color: palette.muted }}>Select a note or create a new one</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
