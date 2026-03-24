/**
 * QClawAgentLoop.ts - Agent执行循环 v2.0
 *
 * 来源：QClaw官方架构 v2
 * 用途：最顶层循环，整合Registry+Planner+Runner
 * 依赖：QClawSkillRegistry.ts, QClawPlanner.ts, QClawSkillRunner.ts
 */

// ===================== 类型定义 =====================

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

export type AgentLoopState = 'IDLE' | 'RUNNING' | 'STOPPING' | 'STOPPED';
export type AgentTurnStatus = 'PLANNING' | 'EXECUTING' | 'OBSERVING' | 'DONE' | 'FAILED' | 'CANCELLED';
export type SkillRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type SkillStatus = 'ENABLED' | 'DISABLED' | 'DEPRECATED' | 'EXPERIMENTAL';
export type SkillDomain = 'SEARCH' | 'BROWSE' | 'EXTRACTION' | 'NAVIGATION' | 'FORM' | 'AUTH' | 'DOWNLOAD' | 'SYSTEM' | 'CUSTOM';

export interface SkillExecutionPolicy {
  defaultTimeoutMs?: number; maxTimeoutMs?: number; retryable?: boolean;
  maxRetries?: number; queueGroup?: string; exclusive?: boolean;
  pageReusePreferred?: boolean; pagePoolRequired?: boolean; idempotent?: boolean;
}

export interface SkillCapabilityFlags {
  readOnly?: boolean; mutatesPage?: boolean; mutatesRemoteState?: boolean;
  needsLoginState?: boolean; needsNetwork?: boolean; producesStructuredOutput?: boolean;
}

export interface SkillPublicView {
  name: string; version: string; aliases: string[];
  displayName?: string; description?: string; tags: string[];
  category?: string; domains: SkillDomain[];
  riskLevel: SkillRiskLevel; status: SkillStatus;
  permissions: string[]; capabilities: SkillCapabilityFlags;
  execution: SkillExecutionPolicy;
  plannerCallable: boolean; manualCallable: boolean;
  plannerVisible: boolean; uiVisible: boolean; notes?: string;
}

export interface SkillSelectionContext {
  mode?: string; taskType?: string; currentDomain?: string;
  allowHighRisk?: boolean; requirePlannerCallable?: boolean;
  requireManualCallable?: boolean;
  includeExperimental?: boolean; includeDeprecated?: boolean;
  allowedNames?: string[]; blockedNames?: string[];
}

export interface PlannerDecision {
  type: 'RUN_SKILL' | 'FINISH' | 'FAIL';
  reason?: string; skillName?: string; skillInput?: unknown; finalText?: string;
}

export interface PlannerMemoryItem {
  turn: number;
  type: 'USER' | 'PLAN' | 'ACTION' | 'OBSERVATION' | 'RESULT' | 'ERROR' | 'SYSTEM';
  content: string; data?: unknown; timestamp: number;
}

export interface PlannerSkillResult {
  runId: string; skillName: string;
  status: 'QUEUED' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'TIMEOUT' | 'CANCELLED';
  output?: unknown; error?: string;
  startedAt: number; endedAt: number; durationMs: number;
  cancelled?: boolean; timedOut?: boolean;
}

export interface PlannerTurnRecord {
  turn: number; status: AgentTurnStatus;
  chosenSkill?: string; chosenInput?: unknown;
  skillResult?: PlannerSkillResult; summary?: string; error?: string;
  startedAt: number; endedAt?: number;
}

export interface PlannerTaskInput {
  taskType?: string; userGoal: string;
  payload?: Record<string, unknown>; metadata?: Record<string, unknown>;
}

export interface PlannerContext {
  runId: string; task: PlannerTaskInput;
  turn: number; maxTurns: number;
  memory: PlannerMemoryItem[]; turns: PlannerTurnRecord[];
  availableSkills: SkillPublicView[];
  signal: AbortSignal; now: () => number;
  log: (level: LogLevel, message: string, extra?: unknown) => void;
}

export interface AgentObservation {
  title?: string; url?: string; textSnippet?: string;
  structuredData?: unknown; timestamp?: number;
}

export interface AgentFinalResult {
  runId: string;
  state: 'SUCCESS' | 'FAILED' | 'CANCELLED' | 'MAX_TURNS_REACHED';
  userGoal: string; finalText: string;
  turns: PlannerTurnRecord[]; memory: PlannerMemoryItem[]; observations: AgentObservation[];
  startedAt: number; endedAt: number; durationMs: number;
}

