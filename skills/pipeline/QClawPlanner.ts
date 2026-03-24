/**
 * QClawPlanner.ts - 规划决策器
 * 
 * 来源：QClaw官方架构
 * 用途：整合SkillRegistry + PromptBuilder，接LLM做规划决策
 * 依赖：QClawSkillRegistry.ts, QClawPromptBuilder.ts
 */

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

// ===================== 类型定义 =====================

export type PlannerDecisionType = 'RUN_SKILL' | 'FINISH' | 'FAIL';

export interface PlannerDecision {
  type: PlannerDecisionType;
  reason: string;
  skillName?: string;
  skillInput?: Record<string, unknown>;
  finalText?: string;
}

export interface PlannerOptions {
  /**
   * LLM规划器（核心）— 接收PromptBuilderContext，返回PlannerDecision
   */
  llmPlanner: (
    ctx: import('./QClawPromptBuilder').PromptBuilderContext
  ) => Promise<PlannerDecision | null>;

  /**
   * 最大回合数
   */
  maxTurns?: number;

  /**
   * 单个技能超时（毫秒）
   */
  defaultSkillTimeoutMs?: number;

  /**
   * 是否记录详细日志
   */
  verbose?: boolean;

  /**
   * 日志前缀
   */
  logPrefix?: string;
}

export interface PlannerContext {
  runId: string;
  mode?: string;
  taskType?: string;
  task: import('./QClawPromptBuilder').PromptTaskInput;
}

export interface SkillRunner {
  run(
    skillName: string,
    input: Record<string, unknown>,
    options?: { timeoutMs?: number }
  ): Promise<{ output: unknown; durationMs: number }>;
}

export interface PlannerRunResult {
  runId: string;
  finalDecision: PlannerDecision;
  turns: import('./QClawPromptBuilder').PromptTurnRecord[];
  totalDurationMs: number;
  success: boolean;
  error?: string;
}

// ===================== 核心类 =====================

export class QClawPlanner {
  private readonly llmPlanner: (
    ctx: import('./QClawPromptBuilder').PromptBuilderContext
  ) => Promise<PlannerDecision | null>;
  private readonly maxTurns: number;
  private readonly defaultSkillTimeoutMs: number;
  private readonly verbose: boolean;
  private readonly logPrefix: string;

  constructor(options: PlannerOptions) {
    this.llmPlanner = options.llmPlanner;
    this.maxTurns = options.maxTurns ?? 20;
    this.defaultSkillTimeoutMs = options.defaultSkillTimeoutMs ?? 60_000;
    this.verbose = options.verbose ?? false;
    this.logPrefix = options.logPrefix ?? 'QCLAW_PLANNER';
  }

