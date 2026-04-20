#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { PNG } from 'pngjs';
import pixelmatch from 'pixelmatch';
import { chromium } from 'playwright-core';

const htmlArg = process.argv[2];
const outDirArg = process.argv[3];

if (!htmlArg || !outDirArg) {
  console.error('usage: collect_vague_evidence.mjs <html-path> <artifact-dir>');
  process.exit(1);
}

const htmlPath = path.resolve(process.cwd(), htmlArg);
const htmlDir = path.dirname(htmlPath);
const htmlName = path.basename(htmlPath);
const outDir = path.resolve(process.cwd(), outDirArg);

function contentType(filePath) {
  if (filePath.endsWith('.html')) return 'text/html; charset=utf-8';
  if (filePath.endsWith('.js')) return 'text/javascript; charset=utf-8';
  if (filePath.endsWith('.css')) return 'text/css; charset=utf-8';
  if (filePath.endsWith('.json')) return 'application/json; charset=utf-8';
  if (filePath.endsWith('.svg')) return 'image/svg+xml';
  if (filePath.endsWith('.png')) return 'image/png';
  if (filePath.endsWith('.jpg') || filePath.endsWith('.jpeg')) return 'image/jpeg';
  return 'text/plain; charset=utf-8';
}

async function createServer(rootDir, entryName) {
  const server = http.createServer(async (req, res) => {
    try {
      const reqPath = new URL(req.url, 'http://127.0.0.1').pathname;
      if (reqPath === '/favicon.ico') {
        res.writeHead(204).end();
        return;
      }
      const relative = reqPath === '/' ? `/${entryName}` : reqPath;
      const target = path.normalize(path.join(rootDir, relative));
      if (!target.startsWith(rootDir)) {
        res.writeHead(403).end('forbidden');
        return;
      }
      const data = await fs.readFile(target);
      res.writeHead(200, { 'Content-Type': contentType(target) });
      res.end(data);
    } catch (err) {
      res.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
      res.end(`not found: ${err.message}`);
    }
  });

  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  const address = server.address();
  return {
    server,
    url: `http://127.0.0.1:${address.port}/${entryName}`,
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function round(value, digits = 3) {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

async function readPng(filePath) {
  const buffer = await fs.readFile(filePath);
  return PNG.sync.read(buffer);
}

function averageSample(png, x, y, radius = 2) {
  const cx = clamp(Math.round(x), 0, png.width - 1);
  const cy = clamp(Math.round(y), 0, png.height - 1);
  let totalR = 0;
  let totalG = 0;
  let totalB = 0;
  let totalA = 0;
  let count = 0;

  for (let yy = cy - radius; yy <= cy + radius; yy++) {
    for (let xx = cx - radius; xx <= cx + radius; xx++) {
      if (xx < 0 || yy < 0 || xx >= png.width || yy >= png.height) continue;
      const idx = (png.width * yy + xx) << 2;
      totalR += png.data[idx];
      totalG += png.data[idx + 1];
      totalB += png.data[idx + 2];
      totalA += png.data[idx + 3];
      count += 1;
    }
  }

  const r = Math.round(totalR / count);
  const g = Math.round(totalG / count);
  const b = Math.round(totalB / count);
  const a = Math.round(totalA / count);
  const brightness = Math.round((r + g + b) / 3);

  let label = 'mid';
  if (brightness <= 70 && Math.max(r, g, b) <= 120) {
    label = 'dark-stoneish';
  } else if (brightness >= 205 && Math.min(r, g, b) >= 145) {
    label = 'light-stoneish';
  } else if (r >= 90 && g >= 60 && b <= 120 && brightness >= 90 && brightness <= 190) {
    label = 'boardish';
  }

  return { r, g, b, a, brightness, label };
}

async function diffStats(beforePath, afterPath) {
  const before = await readPng(beforePath);
  const after = await readPng(afterPath);
  if (before.width !== after.width || before.height !== after.height) {
    return {
      changed_pixels: null,
      changed_ratio: null,
      note: 'image size changed',
    };
  }
  const diff = new PNG({ width: before.width, height: before.height });
  const changedPixels = pixelmatch(before.data, after.data, diff.data, before.width, before.height, {
    threshold: 0.1,
  });
  const totalPixels = before.width * before.height;
  return {
    changed_pixels: changedPixels,
    total_pixels: totalPixels,
    changed_ratio: round(changedPixels / totalPixels, 6),
  };
}

async function collectDomSummary(page) {
  return page.evaluate(() => {
    function isVisible(el) {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return (
        rect.width >= 10 &&
        rect.height >= 10 &&
        style.display !== 'none' &&
        style.visibility !== 'hidden' &&
        style.opacity !== '0'
      );
    }

    function selectorHint(el) {
      let hint = el.tagName.toLowerCase();
      if (el.id) hint += `#${el.id}`;
      const classes = [...el.classList].slice(0, 3);
      if (classes.length) hint += `.${classes.join('.')}`;
      return hint;
    }

    function rectOf(el) {
      const rect = el.getBoundingClientRect();
      return {
        x: rect.x,
        y: rect.y,
        width: rect.width,
        height: rect.height,
      };
    }

    function unionRect(els) {
      const rects = els.map((el) => el.getBoundingClientRect()).filter((rect) => rect.width > 0 && rect.height > 0);
      if (!rects.length) return null;
      const left = Math.min(...rects.map((rect) => rect.left));
      const top = Math.min(...rects.map((rect) => rect.top));
      const right = Math.max(...rects.map((rect) => rect.right));
      const bottom = Math.max(...rects.map((rect) => rect.bottom));
      return {
        x: left,
        y: top,
        width: right - left,
        height: bottom - top,
      };
    }

    function candidateScore(rect, bonus = 1) {
      const area = rect.width * rect.height;
      const squareness = 1 - Math.min(0.9, Math.abs(rect.width - rect.height) / Math.max(rect.width, rect.height));
      return area * (0.5 + squareness) * bonus;
    }

    const textLines = (document.body?.innerText || '')
      .split(/\n+/)
      .map((line) => line.replace(/\s+/g, ' ').trim())
      .filter(Boolean);
    const bodyText = textLines.join(' ').slice(0, 1200);
    const statusLines = textLines
      .filter((line) => /(black|white|turn|play|move|captur|status|pass|reset|new|undo|score|suicide|ko|resign)/i.test(line))
      .slice(0, 16);

    const buttons = [...document.querySelectorAll('button,[role="button"],[onclick]')]
      .filter(isVisible)
      .map((el) => ({
        text: (el.innerText || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().slice(0, 80),
        selector: selectorHint(el),
      }))
      .filter((item) => item.text)
      .slice(0, 20);

    const dataCells = [...document.querySelectorAll('[data-cell]')].filter(isVisible);
    const gridLike = [...document.querySelectorAll('div,section,main,article,table')]
      .filter(isVisible)
      .map((el) => {
        const children = [...el.children].filter(isVisible);
        if (children.length < 49 || children.length > 100) return null;
        const union = unionRect(children);
        if (!union || union.width < 200 || union.height < 200) return null;
        return {
          type: 'grid-like',
          source: 'grid-like-children',
          selector: selectorHint(el),
          child_count: children.length,
          rect: union,
          score: candidateScore(union, 1.2 + children.length / 100),
        };
      })
      .filter(Boolean)
      .sort((a, b) => b.score - a.score)
      .slice(0, 6);

    const canvases = [...document.querySelectorAll('canvas')]
      .filter(isVisible)
      .map((el) => ({
        type: 'canvas',
        source: 'canvas',
        selector: selectorHint(el),
        rect: rectOf(el),
        score: candidateScore(rectOf(el), 1.6),
      }))
      .sort((a, b) => b.score - a.score);

    const svgs = [...document.querySelectorAll('svg')]
      .filter(isVisible)
      .map((el) => ({
        type: 'svg',
        source: 'svg',
        selector: selectorHint(el),
        rect: rectOf(el),
        score: candidateScore(rectOf(el), 1.4),
      }))
      .sort((a, b) => b.score - a.score);

    const generic = [...document.querySelectorAll('div,section,main,article,table')]
      .filter((el) => isVisible(el) && !['body', 'html'].includes(el.tagName.toLowerCase()))
      .map((el) => ({
        type: el.tagName.toLowerCase(),
        source: 'generic',
        selector: selectorHint(el),
        rect: rectOf(el),
        score: candidateScore(rectOf(el), 1.0),
      }))
      .filter((item) => item.rect.width >= 220 && item.rect.height >= 220)
      .sort((a, b) => b.score - a.score)
      .slice(0, 10);

    let candidate = null;
    if (dataCells.length >= 25) {
      const union = unionRect(dataCells);
      candidate = {
        type: 'data-cell-grid',
        source: 'data-cells',
        selector: '[data-cell]',
        rect: union,
        count: dataCells.length,
      };
    } else if (gridLike.length) {
      candidate = gridLike[0];
    } else if (canvases.length) {
      candidate = canvases[0];
    } else if (svgs.length) {
      candidate = svgs[0];
    } else if (generic.length) {
      candidate = generic[0];
    }

    const resetCandidates = [...document.querySelectorAll('button,[role="button"],[onclick],a,div,span')]
      .filter(isVisible)
      .map((el) => ({
        text: (el.innerText || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().slice(0, 80),
        selector: selectorHint(el),
      }))
      .filter((item) => item.text && /(new|reset|restart)/i.test(item.text))
      .slice(0, 8);

    return {
      title: document.title || '',
      body_text_excerpt: bodyText,
      status_lines: statusLines,
      buttons,
      counts: {
        canvas: canvases.length,
        svg: svgs.length,
        data_cells: dataCells.length,
        buttonish: buttons.length,
        grid_like: gridLike.length,
      },
      board_candidate: candidate,
      candidate_preview: [...gridLike, ...canvases, ...svgs, ...generic].slice(0, 10),
      reset_candidates: resetCandidates,
    };
  });
}

function normalizeCandidate(candidate, viewport) {
  if (!candidate?.rect) return null;
  const x = clamp(Math.floor(candidate.rect.x), 0, Math.max(0, viewport.width - 2));
  const y = clamp(Math.floor(candidate.rect.y), 0, Math.max(0, viewport.height - 2));
  const width = clamp(Math.ceil(candidate.rect.width), 2, viewport.width - x);
  const height = clamp(Math.ceil(candidate.rect.height), 2, viewport.height - y);
  if (width < 2 || height < 2) return null;
  return {
    ...candidate,
    rect: {
      x,
      y,
      width,
      height,
    },
  };
}

function midpoint(name, left, right) {
  return {
    name,
    i: round((left.i + right.i) / 2, 3),
    j: round((left.j + right.j) / 2, 3),
    x: round((left.x + right.x) / 2, 3),
    y: round((left.y + right.y) / 2, 3),
  };
}

function buildPoints(candidateRect) {
  const margin = 0.1;
  const spanX = candidateRect.width * 0.8;
  const spanY = candidateRect.height * 0.8;
  const xFor = (i) => candidateRect.x + candidateRect.width * margin + (spanX * i) / 8;
  const yFor = (j) => candidateRect.y + candidateRect.height * margin + (spanY * j) / 8;
  const points = {
    P00: { i: 0, j: 0, x: xFor(0), y: yFor(0) },
    P10: { i: 1, j: 0, x: xFor(1), y: yFor(0) },
    P01: { i: 0, j: 1, x: xFor(0), y: yFor(1) },
    P11: { i: 1, j: 1, x: xFor(1), y: yFor(1) },
    P20: { i: 2, j: 0, x: xFor(2), y: yFor(0) },
    P21: { i: 2, j: 1, x: xFor(2), y: yFor(1) },
    P12: { i: 1, j: 2, x: xFor(1), y: yFor(2) },
    P22: { i: 2, j: 2, x: xFor(2), y: yFor(2) },
    P23: { i: 2, j: 3, x: xFor(2), y: yFor(3) },
    P25: { i: 2, j: 5, x: xFor(2), y: yFor(5) },
    P26: { i: 2, j: 6, x: xFor(2), y: yFor(6) },
    P32: { i: 3, j: 2, x: xFor(3), y: yFor(2) },
    P36: { i: 3, j: 6, x: xFor(3), y: yFor(6) },
    P44: { i: 4, j: 4, x: xFor(4), y: yFor(4) },
    P45: { i: 4, j: 5, x: xFor(4), y: yFor(5) },
    P54: { i: 5, j: 4, x: xFor(5), y: yFor(4) },
    P62: { i: 6, j: 2, x: xFor(6), y: yFor(2) },
    P63: { i: 6, j: 3, x: xFor(6), y: yFor(3) },
    P65: { i: 6, j: 5, x: xFor(6), y: yFor(5) },
    P66: { i: 6, j: 6, x: xFor(6), y: yFor(6) },
    P72: { i: 7, j: 2, x: xFor(7), y: yFor(2) },
    P76: { i: 7, j: 6, x: xFor(7), y: yFor(6) },
  };

  const extra = {
    M00_10: midpoint('M00_10', points.P00, points.P10),
    M00_01: midpoint('M00_01', points.P00, points.P01),
    M11_21: midpoint('M11_21', points.P11, points.P21),
    M11_12: midpoint('M11_12', points.P11, points.P12),
    M22_32: midpoint('M22_32', points.P22, points.P32),
    M22_23: midpoint('M22_23', points.P22, points.P23),
    M26_36: midpoint('M26_36', points.P26, points.P36),
    M26_25: midpoint('M26_25', points.P26, points.P25),
    M44_54: midpoint('M44_54', points.P44, points.P54),
    M44_45: midpoint('M44_45', points.P44, points.P45),
    M62_72: midpoint('M62_72', points.P62, points.P72),
    M62_63: midpoint('M62_63', points.P62, points.P63),
    M66_76: midpoint('M66_76', points.P66, points.P76),
    M66_65: midpoint('M66_65', points.P66, points.P65),
  };

  return { ...points, ...extra };
}

function deriveVisualHeuristics(scenarios) {
  const initial = scenarios['basic-play']?.steps?.[0] || null;
  const occupiedAfterFirst = scenarios['occupied-point']?.steps?.[1] || null;
  const captureAfterWhite = scenarios['capture-sequence']?.steps?.[2] || null;
  const captureFinal = scenarios['capture-sequence']?.steps?.at(-1) || null;

  const hoshiPairs = [
    ['P22', 'M22_32', 'M22_23'],
    ['P26', 'M26_36', 'M26_25'],
    ['P44', 'M44_54', 'M44_45'],
    ['P62', 'M62_72', 'M62_63'],
    ['P66', 'M66_76', 'M66_65'],
  ];

  const hoshi = initial
    ? Object.fromEntries(
        hoshiPairs.map(([center, refA, refB]) => {
          const centerSample = initial.samples[center];
          const refASample = initial.samples[refA];
          const refBSample = initial.samples[refB];
          return [
            center,
            {
              center: centerSample,
              reference_a: refASample,
              reference_b: refBSample,
              darker_than_reference_a_by: refASample ? refASample.brightness - centerSample.brightness : null,
              darker_than_reference_b_by: refBSample ? refBSample.brightness - centerSample.brightness : null,
            },
          ];
        }),
      )
    : null;

  const stoneCentering = occupiedAfterFirst
    ? {
        intersection: occupiedAfterFirst.samples.P00,
        horizontal_midpoint: occupiedAfterFirst.samples.M00_10,
        vertical_midpoint: occupiedAfterFirst.samples.M00_01,
        darker_than_horizontal_midpoint_by:
          occupiedAfterFirst.samples.M00_10.brightness - occupiedAfterFirst.samples.P00.brightness,
        darker_than_vertical_midpoint_by:
          occupiedAfterFirst.samples.M00_01.brightness - occupiedAfterFirst.samples.P00.brightness,
      }
    : null;

  const captureSignal = captureAfterWhite && captureFinal
    ? {
        after_white_at_P11: captureAfterWhite.samples.P11,
        final_at_P11: captureFinal.samples.P11,
        brightness_delta: captureFinal.samples.P11.brightness - captureAfterWhite.samples.P11.brightness,
      }
    : null;

  return {
    hoshi_contrast: hoshi,
    stone_centering_probe: stoneCentering,
    capture_probe: captureSignal,
  };
}

async function snapshot(page, scenarioName, stepName, candidateRect, points) {
  const fileName = `${scenarioName}-${stepName}.png`;
  const filePath = path.join(outDir, fileName);
  await page.screenshot({
    path: filePath,
    clip: candidateRect,
    animations: 'disabled',
  });
  const png = await readPng(filePath);
  const samples = {};
  for (const [name, point] of Object.entries(points)) {
    samples[name] = averageSample(png, point.x - candidateRect.x, point.y - candidateRect.y);
  }
  const textState = await page.evaluate(() => {
    const lines = (document.body?.innerText || '')
      .split(/\n+/)
      .map((line) => line.replace(/\s+/g, ' ').trim())
      .filter(Boolean);
    return {
      text_excerpt: lines.join(' ').slice(0, 800),
      status_lines: lines
        .filter((line) => /(black|white|turn|play|move|captur|status|pass|reset|new|undo|score|suicide|ko|resign)/i.test(line))
        .slice(0, 12),
    };
  });
  return {
    name: stepName,
    image: fileName,
    text_excerpt: textState.text_excerpt,
    status_lines: textState.status_lines,
    samples,
  };
}

async function clickPoint(page, point) {
  await page.mouse.click(point.x, point.y);
  await page.waitForTimeout(300);
}

async function loadFresh(page, url) {
  await page.goto(url, { waitUntil: 'load' });
  await page.waitForTimeout(1200);
  await page.evaluate(() => window.scrollTo(0, 0));
}

async function runScenarios(page, url, candidate) {
  const candidateRect = candidate.rect;
  const points = buildPoints(candidateRect);
  const result = {
    candidate_rect: candidateRect,
    point_map: Object.fromEntries(
      Object.entries(points).map(([name, point]) => [name, { i: point.i, j: point.j, x: round(point.x), y: round(point.y) }])
    ),
    scenarios: {},
  };

  async function runScenario(name, clickNames, extraAction = null) {
    await loadFresh(page, url);
    const steps = [];
    steps.push(await snapshot(page, name, '00-initial', candidateRect, points));
    for (let idx = 0; idx < clickNames.length; idx++) {
      const clickName = clickNames[idx];
      await clickPoint(page, points[clickName]);
      steps.push(await snapshot(page, name, `${String(idx + 1).padStart(2, '0')}-${clickName}`, candidateRect, points));
    }
    if (extraAction) {
      await extraAction();
      steps.push(await snapshot(page, name, `${String(clickNames.length + 1).padStart(2, '0')}-after-action`, candidateRect, points));
    }
    const diffs = [];
    for (let i = 1; i < steps.length; i++) {
      diffs.push({
        from: steps[i - 1].name,
        to: steps[i].name,
        ...(await diffStats(path.join(outDir, steps[i - 1].image), path.join(outDir, steps[i].image))),
      });
    }
    result.scenarios[name] = {
      click_sequence: clickNames,
      steps,
      diffs,
    };
  }

  await runScenario('basic-play', ['P00', 'P10', 'P01']);
  await runScenario('occupied-point', ['P00', 'P00']);
  await runScenario('capture-sequence', ['P10', 'P11', 'P01', 'P00', 'P21', 'P20', 'P12']);

  const resetMatch = await page.evaluate(() => {
    function isVisible(el) {
      const rect = el.getBoundingClientRect();
      const style = window.getComputedStyle(el);
      return rect.width >= 10 && rect.height >= 10 && style.display !== 'none' && style.visibility !== 'hidden';
    }
    function selectorHint(el) {
      let hint = el.tagName.toLowerCase();
      if (el.id) hint += `#${el.id}`;
      const classes = [...el.classList].slice(0, 3);
      if (classes.length) hint += `.${classes.join('.')}`;
      return hint;
    }
    const matches = [...document.querySelectorAll('button,[role="button"],[onclick],a,div,span')]
      .filter(isVisible)
      .map((el) => ({
        text: (el.innerText || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim().slice(0, 80),
        selector: selectorHint(el),
      }))
      .filter((item) => item.text && /(new|reset|restart)/i.test(item.text));
    return matches[0] || null;
  });

  await runScenario(
    'reset-check',
    ['P00', 'P10'],
    resetMatch
      ? async () => {
          await page.evaluate((targetText) => {
            function isVisible(el) {
              const rect = el.getBoundingClientRect();
              const style = window.getComputedStyle(el);
              return rect.width >= 10 && rect.height >= 10 && style.display !== 'none' && style.visibility !== 'hidden';
            }
            const candidates = [...document.querySelectorAll('button,[role="button"],[onclick],a,div,span')]
              .filter(isVisible)
              .filter((el) => ((el.innerText || el.getAttribute('aria-label') || '').replace(/\s+/g, ' ').trim()) === targetText);
            candidates[0]?.click();
          }, resetMatch.text);
          await page.waitForTimeout(500);
        }
      : null
  );
  result.reset_control = resetMatch;
  result.visual_heuristics = deriveVisualHeuristics(result.scenarios);

  return result;
}

async function main() {
  await fs.mkdir(outDir, { recursive: true });

  const baseEvidence = {
    html_path: htmlPath,
    html_name: htmlName,
    collected_at: new Date().toISOString(),
  };

  try {
    await fs.access(htmlPath);
  } catch {
    console.log(JSON.stringify({ ...baseEvidence, collector_error: 'html file does not exist' }, null, 2));
    return;
  }

  let browser = null;
  let server = null;
  const consoleErrors = [];
  const pageErrors = [];
  const requestFailures = [];
  const externalRequests = [];

  try {
    const served = await createServer(htmlDir, htmlName);
    server = served.server;

    browser = await chromium.launch({
      executablePath: process.env.CHROMIUM_PATH || '/usr/sbin/chromium',
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });

    const page = await browser.newPage({
      viewport: { width: 1440, height: 1200 },
      deviceScaleFactor: 1,
    });

    page.on('pageerror', (err) => pageErrors.push(String(err)));
    page.on('console', (msg) => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      }
    });
    page.on('requestfailed', (req) => {
      requestFailures.push({
        url: req.url(),
        method: req.method(),
        resource_type: req.resourceType(),
        failure_text: req.failure()?.errorText || 'request failed',
      });
    });
    page.on('requestfinished', (req) => {
      try {
        const url = new URL(req.url());
        if (url.hostname !== '127.0.0.1' && url.hostname !== 'localhost') {
          externalRequests.push({
            url: req.url(),
            method: req.method(),
            resource_type: req.resourceType(),
          });
        }
      } catch {
        // ignore malformed urls
      }
    });

    await loadFresh(page, served.url);
    const initialSummary = await collectDomSummary(page);
    const candidate = normalizeCandidate(initialSummary.board_candidate, page.viewportSize());

    const fullShot = 'full-page.png';
    await page.screenshot({ path: path.join(outDir, fullShot), fullPage: true, animations: 'disabled' });

    let scenarioData = null;
    if (candidate) {
      scenarioData = await runScenarios(page, served.url, candidate);
    }

    const evidence = {
      ...baseEvidence,
      served_url: served.url,
      full_page_screenshot: fullShot,
      dom: initialSummary,
      board_candidate: candidate,
      console_errors: consoleErrors,
      page_errors: pageErrors,
      request_failures: requestFailures,
      external_requests: externalRequests.slice(0, 30),
      scenarios: scenarioData?.scenarios || {},
      scenario_meta: scenarioData
        ? {
            candidate_rect: scenarioData.candidate_rect,
            point_map: scenarioData.point_map,
            reset_control: scenarioData.reset_control,
            visual_heuristics: scenarioData.visual_heuristics,
          }
        : null,
    };

    console.log(JSON.stringify(evidence, null, 2));
  } catch (err) {
    console.log(
      JSON.stringify(
        {
          ...baseEvidence,
          collector_error: String(err),
          console_errors: consoleErrors,
          page_errors: pageErrors,
          request_failures: requestFailures,
          external_requests: externalRequests.slice(0, 30),
        },
        null,
        2,
      ),
    );
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (server) await new Promise((resolve) => server.close(resolve));
  }
}

await main();
