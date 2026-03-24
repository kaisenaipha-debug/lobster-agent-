/**
 * QClawPlanner.ts - 规划决策器 v2.0
 *
 * 来源：QClaw官方架构 v2
 * 用途：整合SkillRegistry + PromptBuilder，四层决策路由
 * 依赖：QClawSkillRegistry.ts, QClawPromptBuilder.ts
 */

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

export type PlannerDecisionType = 'RUN_SKILL' | 'FINISH' | 'FAIL';
export type SkillRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type SkillDomain = 'SEARCH' | 'BROWSE' | 'EXTRACTION' | 'NAVIGATION' | 'FORM' | 'AUTH' | 'DOWNLOAD' | 'SYSTEM' | 'CUSTOM';

export interface SkillExecutionPolicy {
  defaultTimeoutMs?: number;
  maxTimeoutMs?: number;
  retryable?: boolean;
  maxRetries?: number;
  queueGroup?: string;
  exclusive?: boolean;
  pageReusePreferred?: boolean;
  pagePoolRequired?: boolean;
  idempotent?: boolean;
}

export interface SkillCapabilityFlags {
  readOnly?: boolean;
  mutatesPage?: boolean;
  mutatesRemoteState?: boolean;
  needsLoginState?: boolean;
  needsNetwork?: boolean;
  producesStructuredOutput?: boolean;
}

export interface SkillPublicViewV2 {
  name: string;
  version: string;
  aliases: string[];
  displayName?: string;
  description?: string;
  tags: string[];
  category?: string;
  domains: SkillDomain[];
  riskLevel: SkillRiskLevel;
  status: 'ENABLED' | 'DISABLED' | 'DEPRECATED' | 'EXPERIMENTAL';
  permissions: string[];
  capabilities: SkillCapabilityFlags;
  execution: SkillExecutionPolicy;
  plannerCallable: boolean;
  manualCallable: boolean;
  plannerVisible: boolean;
  uiVisible: boolean;
  notes?: string;
}

export interface PlannerDecision {
  type: PlannerDecisionType;
  reason?: string;
  skillName?: string;
  skillInput?: unknown;
  finalText?: string;
}

export interface PlannerMemoryItem {
  turn: number;
  type: 'USER' | 'PLAN' | 'ACTION' | 'OBSERVATION' | 'RESULT' | 'ERROR' | 'SYSTEM';
  content: string;
  data?: unknown;
  timestamp: number;
}

export interface PlannerSkillResult {
  runId: string;
  skillName: string;
  status: 'QUEUED' | 'RUNNING' | 'SUCCESS' | 'FAILED' | 'TIMEOUT' | 'CANCELLED';
  output?: unknown;
  error?: string;
  startedAt: number;
  endedAt: number;
  durationMs: number;
  cancelled?: boolean;
  timedOut?: boolean;
}

export interface PlannerTurnRecord {
  turn: number;
  status: 'PLANNING' | 'EXECUTING' | 'OBSERVING' | 'DONE' | 'FAILED' | 'CANCELLED';
  chosenSkill?: string;
  chosenInput?: unknown;
  skillResult?: PlannerSkillResult;
  summary?: string;
  error?: string;
  startedAt: number;
  endedAt?: number;
}

