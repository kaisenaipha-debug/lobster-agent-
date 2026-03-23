#!/usr/bin/env node
/**
 * browser_supervisor.ts — Chrome 自愈管理守护进程
 * ============================
 * 用法：
 *   npx ts-node browser_supervisor.ts start
 *   npx ts-node browser_supervisor.ts status
 *   npx ts-node browser_supervisor.ts stop
 *
 * 编程接口（stdio JSON-RPC）：
 *   { "id": 1, "method": "start" }
 *   { "id": 2, "method": "status" }
 *   { "id": 3, "method": "stop" }
 *   { "id": 4, "method": "browser" }   → 返回 { browser }
 */

import { chromium, Browser, BrowserContext, Page } from 'playwright';
import { spawn, ChildProcess } from 'child_process';
import * as net from 'net';
import * as fs from 'fs';
import * as path from 'path';
import * as http from 'http';

type SupervisorState =
  | 'STOPPED'
  | 'STARTING'
  | 'CONNECTING'
  | 'CONNECTED'
  | 'DEGRADED'
  | 'RECOVERING';

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

interface ChromeSupervisorOptions {
  chromePath: string;
  debugPort?: number;
  host?: string;
  userDataDir: string;
  startupTimeoutMs?: number;
  connectTimeoutMs?: number;
  healthCheckIntervalMs?: number;
  portProbeTimeoutMs?: number;
  gracefulKillTimeoutMs?: number;
  maxRecoveryBackoffMs?: number;
  initialRecoveryBackoffMs?: number;
  chromeArgs?: string[];
  logPrefix?: string;
  autoCreateFirstPage?: boolean;
}

export class ChromeSupervisor {
  private readonly chromePath: string;
  private readonly debugPort: number;
  private readonly host: string;
  private readonly userDataDir: string;
  private readonly startupTimeoutMs: number;
  private readonly connectTimeoutMs: number;
  private readonly healthCheckIntervalMs: number;
  private readonly portProbeTimeoutMs: number;
  private readonly gracefulKillTimeoutMs: number;
  private readonly maxRecoveryBackoffMs: number;
  private readonly initialRecoveryBackoffMs: number;
  private readonly chromeArgs: string[];
  private readonly logPrefix: string;
  private readonly autoCreateFirstPage: boolean;

  private chromeProc: ChildProcess | null = null;
  private browser: Browser | null = null;
  private healthTimer: NodeJS.Timeout | null = null;

  private state: SupervisorState = 'STOPPED';
  private stopped = true;
  private recovering = false;
  private connectGeneration = 0;
  private recoveryAttempt = 0;
  private lastDisconnectReason = '';

  constructor(options: ChromeSupervisorOptions) {
    this.chromePath = options.chromePath;
    this.debugPort = options.debugPort ?? 9222;
    this.host = options.host ?? '127.0.0.1';
    this.userDataDir = options.userDataDir;
    this.startupTimeoutMs = options.startupTimeoutMs ?? 20_000;
    this.connectTimeoutMs = options.connectTimeoutMs ?? 10_000;
    this.healthCheckIntervalMs = options.healthCheckIntervalMs ?? 3_000;
    this.portProbeTimeoutMs = options.portProbeTimeoutMs ?? 1_500;
    this.gracefulKillTimeoutMs = options.gracefulKillTimeoutMs ?? 5_000;
    this.maxRecoveryBackoffMs = options.maxRecoveryBackoffMs ?? 30_000;
    this.initialRecoveryBackoffMs = options.initialRecoveryBackoffMs ?? 1_000;
    this.chromeArgs = options.chromeArgs ?? [];
    this.logPrefix = options.logPrefix ?? 'SUPERVISOR';
    this.autoCreateFirstPage = options.autoCreateFirstPage ?? true;
  }

  // ─── Public API ──────────────────────────────────────────

  async start(): Promise<void> {
    if (!this.stopped) {
      this.log('INFO', 'start() already running, returning current state');
      return; // already running, state reflects actual condition
    }
    this.stopped = false;
    this.recovering = false;
    this.recoveryAttempt = 0;
    this.lastDisconnectReason = '';
    this.setState('STARTING', 'start requested');
    await this.ensureUserDataDir();
    await this.ensureChromeAndConnect();
    this.startHealthLoop();
  }

  reset(): void {
    this.stopped = true;
    this.recovering = false;
    this.recoveryAttempt = 0;
    this.lastDisconnectReason = '';
    this.state = 'STOPPED';
    this.browser = null;
    this.chromeProc = null;
  }

