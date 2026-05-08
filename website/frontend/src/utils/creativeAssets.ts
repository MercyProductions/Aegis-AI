import type { ChatMediaJob, MediaAsset, MediaJobResponse } from '../types';
import { getResolvedApiBase } from '../api';

export type PreviewableMediaJob = MediaJobResponse | ChatMediaJob;

const imageFormats = new Set(['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp']);
const audioFormats = new Set(['wav', 'mp3', 'midi']);

export function creativeAssetUrl(path: string): string {
  const base = (getResolvedApiBase() || import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8787').replace(/\/+$/, '');
  return `${base}/api/creative-studio/assets/file?path=${encodeURIComponent(path)}`;
}

export function mediaJobPreviewAsset(job: PreviewableMediaJob | null | undefined): MediaAsset | null {
  return (
    job?.assets.find((asset) => imageFormats.has(asset.format.toLowerCase())) ??
    job?.assets.find((asset) => audioFormats.has(asset.format.toLowerCase())) ??
    null
  );
}

export function mediaJobImageAsset(job: PreviewableMediaJob | null | undefined): MediaAsset | null {
  return job?.assets.find((asset) => imageFormats.has(asset.format.toLowerCase())) ?? null;
}

export function mediaJobAudioAsset(job: PreviewableMediaJob | null | undefined): MediaAsset | null {
  return job?.assets.find((asset) => audioFormats.has(asset.format.toLowerCase())) ?? null;
}

export function creativeStudioTabForMediaJob(job: PreviewableMediaJob): 'image' | 'video' | 'beat' | 'voice' | 'library' {
  const studio = String(job.studio || '').toLowerCase();
  const kind = String(job.kind || '').toLowerCase();
  if (studio === 'video' || kind.includes('video') || kind === 'animation' || kind === 'logo_intro') return 'video';
  if (studio === 'beat' || kind.includes('beat') || kind.includes('music')) return 'beat';
  if (studio === 'voice' || kind.includes('voice') || kind.includes('audio')) return 'voice';
  return 'image';
}

export function mediaJobAssetLabel(job: PreviewableMediaJob): string {
  const count = job.assets.length;
  return `${count} asset${count === 1 ? '' : 's'}`;
}