export interface PlannerTaskInput {
  taskType?: string;
  userGoal: string;
  payload?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface PlannerContext {
  runId: string;
  task: PlannerTaskInput;
  turn: number;
  maxTurns: number;
  memory: PlannerMemoryItem[];
  turns: PlannerTurnRecord[];
  availableSkills: SkillPublicViewV2[];
  signal: AbortSignal;
  now: () => number;
  log: (level: LogLevel, message: string, extra?: unknown) => void;
}

export interface SkillRouteRuleV2 {
  name: string;
  enabled?: boolean;
  skillName: string;
  score: (ctx: PlannerContext) => number;
  buildInput?: (ctx: PlannerContext, skill: SkillPublicViewV2) => unknown;
  reason?: string;
}

export interface LlmPlannerResponseV2 {
  type: PlannerDecisionType;
  reason?: string;
  skillName?: string;
  skillInput?: unknown;
  finalText?: string;
}

export interface PlannerHooksV2 {
  onBeforePlan?: (ctx: PlannerContext) => Promise<void> | void;
  onAfterPlan?: (ctx: PlannerContext, decision: PlannerDecision) => Promise<void> | void;
  onFallback?: (ctx: PlannerContext, reason: string) => Promise<void> | void;
}

export interface QClawPlannerOptionsV2 {
  logPrefix?: string;
  rules?: SkillRouteRuleV2[];
  llmPlanner?: (ctx: PlannerContext) => Promise<LlmPlannerResponseV2 | null>;
  fallbackSkillName?: string;
  finishOnLastSuccess?: boolean;
  maxConsecutiveFailuresPerSkill?: number;
  maxConsecutiveTimeoutsPerSkill?: number;
  allowHighRisk?: boolean;
  allowCriticalRisk?: boolean;
  hooks?: PlannerHooksV2;
}

// ===================== 核心类 =====================

export class QClawPlanner {
  private readonly logPrefix: string;
  private readonly rules: SkillRouteRuleV2[];
  private readonly llmPlanner?: QClawPlannerOptionsV2['llmPlanner'];
  private readonly fallbackSkillName?: string;
  private readonly finishOnLastSuccess: boolean;
  private readonly maxConsecutiveFailuresPerSkill: number;
  private readonly maxConsecutiveTimeoutsPerSkill: number;
  private readonly allowHighRisk: boolean;
  private readonly allowCriticalRisk: boolean;
  private readonly hooks?: PlannerHooksV2;

  constructor(options: QClawPlannerOptionsV2 = {}) {
    this.logPrefix = options.logPrefix ?? 'QCLAW_PLANNER_V2';
    this.rules = options.rules ?? [];
    this.llmPlanner = options.llmPlanner;
    this.fallbackSkillName = options.fallbackSkillName;
    this.finishOnLastSuccess = options.finishOnLastSuccess ?? true;
    this.maxConsecutiveFailuresPerSkill = Math.max(1, options.maxConsecutiveFailuresPerSkill ?? 2);
    this.maxConsecutiveTimeoutsPerSkill = Math.max(1, options.maxConsecutiveTimeoutsPerSkill ?? 1);
    this.allowHighRisk = options.allowHighRisk ?? false;
    this.allowCriticalRisk = options.allowCriticalRisk ?? false;
    this.hooks = options.hooks;
  }

  /**
   * 四层决策路由
   * Layer 1: 规则路由（tryRuleRouting）— 分数制，优先级最高
   * Layer 2: LLM 大脑（tryLlmPlanner）— 可注入 GPT/Claude
   * Layer 3: 历史推断（tryHistoryBasedDecision）— 上轮失败自动换 skill
   * Layer 4: 最终兜底（tryFallback）— 必定执行
   */
  public async plan(ctx: PlannerContext): Promise<PlannerDecision> {
    await this.safeHook('onBeforePlan', ctx);

    if (ctx.signal.aborted) {
      return this.finish('planner aborted before decision');
    }

    const validationError = this.validateContext(ctx);
    if (validationError) {
      return this.fail(validationError);
    }

    const usableSkills = this.getUsableSkills(ctx);
    if (usableSkills.length === 0) {
      return this.fail('no usable planner-callable skills after filtering');
    }

    // Layer 0: 上一步成功 → 直接 FINISH
    if (this.finishOnLastSuccess && ctx.turn > 1 && this.lastResult()?.status === 'SUCCESS') {
      return this.finish('last skill succeeded, finish by policy', ctx);
    }

    // Layer 1: 规则路由
    const ruleDecision = this.tryRuleRouting(ctx, usableSkills);
    if (ruleDecision) {
      ctx.log('INFO', `Layer1(rule): ${ruleDecision.skillName} reason=${ruleDecision.reason}`);
      await this.safeHook('onAfterPlan', ctx, ruleDecision);
      return ruleDecision;
    }

    // Layer 2: LLM 大脑
    const llmDecision = await this.tryLlmPlanner(ctx, usableSkills);
    if (llmDecision) {
      ctx.log('INFO', `Layer2(llm): ${llmDecision.type} reason=${llmDecision.reason}`);
      await this.safeHook('onAfterPlan', ctx, llmDecision);
      return llmDecision;
    }

    // Layer 3: 历史推断
    const historyDecision = this.tryHistoryBasedDecision(ctx, usableSkills);
    if (historyDecision) {
      ctx.log('INFO', `Layer3(history): ${historyDecision.type} reason=${historyDecision.reason}`);
      await this.safeHook('onAfterPlan', ctx, historyDecision);
      return historyDecision;
    }

    // Layer 4: 兜底
    const fallbackDecision = this.tryFallback(ctx, usableSkills);
    ctx.log('INFO', `Layer4(fallback): ${fallbackDecision.type} reason=${fallbackDecision.reason}`);
    await this.safeHook('onAfterPlan', ctx, fallbackDecision);
    return fallbackDecision;
  }