  async stop(): Promise<void> {
    this.log('INFO', 'stop() begin');
    this.stopped = true;
    this.recovering = false;
    this.recoveryAttempt = 0;
    this.stopHealthLoop();
    const localBrowser = this.browser;
    this.browser = null;
    if (localBrowser) {
      try { await localBrowser.close(); this.log('INFO', 'browser.close() done'); }
      catch (err) { this.log('WARN', `browser.close() failed: ${this.errMsg(err)}`); }
    }
    await this.killChromeProcessGracefully();
    this.setState('STOPPED', 'stop completed');
  }

  getBrowser(): Browser | null { return this.browser; }
  getState(): SupervisorState { return this.state; }
  isConnected(): boolean { return !!this.browser && this.state === 'CONNECTED'; }
  getDebugEndpointHttp(): string { return `http://${this.host}:${this.debugPort}`; }
  getDebugEndpointWsJson(): string { return `http://${this.host}:${this.debugPort}/json/version`; }

  async getPrimaryContextAndPage(): Promise<{ context: BrowserContext | null; page: Page | null }> {
    const browser = this.browser;
    if (!browser) return { context: null, page: null };
    let context: BrowserContext | null = browser.contexts()[0] ?? null;
    if (!context && this.autoCreateFirstPage) context = await browser.newContext();
    if (!context) return { context: null, page: null };
    let page = context.pages()[0] ?? null;
    if (!page && this.autoCreateFirstPage) page = await context.newPage();
    return { context, page };
  }

  async forceReconnect(reason = 'manual force reconnect'): Promise<void> { await this.recover(reason, true); }

  // ─── Internals ────────────────────────────────────────────

  private async ensureUserDataDir(): Promise<void> {
    await fs.promises.mkdir(this.userDataDir, { recursive: true });
    this.log('INFO', `userDataDir ready: ${this.userDataDir}`);
  }

  private buildChromeArgs(): string[] {
    const args = [
      `--remote-debugging-port=${this.debugPort}`,
      `--user-data-dir=${this.userDataDir}`,
      '--no-first-run',
      '--no-default-browser-check',
      '--disable-background-networking',
      '--disable-component-update',
      '--disable-features=Translate,OptimizationHints,MediaRouter',
      '--disable-renderer-backgrounding',
      '--metrics-recording-only',
      '--password-store=basic',
      '--use-mock-keychain',
      ...this.chromeArgs,
    ];
    return Array.from(new Set(args));
  }

  private async ensureChromeAndConnect(): Promise<void> {
    const portOpen = await this.isDebugPortOpen();
    if (!portOpen) {
      await this.launchChrome();
      await this.waitForDebugPort(this.startupTimeoutMs);
    } else {
      this.log('INFO', 'debug port already open, skip launch');
    }
    await this.connectBrowser();
  }

  private async launchChrome(): Promise<void> {
    if (this.chromeProc && !this.chromeProc.killed) {
      this.log('INFO', `launchChrome() skipped: existing chrome pid=${this.chromeProc.pid ?? 'unknown'}`);
      return;
    }
    this.setState('STARTING', 'launching chrome');
    const args = this.buildChromeArgs();
    this.log('INFO', `launching chrome: ${this.chromePath}`);
    this.log('DEBUG', `chrome args: ${args.join(' ')}`);

    this.chromeProc = spawn(this.chromePath, args, {
      detached: false,
      stdio: 'ignore',
      windowsHide: true,
    });

    const localProc = this.chromeProc;
    localProc.once('spawn', () => {
      this.log('INFO', `chrome spawned pid=${localProc.pid ?? 'unknown'}`);
    });
    localProc.once('error', async (err) => {
      this.log('ERROR', `chrome process error: ${this.errMsg(err)}`);
      if (!this.stopped) await this.recover(`chrome process error: ${this.errMsg(err)}`);
    });
    localProc.once('exit', async (code, signal) => {
      const msg = `chrome exited code=${code ?? 'null'} signal=${signal ?? 'null'}`;
      this.log('WARN', msg);
      if (this.chromeProc === localProc) this.chromeProc = null;
      if (!this.stopped) await this.recover(msg);
    });
  }

