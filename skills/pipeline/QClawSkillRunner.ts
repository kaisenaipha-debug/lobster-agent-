/**
 * QClawSkillRunner.ts - 技能执行引擎
 * 
 * 来源：QClaw官方架构
 * 用途：技能执行，超时/取消/队列/生命周期管理
 * 依赖：QClawSkillRegistry.ts（安全校验）
 */

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

export type SkillRunStatus = 'QUEUED' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'TIMEOUT' | 'CANCELLED';

export interface SkillRunResult {
  runId: string;
  skillName: string;
  status: SkillRunStatus;
  output?: unknown;
  error?: string;
  startedAt: number;
  endedAt: number;
  durationMs: number;
  cancelled?: boolean;
  timedOut?: boolean;
}

export interface SkillContext {
  runId: string;
  skillName: string;
  input: Record<string, unknown>;
  signal?: AbortSignal;
  page?: unknown;           // 可选：预分配的Page（来自BrowserManager）
  pageLease?: () => void;   // 可选：归还Page的函数
}

export interface SkillExecutor {
  (ctx: SkillContext): Promise<unknown>;
}

export interface SkillRunnerOptions {
  /**
   * 技能执行器注册表
   * key: skillName
   * value: 异步执行函数
   */
  executors: Record<string, SkillExecutor>;

  /**
   * 全局默认超时（毫秒）
   */
  defaultTimeoutMs?: number;

  /**
   * 全局最大超时（毫秒）
   */
  maxTimeoutMs?: number;

  /**
   * 单个技能最大重试次数
   */
  maxRetries?: number;

  /**
   * 是否记录详细日志
   */
  verbose?: boolean;

  /**
   * 技能执行钩子
   */
  hooks?: {
    onQueued?: (runId: string, skillName: string) => void;
    onStart?: (runId: string, skillName: string) => void;
    onSuccess?: (runId: string, skillName: string, durationMs: number, output: unknown) => void;
    onFailed?: (runId: string, skillName: string, error: string, durationMs: number) => void;
    onTimeout?: (runId: string, skillName: string) => void;
    onCancelled?: (runId: string, skillName: string) => void;
    onFinally?: (runId: string, skillName: string) => void;
  };

  logPrefix?: string;
}

// ===================== 核心类 =====================

export class QClawSkillRunner {
  private readonly executors: Record<string, SkillExecutor>;
  private readonly defaultTimeoutMs: number;
  private readonly maxTimeoutMs: number;
  private readonly maxRetries: number;
  private readonly verbose: boolean;
  private readonly hooks?: SkillRunnerOptions['hooks'];
  private readonly logPrefix: string;

  // 运行中任务
  private readonly running = new Map<string, { abort: () => void; startedAt: number }>();

  // 任务队列（串行）
  private readonly queue: Array<{
    ctx: SkillContext;
    executor: SkillExecutor;
    timeoutMs: number;
    retries: number;
    resolve: (r: SkillRunResult) => void;
    reject: (e: Error) => void;
  }> = [];

  private draining = false;

  constructor(options: SkillRunnerOptions) {
    this.executors = options.executors;
    this.defaultTimeoutMs = options.defaultTimeoutMs ?? 60_000;
    this.maxTimeoutMs = options.maxTimeoutMs ?? 300_000;
    this.maxRetries = options.maxRetries ?? 0;
    this.verbose = options.verbose ?? false;
    this.hooks = options.hooks;
    this.logPrefix = options.logPrefix ?? 'QCLAW_SKILL_RUNNER';
  }

  /**
   * 注册技能执行器
   */
  public register(skillName: string, executor: SkillExecutor): void {
    this.executors[skillName] = executor;
    this.log('INFO', `register skill: ${skillName}`);
  }

