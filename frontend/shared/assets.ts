declare const __ASSET_URLS__: Record<string, string>;
const urls: Record<string, string> = typeof __ASSET_URLS__ === 'undefined' ? {} : __ASSET_URLS__;

/** Generated at build time; content hashes make long browser caching safe. */
export function assetURL(path: string): string {
  return urls[path] ?? path;
}

export function assetMarkup(html: string): string {
  return html.replace(/src="(\/assets\/[^"\s]+)"/g, (_match, path: string) => `src="${assetURL(path)}"`);
}