  // ===================== 上下文校验 =====================

  private validateContext(ctx: PlannerContext): string | null {
    if (!ctx.task?.userGoal?.trim()) return 'task.userGoal is required';
    if (!Array.isArray(ctx.availableSkills) || ctx.availableSkills.length === 0) {
      return 'availableSkills is empty';
    }
    return null;
  }

  private getUsableSkills(ctx: PlannerContext): SkillPublicViewV2[] {
    return ctx.availableSkills
      .filter((s) => s.status === 'ENABLED' || s.status === 'EXPERIMENTAL')
      .filter((s) => s.plannerCallable)
      .filter((s) => s.plannerVisible)
      .filter((s) => this.isRiskAllowed(s))
      .filter((s) => !this.shouldAvoidDueToFailures(ctx, s.name))
      .filter((s) => !this.shouldAvoidDueToTimeouts(ctx, s.name));
  }

  private isRiskAllowed(skill: SkillPublicViewV2): boolean {
    if (skill.riskLevel === 'CRITICAL') return this.allowCriticalRisk;
    if (skill.riskLevel === 'HIGH') return this.allowHighRisk;
    return true;
  }

  // ===================== Layer 1: 规则路由 =====================

  private tryRuleRouting(ctx: PlannerContext, usableSkills: SkillPublicViewV2[]): PlannerDecision | null {
    const scored = this.rules
      .filter((r) => r.enabled !== false)
      .map((rule) => {
        let score = 0;
        try { score = rule.score(ctx); } catch (err) { /* skip */ }
        return { rule, score };
      })
      .filter((x) => x.score > 0)
      .sort((a, b) => b.score - a.score);

    for (const item of scored) {
      const skill = this.findSkill(item.rule.skillName, usableSkills);
      if (!skill) continue;

      let input: unknown = ctx.task.payload ?? {};
      try {
        if (item.rule.buildInput) {
          input = item.rule.buildInput(ctx, skill);
        }
      } catch (err) {
        ctx.log('WARN', `rule buildInput error rule=${item.rule.name}: ${this.errMsg(err)}`);
      }

      return {
        type: 'RUN_SKILL',
        reason: item.rule.reason ?? `rule matched: ${item.rule.name}`,
        skillName: skill.name,
        skillInput: input,
      };
    }

    return null;
  }

  // ===================== Layer 2: LLM 大脑 =====================

  private async tryLlmPlanner(ctx: PlannerContext, usableSkills: SkillPublicViewV2[]): Promise<PlannerDecision | null> {
    if (!this.llmPlanner) return null;

    try {
      const res = await this.llmPlanner({ ...ctx, availableSkills: usableSkills });
      if (!res) return null;

      if (res.type === 'RUN_SKILL') {
        if (!res.skillName) {
          return this.fail('llmPlanner returned RUN_SKILL without skillName');
        }
        const skill = this.findSkill(res.skillName, usableSkills);
        if (!skill) {
          return this.fail(`llmPlanner selected unavailable skill: ${res.skillName}`);
        }
        return {
          type: 'RUN_SKILL',
          reason: res.reason ?? 'llm planner selected skill',
          skillName: skill.name,
          skillInput: res.skillInput ?? ctx.task.payload ?? {},
        };
      }

      if (res.type === 'FINISH') {
        return this.finish(res.reason ?? 'llm planner finished', ctx, res.finalText);
      }

      return this.fail(res.reason ?? 'llm planner failed');

    } catch (err) {
      ctx.log('WARN', `llmPlanner error: ${this.errMsg(err)}`);
      return null;
    }
  }

