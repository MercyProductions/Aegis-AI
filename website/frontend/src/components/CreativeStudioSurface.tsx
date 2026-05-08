import type { ReactNode } from 'react';
import { Download, Loader2, Play, Search, Square, Zap } from 'lucide-react';
import { getCreativeJob } from '../api';
import { formatDateTime, formatStatusLabel } from '../utils/appUi';
import { creativeAssetUrl } from '../utils/creativeAssets';
import type {
  MediaAssetLibraryResponse,
  MediaCapabilitiesResponse,
  MediaJobResponse,
  MediaKind
} from '../types';

type AppStyleBag = Record<string, any>;
type PaletteLike = Record<string, unknown>;
export type CreativeStudioTab = 'image' | 'video' | 'beat' | 'voice' | 'library';

type CreativeStudioSurfaceProps = {
  creativeStudioTab: CreativeStudioTab;
  creativePrompt: string;
  creativeStyle: string;
  creativeCapabilities: MediaCapabilitiesResponse | null;
  creativeLibrary: MediaAssetLibraryResponse | null;
  creativeJobs: MediaJobResponse[];
  selectedCreativeJob: MediaJobResponse | null;
  creativeStatus: string;
  creativeLoading: boolean;
  creativeAction: string;
  palette: PaletteLike;
  styles: AppStyleBag;
  renderSurfaceHeader: (icon: ReactNode, title: string, description: string, actions?: ReactNode) => ReactNode;
  creativeKindForTab: (tab?: CreativeStudioTab) => MediaKind;
  creativeProviderForTab: (tab?: CreativeStudioTab) => string;
  setCreativeStudioTab: (tab: CreativeStudioTab) => void;
  setCreativePrompt: (value: string) => void;
  setCreativeStyle: (value: string) => void;
  setCreativeProviderId: (value: string) => void;
  setSelectedCreativeJob: (job: MediaJobResponse | null) => void;
  setCreativeStatus: (value: string) => void;
  refreshCreativeStudio: () => void | Promise<void>;
  generateCreativeAsset: () => void | Promise<void>;
  exportSelectedCreativeJob: (format: string) => void | Promise<void>;
  cancelSelectedCreativeJob: () => void | Promise<void>;
};