export interface SkillRunResult {
  runId: string; skillName: string;
  status: 'QUEUED' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'TIMEOUT' | 'CANCELLED';
  output?: unknown; error?: string;
  startedAt: number; endedAt: number; durationMs: number;
  cancelled?: boolean; timedOut?: boolean;
}

export interface SkillRunnerLike {
  runSkill<TInput = unknown, TOutput = unknown>(
    skillName: string, input: TInput
  ): Promise<SkillRunResult>;
  cancelCurrentRun(): boolean;
}

export interface PlannerLike {
  plan(ctx: PlannerContext): Promise<PlannerDecision>;
}

export interface SkillRegistryLike {
  getAvailableSkills(ctx?: SkillSelectionContext): SkillPublicView[];
  validateSkillCallable(nameOrAlias: string, ctx?: SkillSelectionContext):
    { ok: boolean; reason?: string; meta?: SkillPublicView };
}

export interface AgentLoopHooks {
  onRunStart?: (ctx: { runId: string; task: PlannerTaskInput }) => Promise<void> | void;
  onTurnStart?: (ctx: { runId: string; turn: number }) => Promise<void> | void;
  onTurnEnd?: (ctx: { runId: string; turn: number; record: PlannerTurnRecord }) => Promise<void> | void;
  onObservation?: (ctx: { runId: string; turn: number; observation: AgentObservation }) => Promise<void> | void;
  onRunEnd?: (result: AgentFinalResult) => Promise<void> | void;
}

export interface FinalizerFn {
  (ctx: {
    runId: string; task: PlannerTaskInput;
    turns: PlannerTurnRecord[]; memory: PlannerMemoryItem[]; observations: AgentObservation[];
  }): Promise<string> | string;
}

export interface ObservationExtractorFn {
  (params: {
    task: PlannerTaskInput; turn: number; skillName: string; skillResult: SkillRunResult;
  }): Promise<AgentObservation | null> | AgentObservation | null;
}

// ===================== 核心类 =====================

export class QClawAgentLoop {
  private readonly skillRunner: SkillRunnerLike;
  private readonly planner: PlannerLike;
  private readonly registry: SkillRegistryLike;
  private readonly logPrefix: string;
  private readonly maxTurns: number;
  private readonly defaultMode?: string;
  private readonly allowHighRisk: boolean;
  private readonly currentDomain?: string;
  private readonly hooks?: AgentLoopHooks;
  private readonly finalizer?: FinalizerFn;
  private readonly observationExtractor?: ObservationExtractorFn;

  private state: AgentLoopState = 'IDLE';
  private currentRunId: string | null = null;
  private currentController: AbortController | null = null;

  constructor(options: {
    skillRunner: SkillRunnerLike;
    planner: PlannerLike;
    registry: SkillRegistryLike;
    logPrefix?: string;
    maxTurns?: number;
    defaultMode?: string;
    allowHighRisk?: boolean;
    currentDomain?: string;
    hooks?: AgentLoopHooks;
    finalizer?: FinalizerFn;
    observationExtractor?: ObservationExtractorFn;
  }) {
    this.skillRunner = options.skillRunner;
    this.planner = options.planner;
    this.registry = options.registry;
    this.logPrefix = options.logPrefix ?? 'QCLAW_AGENT_LOOP';
    this.maxTurns = Math.max(1, options.maxTurns ?? 5);
    this.defaultMode = options.defaultMode;
    this.allowHighRisk = options.allowHighRisk ?? false;
    this.currentDomain = options.currentDomain;
    this.hooks = options.hooks;
    this.finalizer = options.finalizer;
    this.observationExtractor = options.observationExtractor;
  }

  public getState(): AgentLoopState { return this.state; }
  public getCurrentRunId(): string | null { return this.currentRunId; }
  public isRunning(): boolean { return this.state === 'RUNNING'; }

  public cancelCurrentRun(reason = 'manual cancel'): boolean {
    if (!this.currentController || !this.currentRunId) return false;
    this.setState('STOPPING', `runId=${this.currentRunId} reason=${reason}`);
    this.currentController.abort(reason);
    this.skillRunner.cancelCurrentRun();
    return true;
  }