  // ===================== Layer 3: 历史推断 =====================

  private tryHistoryBasedDecision(ctx: PlannerContext, usableSkills: SkillPublicViewV2[]): PlannerDecision | null {
    const last = this.lastTurn(ctx);
    const lastResult = last?.skillResult;
    if (!lastResult) return null;

    if (lastResult.status === 'SUCCESS') {
      return this.finish('last result succeeded, finish by history', ctx);
    }

    if (lastResult.status === 'CANCELLED') {
      return this.fail(`last skill cancelled: ${lastResult.error ?? 'unknown reason'}`);
    }

    if (lastResult.status === 'TIMEOUT') {
      const failedSkill = last?.chosenSkill;
      const timeoutCount = failedSkill ? this.getConsecutiveTimeoutCount(ctx, failedSkill) : 0;

      if (failedSkill && timeoutCount < this.maxConsecutiveTimeoutsPerSkill) {
        const same = this.findSkill(failedSkill, usableSkills);
        if (same) {
          return {
            type: 'RUN_SKILL',
            reason: `retry timed out skill once: ${same.name}`,
            skillName: same.name,
            skillInput: last?.chosenInput ?? ctx.task.payload ?? {},
          };
        }
      }

      const alt = this.findAlternativeSkill(ctx, usableSkills, failedSkill);
      if (alt) {
        return {
          type: 'RUN_SKILL',
          reason: `switch skill after timeout: ${alt.name}`,
          skillName: alt.name,
          skillInput: this.buildDefaultSkillInput(ctx, alt),
        };
      }

      return this.fail('last skill timed out and no alternative available');
    }

    if (lastResult.status === 'FAILED') {
      const failedSkill = last?.chosenSkill;
      const failCount = failedSkill ? this.getConsecutiveFailureCount(ctx, failedSkill) : 0;

      if (failedSkill && failCount < this.maxConsecutiveFailuresPerSkill) {
        const same = this.findSkill(failedSkill, usableSkills);
        if (same && this.isRetryable(same)) {
          return {
            type: 'RUN_SKILL',
            reason: `retry retryable failed skill: ${same.name}`,
            skillName: same.name,
            skillInput: last?.chosenInput ?? ctx.task.payload ?? {},
          };
        }
      }

      const alt = this.findAlternativeSkill(ctx, usableSkills, failedSkill);
      if (alt) {
        return {
          type: 'RUN_SKILL',
          reason: `switch to alternative after failure: ${alt.name}`,
          skillName: alt.name,
          skillInput: this.buildDefaultSkillInput(ctx, alt),
        };
      }

      return this.fail('last skill failed and no alternative available');
    }

    return null;
  }

  // ===================== Layer 4: 兜底 =====================

  private tryFallback(ctx: PlannerContext, usableSkills: SkillPublicViewV2[]): PlannerDecision {
    if (this.fallbackSkillName) {
      const skill = this.findSkill(this.fallbackSkillName, usableSkills);
      if (skill) {
        this.safeHook('onFallback', ctx, `use configured fallback=${skill.name}`);
        return {
          type: 'RUN_SKILL',
          reason: `fallback skill: ${skill.name}`,
          skillName: skill.name,
          skillInput: this.buildDefaultSkillInput(ctx, skill),
        };
      }
    }

    const ranked = this.rankSkillsForFallback(ctx, usableSkills);
    if (ranked.length > 0) {
      const skill = ranked[0];
      this.safeHook('onFallback', ctx, `use ranked fallback=${skill.name}`);
      return {
        type: 'RUN_SKILL',
        reason: `ranked fallback skill: ${skill.name}`,
        skillName: skill.name,
        skillInput: this.buildDefaultSkillInput(ctx, skill),
      };
    }

    return this.fail('planner fallback failed: no usable skill');
  }

  // ===================== 兜底评分 =====================

  private rankSkillsForFallback(ctx: PlannerContext, skills: SkillPublicViewV2[]): SkillPublicViewV2[] {
    const taskType = (ctx.task.taskType ?? '').toLowerCase();
    const goal = ctx.task.userGoal.toLowerCase();

    return [...skills].sort((a, b) => {
      const sa = this.computeFallbackScore(a, taskType, goal);
      const sb = this.computeFallbackScore(b, taskType, goal);
      return sb - sa;
    });
  }