  private async connectBrowser(): Promise<void> {
    this.setState('CONNECTING', 'connecting over CDP');
    const currentGeneration = ++this.connectGeneration;
    if (this.browser) {
      try { await this.browser.close(); }
      catch (err) { this.log('WARN', `close old browser handle failed: ${this.errMsg(err)}`); }
      this.browser = null;
    }
    const endpoint = this.getDebugEndpointHttp();
    this.log('INFO', `connectOverCDP -> ${endpoint}`);
    const timeoutGuard = this.timeoutAfter(this.connectTimeoutMs, 'connectOverCDP timeout');
    try {
      const browser = await Promise.race([
        chromium.connectOverCDP(endpoint, { isLocal: true }),
        timeoutGuard,
      ]) as Browser;
      if (currentGeneration !== this.connectGeneration) {
        try { await browser.close(); } catch {}
        throw new Error('stale connect generation');
      }
      this.browser = browser;
      this.attachBrowserListeners(browser, currentGeneration);
      const { context, page } = await this.getPrimaryContextAndPage();
      this.setState('CONNECTED', 'cdp connected');
      this.recoveryAttempt = 0;
      this.log('INFO', `connected: contexts=${browser.contexts().length} page=${!!page}`);
    } catch (err) {
      this.browser = null;
      this.setState('DEGRADED', `connect failed: ${this.errMsg(err)}`);
      throw err;
    }
  }

  private attachBrowserListeners(browser: Browser, generation: number): void {
    browser.on('disconnected', async () => {
      if (generation !== this.connectGeneration) return;
      const reason = 'playwright browser disconnected';
      this.log('WARN', reason);
      this.browser = null;
      this.lastDisconnectReason = reason;
      if (!this.stopped) await this.recover(reason);
    });
  }

  private startHealthLoop(): void {
    this.stopHealthLoop();
    const loop = async () => {
      if (this.stopped) return;
      try { await this.healthCheckTick(); }
      catch (err) {
        this.log('WARN', `health loop error: ${this.errMsg(err)}`);
        await this.recover(`health loop error: ${this.errMsg(err)}`);
      } finally {
        if (!this.stopped) this.healthTimer = setTimeout(loop, this.healthCheckIntervalMs);
      }
    };
    this.healthTimer = setTimeout(loop, this.healthCheckIntervalMs);
    this.log('INFO', `health loop started interval=${this.healthCheckIntervalMs}ms`);
  }

  private stopHealthLoop(): void {
    if (this.healthTimer) { clearTimeout(this.healthTimer); this.healthTimer = null; }
  }

  private async healthCheckTick(): Promise<void> {
    const portOpen = await this.isDebugPortOpen();
    const procAlive = this.isChromeProcessAlive();
    this.log('DEBUG', `health state=${this.state} procAlive=${procAlive} portOpen=${portOpen} browser=${!!this.browser}`);
    if (!procAlive && !portOpen) { await this.recover('chrome process dead and debug port closed'); return; }
    if (procAlive && !portOpen) { await this.recover('chrome alive but debug port closed'); return; }
    if (portOpen && !this.browser) { await this.recover('debug port open but browser handle missing'); return; }
    if (this.browser) {
      const ok = await this.probeDevToolsHttp();
      if (!ok) { await this.recover('devtools http probe failed'); return; }
    }
  }

  private async probeDevToolsHttp(): Promise<boolean> {
    const url = this.getDebugEndpointWsJson();
    return new Promise<boolean>((resolve) => {
      const req = http.get(url, { timeout: this.portProbeTimeoutMs }, (res) => {
        const ok = (res.statusCode ?? 0) >= 200 && (res.statusCode ?? 0) < 300;
        res.resume();
        resolve(ok);
      });
      req.on('timeout', () => { req.destroy(); resolve(false); });
      req.on('error', () => resolve(false));
    });
  }

  private async recover(reason: string, force = false): Promise<void> {
    if (this.stopped) return;
    if (this.recovering && !force) {
      this.log('DEBUG', `recover skipped: already recovering, reason=${reason}`);
      return;
    }
    this.recovering = true;
    this.lastDisconnectReason = reason;
    this.setState('RECOVERING', reason);
    try {
      const delayMs = this.nextBackoffMs();
      this.log('WARN', `recover reason=${reason} backoff=${delayMs}ms`);
      await this.sleep(delayMs);
      const portOpen = await this.isDebugPortOpen();
      const procAlive = this.isChromeProcessAlive();
      if (procAlive && portOpen) {
        try {
          this.log('INFO', 'recover path: reconnect only');
          await this.connectBrowser();
          this.log('INFO', 'recover success by reconnect');
          return;
        } catch (err) { this.log('WARN', `reconnect failed: ${this.errMsg(err)}`); }
      }
      if (procAlive || this.chromeProc) {
        this.log('WARN', 'recover path: unhealthy chrome, killing old process');
        await this.killChromeProcessGracefully();
      }
      this.log('INFO', 'recover path: relaunch chrome');
      await this.launchChrome();
      await this.waitForDebugPort(this.startupTimeoutMs);
      await this.connectBrowser();
      this.log('INFO', 'recover success by relaunch');
    } catch (err) {
      this.setState('DEGRADED', `recover failed: ${this.errMsg(err)}`);
      this.log('ERROR', `recover failed: ${this.errMsg(err)}`);
    } finally {
      this.recovering = false;
    }
  }