  /**
   * 执行规划循环
   */
  public async run(
    ctx: PlannerContext,
    skillRunner: SkillRunner,
    registry: import('./QClawSkillRegistry').QClawSkillRegistry
  ): Promise<PlannerRunResult> {
    const startTime = Date.now();
    const turns: import('./QClawPromptBuilder').PromptTurnRecord[] = [];
    let turn = 0;

    this.log('INFO', `=== Planner启动 runId=${ctx.runId} goal=${ctx.task.userGoal}`);

    while (turn < this.maxTurns) {
      turn++;
      const turnStart = Date.now();

      this.log('INFO', `--- Turn ${turn}/${this.maxTurns} ---`);

      // 获取可用技能
      const availableSkills = registry.getAvailableSkills({
        mode: ctx.mode,
        taskType: ctx.taskType,
        allowHighRisk: false,
        requirePlannerCallable: true,
      });

      // 构建Prompt
      const { QClawPromptBuilder, buildPlannerPromptInput } = await import('./QClawPromptBuilder');

      const builder = new QClawPromptBuilder({ strictJsonOutput: true });
      const promptCtx = buildPlannerPromptInput({
        runId: ctx.runId,
        mode: ctx.mode,
        task: ctx.task,
        turn,
        maxTurns: this.maxTurns,
        memory: [], // 可注入记忆
        turns,
        availableSkills,
        observations: [],
      });

      const promptResult = builder.build(promptCtx);

      if (this.verbose) {
        this.log('DEBUG', `Turn ${turn} Prompt构建完成`);
      }

      // 调用LLM
      let decision: PlannerDecision | null;
      try {
        decision = await this.llmPlanner(promptCtx);
      } catch (e: any) {
        this.log('ERROR', `Turn ${turn} LLM调用失败: ${e.message}`);
        break;
      }

      if (!decision) {
        this.log('WARN', `Turn ${turn} LLM返回null`);
        break;
      }

      const turnRecord: import('./QClawPromptBuilder').PromptTurnRecord = {
        turn,
        status: 'EXECUTING',
        chosenSkill: decision.skillName,
        chosenInput: decision.skillInput,
        startedAt: turnStart,
      };

      // 执行决策
      if (decision.type === 'FINISH') {
        turnRecord.status = 'DONE';
        turnRecord.endedAt = Date.now();
        turns.push(turnRecord);

        const result: PlannerRunResult = {
          runId: ctx.runId,
          finalDecision: decision,
          turns,
          totalDurationMs: Date.now() - startTime,
          success: true,
        };

        this.log('INFO', `✅ FINISH: ${decision.reason} | 总耗时: ${result.totalDurationMs}ms`);
        return result;
      }

      if (decision.type === 'FAIL') {
        turnRecord.status = 'FAILED';
        turnRecord.error = decision.reason;
        turnRecord.endedAt = Date.now();
        turns.push(turnRecord);

        const result: PlannerRunResult = {
          runId: ctx.runId,
          finalDecision: decision,
          turns,
          totalDurationMs: Date.now() - startTime,
          success: false,
          error: decision.reason,
        };

        this.log('INFO', `❌ FAIL: ${decision.reason}`);
        return result;
      }

      // RUN_SKILL
      if (decision.type === 'RUN_SKILL') {
        if (!decision.skillName) {
          turnRecord.status = 'FAILED';
          turnRecord.error = 'RUN_SKILL但未提供skillName';
          turnRecord.endedAt = Date.now();
          turns.push(turnRecord);
          break;
        }

        // 安全校验
        const validation = registry.validateSkillCallable(decision.skillName, {
          mode: ctx.mode,
          taskType: ctx.taskType,
          allowHighRisk: false,
        });

        if (!validation.ok) {
          turnRecord.status = 'FAILED';
          turnRecord.error = `技能不可用: ${validation.reason}`;
          turnRecord.endedAt = Date.now();
          turns.push(turnRecord);
          break;
        }

        this.log('INFO', `🔧 执行: ${decision.skillName}`);

        // 执行技能
        const skillStart = Date.now();
        turnRecord.status = 'RUNNING';
        turns.push(turnRecord);

        try {
          const timeoutMs = validation.meta?.execution?.defaultTimeoutMs ?? this.defaultSkillTimeoutMs;
          const skillResult = await skillRunner.run(decision.skillName, decision.skillInput ?? {}, { timeoutMs });

          turnRecord.status = 'OBSERVING';
          turnRecord.skillResult = {
            runId: `run-${turn}`,
            skillName: decision.skillName,
            status: 'SUCCESS',
            output: skillResult.output,
            startedAt: skillStart,
            endedAt: Date.now(),
            durationMs: skillResult.durationMs,
          };
          turnRecord.summary = `技能${decision.skillName}执行成功`;

          this.log('INFO', `✅ ${decision.skillName} 成功，耗时 ${skillResult.durationMs}ms`);

        } catch (e: any) {
          const isTimeout = e.message?.includes('timeout') || e.message?.includes('Timeout');
          turnRecord.status = 'FAILED';
          turnRecord.skillResult = {
            runId: `run-${turn}`,
            skillName: decision.skillName,
            status: isTimeout ? 'TIMEOUT' : 'FAILED',
            error: e.message,
            startedAt: skillStart,
            endedAt: Date.now(),
            durationMs: Date.now() - skillStart,
            timedOut: isTimeout,
          };
          turnRecord.error = e.message;

          this.log('WARN', `⚠️ ${decision.skillName} 失败: ${e.message}`);
        }

        turnRecord.endedAt = Date.now();
        // 更新turnRecord
        turns[turns.length - 1] = turnRecord;
      }
    }

    // 达到最大回合
    const failDecision: PlannerDecision = {
      type: 'FAIL',
      reason: `达到最大回合数 ${this.maxTurns}`,
    };

    return {
      runId: ctx.runId,
      finalDecision: failDecision,
      turns,
      totalDurationMs: Date.now() - startTime,
      success: false,
      error: 'max_turns_exceeded',
    };
  }

  private log(level: LogLevel, message: string): void {
    const ts = new Date().toISOString();
    console.log(`[${ts}] [${this.logPrefix}] [${level}] ${message}`);
  }
}