  /**
   * 执行技能（返回Promise）
   */
  public async run(
    skillName: string,
    input: Record<string, unknown> = {},
    options?: { timeoutMs?: number; runId?: string; signal?: AbortSignal }
  ): Promise<SkillRunResult> {
    const runId = options?.runId ?? `run-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
    const timeoutMs = Math.min(
      options?.timeoutMs ?? this.defaultTimeoutMs,
      this.maxTimeoutMs
    );

    // 检查是否有执行器
    const executor = this.executors[skillName];
    if (!executor) {
      const result: SkillRunResult = {
        runId,
        skillName,
        status: 'FAILED',
        error: `executor not found: ${skillName}`,
        startedAt: Date.now(),
        endedAt: Date.now(),
        durationMs: 0,
      };
      return result;
    }

    // 构建上下文
    const ctx: SkillContext = {
      runId,
      skillName,
      input,
      signal: options?.signal,
    };

    return this.enqueue(ctx, executor, timeoutMs);
  }

  /**
   * 串行任务队列
   */
  private enqueue(
    ctx: SkillContext,
    executor: SkillExecutor,
    timeoutMs: number
  ): Promise<SkillRunResult> {
    return new Promise((resolve, reject) => {
      this.queue.push({
        ctx,
        executor,
        timeoutMs,
        retries: this.maxRetries,
        resolve,
        reject,
      });
      this.log('DEBUG', `enqueue: ${ctx.skillName} (queue len=${this.queue.length})`);
      this.hooks?.onQueued?.(ctx.runId, ctx.skillName);
      this.drain();
    });
  }

  /**
   * 消费队列（串行）
   */
  private drain(): void {
    if (this.draining || this.queue.length === 0) return;
    this.draining = true;

    const job = this.queue.shift()!;
    this.executeJob(job).finally(() => {
      this.draining = false;
      if (this.queue.length > 0) this.drain();
    });
  }

  private async executeJob(job: {
    ctx: SkillContext;
    executor: SkillExecutor;
    timeoutMs: number;
    retries: number;
    resolve: (r: SkillRunResult) => void;
    reject: (e: Error) => void;
  }): Promise<void> {
    const { ctx, executor, timeoutMs } = job;
    const startedAt = Date.now();

    this.log('INFO', `▶️ start: ${ctx.skillName} runId=${ctx.runId} timeout=${timeoutMs}ms`);
    this.hooks?.onStart?.(ctx.runId, ctx.skillName);

    // 注册中断信号
    let aborted = false;
    const abortFn = () => {
      aborted = true;
    };

    if (ctx.signal?.aborted) {
      const result = this.buildResult(ctx.runId, ctx.skillName, startedAt, 'CANCELLED',
        undefined, 'aborted before start', true);
      this.cleanup(ctx.runId);
      job.resolve(result);
      return;
    }

    if (ctx.signal) {
      ctx.signal.addEventListener('abort', abortFn, { once: true });
    }

    this.running.set(ctx.runId, { abort: abortFn, startedAt });

    let timer: NodeJS.Timeout;
    const timeoutPromise = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error('TIMEOUT')), timeoutMs);
    });

    try {
      let output: unknown;
      const raceResult = await Promise.race([
        executor(ctx),
        timeoutPromise,
      ]);

      clearTimeout(timer!);
      if (ctx.signal) ctx.signal.removeEventListener('abort', abortFn);
      this.running.delete(ctx.runId);

      if (aborted) {
        const result = this.buildResult(ctx.runId, ctx.skillName, startedAt, 'CANCELLED',
          undefined, 'cancelled by signal', false);
        this.hooks?.onCancelled?.(ctx.runId, ctx.skillName);
        this.hooks?.onFinally?.(ctx.runId, ctx.skillName);
        job.resolve(result);
        return;
      }

      output = raceResult;
      const result = this.buildResult(ctx.runId, ctx.skillName, startedAt, 'SUCCESS', output);

      this.log('INFO', `✅ success: ${ctx.skillName} runId=${ctx.runId} duration=${result.durationMs}ms`);
      this.hooks?.onSuccess?.(ctx.runId, ctx.skillName, result.durationMs, output);
      this.hooks?.onFinally?.(ctx.runId, ctx.skillName);

      // 归还Page（如有）
      ctx.pageLease?.();

      job.resolve(result);

    } catch (e: any) {
      clearTimeout(timer!);
      if (ctx.signal) ctx.signal.removeEventListener('abort', abortFn);
      this.running.delete(ctx.runId);

      const isTimeout = e.message === 'TIMEOUT';
      const status: SkillRunStatus = aborted ? 'CANCELLED' : (isTimeout ? 'TIMEOUT' : 'FAILED');
      const error = aborted ? 'cancelled by signal' : (isTimeout ? `timeout after ${timeoutMs}ms` : e.message);

      const result = this.buildResult(ctx.runId, ctx.skillName, startedAt, status, undefined, error, false, isTimeout);

      this.log('WARN', `${isTimeout || aborted ? '⚠️' : '❌'} ${status.toLowerCase()}: ${ctx.skillName} runId=${ctx.runId} error=${error}`);

      if (isTimeout) this.hooks?.onTimeout?.(ctx.runId, ctx.skillName);
      else this.hooks?.onFailed?.(ctx.runId, ctx.skillName, error, result.durationMs);
      this.hooks?.onFinally?.(ctx.runId, ctx.skillName);

      // 归还Page
      ctx.pageLease?.();

      job.resolve(result);
    }
  }

  private buildResult(
    runId: string, skillName: string, startedAt: number,
    status: SkillRunStatus,
    output?: unknown, error?: string,
    cancelled?: boolean, timedOut?: boolean
  ): SkillRunResult {
    const endedAt = Date.now();
    return {
      runId,
      skillName,
      status,
      output,
      error,
      startedAt,
      endedAt,
      durationMs: endedAt - startedAt,
      cancelled,
      timedOut,
    };
  }

  // ===================== 生命周期管理 =====================

  /**
   * 取消指定任务
   */
  public cancel(runId: string): boolean {
    const running = this.running.get(runId);
    if (running) {
      running.abort();
      this.running.delete(runId);
      this.log('INFO', `cancel: runId=${runId}`);
      return true;
    }
    return false;
  }

  /**
   * 取消所有运行中任务
   */
  public cancelAll(): void {
    for (const [runId] of this.running) {
      this.cancel(runId);
    }
    this.log('INFO', 'cancelAll: all running tasks cancelled');
  }

  /**
   * 获取运行中的任务数
   */
  public getRunningCount(): number {
    return this.running.size;
  }

  /**
   * 获取队列长度
   */
  public getQueueLength(): number {
    return this.queue.length;
  }

  /**
   * 获取运行中任务详情
   */
  public getRunningTasks(): Array<{ runId: string; skillName: string; elapsedMs: number }> {
    return Array.from(this.running.entries()).map(([runId, { startedAt }]) => ({
      runId,
      skillName: 'unknown', // 简化：实际应存skillName
      elapsedMs: Date.now() - startedAt,
    }));
  }

  /**
   * 健康检查：是否有任务超时
   */
  public isHealthy(): boolean {
    for (const [, { startedAt }] of this.running) {
      if (Date.now() - startedAt > this.maxTimeoutMs * 2) {
        return false;
      }
    }
    return true;
  }

  private cleanup(runId: string): void {
    this.running.delete(runId);
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

export interface BrowserManager {
  getReadyPage(skillName: string): Promise<ReadyPageLease>;
  releasePage(page: unknown): void;
  markBroken(page: unknown): void;
  getPoolSize(): { total: number; idle: number; busy: number };
}

// ===================== SkillRunner + BrowserManager 集成 =====================

export interface IntegratedSkillRunnerOptions extends Omit<SkillRunnerOptions, 'executors'> {
  browserManager?: BrowserManager;
  executors: Record<string, SkillExecutor>;
}

export class IntegratedSkillRunner extends QClawSkillRunner {
  private readonly browserManager?: BrowserManager;

  constructor(options: IntegratedSkillRunnerOptions) {
    super(options);
    this.browserManager = options.browserManager;
  }

  /**
   * 执行技能，自动从BrowserManager获取Page
   */
  public async runWithPage(
    skillName: string,
    input: Record<string, unknown> = {},
    options?: { timeoutMs?: number; runId?: string; signal?: AbortSignal }
  ): Promise<SkillRunResult> {
    const runId = options?.runId ?? `run-${Date.now()}`;

    // 如果有BrowserManager，自动分配Page
    let pageLease: ReadyPageLease | undefined;
    if (this.browserManager) {
      try {
        pageLease = await this.browserManager.getReadyPage(skillName);
        input = { ...input, page: pageLease.page };
        this.log('DEBUG', `getReadyPage: ${skillName} page leased`);
      } catch (e: any) {
        this.log('WARN', `getReadyPage failed: ${e.message}`);
      }
    }

    const result = await this.run(skillName, input, { ...options, runId });

    // 自动归还Page
    if (pageLease) {
      pageLease.release();
    }

    return result;
  }
}