  private nextBackoffMs(): number {
    const attempt = this.recoveryAttempt++;
    if (attempt <= 0) return this.initialRecoveryBackoffMs;
    return Math.min(this.initialRecoveryBackoffMs * Math.pow(2, attempt), this.maxRecoveryBackoffMs);
  }

  private async killChromeProcessGracefully(): Promise<void> {
    const proc = this.chromeProc;
    if (!proc) return;
    this.log('INFO', `killing chrome pid=${proc.pid ?? 'unknown'}`);
    try { proc.kill(process.platform === 'win32' ? undefined : 'SIGTERM'); }
    catch (err) { this.log('WARN', `first kill failed: ${this.errMsg(err)}`); }
    const exited = await this.waitProcessExit(proc, this.gracefulKillTimeoutMs);
    if (!exited) {
      this.log('WARN', 'chrome did not exit gracefully, forcing SIGKILL');
      try { proc.kill('SIGKILL'); } catch (err) { this.log('WARN', `force kill failed: ${this.errMsg(err)}`); }
      await this.waitProcessExit(proc, 2_000);
    }
    if (this.chromeProc === proc) this.chromeProc = null;
  }

  private waitProcessExit(proc: ChildProcess, timeoutMs: number): Promise<boolean> {
    return new Promise((resolve) => {
      let done = false;
      const finish = (ok: boolean) => { if (!done) { done = true; clearTimeout(timer); proc.removeListener('exit', onExit); resolve(ok); } };
      const onExit = () => finish(true);
      const timer = setTimeout(() => finish(false), timeoutMs);
      proc.once('exit', onExit);
    });
  }

  private async waitForDebugPort(maxWaitMs: number): Promise<void> {
    const start = Date.now();
    while (Date.now() - start < maxWaitMs) {
      if (await this.isDebugPortOpen()) { this.log('INFO', 'debug port ready'); return; }
      await this.sleep(400);
    }
    throw new Error(`debug port ${this.debugPort} not ready within ${maxWaitMs}ms`);
  }

  private isChromeProcessAlive(): boolean {
    const proc = this.chromeProc;
    if (!proc || !proc.pid) return false;
    try { process.kill(proc.pid, 0); return true; } catch { return false; }
  }

  private isDebugPortOpen(): Promise<boolean> {
    return new Promise((resolve) => {
      const socket = new net.Socket();
      let settled = false;
      const finish = (ok: boolean) => { if (!settled) { settled = true; socket.destroy(); resolve(ok); } };
      socket.setTimeout(this.portProbeTimeoutMs);
      socket.once('connect', () => finish(true));
      socket.once('timeout', () => finish(false));
      socket.once('error', () => finish(false));
      socket.connect(this.debugPort, this.host);
    });
  }

  private timeoutAfter(ms: number, message: string): Promise<never> {
    return new Promise((_, reject) => setTimeout(() => reject(new Error(message)), ms));
  }

  private sleep(ms: number): Promise<void> { return new Promise((resolve) => setTimeout(resolve, ms)); }

  private setState(next: SupervisorState, reason: string): void {
    if (this.state === next) { this.log('DEBUG', `state keep ${next} reason=${reason}`); return; }
    const prev = this.state;
    this.state = next;
    this.log('INFO', `state ${prev} -> ${next} reason=${reason}`);
  }

  public errMsg(err: unknown): string { return err instanceof Error ? err.message : String(err); }

  private log(level: LogLevel, message: string): void {
    const ts = new Date().toISOString();
    const line = `[${ts}] [${this.logPrefix}] [${level}] ${message}`;
    console.log(line);
    // Also write to log file
    fs.promises.appendFile('/tmp/browser_supervisor.log', line + '\n').catch(() => {});
  }
}

// ─── CLI Entry ──────────────────────────────────────────────

