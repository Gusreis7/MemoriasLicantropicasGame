import {afterEach,describe,expect,it,vi} from 'vitest';

afterEach(()=>{vi.unstubAllGlobals();vi.resetModules();});

describe('retratos responsivos',()=>{
  it('expõe tamanhos disponíveis e mantém a imagem inteira como fallback',async()=>{
    vi.stubGlobal('__ASSET_URLS__',{
      '/assets/portraits/capitu.png':'/assets/optimized/full.webp',
      '/assets/portraits/capitu.png?width=320':'/assets/optimized/small.webp',
      '/assets/portraits/capitu.png?width=640':'/assets/optimized/medium.webp',
    });
    const {portraitSources}=await import('./assets');
    expect(portraitSources('/assets/portraits/capitu.png')).toEqual({
      src:'/assets/optimized/full.webp',srcset:'/assets/optimized/small.webp 320w, /assets/optimized/medium.webp 640w',
    });
  });
  it('preserva o caminho original quando não há cópias geradas',async()=>{
    const {portraitSources}=await import('./assets');
    expect(portraitSources('/assets/portraits/test.png')).toEqual({src:'/assets/portraits/test.png',srcset:''});
  });
});
