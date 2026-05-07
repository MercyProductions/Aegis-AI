import { lazy } from 'react';

export const ApprovalSettings = lazy(() =>
  import('./ApprovalSettings').then((module) => ({ default: module.ApprovalSettings }))
);

export const MemoryEditor = lazy(() =>
  import('./MemoryEditor').then((module) => ({ default: module.MemoryEditor }))
);

export const ObservabilityPanel = lazy(() =>
  import('./ObservabilityPanel').then((module) => ({ default: module.ObservabilityPanel }))
);

export const PublicSite = lazy(() =>
  import('./PublicSite').then((module) => ({ default: module.PublicSite }))
);

export const ProductizationSurface = lazy(() =>
  import('./ProductizationSurface').then((module) => ({ default: module.ProductizationSurface }))
);

export const CreativeStudioSurface = lazy(() =>
  import('./CreativeStudioSurface').then((module) => ({ default: module.CreativeStudioSurface }))
);

export const ModelSelector = lazy(() =>
  import('./ModelSelector').then((module) => ({ default: module.ModelSelector }))
);

export const TaskStatusSummary = lazy(() =>
  import('./TaskStatusSummary').then((module) => ({ default: module.TaskStatusSummary }))
);
