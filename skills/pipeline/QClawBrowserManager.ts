/**
 * QClawBrowserManager.ts - 浏览器页面池化管理
 * 
 * 来源：QClaw官方架构
 * 用途：Page池化 + Lease归还 + Janitor自动回收
 * 依赖：Playwright (Node.js)
 */

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

type BrowserManagerState = 'STOPPED' | 'STARTING' | 'CONNECTING' | 'CONNECTED' | 'DEGRADED' | 'RECOVERING';
type ManagedPageState = 'IDLE' | 'BUSY' | 'BROKEN' | 'CLOSED';

interface ManagedPage {
  readonly id: string;
  page: unknown;         // Playwright Page
  state: ManagedPageState;
  leasedAt?: number;
  leasedBy?: string;    // skillName
  generation: number;    // 浏览器断连时递增，旧lease自动失效
}

export interface BrowserManagerOptions {
  /**
   * Playwright chromium实例（已启动的）
   */
  browser: unknown;

  /**
   * Chrome CDP端点
   */
  cdpEndpoint?: string;

  /**
   * 初始Page池大小
   */
  poolSize?: number;

  /**
   * Lease超时（毫秒），超时未归还则强制回收
   */
  leaseTimeoutMs?: number;

  /**
   * Janitor检查间隔（毫秒）
   */
  janitorIntervalMs?: number;

  /**
   * 浏览器断连后是否自动重启
   */
  autoReconnect?: boolean;

  /**
   * 最大恢复尝试次数
   */
  maxRecoveryAttempts?: number;

  /**
   * 是否记录详细日志
   */
  verbose?: boolean;

  logPrefix?: string;
}

// ===================== 核心类 =====================

export class QClawBrowserManager {
  private readonly browser: unknown;
  private readonly cdpEndpoint?: string;
  private readonly poolSize: number;
  private readonly leaseTimeoutMs: number;
  private readonly janitorIntervalMs: number;
  private readonly autoReconnect: boolean;
  private readonly maxRecoveryAttempts: number;
  private readonly verbose: boolean;
  private readonly logPrefix: string;

  private pages = new Map<string, ManagedPage>();
  private readonly idle: string[] = [];   // 可用Page ID队列
  private state: BrowserManagerState = 'STOPPED';
  private generation = 0;
  private janitorTimer?: NodeJS.Timeout;
  private readonly leases = new Map<string, string>(); // runId → pageId

  constructor(options: BrowserManagerOptions) {
    this.browser = options.browser;
    this.cdpEndpoint = options.cdpEndpoint;
    this.poolSize = options.poolSize ?? 3;
    this.leaseTimeoutMs = options.leaseTimeoutMs ?? 60_000;
    this.janitorIntervalMs = options.janitorIntervalMs ?? 30_000;
    this.autoReconnect = options.autoReconnect ?? true;
    this.maxRecoveryAttempts = options.maxRecoveryAttempts ?? 3;
    this.verbose = options.verbose ?? false;
    this.logPrefix = options.logPrefix ?? 'QCLAW_BROWSER_MANAGER';

    this.log('INFO', `BrowserManager初始化 poolSize=${this.poolSize} leaseTimeout=${this.leaseTimeoutMs}ms`);
  }

  /**
   * 启动Manager，建立Page池
   */
  public async start(): Promise<void> {
    if (this.state !== 'STOPPED') {
      this.log('WARN', `start() 被调用但状态是${this.state}，忽略`);
      return;
    }

    this.state = 'STARTING';
    this.log('INFO', '启动BrowserManager...');

    try {
      // 建立初始Page池
      for (let i = 0; i < this.poolSize; i++) {
        await this.createPage();
      }
      this.state = 'CONNECTED';
      this.log('INFO', `✅ BrowserManager已启动，${this.idle.length}个Page就绪`);

      // 启动Janitor
      this.startJanitor();

    } catch (e: any) {
      this.state = 'DEGRADED';
      this.log('ERROR', `启动失败: ${e.message}`);
      throw e;
    }
  }