  private computeFallbackScore(skill: SkillPublicViewV2, taskType: string, goal: string): number {
    let score = 0;

    if (skill.riskLevel === 'LOW') score += 30;
    if (skill.capabilities.readOnly) score += 20;
    if (skill.execution.idempotent) score += 10;
    if (skill.execution.pageReusePreferred) score += 5;

    if (taskType && skill.category?.toLowerCase() === taskType) score += 40;
    if (taskType && skill.domains.some((d) => d.toLowerCase() === taskType)) score += 30;

    for (const tag of skill.tags) {
      if (goal.includes(tag.toLowerCase())) score += 8;
    }

    if (skill.name.includes('search') &&
        (goal.includes('search') || goal.includes('搜索') || goal.includes('google'))) {
      score += 20;
    }

    if (skill.name.includes('browse') || skill.domains.includes('BROWSE')) score += 5;

    return score;
  }

  // ===================== 辅助方法 =====================

  private findAlternativeSkill(
    ctx: PlannerContext,
    skills: SkillPublicViewV2[],
    exclude?: string
  ): SkillPublicViewV2 | null {
    const currentTaskType = (ctx.task.taskType ?? '').toLowerCase();
    const excludeResolved = exclude?.trim();

    const candidates = skills
      .filter((s) => s.name !== excludeResolved)
      .sort((a, b) => {
        const sa = this.alternativeScore(ctx, a, currentTaskType);
        const sb = this.alternativeScore(ctx, b, currentTaskType);
        return sb - sa;
      });

    return candidates[0] ?? null;
  }

  private alternativeScore(ctx: PlannerContext, skill: SkillPublicViewV2, currentTaskType: string): number {
    let score = 0;

    if (skill.riskLevel === 'LOW') score += 20;
    if (skill.capabilities.readOnly) score += 20;
    if (skill.execution.retryable) score += 5;
    if (skill.execution.idempotent) score += 5;

    if (currentTaskType && skill.category?.toLowerCase() === currentTaskType) score += 25;
    if (currentTaskType && skill.domains.some((d) => d.toLowerCase() === currentTaskType)) score += 15;

    const goal = ctx.task.userGoal.toLowerCase();
    if (skill.tags.some((t) => goal.includes(t.toLowerCase()))) score += 10;

    return score;
  }

  private isRetryable(skill: SkillPublicViewV2): boolean {
    return !!skill.execution.retryable && (skill.execution.maxRetries ?? 0) > 0;
  }

  private shouldAvoidDueToFailures(ctx: PlannerContext, skillName: string): boolean {
    return this.getConsecutiveFailureCount(ctx, skillName) >= this.maxConsecutiveFailuresPerSkill;
  }

  private shouldAvoidDueToTimeouts(ctx: PlannerContext, skillName: string): boolean {
    return this.getConsecutiveTimeoutCount(ctx, skillName) >= this.maxConsecutiveTimeoutsPerSkill;
  }

  private getConsecutiveFailureCount(ctx: PlannerContext, skillName: string): number {
    let count = 0;
    for (let i = ctx.turns.length - 1; i >= 0; i--) {
      const t = ctx.turns[i];
      if (t.chosenSkill !== skillName) break;
      if (t.skillResult?.status === 'FAILED') { count++; continue; }
      break;
    }
    return count;
  }

  private getConsecutiveTimeoutCount(ctx: PlannerContext, skillName: string): number {
    let count = 0;
    for (let i = ctx.turns.length - 1; i >= 0; i--) {
      const t = ctx.turns[i];
      if (t.chosenSkill !== skillName) break;
      if (t.skillResult?.status === 'TIMEOUT') { count++; continue; }
      break;
    }
    return count;
  }

  private findSkill(nameOrAlias: string, skills: SkillPublicViewV2[]): SkillPublicViewV2 | null {
    const key = nameOrAlias.trim();
    if (!key) return null;
    for (const skill of skills) {
      if (skill.name === key) return skill;
      if (skill.aliases.includes(key)) return skill;
    }
    return null;
  }

