const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const outRoot = 'E:\\nan\\《基于 RAG 与大语言模型的网络新闻真伪鉴别系统设计》\\报告\\第五章撰写';
const figureDir = path.join(outRoot, 'chapter5_figures');
const runFile = path.join(outRoot, 'chapter5_run.json');
const frontendUrl = 'http://127.0.0.1:5173';
const apiUrl = 'http://127.0.0.1:8000/api';
const edgePath = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const password = 'Chapter5Demo!2026';

fs.mkdirSync(figureDir, { recursive: true });

async function apiLogin(username) {
  const response = await fetch(`${apiUrl}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password })
  });
  if (!response.ok) {
    throw new Error(`login failed for ${username}: ${response.status}`);
  }
  const payload = await response.json();
  return payload.data;
}

async function makeContext(browser, authData) {
  const context = await browser.newContext({
    viewport: { width: 1600, height: 950 },
    deviceScaleFactor: 1,
    locale: 'zh-CN',
    acceptDownloads: true
  });
  const token = authData.access_token;
  const user = authData.user || {};
  await context.addInitScript(({ token, user }) => {
    window.localStorage.setItem('zhiyun_bianzhen_token', token);
    window.localStorage.setItem('zhiyun_bianzhen_user', JSON.stringify(user));
  }, { token, user });
  return context;
}

async function gotoReady(page, url) {
  await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
  await page.waitForTimeout(1200);
}

async function shot(page, name, description, options = {}) {
  const file = path.join(figureDir, `${name}.png`);
  await page.screenshot({ path: file, fullPage: false, ...options });
  return { name, file, description };
}

async function safeStep(manifest, name, description, fn) {
  try {
    const result = await fn();
    manifest.screenshots.push(result || { name, description, skipped: true });
    console.log(`[ok] ${name}`);
  } catch (error) {
    manifest.failures.push({ name, description, error: String(error && error.message || error) });
    console.log(`[warn] ${name}: ${error && error.message || error}`);
  }
}

async function fillDetectPreview(page) {
  await gotoReady(page, `${frontendUrl}/detect`);
  const urlInput = page.getByPlaceholder('粘贴新闻链接，如 https://...');
  await urlInput.fill('https://www.gov.cn/');
  await page.getByRole('button', { name: /^提取$/ }).click();
  await page.waitForTimeout(5000);
  await page.getByPlaceholder('请输入需要检测的新闻标题').waitFor({ timeout: 20000 });
}

async function scrollToText(page, text) {
  const locator = page.getByText(text, { exact: false }).first();
  await locator.waitFor({ timeout: 20000 });
  await locator.scrollIntoViewIfNeeded();
  await page.waitForTimeout(700);
}

async function main() {
  const run = JSON.parse(fs.readFileSync(runFile, 'utf8'));
  const detectionId = run.detection_id || 62;
  const webDetectionId = run.web_supplement_demo?.detection_id || 58;
  const degradedDetectionId = run.degradation_demo?.detection_id || 59;
  const manifest = {
    viewport: '1600x950',
    frontendUrl,
    detectionId,
    webDetectionId,
    degradedDetectionId,
    screenshots: [],
    failures: []
  };

  const [userAuth, adminAuth] = await Promise.all([
    apiLogin('chapter5_user'),
    apiLogin('chapter5_admin')
  ]);

  const browser = await chromium.launch({
    headless: true,
    executablePath: fs.existsSync(edgePath) ? edgePath : undefined
  });
  const userContext = await makeContext(browser, userAuth);
  const adminContext = await makeContext(browser, adminAuth);
  const userPage = await userContext.newPage();
  const adminPage = await adminContext.newPage();

  await safeStep(manifest, 'fig5-7-detect-url-preview', '新闻检测页面与URL提取回填状态', async () => {
    await fillDetectPreview(userPage);
    return shot(userPage, 'fig5-7-detect-url-preview', '新闻检测页面与URL提取回填状态');
  });

  await safeStep(manifest, 'fig5-8-result-overview', '检测结果总览、评分与报告按钮', async () => {
    await gotoReady(userPage, `${frontendUrl}/result/${detectionId}`);
    return shot(userPage, 'fig5-8-result-overview', '检测结果总览、评分与报告按钮');
  });

  await safeStep(manifest, 'fig5-9-result-evidence', '有效证据与证据质量区域', async () => {
    await gotoReady(userPage, `${frontendUrl}/result/${detectionId}`);
    await userPage.evaluate(() => window.scrollTo(0, 1720));
    await userPage.waitForTimeout(700);
    return shot(userPage, 'fig5-9-result-evidence', '有效证据与证据质量区域');
  });

  await safeStep(manifest, 'fig5-10-web-excluded-evidence', '联网候选证据与排除证据区域', async () => {
    await gotoReady(adminPage, `${frontendUrl}/result/${webDetectionId}`);
    await scrollToText(adminPage, '排除证据');
    return shot(adminPage, 'fig5-10-web-excluded-evidence', '联网候选证据与排除证据区域');
  });

  await safeStep(manifest, 'fig5-11-history-report', '历史记录与PDF报告状态', async () => {
    await gotoReady(userPage, `${frontendUrl}/history`);
    return shot(userPage, 'fig5-11-history-report', '历史记录与PDF报告状态');
  });

  await safeStep(manifest, 'fig5-12-admin-knowledge', '管理员知识库与向量同步状态', async () => {
    await gotoReady(adminPage, `${frontendUrl}/admin/knowledge`);
    const keyword = adminPage.getByPlaceholder('标题、正文、摘要或关键词');
    await keyword.fill('第五章演示');
    await adminPage.getByRole('button', { name: /查询/ }).click();
    await adminPage.waitForTimeout(1800);
    return shot(adminPage, 'fig5-12-admin-knowledge', '管理员知识库与向量同步状态');
  });

  await safeStep(manifest, 'fig5-13-admin-high-risk', '高风险记录复核列表', async () => {
    await gotoReady(adminPage, `${frontendUrl}/admin/high-risk`);
    await adminPage.waitForTimeout(1600);
    return shot(adminPage, 'fig5-13-admin-high-risk', '高风险记录复核列表');
  });

  await safeStep(manifest, 'fig5-14-degraded-result', '模型异常或仲裁不可用降级展示', async () => {
    await gotoReady(adminPage, `${frontendUrl}/result/${degradedDetectionId}`);
    await scrollToText(adminPage, '证据仲裁暂不可用');
    return shot(adminPage, 'fig5-14-degraded-result', '模型异常或仲裁不可用降级展示');
  });

  await userContext.close();
  await adminContext.close();
  await browser.close();

  const manifestFile = path.join(figureDir, 'screenshot_manifest.json');
  fs.writeFileSync(manifestFile, JSON.stringify(manifest, null, 2), 'utf8');
  console.log(manifestFile);
  if (manifest.failures.length) {
    process.exitCode = 2;
  }
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