  /**
   * 主循环：RUN_SKILL → OBSERVING → plan() → ... → FINISH/FAIL/MAX_TURNS
   */
  public async runTask(
    task: PlannerTaskInput,
    runtime?: {
      mode?: string; allowHighRisk?: boolean; currentDomain?: string;
      allowedSkillNames?: string[]; blockedSkillNames?: string[];
    }
  ): Promise<AgentFinalResult> {
    if (this.state === 'RUNNING') throw new Error('AgentLoop is already running');

    const runId = this.makeId('agent');
    const controller = new AbortController();
    const startedAt = Date.now();

    this.currentRunId = runId;
    this.currentController = controller;
    this.setState('RUNNING', `runId=${runId}`);

    const memory: PlannerMemoryItem[] = [];
    const turns: PlannerTurnRecord[] = [];
    const observations: AgentObservation[] = [];

    this.pushMemory(memory, 0, 'USER', task.userGoal, task);
    await this.safeHook('onRunStart', { runId, task });

    try {
      for (let turn = 1; turn <= this.maxTurns; turn++) {
        if (controller.signal.aborted) {
          return this.buildCancelledResult(runId, task, turns, memory, observations, startedAt, 'agent cancelled');
        }

        await this.safeHook('onTurnStart', { runId, turn });

        const turnRecord: PlannerTurnRecord = {
          turn, status: 'PLANNING', startedAt: Date.now(),
        };
        turns.push(turnRecord);

        const selCtx: SkillSelectionContext = {
          mode: runtime?.mode ?? this.defaultMode,
          taskType: task.taskType,
          currentDomain: runtime?.currentDomain ?? this.currentDomain,
          allowHighRisk: runtime?.allowHighRisk ?? this.allowHighRisk,
          requirePlannerCallable: true,
          allowedNames: runtime?.allowedSkillNames,
          blockedNames: runtime?.blockedSkillNames,
        };

        const availableSkills = this.registry.getAvailableSkills(selCtx);

        const plannerCtx: PlannerContext = {
          runId, task, turn, maxTurns: this.maxTurns,
          memory, turns, availableSkills,
          signal: controller.signal,
          now: () => Date.now(),
          log: (level, msg, extra) => {
            this.log(level, `runId=${runId} turn=${turn} ${msg}${extra ? ' extra=' + this.safeJson(extra) : ''}`);
          },
        };

        this.log('INFO', `turn=${turn} planning start skills=${availableSkills.length}`);

        const decision = await this.planner.plan(plannerCtx);
        this.pushMemory(memory, turn, 'PLAN', this.planToText(decision), decision);

        // FINISH
        if (decision.type === 'FINISH') {
          turnRecord.status = 'DONE';
          turnRecord.summary = decision.reason ?? 'planner finished';
          turnRecord.endedAt = Date.now();
          await this.safeHook('onTurnEnd', { runId, turn, record: turnRecord });
          const finalText = await this.makeFinalText(runId, task, turns, memory, observations, decision.finalText);
          const result = this.buildSuccessResult(runId, task, turns, memory, observations, startedAt, finalText);
          await this.safeHook('onRunEnd', result);
          this.cleanup();
          return result;
        }

        // FAIL
        if (decision.type === 'FAIL') {
          turnRecord.status = 'FAILED';
          turnRecord.error = decision.reason ?? 'planner failed';
          turnRecord.endedAt = Date.now();
          this.pushMemory(memory, turn, 'ERROR', turnRecord.error, decision);
          await this.safeHook('onTurnEnd', { runId, turn, record: turnRecord });
          const result = this.buildFailedResult(runId, task, turns, memory, observations, startedAt, turnRecord.error);
          await this.safeHook('onRunEnd', result);
          this.cleanup();
          return result;
        }

        // RUN_SKILL
        if (!decision.skillName) {
          turnRecord.status = 'FAILED';
          turnRecord.error = 'RUN_SKILL without skillName';
          turnRecord.endedAt = Date.now();
          await this.safeHook('onTurnEnd', { runId, turn, record: turnRecord });
          const result = this.buildFailedResult(runId, task, turns, memory, observations, startedAt, turnRecord.error);
          await this.safeHook('onRunEnd', result);
          this.cleanup();
          return result;
        }

        const callable = this.registry.validateSkillCallable(decision.skillName, selCtx);
        if (!callable.ok || !callable.meta) {
          turnRecord.status = 'FAILED';
          turnRecord.error = callable.reason ?? `skill not callable: ${decision.skillName}`;
          turnRecord.endedAt = Date.now();
          await this.safeHook('onTurnEnd', { runId, turn, record: turnRecord });
          const result = this.buildFailedResult(runId, task, turns, memory, observations, startedAt, turnRecord.error);
          await this.safeHook('onRunEnd', result);
          this.cleanup();
          return result;
        }

        turnRecord.status = 'EXECUTING';
        turnRecord.chosenSkill = callable.meta.name;
        turnRecord.chosenInput = decision.skillInput;

        this.pushMemory(memory, turn, 'ACTION', `run skill: ${callable.meta.name}`, {
          skillName: callable.meta.name, skillInput: decision.skillInput, plannerReason: decision.reason,
        });

        this.log('INFO', `turn=${turn} execute skill=${callable.meta.name}`);

        const skillResult = await this.skillRunner.runSkill(callable.meta.name, decision.skillInput ?? {});
        turnRecord.skillResult = skillResult;

        turnRecord.status =
          skillResult.status === 'SUCCESS' ? 'OBSERVING' :
          skillResult.status === 'CANCELLED' ? 'CANCELLED' : 'FAILED';

        const extractedObs = await this.extractObservation({ task, turn, skillName: callable.meta.name, skillResult });
        if (extractedObs) {
          observations.push(extractedObs);
          await this.safeHook('onObservation', { runId, turn, observation: extractedObs });
        }

        // SUCCESS → 继续
        if (skillResult.status === 'SUCCESS') {
          turnRecord.summary = this.summarizeResult(skillResult);
          turnRecord.endedAt = Date.now();
          this.pushMemory(memory, turn, 'RESULT', turnRecord.summary, skillResult);
          await this.safeHook('onTurnEnd', { runId, turn, record: turnRecord });
          continue;
        }

        // CANCELLED
        if (skillResult.status === 'CANCELLED') {
          turnRecord.error = skillResult.error ?? 'skill cancelled';
          turnRecord.endedAt = Date.now();
          await this.safeHook('onTurnEnd', { runId, turn, record: turnRecord });
          const result = this.buildCancelledResult(runId, task, turns, memory, observations, startedAt, turnRecord.error);
          await this.safeHook('onRunEnd', result);
          this.cleanup();
          return result;
        }

        // FAILED/TIMEOUT
        turnRecord.error = skillResult.error ?? `skill ${callable.meta.name} failed`;
        turnRecord.endedAt = Date.now();
        this.pushMemory(memory, turn, 'ERROR', turnRecord.error, skillResult);
        await this.safeHook('onTurnEnd', { runId, turn, record: turnRecord });
        const result = this.buildFailedResult(runId, task, turns, memory, observations, startedAt, turnRecord.error);
        await this.safeHook('onRunEnd', result);
        this.cleanup();
        return result;
      }

      // MAX_TURNS
      const finalText = await this.makeFinalText(runId, task, turns, memory, observations, 'Reached max turns');
      const result: AgentFinalResult = {
        runId, state: 'MAX_TURNS_REACHED', userGoal: task.userGoal,
        finalText, turns, memory, observations,
        startedAt, endedAt: Date.now(), durationMs: Date.now() - startedAt,
      };
      await this.safeHook('onRunEnd', result);
      this.cleanup();
      return result;

    } catch (err) {
      const result = this.buildFailedResult(runId, task, turns, memory, observations, startedAt, this.errMsg(err));
      await this.safeHook('onRunEnd', result);
      this.cleanup();
      return result;
    }
  }