export function CreativeStudioSurface({
  creativeStudioTab,
  creativePrompt,
  creativeStyle,
  creativeCapabilities,
  creativeLibrary,
  creativeJobs,
  selectedCreativeJob,
  creativeStatus,
  creativeLoading,
  creativeAction,
  palette,
  styles,
  renderSurfaceHeader,
  creativeKindForTab,
  creativeProviderForTab,
  setCreativeStudioTab,
  setCreativePrompt,
  setCreativeStyle,
  setCreativeProviderId,
  setSelectedCreativeJob,
  setCreativeStatus,
  refreshCreativeStudio,
  generateCreativeAsset,
  exportSelectedCreativeJob,
  cancelSelectedCreativeJob
}: CreativeStudioSurfaceProps) {
  const tabs: Array<{ id: CreativeStudioTab; label: string; prompt: string }> = [
    { id: 'image', label: 'Image', prompt: 'Create a premium product mockup for Auralith Creative Studio' },
    { id: 'video', label: 'Video', prompt: 'Create a short app showcase video for Auralith Creative Studio' },
    { id: 'beat', label: 'Beat', prompt: 'Generate a clean tech beat with crisp drums and a loopable hook' },
    { id: 'voice', label: 'Voice', prompt: 'Create a calm narration for a premium product launch' },
    { id: 'library', label: 'Library', prompt: creativePrompt }
  ];
  const currentKind = creativeKindForTab();
  const providers = (creativeCapabilities?.providers ?? []).filter((provider) => provider.supports.includes(currentKind));
  const selectedProviderId = creativeProviderForTab();
  const selectedProvider = creativeCapabilities?.providers.find((provider) => provider.id === selectedProviderId);
  const imageAssets = selectedCreativeJob?.assets.filter((asset) => ['png', 'jpg', 'gif', 'svg'].includes(asset.format)) ?? [];
  const previewAsset = imageAssets[0] ?? null;
  const audioAssets = selectedCreativeJob?.assets.filter((asset) => ['wav', 'mp3', 'midi'].includes(asset.format)) ?? [];
  const inputBorder = typeof palette.inputBorder === 'string' ? palette.inputBorder : 'rgba(255,255,255,0.12)';

  return (
    <div style={styles.surfacePage}>
      {renderSurfaceHeader(
        <Zap size={22} />,
        'Creative Studio',
        'Generate, organize, revise, and export local images, motion packages, beats, voice drafts, prompts, and asset packs.',
        <div style={styles.surfaceActions}>
          <button type="button" style={styles.secondaryButton(palette)} onClick={() => void refreshCreativeStudio()} disabled={creativeLoading}>
            {creativeLoading ? <Loader2 size={16} className="spin" /> : <Search size={16} />}
            Refresh
          </button>
          <button
            type="button"
            style={styles.primaryButton(palette)}
            onClick={() => void generateCreativeAsset()}
            disabled={Boolean(creativeAction) || creativeStudioTab === 'library'}
          >
            {creativeAction.startsWith('generate') ? <Loader2 size={16} className="spin" /> : <Play size={16} />}
            Generate
          </button>
        </div>
      )}

      <div style={styles.metricGrid}>
        <div style={styles.metricCard(palette)}>
          <span style={styles.metricLabel(palette)}>Jobs</span>
          <strong style={styles.metricValue(palette)}>{creativeJobs.length}</strong>
        </div>
        <div style={styles.metricCard(palette)}>
          <span style={styles.metricLabel(palette)}>Assets</span>
          <strong style={styles.metricValue(palette)}>{creativeLibrary?.total_assets ?? 0}</strong>
        </div>
        <div style={styles.metricCard(palette)}>
          <span style={styles.metricLabel(palette)}>Providers</span>
          <strong style={styles.metricValue(palette)}>{creativeCapabilities?.providers.length ?? 0}</strong>
        </div>
        <div style={styles.metricCard(palette)}>
          <span style={styles.metricLabel(palette)}>Formats</span>
          <strong style={styles.metricValue(palette)}>{creativeLibrary?.formats.slice(0, 4).join(', ') || 'pending'}</strong>
        </div>
      </div>

      {creativeStatus ? (
        <div style={styles.eventRow(palette, creativeStatus.includes('Could not') || creativeStatus.includes('requires') ? 'error' : 'ok')}>
          <div>
            <strong style={styles.eventTitle(palette)}>Creative Status</strong>
            <div style={styles.eventDetail(palette)}>{creativeStatus}</div>
          </div>
        </div>
      ) : null}

      <section style={styles.settingsSection(palette)}>
        <div style={styles.segmentedControl(palette)} role="group" aria-label="Creative Studio sections">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              type="button"
              style={styles.segmentedButton(palette, creativeStudioTab === tab.id)}
              onClick={() => {
                setCreativeStudioTab(tab.id);
                if (tab.id !== 'library') setCreativePrompt(tab.prompt);
              }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </section>

      {creativeStudioTab !== 'library' ? (
        <div style={styles.surfaceColumns}>
          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Prompt Builder</h3>
              <span style={styles.contextTag(palette)}>{formatStatusLabel(currentKind)}</span>
            </div>
            <label style={styles.fieldLabel(palette)}>
              <span>Prompt</span>
              <textarea
                value={creativePrompt}
                onChange={(event) => setCreativePrompt(event.target.value)}
                rows={5}
                style={styles.fieldTextarea(palette)}
              />
            </label>
            <label style={styles.fieldLabel(palette)}>
              <span>Style</span>
              <input value={creativeStyle} onChange={(event) => setCreativeStyle(event.target.value)} style={styles.fieldInput(palette)} />
            </label>
            <label style={styles.fieldLabel(palette)}>
              <span>Provider</span>
              <select value={selectedProviderId} onChange={(event) => setCreativeProviderId(event.target.value)} style={styles.fieldInput(palette)}>
                {providers.map((provider) => (
                  <option key={provider.id} value={provider.id}>
                    {provider.name}
                    {provider.paid ? ' (approval)' : ''}
                  </option>
                ))}
                {!providers.length ? <option value={selectedProviderId}>{selectedProvider?.name || selectedProviderId}</option> : null}
              </select>
            </label>
            <div style={styles.tagWrap}>
              <span style={styles.contextTag(palette)}>local drafts first</span>
              <span style={styles.contextTag(palette)}>prompt pack saved</span>
              <span style={styles.contextTag(palette)}>exports supported</span>
            </div>
            {selectedProvider ? <div style={styles.eventDetail(palette)}>{selectedProvider.notes}</div> : null}
          </section>

          <section style={styles.settingsSection(palette)}>
            <div style={styles.sectionHeaderInline}>
              <h3 style={styles.settingsHeading(palette)}>Selected Job</h3>
              <span style={styles.diagnosticChip(palette, selectedCreativeJob?.status === 'failed' ? 'error' : selectedCreativeJob ? 'ok' : 'warning')}>
                {selectedCreativeJob ? formatStatusLabel(selectedCreativeJob.status) : 'None'}
              </span>
            </div>
            {selectedCreativeJob ? (
              <>
                {previewAsset ? (
                  <img
                    src={creativeAssetUrl(previewAsset.thumbnail_path || previewAsset.path)}
                    alt={previewAsset.role}
                    style={{ width: '100%', maxHeight: 260, objectFit: 'cover', borderRadius: 8, border: `1px solid ${inputBorder}` }}
                  />
                ) : audioAssets.length ? (
                  <audio src={creativeAssetUrl(audioAssets[0].path)} controls style={{ width: '100%' }} />
                ) : (
                  <div style={styles.emptyPanel(palette)}>This job saved source assets without a browser preview.</div>
                )}
                <div style={styles.workspaceMeta(palette)}>
                  <strong>Provider</strong>
                  <span>{selectedCreativeJob.provider_name}</span>
                  <strong>Assets</strong>
                  <span>{selectedCreativeJob.assets.length}</span>
                  <strong>Seed</strong>
                  <span>{selectedCreativeJob.seed ?? 'n/a'}</span>
                  <strong>Time</strong>
                  <span>{selectedCreativeJob.time_taken_seconds}s</span>
                </div>
                <div style={styles.rowActions}>
                  {['zip', 'png', 'jpg', 'svg', 'wav', 'midi'].map((format) => (
                    <button
                      key={format}
                      type="button"
                      style={styles.iconTextButton(palette)}
                      onClick={() => void exportSelectedCreativeJob(format)}
                      disabled={Boolean(creativeAction)}
                    >
                      <Download size={14} />
                      {format.toUpperCase()}
                    </button>
                  ))}
                  <button type="button" style={styles.iconTextButton(palette)} onClick={() => void cancelSelectedCreativeJob()} disabled={Boolean(creativeAction)}>
                    <Square size={14} />
                    Cancel
                  </button>
                </div>
              </>
            ) : (
              <div style={styles.emptyPanel(palette)}>Generate or select a creative job to preview assets and exports.</div>
            )}
          </section>
        </div>
      ) : null}

      <div style={styles.surfaceColumns}>
        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Generation Jobs</h3>
            <span style={styles.contextTag(palette)}>{creativeJobs.length} tracked</span>
          </div>
          <div style={styles.modelList}>
            {creativeJobs.slice(0, 12).map((job) => (
              <button
                key={job.id}
                type="button"
                style={styles.modelRow(palette, selectedCreativeJob?.id === job.id)}
                onClick={() => {
                  setSelectedCreativeJob(job);
                  void getCreativeJob(job.id).then(setSelectedCreativeJob).catch((error) => {
                    setCreativeStatus(error instanceof Error ? error.message : 'Could not open creative job');
                  });
                }}
              >
                <div style={styles.modelRowMain}>
                  <div style={styles.modelRowTop}>
                    <div style={styles.cardTitle(palette)}>{formatStatusLabel(job.kind)}</div>
                    <span style={styles.diagnosticChip(palette, job.status === 'failed' ? 'error' : job.status === 'canceled' ? 'warning' : 'ok')}>
                      {formatStatusLabel(job.status)}
                    </span>
                  </div>
                  <div style={styles.eventDetail(palette)}>{job.prompt}</div>
                  <div style={styles.tagWrap}>
                    <span style={styles.contextTag(palette)}>{job.provider_name || job.provider_id}</span>
                    <span style={styles.contextTag(palette)}>{job.assets.length} assets</span>
                    <span style={styles.contextTag(palette)}>{formatDateTime(job.created_at)}</span>
                  </div>
                </div>
              </button>
            ))}
            {!creativeJobs.length ? <div style={styles.emptyPanel(palette)}>Creative jobs will appear after the first generation.</div> : null}
          </div>
        </section>

        <section style={styles.settingsSection(palette)}>
          <div style={styles.sectionHeaderInline}>
            <h3 style={styles.settingsHeading(palette)}>Asset Library</h3>
            <span style={styles.contextTag(palette)}>{creativeLibrary?.total_assets ?? 0} asset(s)</span>
          </div>
          <div style={styles.eventList}>
            {(creativeLibrary?.assets ?? []).slice(0, 14).map((asset) => (
              <div key={asset.id || asset.path} style={styles.eventRow(palette, 'ok')}>
                <div>
                  <strong style={styles.eventTitle(palette)}>{asset.role}</strong>
                  <div style={styles.eventDetail(palette)}>{asset.path}</div>
                  <div style={styles.tagWrap}>
                    <span style={styles.contextTag(palette)}>{asset.format}</span>
                    <span style={styles.contextTag(palette)}>{formatStatusLabel(asset.kind)}</span>
                    {asset.editable ? <span style={styles.goodTag(palette)}>Editable</span> : null}
                  </div>
                </div>
              </div>
            ))}
            {!creativeLibrary?.assets.length ? <div style={styles.emptyPanel(palette)}>No creative assets are saved yet.</div> : null}
          </div>
        </section>
      </div>
    </div>
  );
}