  private lastTurn(ctx: PlannerContext): PlannerTurnRecord | undefined {
    return ctx.turns[ctx.turns.length - 1];
  }

  private lastResult(): PlannerSkillResult | undefined {
    return this.lastTurn.arguments?.[0]?.skillResult;
  }

  private buildDefaultSkillInput(ctx: PlannerContext, skill: SkillPublicViewV2): unknown {
    const payload = ctx.task.payload ?? {};
    const goal = ctx.task.userGoal;

    if (skill.name === 'google-search' || skill.aliases.includes('search-google')) {
      return { keyword: payload['keyword'] ?? goal };
    }

    return payload;
  }

  private buildDefaultFinalText(ctx: PlannerContext): string {
    const last = this.lastTurn(ctx);
    const output = last?.skillResult?.output;
    if (output == null) return '任务已完成。';
    const text = this.safeJson(output);
    if (text.length <= 320) return `任务已完成。结果：${text}`;
    return `任务已完成。结果摘要：${text.slice(0, 320)}...`;
  }

  private finish(reason: string, ctx?: PlannerContext, finalText?: string): PlannerDecision {
    return {
      type: 'FINISH',
      reason,
      finalText: finalText ?? (ctx ? this.buildDefaultFinalText(ctx) : '任务已完成。'),
    };
  }

  private fail(reason: string): PlannerDecision {
    return { type: 'FAIL', reason };
  }

  private async safeHook(name: keyof PlannerHooksV2, ctx: PlannerContext, arg?: unknown): Promise<void> {
    const hook = this.hooks?.[name];
    if (!hook) return;
    try {
      if (name === 'onBeforePlan') { await (hook as (c: PlannerContext) => Promise<void>)(ctx); }
      else if (name === 'onAfterPlan') { await (hook as (c: PlannerContext, d: PlannerDecision) => Promise<void>)(ctx, arg as PlannerDecision); }
      else if (name === 'onFallback') { await (hook as (c: PlannerContext, r: string) => Promise<void>)(ctx, String(arg)); }
    } catch (err) {
      console.warn(`hook ${String(name)} failed:`, err);
    }
  }

  private safeJson(value: unknown): string {
    try { return JSON.stringify(value); } catch { return '[unserializable]'; }
  }

  private errMsg(err: unknown): string {
    return err instanceof Error ? err.message : String(err);
  }
}

// ===================== 默认规则工厂 =====================

export function createDefaultPlannerRulesV2(): SkillRouteRuleV2[] {
  return [
    {
      name: 'google-search-rule',
      skillName: 'google-search',
      reason: 'goal strongly suggests web search',
      score: (ctx) => {
        const goal = ctx.task.userGoal.toLowerCase();
        const taskType = (ctx.task.taskType ?? '').toLowerCase();
        let score = 0;
        if (goal.includes('google')) score += 100;
        if (goal.includes('搜索')) score += 90;
        if (goal.includes('search')) score += 80;
        if (taskType === 'search') score += 70;
        return score;
      },
      buildInput: (ctx) => ({ keyword: ctx.task.payload?.['keyword'] ?? ctx.task.userGoal }),
    },
    {
      name: 'smart-search-rule',
      skillName: 'smart-search',
      reason: 'multi-channel intelligence search',
      score: (ctx) => {
        const goal = ctx.task.userGoal.toLowerCase();
        let score = 0;
        if (goal.includes('招标') || goal.includes('采购')) score += 80;
        if (goal.includes('情报') || goal.includes('调研')) score += 70;
        if (goal.includes('政府') && goal.includes('搜索')) score += 60;
        return score;
      },
      buildInput: (ctx) => ({ keyword: ctx.task.payload?.['keyword'] ?? ctx.task.userGoal }),
    },
    {
      name: 'x-search-rule',
      skillName: 'x-search',
      reason: 'X/Twitter social search',
      score: (ctx) => {
        const goal = ctx.task.userGoal.toLowerCase();
        let score = 0;
        if (goal.includes('twitter') || goal.includes('x.com')) score += 90;
        if (goal.includes('社交') && goal.includes('搜索')) score += 70;
        return score;
      },
      buildInput: (ctx) => ({ keyword: ctx.task.payload?.['keyword'] ?? ctx.task.userGoal }),
    },
  ];
}