  // ===================== 观察提取 =====================

  private async extractObservation(params: {
    task: PlannerTaskInput; turn: number; skillName: string; skillResult: SkillRunResult;
  }): Promise<AgentObservation | null> {
    if (this.observationExtractor) {
      try { return await this.observationExtractor(params); } catch { return null; }
    }
    if (params.skillResult.status !== 'SUCCESS' || params.skillResult.output == null) return null;
    const out = params.skillResult.output as Record<string, unknown>;
    if (out && typeof out === 'object') {
      return {
        title: typeof out.title === 'string' ? out.title : undefined,
        url: typeof out.url === 'string' ? out.url : undefined,
        textSnippet: typeof out.textSnippet === 'string' ? out.textSnippet
          : typeof out.snippet === 'string' ? out.snippet : undefined,
        structuredData: out, timestamp: Date.now(),
      };
    }
    return { textSnippet: String(params.skillResult.output), timestamp: Date.now() };
  }

  // ===================== 结果构建 =====================

  private async makeFinalText(
    runId: string, task: PlannerTaskInput,
    turns: PlannerTurnRecord[], memory: PlannerMemoryItem[],
    observations: AgentObservation[], suggested?: string
  ): Promise<string> {
    if (suggested?.trim()) return suggested.trim();
    if (this.finalizer) return this.finalizer({ runId, task, turns, memory, observations });
    const last = [...turns].reverse().find(t => t.skillResult?.status === 'SUCCESS');
    if (last?.skillResult?.output != null) {
      return `任务已完成。结果：${this.safeJson(last.skillResult.output)}`;
    }
    return '任务已结束。';
  }

