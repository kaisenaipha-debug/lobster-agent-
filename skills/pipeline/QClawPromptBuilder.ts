/**
 * QClawPromptBuilder.ts - Prompt构建器
 * 
 * 来源：QClaw官方架构
 * 用途：将SkillRegistry查询结果 + 记忆 + 观察 → LLM可解析的Prompt
 * 依赖：QClawSkillRegistry.ts, QClawPromptBuilder.ts
 */

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

// ===================== 类型定义 =====================

export type PromptMemoryType =
  | 'USER'
  | 'PLAN'
  | 'ACTION'
  | 'OBSERVATION'
  | 'RESULT'
  | 'ERROR'
  | 'SYSTEM';

export interface PromptMemoryItem {
  turn: number;
  type: PromptMemoryType;
  content: string;
  data?: unknown;
  timestamp: number;
}

export interface PromptSkillView {
  name: string;
  displayName?: string;
  description?: string;
  tags?: string[];
  category?: string;
  riskLevel?: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  permissions?: string[];
  plannerEnabled?: boolean;
  manualCallable?: boolean;
  defaultTimeoutMs?: number;
  notes?: string;
}

export interface PromptObservation {
  title?: string;
  url?: string;
  textSnippet?: string;
  structuredData?: unknown;
  timestamp?: number;
}

export interface PromptTaskInput {
  taskType?: string;
  userGoal: string;
  payload?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface PromptTurnRecord {
  turn: number;
  status: 'PLANNING' | 'EXECUTING' | 'OBSERVING' | 'DONE' | 'FAILED' | 'CANCELLED';
  chosenSkill?: string;
  chosenInput?: unknown;
  skillResult?: {
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
  };
  summary?: string;
  error?: string;
  startedAt: number;
  endedAt?: number;
}

export interface PromptBuilderContext {
  runId: string;
  mode?: string;
  task: PromptTaskInput;
  turn: number;
  maxTurns: number;
  memory: PromptMemoryItem[];
  turns: PromptTurnRecord[];
  availableSkills: PromptSkillView[];
  observations?: PromptObservation[];
  systemStyle?: string;
  plannerPolicyText?: string;
  extraInstructions?: string[];
}

export interface PromptBuildResult {
  systemPrompt: string;
  userPrompt: string;
  combinedPrompt: string;
  debug: {
    memoryCount: number;
    skillCount: number;
    observationCount: number;
    turnCount: number;
  };
}

export interface QClawPromptBuilderOptions {
  logPrefix?: string;
  maxMemoryItems?: number;
  maxObservations?: number;
  maxSkills?: number;
  maxMemoryContentLength?: number;
  maxObservationSnippetLength?: number;
  includeTurnSummary?: boolean;
  strictJsonOutput?: boolean;
  defaultSystemStyle?: string;
}

// ===================== 核心类 =====================

export class QClawPromptBuilder {
  private readonly logPrefix: string;
  private readonly maxMemoryItems: number;
  private readonly maxObservations: number;
  private readonly maxSkills: number;
  private readonly maxMemoryContentLength: number;
  private readonly maxObservationSnippetLength: number;
  private readonly includeTurnSummary: boolean;
  private readonly strictJsonOutput: boolean;
  private readonly defaultSystemStyle: string;

  constructor(options: QClawPromptBuilderOptions = {}) {
    this.logPrefix = options.logPrefix ?? 'QCLAW_PROMPT_BUILDER';
    this.maxMemoryItems = Math.max(1, options.maxMemoryItems ?? 12);
    this.maxObservations = Math.max(0, options.maxObservations ?? 5);
    this.maxSkills = Math.max(1, options.maxSkills ?? 20);
    this.maxMemoryContentLength = Math.max(60, options.maxMemoryContentLength ?? 300);
    this.maxObservationSnippetLength = Math.max(60, options.maxObservationSnippetLength ?? 500);
    this.includeTurnSummary = options.includeTurnSummary ?? true;
    this.strictJsonOutput = options.strictJsonOutput ?? true;
    this.defaultSystemStyle =
      options.defaultSystemStyle ??
      '你是小龙虾的规划大脑。你的职责是根据目标、记忆、观察和可用技能，做出稳健、简洁、可执行的下一步决策。优先选择低风险、低副作用、最直接达成目标的动作。';
  }

  public build(ctx: PromptBuilderContext): PromptBuildResult {
    const safeMemory = this.pickMemory(ctx.memory);
    const safeSkills = this.pickSkills(ctx.availableSkills);
    const safeObs = this.pickObservations(ctx.observations ?? []);
    const turnSummary = this.includeTurnSummary ? this.buildTurnSummary(ctx.turns) : '';

    const systemPrompt = this.buildSystemPrompt(ctx);
    const userPrompt = this.buildUserPrompt({
      ...ctx,
      memory: safeMemory,
      availableSkills: safeSkills,
      observations: safeObs,
      turns: ctx.turns,
    }, turnSummary);

    const combinedPrompt = `${systemPrompt}\n\n${userPrompt}`;

    const result: PromptBuildResult = {
      systemPrompt,
      userPrompt,
      combinedPrompt,
      debug: {
        memoryCount: safeMemory.length,
        skillCount: safeSkills.length,
        observationCount: safeObs.length,
        turnCount: ctx.turns.length,
      },
    };

    this.log('INFO',
      `build prompt runId=${ctx.runId} turn=${ctx.turn} memory=${result.debug.memoryCount} skills=${result.debug.skillCount} obs=${result.debug.observationCount}`
    );

    return result;
  }

