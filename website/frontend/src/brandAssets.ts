const assetBase = (import.meta.env.BASE_URL ?? '/').replace(/\/+$/, '');
const brandPath = (path: string) => `${assetBase}${path}`;

export const brandAssets = {
  logo: brandPath('/brand/auralith-logo.png'),
  mark: brandPath('/brand/auralith-mark-ui.png'),
  markSource: brandPath('/brand/auralith-mark.png'),
  wordmark: brandPath('/brand/auralith-wordmark.png'),
  banner: brandPath('/brand/auralith-banner.png'),
  brandKit: brandPath('/brand/auralith-brand-kit.png')
} as const;