  private summarizeResult(r: SkillRunResult): string {
    if (r.output == null) return `${r.skillName} success`;
    const t = this.safeJson(r.output);
    return t.length <= 180 ? t : t.slice(0, 180) + '...';
  }

  private buildSuccessResult(
    runId: string, task: PlannerTaskInput, turns: PlannerTurnRecord[],
    memory: PlannerMemoryItem[], observations: AgentObservation[],
    startedAt: number, finalText: string
  ): AgentFinalResult {
    this.pushMemory(memory, turns.length, 'RESULT', finalText, { state: 'SUCCESS' });
    return {
      runId, state: 'SUCCESS', userGoal: task.userGoal, finalText,
      turns, memory, observations,
      startedAt, endedAt: Date.now(), durationMs: Date.now() - startedAt,
    };
  }

  private buildFailedResult(
    runId: string, task: PlannerTaskInput, turns: PlannerTurnRecord[],
    memory: PlannerMemoryItem[], observations: AgentObservation[],
    startedAt: number, error: string
  ): AgentFinalResult {
    this.pushMemory(memory, turns.length, 'ERROR', error, { state: 'FAILED' });
    return {
      runId, state: 'FAILED', userGoal: task.userGoal, finalText: `任务失败：${error}`,
      turns, memory, observations,
      startedAt, endedAt: Date.now(), durationMs: Date.now() - startedAt,
    };
  }

  private buildCancelledResult(
    runId: string, task: PlannerTaskInput, turns: PlannerTurnRecord[],
    memory: PlannerMemoryItem[], observations: AgentObservation[],
    startedAt: number, reason: string
  ): AgentFinalResult {
    this.pushMemory(memory, turns.length, 'SYSTEM', `cancelled: ${reason}`, { state: 'CANCELLED' });
    return {
      runId, state: 'CANCELLED', userGoal: task.userGoal, finalText: `任务已取消：${reason}`,
      turns, memory, observations,
      startedAt, endedAt: Date.now(), durationMs: Date.now() - startedAt,
    };
  }

  // ===================== 辅助 =====================

  private planToText(d: PlannerDecision): string {
    if (d.type === 'RUN_SKILL') return `Planner chose: ${d.skillName ?? 'unknown'}`;
    if (d.type === 'FINISH') return `Planner finished: ${d.reason ?? ''}`.trim();
    return `Planner failed: ${d.reason ?? ''}`.trim();
  }

  private pushMemory(
    m: PlannerMemoryItem[], turn: number, type: PlannerMemoryItem['type'],
    content: string, data?: unknown
  ): void {
    m.push({ turn, type, content, data, timestamp: Date.now() });
  }

  private cleanup(): void {
    this.currentRunId = null;
    this.currentController = null;
    this.setState('IDLE', 'run finished');
  }

  private async safeHook(name: keyof AgentLoopHooks, payload: unknown): Promise<void> {
    const h = this.hooks?.[name];
    if (!h) return;
    try { await (h as (p: unknown) => Promise<void>)(payload); } catch (err) {
      this.log('WARN', `hook ${String(name)} failed: ${this.errMsg(err)}`);
    }
  }

  private setState(next: AgentLoopState, reason: string): void {
    if (this.state !== next) {
      const prev = this.state;
      this.state = next;
      this.log('INFO', `state ${prev} -> ${next} reason=${reason}`);
    }
  }

  private makeId(prefix: string): string {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
  }

  private safeJson(v: unknown): string { try { return JSON.stringify(v); } catch { return '[unserializable]'; } }
  private errMsg(e: unknown): string { return e instanceof Error ? e.message : String(e); }

  private log(level: LogLevel, message: string): void {
    console.log(`[${new Date().toISOString()}] [${this.logPrefix}] [${level}] ${message}`);
  }
}