  public buildMessages(ctx: PromptBuilderContext): Array<{ role: 'system' | 'user'; content: string }> {
    const built = this.build(ctx);
    return [
      { role: 'system', content: built.systemPrompt },
      { role: 'user', content: built.userPrompt },
    ];
  }

  // ===================== 构建系统Prompt =====================

  private buildSystemPrompt(ctx: PromptBuilderContext): string {
    const style = (ctx.systemStyle || this.defaultSystemStyle).trim();
    const modeText = ctx.mode?.trim() ? `当前模式：${ctx.mode?.trim()}` : '当前模式：未指定';

    const policyLines = [
      style,
      modeText,
      '你的任务不是直接长篇解释，而是给出下一步决策。',
      '你必须基于当前可用技能做选择，不能虚构不存在的技能。',
      '优先低风险技能，除非高风险技能是唯一合理路径。',
      '如果目标已经完成，应明确选择 FINISH。',
      '如果没有合理下一步，应明确选择 FAIL，并说明原因。',
      '如果上一步技能已经成功且结果足以完成目标，优先 FINISH。',
    ];

    if (ctx.plannerPolicyText?.trim()) {
      policyLines.push(`附加策略：${ctx.plannerPolicyText.trim()}`);
    }

    if (this.strictJsonOutput) {
      policyLines.push(
        '你的输出必须是严格 JSON，不要输出 JSON 之外的解释、前后缀、markdown、代码块。'
      );
    }

    return policyLines.join('\n');
  }

  // ===================== 构建用户Prompt =====================

  private buildUserPrompt(
    ctx: PromptBuilderContext & {
      memory: PromptMemoryItem[];
      availableSkills: PromptSkillView[];
      observations: PromptObservation[];
      turns: PromptTurnRecord[];
    },
    turnSummary: string
  ): string {
    const sections: string[] = [];

    // 任务上下文
    sections.push('## 任务上下文');
    sections.push(`runId: ${ctx.runId}`);
    sections.push(`currentTurn: ${ctx.turn}`);
    sections.push(`maxTurns: ${ctx.maxTurns}`);
    sections.push(`taskType: ${ctx.task.taskType ?? 'unspecified'}`);
    sections.push(`userGoal: ${ctx.task.userGoal}`);

    if (ctx.task.payload && Object.keys(ctx.task.payload).length > 0) {
      sections.push(`payload: ${this.safeJson(ctx.task.payload)}`);
    }

    if (ctx.task.metadata && Object.keys(ctx.task.metadata).length > 0) {
      sections.push(`metadata: ${this.safeJson(ctx.task.metadata)}`);
    }

    // 历史回合摘要
    if (turnSummary) {
      sections.push('\n## 最近回合摘要');
      sections.push(turnSummary);
    }

    // 可用技能
    sections.push('\n## 可用技能');
    sections.push(this.formatSkills(ctx.availableSkills));

    // 最近观察
    if (ctx.observations.length > 0) {
      sections.push('\n## 最近观察');
      sections.push(this.formatObservations(ctx.observations));
    }

    // 最近记忆
    if (ctx.memory.length > 0) {
      sections.push('\n## 最近记忆');
      sections.push(this.formatMemory(ctx.memory));
    }

    // 附加指令
    if (ctx.extraInstructions?.length) {
      sections.push('\n## 附加指令');
      for (const line of ctx.extraInstructions.filter(Boolean)) {
        sections.push(`- ${line}`);
      }
    }

    // 输出任务
    sections.push('\n## 你的输出任务');
    sections.push('请根据以上上下文，输出下一步 PlannerDecision。');
    sections.push('你只能输出以下三种类型之一：RUN_SKILL / FINISH / FAIL。');

    // JSON格式说明
    if (this.strictJsonOutput) {
      sections.push('\n## 输出 JSON 格式');
      sections.push(
        [
          '{',
          '  "type": "RUN_SKILL | FINISH | FAIL",',
          '  "reason": "string",',
          '  "skillName": "string | optional",',
          '  "skillInput": "object | optional",',
          '  "finalText": "string | optional"',
          '}',
        ].join('\n')
      );

      sections.push('\n## 输出规则');
      sections.push('- RUN_SKILL 时必须提供 skillName。');
      sections.push('- skillName 必须来自"可用技能"列表。');
      sections.push('- FINISH 时可提供 finalText。');
      sections.push('- FAIL 时必须说明 reason。');
      sections.push('- 不要输出不存在的字段。');
    }

    return sections.join('\n');
  }