  /**
   * 从池中获取一个可用的Page（Lease模式）
   */
  public async getReadyPage(skillName: string): Promise<ReadyPageLease> {
    if (this.state !== 'CONNECTED' && this.state !== 'DEGRADED') {
      throw new Error(`BrowserManager状态是${this.state}，无法分配Page`);
    }

    // 检查并补充Page
    if (this.idle.length === 0) {
      this.log('WARN', `Page池空，创建新Page补充`);
      await this.createPage();
    }

    const pageId = this.idle.shift()!;
    const mp = this.pages.get(pageId)!;

    if (mp.state === 'BROKEN') {
      // 跳过broken的，重试
      this.pages.delete(pageId);
      return this.getReadyPage(skillName);
    }

    mp.state = 'BUSY';
    mp.leasedAt = Date.now();
    mp.leasedBy = skillName;

    this.leases.set(mp.id, mp.id);

    this.log('DEBUG', `Lease: skill=${skillName} pageId=${pageId} gen=${mp.generation}`);

    return {
      get page() { return mp.page; },
      get runId() { return mp.leasedBy ?? 'unknown'; },
      get skillName() { return skillName; },
      get leasedAt() { return mp.leasedAt!; },
      release: () => this.releasePage(pageId),
      markBroken: () => this.markBrokenPage(pageId),
    };
  }

  /**
   * 归还Page
   */
  public releasePage(pageId: string): void {
    const mp = this.pages.get(pageId);
    if (!mp) {
      this.log('WARN', `releasePage: pageId=${pageId} 不存在`);
      return;
    }

    if (mp.generation !== this.getCurrentGeneration()) {
      this.log('DEBUG', `releasePage: pageId=${pageId} generation过期，关闭`);
      this.closePage(pageId);
      return;
    }

    mp.state = 'IDLE';
    mp.leasedAt = undefined;
    mp.leasedBy = undefined;
    this.idle.push(pageId);
    this.leases.delete(pageId);

    this.log('DEBUG', `release: pageId=${pageId} 回池，idle=${this.idle.length}`);
  }

  /**
   * 标记Page为坏掉
   */
  public markBroken(pageId: string): void {
    this.markBrokenPage(pageId);
  }

  private markBrokenPage(pageId: string): void {
    const mp = this.pages.get(pageId);
    if (!mp) return;

    this.log('WARN', `markBroken: pageId=${pageId}`);
    mp.state = 'BROKEN';
    this.idle = this.idle.filter(id => id !== pageId);
    this.leases.delete(pageId);

    // 立即关闭并替换
    this.closePage(pageId);
    this.pages.delete(pageId);
    this.createPage().catch(e => this.log('ERROR', `补充Page失败: ${e.message}`));
  }

