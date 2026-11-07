declare const __ASSET_URLS__: Record<string, string>;
const urls: Record<string, string> = typeof __ASSET_URLS__ === 'undefined' ? {} : __ASSET_URLS__;

/** Generated at build time; content hashes make long browser caching safe. */
export function assetURL(path: string): string {
  return urls[path] ?? path;
}

/** Set sizes/srcset before src so the browser requests only its chosen size. */
export function portraitSources(path: string): {src: string; srcset: string} {
  return {src: assetURL(path), srcset: [320, 640, 960]
    .filter(width => urls[`${path}?width=${width}`])
    .map(width => `${urls[`${path}?width=${width}`]} ${width}w`).join(', ')};
}

export function assetMarkup(html: string): string {
  return html.replace(/src="(\/assets\/[^"\s]+)"/g, (_match, path: string) => `src="${assetURL(path)}"`);
}
