import sharp from 'sharp';
import {createHash} from 'node:crypto';
import {readdir, readFile, mkdir, stat, writeFile, rename} from 'node:fs/promises';
import {join, relative} from 'node:path';

/** Lossless derivatives only: originals and atlas coordinates remain unchanged. */
export async function optimizeAssets(root: string): Promise<Record<string, string>> {
  const output = join(root, 'optimized');
  await mkdir(output, {recursive: true});
  const urls: Record<string, string> = {};
  let originalBytes = 0, optimizedBytes = 0;
  async function visit(directory: string) {
    for (const item of await readdir(directory, {withFileTypes: true})) {
      if (item.name === 'optimized') continue;
      const path = join(directory, item.name);
      if (item.isDirectory()) {await visit(path); continue;}
      if (!item.name.endsWith('.png')) continue;
      const input = await readFile(path);
      const hash = createHash('sha256').update(input).update(`webp-lossless-6:${sharp.versions.sharp}`).digest('hex').slice(0, 24);
      const filename = `${hash}.webp`;
      const destination = join(output, filename);
      try {await stat(destination);} catch {
        const temporary = `${destination}.${process.pid}.tmp`;
        await sharp(input).webp({lossless: true, effort: 6}).toFile(temporary);
        await rename(temporary, destination);
      }
      const size = (await stat(destination)).size;
      const key = '/assets/' + relative(root, path).split('\\').join('/');
      // Keep the PNG if this particular derivative is larger.
      if (size < input.length) urls[key] = '/assets/optimized/' + filename;
      if (key.startsWith('/assets/portraits/')) {
        for (const width of [320, 640, 960]) {
          const smallHash = createHash('sha256').update(input).update(`portrait-nearest-${width}-6:${sharp.versions.sharp}`).digest('hex').slice(0,24);
          const smallName = `${smallHash}.webp`;
          const smallPath = join(output, smallName);
          try {await stat(smallPath);} catch {
            const temporary = `${smallPath}.${process.pid}.tmp`;
            await sharp(input).resize({width, withoutEnlargement:true, kernel:'nearest'}).webp({lossless:true, effort:6}).toFile(temporary);
            await rename(temporary, smallPath);
          }
          urls[`${key}?width=${width}`] = '/assets/optimized/' + smallName;
        }
      }
      originalBytes += input.length; optimizedBytes += Math.min(size, input.length);
    }
  }
  await visit(root);
  await writeFile(join(output, 'report.json'), JSON.stringify({originalBytes, optimizedBytes,
    images: Object.keys(urls).filter(path => !path.includes('?width=')).length,
    portraitVariants: Object.keys(urls).filter(path => path.includes('?width=')).length}, null, 2));
  console.log(`Images: ${(originalBytes / 1e6).toFixed(1)} → ${(optimizedBytes / 1e6).toFixed(1)} MB (lossless)`);
  return urls;
}