  /**
   * 创建新Page
   */
  private async createPage(): Promise<string> {
    const { chromium } = await import('playwright');
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const browser = this.browser as any;
    const context = await browser.newContext();
    const page = await context.newPage();

    const id = `page-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;

    const mp: ManagedPage = {
      id,
      page,
      state: 'IDLE',
      generation: this.getCurrentGeneration(),
    };

    this.pages.set(id, mp);
    this.idle.push(id);

    this.log('DEBUG', `createPage: id=${id} 总Page=${this.pages.size} idle=${this.idle.length}`);
    return id;
  }

  /**
   * 关闭Page
   */
  private async closePage(pageId: string): Promise<void> {
    const mp = this.pages.get(pageId);
    if (!mp) return;

    try {
      const { chromium } = await import('playwright');
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const page = mp.page as any;
      if (page && typeof page.close === 'function') {
        await page.close().catch(() => {});
      }
    } catch { /* ignore */ }
  }

  /**
   * Janitor：定期检查，回收超时/损坏的Page
   */
  private startJanitor(): void {
    this.janitorTimer = setInterval(() => {
      this.janitor();
    }, this.janitorIntervalMs);
    this.log('DEBUG', `Janitor启动，间隔=${this.janitorIntervalMs}ms`);
  }

  private janitor(): void {
    const now = Date.now();
    const stale: string[] = [];
    const broken: string[] = [];

    for (const [id, mp] of this.pages) {
      if (mp.state === 'BROKEN' || mp.state === 'CLOSED') {
        broken.push(id);
        continue;
      }

      // 检查lease超时
      if (mp.state === 'BUSY' && mp.leasedAt && (now - mp.leasedAt > this.leaseTimeoutMs)) {
        this.log('WARN', `Janitor: pageId=${id} lease超时(${now - mp.leasedAt}ms > ${this.leaseTimeoutMs}ms)，强制回收`);
        stale.push(id);
      }
    }

    // 关闭损坏和超时的
    for (const id of [...broken, ...stale]) {
      const mp = this.pages.get(id);
      if (mp) {
        mp.state = 'CLOSED';
        this.closePage(id).catch(() => {});
        this.pages.delete(id);
        this.idle = this.idle.filter(pid => pid !== id);
      }
    }

    // 补充Page池
    const target = this.poolSize - this.pages.size;
    if (target > 0) {
      this.log('DEBUG', `Janitor: 补充${target}个Page`);
      for (let i = 0; i < target; i++) {
        this.createPage().catch(e => this.log('ERROR', `Janitor补充失败: ${e.message}`));
      }
    }

    if (broken.length || stale.length) {
      this.log('INFO', `Janitor: 回收${broken.length}个broken + ${stale.length}个stale，当前pool=${this.pages.size} idle=${this.idle.length}`);
    }
  }

  /**
   * 获取当前generation
   */
  public getCurrentGeneration(): number {
    return this.generation;
  }

  /**
   * 浏览器断连时调用，废弃所有现有lease
   */
  public markDisconnected(): void {
    this.generation++;
    this.log('WARN', `Browser断开，generation=${this.generation}，废弃${this.leases.size}个lease`);
    this.leases.clear();

    if (this.autoReconnect) {
      this.state = 'RECOVERING';
      this.scheduleReconnect();
    }
  }

  private scheduleReconnect(): void {
    this.state = 'RECOVERING';
    this.log('INFO', '计划重新连接...');

    setTimeout(async () => {
      try {
        this.state = 'CONNECTING';
        // 重连逻辑（连接已有CDP）
        if (this.cdpEndpoint) {
          const { chromium } = await import('playwright');
          const browser = await chromium.connectOverCDP(this.cdpEndpoint);
          this.log('INFO', '✅ 重连成功');
          this.state = 'CONNECTED';
          // 重新初始化Page池
          await this.start();
        }
      } catch (e: any) {
        this.log('ERROR', `重连失败: ${e.message}`);
        if (this.autoReconnect) {
          this.scheduleReconnect();
        } else {
          this.state = 'DEGRADED';
        }
      }
    }, 3000);
  }

  /**
   * 获取池状态
   */
  public getPoolSize(): { total: number; idle: number; busy: number; broken: number } {
    let idle = 0, busy = 0, broken = 0;
    for (const mp of this.pages.values()) {
      if (mp.state === 'IDLE') idle++;
      else if (mp.state === 'BUSY') busy++;
      else broken++;
    }
    return { total: this.pages.size, idle, busy, broken };
  }

  /**
   * 健康检查
   */
  public isHealthy(): boolean {
    if (this.state !== 'CONNECTED' && this.state !== 'DEGRADED') return false;
    return this.pages.size >= this.poolSize * 0.5; // 至少一半可用
  }

  /**
   * 关闭Manager
   */
  public async stop(): Promise<void> {
    if (this.janitorTimer) clearInterval(this.janitorTimer);
    for (const [id] of this.pages) {
      await this.closePage(id);
    }
    this.pages.clear();
    this.idle = [];
    this.state = 'STOPPED';
    this.log('INFO', 'BrowserManager已停止');
  }

  private log(level: LogLevel, message: string): void {
    if (level === 'DEBUG' && !this.verbose) return;
    const ts = new Date().toISOString();
    console.log(`[${ts}] [${this.logPrefix}] [${level}] ${message}`);
  }
}

// ===================== ReadyPageLease =====================

export interface ReadyPageLease {
  readonly page: unknown;
  readonly runId: string;
  readonly skillName: string;
  readonly leasedAt: number;
  release(): void;
  markBroken(): void;
}