function getChromePath(): string {
  const p = process.platform;
  if (p === 'darwin') return '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
  if (p === 'win32') return 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
  return '/usr/bin/google-chrome';
}

async function main() {
  const cmd = process.argv[2] ?? 'status';

  const supervisor = new ChromeSupervisor({
    chromePath: getChromePath(),
    debugPort: 9222,
    userDataDir: path.join(process.env.HOME ?? '/tmp', '.qclaw', 'browser', 'pha-debug'),
    chromeArgs: [
      '--profile-directory=Profile 34',
      '--disable-sync',
      '--disable-background-networking',
    ],
    logPrefix: 'SUPERVISOR',
    startupTimeoutMs: 20_000,
    connectTimeoutMs: 10_000,
    healthCheckIntervalMs: 3_000,
    portProbeTimeoutMs: 1_500,
    gracefulKillTimeoutMs: 5_000,
    maxRecoveryBackoffMs: 30_000,
    initialRecoveryBackoffMs: 1_000,
    autoCreateFirstPage: true,
  });

  // Handle stdio JSON-RPC
  let rpcId = 0;
  const rpc = (method: string, params?: unknown) => {
    const id = ++rpcId;
    return new Promise<void>((resolve) => {
      const handler = (data: Buffer) => {
        try {
          const msg = JSON.parse(data.toString());
          if (msg.id === id) {
            process.stdin.off('data', handler);
            resolve();
          }
        } catch {}
      };
      process.stdin.on('data', handler);
      const req = JSON.stringify({ jsonrpc: '2.0', id, method, params });
      console.log('RESP:' + req);
      setTimeout(resolve, 100);
    });
  };

  if (cmd === 'start') {
    try {
      await supervisor.start();
      console.log(JSON.stringify({ ok: true, state: supervisor.getState(), endpoint: supervisor.getDebugEndpointHttp() }));
    } catch (e) {
      console.log(JSON.stringify({ ok: false, error: supervisor.errMsg(e) }));
      process.exit(1);
    }
  } else if (cmd === 'status') {
    const state = supervisor.getState();
    console.log(JSON.stringify({ state, connected: supervisor.isConnected(), endpoint: supervisor.getDebugEndpointHttp() }));
  } else if (cmd === 'stop') {
    await supervisor.stop();
    console.log(JSON.stringify({ ok: true }));
  } else if (cmd === 'rpc') {
    // Long-running RPC mode: read JSON-RPC requests from stdin, write responses to stdout
    process.stdin.setEncoding('utf8');
    let supervisorStarted = false;
    const ensureStarted = async () => {
      if (!supervisorStarted) {
        try {
          await supervisor.start();
          supervisorStarted = true;
        } catch {}
      }
    };

    for await (const chunk of process.stdin) {
      const lines = chunk.split('\n');
      for (const raw of lines) {
        const line = raw.trim();
        if (!line || line === 'RESP:') continue;
        if (line.startsWith('RESP:')) continue; // skip echoed responses
        try {
          const req = JSON.parse(line);
          const { method, id, params } = req;

          if (method === 'start') {
            if (supervisorStarted) {
              // Already started, return current state
              process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result: { ok: true, state: supervisor.getState(), endpoint: supervisor.getDebugEndpointHttp() } }) + '\n');
            } else {
              supervisor.reset();  // allow fresh start
              await supervisor.start();
              supervisorStarted = true;
              process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result: { ok: true, state: supervisor.getState(), endpoint: supervisor.getDebugEndpointHttp() } }) + '\n');
            }
          } else if (method === 'stop') {
            await supervisor.stop();
            supervisorStarted = false;
            process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result: { ok: true } }) + '\n');
          } else if (method === 'status') {
            process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result: { state: supervisor.getState(), connected: supervisor.isConnected(), endpoint: supervisor.getDebugEndpointHttp() } }) + '\n');
          } else if (method === 'browser') {
            await ensureStarted();
            const browser = supervisor.getBrowser();
            process.stdout.write(JSON.stringify({ jsonrpc: '2.0', id, result: { hasBrowser: !!browser, connected: supervisor.isConnected() } }) + '\n');
          }
        } catch (e) {
          try {
            console.log(JSON.stringify({ error: { message: String(e) } }));
          } catch {}
        }
      }
    }
  } else {
    console.log('Usage: browser_supervisor.ts [start|status|stop|rpc]');
    process.exit(1);
  }
}

main().catch((e) => { console.error(e); process.exit(1); });
