#!/usr/bin/env node
import http from 'node:http';
import fs from 'node:fs/promises';
import path from 'node:path';
import { chromium } from 'playwright-core';

const targetArg = process.argv[2] || 'workspace/board.html';
const htmlPath = path.resolve(process.cwd(), targetArg);
const htmlDir = path.dirname(htmlPath);
const htmlName = path.basename(htmlPath);

function fail(message, details = []) {
  const extra = details.filter(Boolean).join('\n');
  if (extra) {
    console.error(`FAIL: ${message}\n${extra}`);
  } else {
    console.error(`FAIL: ${message}`);
  }
  process.exit(1);
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function contentType(filePath) {
  if (filePath.endsWith('.html')) return 'text/html; charset=utf-8';
  if (filePath.endsWith('.js')) return 'text/javascript; charset=utf-8';
  if (filePath.endsWith('.css')) return 'text/css; charset=utf-8';
  if (filePath.endsWith('.json')) return 'application/json; charset=utf-8';
  if (filePath.endsWith('.svg')) return 'image/svg+xml';
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

function boardSummary(state) {
  return state.board
    .map((row) => row.map((cell) => (cell === 'black' ? 'B' : cell === 'white' ? 'W' : '.')).join(' '))
    .join('\n');
}

function shouldIgnoreConsoleError(text) {
  const lower = String(text).toLowerCase();
  return lower.includes('favicon');
}

async function main() {
  try {
    await fs.access(htmlPath);
  } catch {
    fail(`${targetArg} does not exist`);
  }

  const pageErrors = [];
  const consoleErrors = [];
  let browser;
  let server;

  try {
    const served = await createServer(htmlDir, htmlName);
    server = served.server;

    browser = await chromium.launch({
      executablePath: process.env.CHROMIUM_PATH || '/usr/sbin/chromium',
      headless: true,
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });

    const page = await browser.newPage({ viewport: { width: 1400, height: 1100 } });
    page.on('pageerror', (err) => pageErrors.push(String(err)));
    page.on('console', (msg) => {
      if (msg.type() !== 'error') return;
      const text = msg.text();
      if (shouldIgnoreConsoleError(text)) return;
      consoleErrors.push(text);
    });

    await page.goto(served.url, { waitUntil: 'networkidle' });
    await page.waitForFunction(() => typeof window.__goGame__?.getState === 'function', { timeout: 3000 });

    const getState = () => page.evaluate(() => window.__goGame__.getState());
    const clickCell = async (x, y) => {
      await page.locator(`[data-cell="${x},${y}"]`).click();
    };
    const reset = async () => {
      await page.locator('#reset').click();
    };
    const assertEmptyBoard = (state, context) => {
      assert(state.board.length === 9, `${context}: board must have 9 rows`);
      for (const [y, row] of state.board.entries()) {
        assert(Array.isArray(row) && row.length === 9, `${context}: row ${y} must have 9 cells`);
        for (const cell of row) {
          assert(cell === null, `${context}: expected empty board`);
        }
      }
    };

    const cellCount = await page.locator('[data-cell]').count();
    assert(cellCount === 81, `expected 81 clickable intersections, got ${cellCount}`);

    let state = await getState();
    assert(state.size === 9, `expected size=9, got ${state.size}`);
    assert(state.currentPlayer === 'black', `expected black to start, got ${state.currentPlayer}`);
    assert(state.captured?.black === 0 && state.captured?.white === 0, 'expected captured counts to start at zero');
    assertEmptyBoard(state, 'initial state');

    await clickCell(1, 1);
    state = await getState();
    assert(state.board[1][1] === 'black', 'first move should place black at 1,1');
    assert(state.currentPlayer === 'white', 'turn should switch to white after black move');

    await clickCell(1, 1);
    const occupiedState = await getState();
    assert(occupiedState.board[1][1] === 'black', 'occupied click should not replace existing stone');
    assert(occupiedState.currentPlayer === 'white', 'occupied click should not advance turn');

    await reset();
    state = await getState();
    assert(state.currentPlayer === 'black', 'reset should restore black turn');
    assert(state.captured.black === 0 && state.captured.white === 0, 'reset should restore capture counters');
    assertEmptyBoard(state, 'after reset');

    const captureMoves = [
      [1, 1],
      [0, 1],
      [8, 8],
      [1, 0],
      [8, 7],
      [2, 1],
      [8, 6],
      [1, 2],
    ];
    for (const [x, y] of captureMoves) {
      await clickCell(x, y);
    }
    state = await getState();
    assert(state.board[1][1] === null, `captured stone at 1,1 should be removed\n${boardSummary(state)}`);
    assert(state.captured.white === 1, `white capture count should be 1, got ${state.captured.white}`);
    assert(state.currentPlayer === 'black', `after white capture it should be black's turn, got ${state.currentPlayer}`);

    await reset();
    state = await getState();
    assertEmptyBoard(state, 'before suicide test');

    const surroundMoves = [
      [0, 1],
      [8, 8],
      [1, 0],
      [8, 7],
      [2, 1],
      [8, 6],
      [1, 2],
    ];
    for (const [x, y] of surroundMoves) {
      await clickCell(x, y);
    }
    state = await getState();
    assert(state.currentPlayer === 'white', `expected white turn before suicide test, got ${state.currentPlayer}`);

    await clickCell(1, 1);
    const suicideState = await getState();
    assert(suicideState.board[1][1] === null, `suicide move should be rejected\n${boardSummary(suicideState)}`);
    assert(suicideState.currentPlayer === 'white', 'rejected suicide move should not advance turn');

    if (pageErrors.length || consoleErrors.length) {
      fail('page emitted runtime errors', [
        pageErrors.length ? `Page errors:\n${pageErrors.join('\n')}` : '',
        consoleErrors.length ? `Console errors:\n${consoleErrors.join('\n')}` : '',
      ]);
    }

    console.log(`PASS: ${targetArg} satisfied all acceptance tests`);
  } catch (err) {
    fail(err.message || String(err), []);
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (server) await new Promise((resolve) => server.close(() => resolve()));
  }
}

main();
