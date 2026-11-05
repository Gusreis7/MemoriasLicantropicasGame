import {chromium} from '@playwright/test';
import assert from 'node:assert/strict';
const base=process.env.SECURITY_BASE_URL??'http://127.0.0.1:17077';
const admin=process.env.SECURITY_ADMIN_URL??'http://127.0.0.1:17078';
const browser=await chromium.launch({executablePath:process.env.BRAVE_PATH??'/usr/bin/brave-browser',args:['--no-sandbox','--disable-dev-shm-usage']});
try{
 const page=await browser.newPage();const response=await page.goto(base);assert.equal(response.status(),200);
 const csp=response.headers()['content-security-policy'];assert.ok(csp.includes("script-src 'self';"));assert.ok(csp.includes("object-src 'none'"));assert.ok(!csp.includes('unsafe-eval'));
 for(const path of ['/admin','/admin.html','/%61dmin.html','/assets/admin-any.js','/docs','/openapi.json'])assert.equal((await page.request.get(base+path)).status(),404,path);
 assert.equal((await page.request.get(admin+'/admin/api/v1/games')).status(),401);
 assert.equal((await page.request.post(admin+'/admin/api/v1/auth/login',{headers:{Origin:'https://attacker.example'},data:{username:'admin',password:'irrelevant'}})).status(),403);
 const login=await page.request.post(admin+'/admin/api/v1/auth/login',{headers:{Origin:new URL(admin).origin},data:{username:'admin',password:'security-test-password-not-production'}});assert.equal(login.status(),200);
 assert.equal((await page.request.get(admin+'/admin/api/v1/games')).status(),200);
 assert.equal((await page.request.post(admin+'/admin/api/v1/auth/logout',{headers:{Origin:new URL(admin).origin}})).status(),200);
 assert.equal((await page.request.get(admin+'/admin/api/v1/games')).status(),401);
 await page.evaluate(()=>{const script=document.createElement('script');script.textContent='window.inlineInjected=true';document.body.append(script);});
 assert.equal(await page.evaluate(()=>Boolean(window.inlineInjected)),false);
 console.log('Docker/Brave: CSP blocks inline JS; public admin denied; private API requires login and origin.');
}finally{await browser.close();}