  // ===================== 格式化辅助 =====================

  private buildTurnSummary(turns: PromptTurnRecord[]): string {
    if (!turns.length) return '无历史回合。';

    const latest = turns.slice(-3);
    return latest
      .map((t) => {
        const parts = [`turn=${t.turn}`, `status=${t.status}`];
        if (t.chosenSkill) parts.push(`skill=${t.chosenSkill}`);
        if (t.skillResult?.status) parts.push(`skillStatus=${t.skillResult.status}`);
        if (t.summary) parts.push(`summary=${this.truncate(t.summary, 160)}`);
        if (t.error) parts.push(`error=${this.truncate(t.error, 160)}`);
        return `- ${parts.join(' | ')}`;
      })
      .join('\n');
  }

  private formatSkills(skills: PromptSkillView[]): string {
    if (!skills.length) return '无可用技能。';

    return skills
      .map((s, idx) => {
        const parts = [`${idx + 1}. name=${s.name}`];
        if (s.displayName) parts.push(`displayName=${s.displayName}`);
        if (s.category) parts.push(`category=${s.category}`);
        if (s.riskLevel) parts.push(`risk=${s.riskLevel}`);
        if (s.description) parts.push(`desc=${this.truncate(s.description, 180)}`);
        if (s.tags?.length) parts.push(`tags=${s.tags.join(',')}`);
        if (s.permissions?.length) parts.push(`permissions=${s.permissions.join(',')}`);
        if (s.defaultTimeoutMs) parts.push(`timeoutMs=${s.defaultTimeoutMs}`);
        return `- ${parts.join(' | ')}`;
      })
      .join('\n');
  }

  private formatObservations(observations: PromptObservation[]): string {
    if (!observations.length) return '无观察。';

    return observations
      .map((o, idx) => {
        const parts: string[] = [`${idx + 1}.`];
        if (o.title) parts.push(`title=${this.truncate(o.title, 120)}`);
        if (o.url) parts.push(`url=${this.truncate(o.url, 200)}`);
        if (o.textSnippet) parts.push(`snippet=${this.truncate(o.textSnippet, this.maxObservationSnippetLength)}`);
        if (o.structuredData != null) parts.push(`data=${this.truncate(this.safeJson(o.structuredData), 220)}`);
        return `- ${parts.join(' | ')}`;
      })
      .join('\n');
  }

  private formatMemory(memory: PromptMemoryItem[]): string {
    if (!memory.length) return '无记忆。';

    return memory
      .map((m) => {
        const content = this.truncate(m.content, this.maxMemoryContentLength);
        return `- turn=${m.turn} | type=${m.type} | content=${content}`;
      })
      .join('\n');
  }

  // ===================== 裁剪逻辑 =====================

  private pickMemory(memory: PromptMemoryItem[]): PromptMemoryItem[] {
    return memory
      .slice(-this.maxMemoryItems)
      .map((m) => ({
        ...m,
        content: this.truncate(m.content, this.maxMemoryContentLength),
      }));
  }

  private pickSkills(skills: PromptSkillView[]): PromptSkillView[] {
    return skills.slice(0, this.maxSkills);
  }

  private pickObservations(observations: PromptObservation[]): PromptObservation[] {
    return observations
      .slice(-this.maxObservations)
      .map((o) => ({
        ...o,
        title: o.title ? this.truncate(o.title, 120) : o.title,
        url: o.url ? this.truncate(o.url, 200) : o.url,
        textSnippet: o.textSnippet
          ? this.truncate(o.textSnippet, this.maxObservationSnippetLength)
          : o.textSnippet,
      }));
  }

  private truncate(text: string, max: number): string {
    if (!text) return text;
    if (text.length <= max) return text;
    return `${text.slice(0, max)}...`;
  }

  private safeJson(value: unknown): string {
    try {
      return JSON.stringify(value);
    } catch {
      return '[unserializable]';
    }
  }

  private log(level: LogLevel, message: string): void {
    const ts = new Date().toISOString();
    console.log(`[${ts}] [${this.logPrefix}] [${level}] ${message}`);
  }
}

// ===================== 辅助函数 =====================

export function buildPlannerPromptInput(params: {
  runId: string;
  mode?: string;
  task: PromptTaskInput;
  turn: number;
  maxTurns: number;
  memory: PromptMemoryItem[];
  turns: PromptTurnRecord[];
  availableSkills: PromptSkillView[];
  observations?: PromptObservation[];
  extraInstructions?: string[];
}): PromptBuilderContext {
  return {
    runId: params.runId,
    mode: params.mode,
    task: params.task,
    turn: params.turn,
    maxTurns: params.maxTurns,
    memory: params.memory,
    turns: params.turns,
    availableSkills: params.availableSkills,
    observations: params.observations ?? [],
    extraInstructions: params.extraInstructions ?? [],
  };
}
