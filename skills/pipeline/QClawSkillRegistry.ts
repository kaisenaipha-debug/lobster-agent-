/**
 * QClawSkillRegistry.ts - Skill元数据中心 v2.0
 * 
 * 来源：QClaw官方架构
 * 用途：技能注册/查询/过滤/安全校验
 * 依赖：TypeScript 6 + Node.js
 * 
 * 与旧版capability_registry.json的差异：
 * - 新增RiskLevel/Permission/Domain分类
 * - 新增Exposure策略（mode/taskType过滤）
 * - 新增Guardrails（确认/关键词/域名拦截）
 * - 新增Alias映射
 * - 新增inputSchema/outputSchema
 * - validateSkillCallable安全校验
 * - getAvailableSkills智能过滤
 */

type LogLevel = 'DEBUG' | 'INFO' | 'WARN' | 'ERROR';

// ===================== 类型定义 =====================

export type SkillRiskLevel = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
export type SkillStatus = 'ENABLED' | 'DISABLED' | 'DEPRECATED' | 'EXPERIMENTAL';

export type SkillPermission =
  | 'BROWSER_READ'
  | 'BROWSER_WRITE'
  | 'PAGE_NAVIGATION'
  | 'FORM_INPUT'
  | 'CLICK'
  | 'DOWNLOAD'
  | 'SCREENSHOT'
  | 'NETWORK_EXTERNAL'
  | 'SYSTEM_INTERNAL';

export type SkillDomain =
  | 'SEARCH'
  | 'BROWSE'
  | 'EXTRACTION'
  | 'NAVIGATION'
  | 'FORM'
  | 'AUTH'
  | 'DOWNLOAD'
  | 'SYSTEM'
  | 'CUSTOM';

export interface SkillJsonSchema {
  type?: 'object' | 'string' | 'number' | 'boolean' | 'array' | 'null';
  required?: string[];
  properties?: Record<string, unknown>;
  items?: unknown;
  enum?: unknown[];
  description?: string;
  additionalProperties?: boolean;
}

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

export interface SkillGuardrails {
  allowPlannerAutoSelect?: boolean;
  allowManualCall?: boolean;
  allowHighRiskContext?: boolean;
  requiresConfirmation?: boolean;
  requireSafeModeOff?: boolean;
  forbiddenKeywords?: string[];
  forbiddenDomains?: string[];
}

export interface SkillExposurePolicy {
  allowModes?: string[];
  blockModes?: string[];
  allowTaskTypes?: string[];
  blockTaskTypes?: string[];
  allowDomains?: string[];
  blockDomains?: string[];
  hiddenFromPlanner?: boolean;
  hiddenFromUI?: boolean;
}

export interface SkillCapabilityFlags {
  readOnly?: boolean;
  mutatesPage?: boolean;
  mutatesRemoteState?: boolean;
  needsLoginState?: boolean;
  needsNetwork?: boolean;
  producesStructuredOutput?: boolean;
}

export interface RegisteredSkillMetaV2 {
  name: string;
  version?: string;
  aliases?: string[];
  displayName?: string;
  description?: string;
  notes?: string;
  tags?: string[];
  category?: string;
  domains?: SkillDomain[];
  riskLevel?: SkillRiskLevel;
  status?: SkillStatus;
  permissions?: SkillPermission[];
  capabilities?: SkillCapabilityFlags;
  inputSchema?: SkillJsonSchema;
  outputSchema?: SkillJsonSchema;
  execution?: SkillExecutionPolicy;
  exposure?: SkillExposurePolicy;
  guardrails?: SkillGuardrails;
}

interface RequiredCoreSkillMetaV2 {
  name: string;
  version: string;
  aliases: string[];
  tags: string[];
  domains: SkillDomain[];
  riskLevel: SkillRiskLevel;
  status: SkillStatus;
  permissions: SkillPermission[];
  capabilities: SkillCapabilityFlags;
  execution: SkillExecutionPolicy;
  exposure: SkillExposurePolicy;
  guardrails: SkillGuardrails;
}

interface RegisteredSkillEntryV2 {
  meta: RegisteredSkillMetaV2 & RequiredCoreSkillMetaV2;
  createdAt: number;
  updatedAt: number;
}

export interface SkillRegistryFilterV2 {
  names?: string[];
  aliases?: string[];
  tags?: string[];
  category?: string;
  domains?: SkillDomain[];
  riskLevels?: SkillRiskLevel[];
  statuses?: SkillStatus[];
  permissionsAny?: SkillPermission[];
  permissionsAll?: SkillPermission[];
  mode?: string;
  taskType?: string;
  plannerVisible?: boolean;
  uiVisible?: boolean;
  manualCallable?: boolean;
  plannerCallable?: boolean;
  keyword?: string;
}

export interface SkillSelectionContextV2 {
  mode?: string;
  taskType?: string;
  currentDomain?: string;
  allowHighRisk?: boolean;
  requirePlannerCallable?: boolean;
  requireManualCallable?: boolean;
  includeExperimental?: boolean;
  includeDeprecated?: boolean;
  allowedNames?: string[];
  blockedNames?: string[];
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
  status: SkillStatus;
  permissions: SkillPermission[];
  capabilities: SkillCapabilityFlags;
  execution: SkillExecutionPolicy;
  plannerCallable: boolean;
  manualCallable: boolean;
  plannerVisible: boolean;
  uiVisible: boolean;
  notes?: string;
}

export interface SkillRegistrySnapshotV2 {
  registryVersion: string;
  count: number;
  exportedAt: number;
  skills: SkillPublicViewV2[];
}

// ===================== 核心类 =====================

export class QClawSkillRegistry {
  private readonly logPrefix: string;
  private readonly registryVersion: string;
  private readonly entries = new Map<string, RegisteredSkillEntryV2>();
  private readonly aliasToName = new Map<string, string>();

  constructor(options?: { logPrefix?: string; registryVersion?: string }) {
    this.logPrefix = options?.logPrefix ?? 'QCLAW_SKILL_REGISTRY_V2';
    this.registryVersion = options?.registryVersion ?? '2.0.0';
  }

  // ===================== 注册接口 =====================

  public register(meta: RegisteredSkillMetaV2): void {
    const normalized = this.normalizeMeta(meta);
    const now = Date.now();
    const existing = this.entries.get(normalized.name);

    if (existing) {
      this.clearAliasIndex(existing.meta);
      const merged = this.normalizeMeta({
        ...existing.meta,
        ...normalized,
        name: normalized.name,
      });
      this.entries.set(normalized.name, {
        meta: merged,
        createdAt: existing.createdAt,
        updatedAt: now,
      });
      this.indexAliases(merged);
      this.log('INFO', `update skill name=${normalized.name} version=${merged.version}`);
      return;
    }

    this.entries.set(normalized.name, {
      meta: normalized,
      createdAt: now,
      updatedAt: now,
    });
    this.indexAliases(normalized);
    this.log('INFO', `register skill name=${normalized.name} version=${normalized.version}`);
  }

  public registerMany(list: RegisteredSkillMetaV2[]): void {
    for (const item of list) {
      this.register(item);
    }
  }

  public unregister(nameOrAlias: string): boolean {
    const resolved = this.resolveName(nameOrAlias);
    if (!resolved) return false;
    const entry = this.entries.get(resolved);
    if (!entry) return false;
    this.clearAliasIndex(entry.meta);
    const ok = this.entries.delete(resolved);
    if (ok) this.log('INFO', `unregister skill name=${resolved}`);
    return ok;
  }

  // ===================== 查询接口 =====================

  public has(nameOrAlias: string): boolean {
    return !!this.resolveName(nameOrAlias);
  }

  public get(nameOrAlias: string): RegisteredSkillEntryV2 | null {
    const resolved = this.resolveName(nameOrAlias);
    if (!resolved) return null;
    return this.entries.get(resolved) ?? null;
  }

  public getMeta(nameOrAlias: string): (RegisteredSkillMetaV2 & RequiredCoreSkillMetaV2) | null {
    return this.get(nameOrAlias)?.meta ?? null;
  }

  public resolveName(nameOrAlias: string): string | null {
    const key = nameOrAlias.trim();
    if (!key) return null;
    if (this.entries.has(key)) return key;
    return this.aliasToName.get(key) ?? null;
  }

  public setStatus(nameOrAlias: string, status: SkillStatus): boolean {
    const entry = this.get(nameOrAlias);
    if (!entry) return false;
    entry.meta.status = status;
    entry.updatedAt = Date.now();
    this.log('INFO', `setStatus name=${entry.meta.name} status=${status}`);
    return true;
  }

  public enable(nameOrAlias: string): boolean {
    return this.setStatus(nameOrAlias, 'ENABLED');
  }

  public disable(nameOrAlias: string): boolean {
    return this.setStatus(nameOrAlias, 'DISABLED');
  }

  public deprecate(nameOrAlias: string): boolean {
    return this.setStatus(nameOrAlias, 'DEPRECATED');
  }

  public updateMeta(nameOrAlias: string, patch: Partial<RegisteredSkillMetaV2>): boolean {
    const resolved = this.resolveName(nameOrAlias);
    if (!resolved) return false;
    const entry = this.entries.get(resolved);
    if (!entry) return false;
    this.clearAliasIndex(entry.meta);
    const merged = this.normalizeMeta({ ...entry.meta, ...patch, name: entry.meta.name });
    entry.meta = merged;
    entry.updatedAt = Date.now();
    this.indexAliases(merged);
    this.log('INFO', `updateMeta name=${resolved}`);
    return true;
  }

  public list(): RegisteredSkillEntryV2[] {
    return Array.from(this.entries.values()).sort((a, b) =>
      a.meta.name.localeCompare(b.meta.name)
    );
  }

  public listNames(): string[] {
    return this.list().map((x) => x.meta.name);
  }

  public find(filter?: SkillRegistryFilterV2): RegisteredSkillEntryV2[] {
    const all = this.list();
    if (!filter) return all;
    return all.filter((entry) => this.matchesFilter(entry, filter!));
  }

  public listPublicViews(filter?: SkillRegistryFilterV2): SkillPublicViewV2[] {
    return this.find(filter).map((entry) => this.toPublicView(entry.meta));
  }

  // ===================== 核心过滤接口 =====================

  public getAvailableSkills(ctx?: SkillSelectionContextV2): SkillPublicViewV2[] {
    const allowHighRisk = ctx?.allowHighRisk ?? false;
    const includeExperimental = ctx?.includeExperimental ?? false;
    const includeDeprecated = ctx?.includeDeprecated ?? false;
    const allowedNames = ctx?.allowedNames?.length ? new Set(ctx.allowedNames) : null;
    const blockedNames = new Set(ctx?.blockedNames ?? []);

    return this.list()
      .map((x) => x.meta)
      .filter((meta) => meta.status !== 'DISABLED')
      .filter((meta) => includeDeprecated || meta.status !== 'DEPRECATED')
      .filter((meta) => includeExperimental || meta.status !== 'EXPERIMENTAL')
      .filter((meta) => !blockedNames.has(meta.name))
      .filter((meta) => !allowedNames || allowedNames.has(meta.name))
      .filter((meta) => allowHighRisk || (meta.riskLevel !== 'HIGH' && meta.riskLevel !== 'CRITICAL'))
      .filter((meta) => this.matchesExposure(meta, ctx))
      .filter((meta) => this.matchesCallableRequirements(meta, ctx))
      .map((meta) => this.toPublicView(meta))
      .sort((a, b) => a.name.localeCompare(b.name));
  }

  public getPlannerSkillNames(ctx?: SkillSelectionContextV2): string[] {
    return this.getAvailableSkills({ ...ctx, requirePlannerCallable: true }).map((x) => x.name);
  }

  public getManualCallableSkillNames(ctx?: SkillSelectionContextV2): string[] {
    return this.getAvailableSkills({ ...ctx, requireManualCallable: true }).map((x) => x.name);
  }

  // ===================== 安全校验 =====================

  public validateSkillCallable(
    nameOrAlias: string,
    ctx?: SkillSelectionContextV2
  ): { ok: boolean; reason?: string; meta?: SkillPublicViewV2 } {
    const entry = this.get(nameOrAlias);
    if (!entry) return { ok: false, reason: `skill not found: ${nameOrAlias}` };

    const meta = entry.meta;

    if (meta.status === 'DISABLED') return { ok: false, reason: `skill disabled: ${meta.name}` };
    if (!(ctx?.includeDeprecated ?? false) && meta.status === 'DEPRECATED')
      return { ok: false, reason: `skill deprecated: ${meta.name}` };
    if (!(ctx?.includeExperimental ?? false) && meta.status === 'EXPERIMENTAL')
      return { ok: false, reason: `skill experimental: ${meta.name}` };
    if (!(ctx?.allowHighRisk ?? false) && (meta.riskLevel === 'HIGH' || meta.riskLevel === 'CRITICAL'))
      return { ok: false, reason: `skill risk too high: ${meta.name}` };
    if (!this.matchesExposure(meta, ctx))
      return { ok: false, reason: `skill exposure mismatch: ${meta.name}` };
    if (!this.matchesCallableRequirements(meta, ctx))
      return { ok: false, reason: `skill callable policy mismatch: ${meta.name}` };
    if (ctx?.blockedNames?.includes(meta.name))
      return { ok: false, reason: `skill blocked by name: ${meta.name}` };
    if (ctx?.allowedNames?.length && !ctx.allowedNames.includes(meta.name))
      return { ok: false, reason: `skill not in allowedNames: ${meta.name}` };

    return { ok: true, meta: this.toPublicView(meta) };
  }

  public exportSnapshot(filter?: SkillRegistryFilterV2): SkillRegistrySnapshotV2 {
    const skills = this.listPublicViews(filter);
    return {
      registryVersion: this.registryVersion,
      count: skills.length,
      exportedAt: Date.now(),
      skills,
    };
  }

  // ===================== 私有方法 =====================

  private matchesFilter(entry: RegisteredSkillEntryV2, filter: SkillRegistryFilterV2): boolean {
    const meta = entry.meta;
    const text = [
      meta.name,
      ...meta.aliases,
      meta.displayName ?? '',
      meta.description ?? '',
      meta.notes ?? '',
      ...(meta.tags ?? []),
      ...(meta.domains ?? []),
      ...(meta.permissions ?? []),
    ].join(' ').toLowerCase();

    if (filter.names?.length && !filter.names.includes(meta.name)) return false;
    if (filter.aliases?.length && !filter.aliases.some((a) => meta.aliases.includes(a))) return false;
    if (filter.tags?.length && !filter.tags.some((t) => meta.tags.includes(t))) return false;
    if (filter.category && meta.category !== filter.category) return false;
    if (filter.domains?.length && !filter.domains.some((d) => meta.domains.includes(d))) return false;
    if (filter.riskLevels?.length && !filter.riskLevels.includes(meta.riskLevel)) return false;
    if (filter.statuses?.length && !filter.statuses.includes(meta.status)) return false;
    if (filter.permissionsAny?.length && !filter.permissionsAny.some((p) => meta.permissions.includes(p))) return false;
    if (filter.permissionsAll?.length && !filter.permissionsAll.every((p) => meta.permissions.includes(p))) return false;
    if (filter.keyword?.trim() && !text.includes(filter.keyword.trim().toLowerCase())) return false;
    if (!this.matchesExposure(meta, { mode: filter.mode, taskType: filter.taskType })) return false;
    return true;
  }

  private matchesExposure(
    meta: RegisteredSkillMetaV2 & RequiredCoreSkillMetaV2,
    ctx?: Pick<SkillSelectionContextV2, 'mode' | 'taskType' | 'currentDomain'>
  ): boolean {
    const exp = meta.exposure;
    if (!exp) return true;
    const mode = ctx?.mode?.trim();
    const taskType = ctx?.taskType?.trim();
    const currentDomain = ctx?.currentDomain?.trim();
    if (mode) {
      if (exp.blockModes?.includes(mode)) return false;
      if (exp.allowModes?.length && !exp.allowModes.includes(mode)) return false;
    }
    if (taskType) {
      if (exp.blockTaskTypes?.includes(taskType)) return false;
      if (exp.allowTaskTypes?.length && !exp.allowTaskTypes.includes(taskType)) return false;
    }
    if (currentDomain) {
      if (exp.blockDomains?.includes(currentDomain)) return false;
      if (exp.allowDomains?.length && !exp.allowDomains.includes(currentDomain)) return false;
    }
    return true;
  }

  private matchesCallableRequirements(
    meta: RegisteredSkillMetaV2 & RequiredCoreSkillMetaV2,
    ctx?: SkillSelectionContextV2
  ): boolean {
    if (ctx?.requirePlannerCallable && !meta.guardrails.allowPlannerAutoSelect) return false;
    if (ctx?.requireManualCallable && !meta.guardrails.allowManualCall) return false;
    return true;
  }

  private normalizeMeta(meta: RegisteredSkillMetaV2): RegisteredSkillMetaV2 & RequiredCoreSkillMetaV2 {
    const name = meta.name?.trim();
    if (!name) throw new Error('skill meta.name is required');

    const aliases = this.normalizeStringArray(meta.aliases).filter((x) => x !== name);
    const tags = this.normalizeStringArray(meta.tags);
    const domains = this.normalizeDomains(meta.domains);
    const permissions = this.normalizePermissions(meta.permissions);

    return {
      ...meta,
      name,
      version: meta.version?.trim() || '1.0.0',
      aliases,
      displayName: meta.displayName?.trim(),
      description: meta.description?.trim(),
      notes: meta.notes?.trim(),
      tags,
      category: meta.category?.trim(),
      domains,
      riskLevel: meta.riskLevel ?? 'LOW',
      status: meta.status ?? 'ENABLED',
      permissions,
      capabilities: {
        readOnly: meta.capabilities?.readOnly ?? false,
        mutatesPage: meta.capabilities?.mutatesPage ?? false,
        mutatesRemoteState: meta.capabilities?.mutatesRemoteState ?? false,
        needsLoginState: meta.capabilities?.needsLoginState ?? false,
        needsNetwork: meta.capabilities?.needsNetwork ?? true,
        producesStructuredOutput: meta.capabilities?.producesStructuredOutput ?? false,
      },
      inputSchema: meta.inputSchema,
      outputSchema: meta.outputSchema,
      execution: {
        defaultTimeoutMs: meta.execution?.defaultTimeoutMs ?? 20_000,
        maxTimeoutMs: meta.execution?.maxTimeoutMs ?? 120_000,
        retryable: meta.execution?.retryable ?? false,
        maxRetries: meta.execution?.maxRetries ?? 0,
        queueGroup: meta.execution?.queueGroup?.trim(),
        exclusive: meta.execution?.exclusive ?? false,
        pageReusePreferred: meta.execution?.pageReusePreferred ?? true,
        pagePoolRequired: meta.execution?.pagePoolRequired ?? false,
        idempotent: meta.execution?.idempotent ?? false,
      },
      exposure: {
        allowModes: this.normalizeStringArray(meta.exposure?.allowModes),
        blockModes: this.normalizeStringArray(meta.exposure?.blockModes),
        allowTaskTypes: this.normalizeStringArray(meta.exposure?.allowTaskTypes),
        blockTaskTypes: this.normalizeStringArray(meta.exposure?.blockTaskTypes),
        allowDomains: this.normalizeStringArray(meta.exposure?.allowDomains),
        blockDomains: this.normalizeStringArray(meta.exposure?.blockDomains),
        hiddenFromPlanner: meta.exposure?.hiddenFromPlanner ?? false,
        hiddenFromUI: meta.exposure?.hiddenFromUI ?? false,
      },
      guardrails: {
        allowPlannerAutoSelect: meta.guardrails?.allowPlannerAutoSelect ?? true,
        allowManualCall: meta.guardrails?.allowManualCall ?? true,
        allowHighRiskContext: meta.guardrails?.allowHighRiskContext ?? false,
        requiresConfirmation: meta.guardrails?.requiresConfirmation ?? false,
        requireSafeModeOff: meta.guardrails?.requireSafeModeOff ?? false,
        forbiddenKeywords: this.normalizeStringArray(meta.guardrails?.forbiddenKeywords),
        forbiddenDomains: this.normalizeStringArray(meta.guardrails?.forbiddenDomains),
      },
    };
  }

  private normalizeStringArray(arr?: string[]): string[] {
    if (!arr?.length) return [];
    return Array.from(new Set(arr.map((x) => x.trim()).filter(Boolean)));
  }

  private normalizePermissions(arr?: SkillPermission[]): SkillPermission[] {
    if (!arr?.length) return [];
    return Array.from(new Set(arr));
  }

  private normalizeDomains(arr?: SkillDomain[]): SkillDomain[] {
    if (!arr?.length) return [];
    return Array.from(new Set(arr));
  }

  private indexAliases(meta: RegisteredSkillMetaV2 & RequiredCoreSkillMetaV2): void {
    for (const alias of meta.aliases) {
      const existing = this.aliasToName.get(alias);
      if (existing && existing !== meta.name) {
        throw new Error(`alias conflict: ${alias} already points to ${existing}`);
      }
      this.aliasToName.set(alias, meta.name);
    }
  }

  private clearAliasIndex(meta: RegisteredSkillMetaV2 & RequiredCoreSkillMetaV2): void {
    for (const alias of meta.aliases) {
      const existing = this.aliasToName.get(alias);
      if (existing === meta.name) this.aliasToName.delete(alias);
    }
  }

  private toPublicView(meta: RegisteredSkillMetaV2 & RequiredCoreSkillMetaV2): SkillPublicViewV2 {
    return {
      name: meta.name,
      version: meta.version,
      aliases: meta.aliases,
      displayName: meta.displayName,
      description: meta.description,
      tags: meta.tags,
      category: meta.category,
      domains: meta.domains,
      riskLevel: meta.riskLevel,
      status: meta.status,
      permissions: meta.permissions,
      capabilities: meta.capabilities,
      execution: meta.execution,
      plannerCallable: meta.guardrails.allowPlannerAutoSelect && !meta.exposure.hiddenFromPlanner,
      manualCallable: meta.guardrails.allowManualCall,
      plannerVisible: !meta.exposure.hiddenFromPlanner,
      uiVisible: !meta.exposure.hiddenFromUI,
      notes: meta.notes,
    };
  }

  private log(level: LogLevel, message: string): void {
    const ts = new Date().toISOString();
    console.log(`[${ts}] [${this.logPrefix}] [${level}] ${message}`);
  }
}

// ===================== 默认注册表工厂 =====================

export function createDefaultSkillRegistryV2(): QClawSkillRegistry {
  const registry = new QClawSkillRegistry({ registryVersion: '2.0.0' });

  registry.registerMany([
    // ========== 核心系统（CRITICAL）==========
    {
      name: 'lm-operator',
      version: '1.0.0',
      aliases: [],
      displayName: 'LM Operator（铁律执行器）',
      description: '大模型操作安全检查，强制can_send确认和confirm，未通过不得操作',
      tags: ['system', 'security', 'core'],
      category: 'system',
      domains: ['SYSTEM_INTERNAL'],
      riskLevel: 'CRITICAL',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL'],
      capabilities: { readOnly: false, mutatesRemoteState: false, needsNetwork: false, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 5000, maxTimeoutMs: 10_000, idempotent: true },
      exposure: { hiddenFromPlanner: true, hiddenFromUI: false },
      guardrails: { allowPlannerAutoSelect: false, allowManualCall: true, requireSafeModeOff: false },
    },
    {
      name: 'pipeline',
      version: '1.0.0',
      aliases: [],
      displayName: 'Pipeline（核心器官）',
      description: 'agent_loop/browser_control/heartbeat_engine等核心脚本集',
      tags: ['system', 'core', 'orchestration'],
      category: 'system',
      domains: ['SYSTEM_INTERNAL'],
      riskLevel: 'CRITICAL',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL', 'BROWSER_READ', 'BROWSER_WRITE', 'NETWORK_EXTERNAL'],
      capabilities: { readOnly: false, mutatesPage: true, mutatesRemoteState: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 60_000, maxTimeoutMs: 300_000, pageReusePreferred: true },
      exposure: { hiddenFromPlanner: true, hiddenFromUI: false },
      guardrails: { allowPlannerAutoSelect: false, allowManualCall: true },
    },

    // ========== 浏览器操控（MEDIUM）==========
    {
      name: 'chatgpt-gemini-agent',
      version: '1.0.0',
      aliases: ['browser-ai', 'chatgpt-agent'],
      displayName: 'ChatGPT/Gemini浏览器操控',
      description: '拟人化操作ChatGPT/Gemini，支持截图分析、深度研究、多轮对话',
      tags: ['browser', 'ai', 'chatgpt', 'gemini'],
      category: 'browser',
      domains: ['BROWSE', 'NAVIGATION', 'EXTRACTION'],
      riskLevel: 'MEDIUM',
      status: 'ENABLED',
      permissions: ['BROWSER_READ', 'BROWSER_WRITE', 'PAGE_NAVIGATION', 'FORM_INPUT', 'CLICK', 'NETWORK_EXTERNAL'],
      capabilities: { readOnly: false, mutatesPage: true, needsLoginState: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 60_000, maxTimeoutMs: 180_000, retryable: true, maxRetries: 2, pagePoolRequired: true },
      exposure: { blockModes: ['safe-mode'] },
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true, allowHighRiskContext: true },
    },
    {
      name: 'agent-browser',
      version: '1.0.0',
      aliases: [],
      displayName: 'Agent浏览器自动化',
      description: 'Playwright CDP浏览器自动化，支持导航/点击/填表/截图',
      tags: ['browser', 'automation', 'playwright'],
      category: 'browser',
      domains: ['BROWSE', 'NAVIGATION', 'FORM'],
      riskLevel: 'MEDIUM',
      status: 'ENABLED',
      permissions: ['BROWSER_READ', 'BROWSER_WRITE', 'PAGE_NAVIGATION', 'FORM_INPUT', 'CLICK', 'SCREENSHOT'],
      capabilities: { readOnly: false, mutatesPage: true, needsLoginState: false, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 30_000, maxTimeoutMs: 120_000, pageReusePreferred: true, pagePoolRequired: true },
      exposure: { blockModes: ['safe-mode'] },
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },

    // ========== 搜索类（LOW）==========
    {
      name: 'smart-search',
      version: '2.1.0',
      aliases: ['search-plus', 'multi-search'],
      displayName: 'S+级多通道搜索',
      description: '9通道并行搜索：Serper/搜狗微信/CCGP/Boss/猎聘/gov.cn等',
      tags: ['search', 'multi-channel', 'intelligence'],
      category: 'search',
      domains: ['SEARCH', 'EXTRACTION'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['NETWORK_EXTERNAL', 'BROWSER_READ'],
      capabilities: { readOnly: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 30_000, maxTimeoutMs: 60_000, retryable: true, maxRetries: 1, idempotent: true },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
    {
      name: 'x-search',
      version: '1.0.0',
      aliases: ['twitter-search', 'xai-search'],
      displayName: 'X搜索',
      description: '通过xAI API搜索X/Twitter帖子和内容',
      tags: ['search', 'social', 'x', 'twitter'],
      category: 'search',
      domains: ['SEARCH'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['NETWORK_EXTERNAL'],
      capabilities: { readOnly: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 20_000, maxTimeoutMs: 45_000, retryable: true, maxRetries: 1 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },

    // ========== 政府B2G销售（LOW）==========
    {
      name: 'gov-sales-pipeline',
      version: '1.0.0',
      aliases: ['gov-pipeline', 'pipeline-sales'],
      displayName: '政府B2G销售全流程',
      description: '政府B2G销售全流程协调器，整合5个政府销售子技能',
      tags: ['gov', 'sales', 'pipeline', 'b2g'],
      category: 'intelligence',
      domains: ['SEARCH', 'EXTRACTION', 'SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['NETWORK_EXTERNAL', 'BROWSER_READ'],
      capabilities: { readOnly: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 120_000, maxTimeoutMs: 300_000 },
      exposure: { blockModes: ['safe-mode'] },
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
    {
      name: 'gov-intel',
      version: '1.0.0',
      aliases: ['gov-cold-intel', 'government-intel'],
      displayName: '政府冷情报五步搜索',
      description: '政府客户冷启动情报采集：百度/Google/CCGP/企查查/LinkedIn',
      tags: ['gov', 'intelligence', 'research'],
      category: 'intelligence',
      domains: ['SEARCH', 'EXTRACTION'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['NETWORK_EXTERNAL', 'BROWSER_READ'],
      capabilities: { readOnly: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 60_000, maxTimeoutMs: 180_000, retryable: true, maxRetries: 2 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
    {
      name: 'client-stage-tracker',
      version: '1.0.0',
      aliases: ['stage-tracker', 'deal-tracker'],
      displayName: '客户阶段追踪器',
      description: '追踪政府客户采购阶段S0-S5，记录跟进状态和关键事件',
      tags: ['gov', 'sales', 'tracking', 'crm'],
      category: 'intelligence',
      domains: ['SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL'],
      capabilities: { readOnly: false, mutatesRemoteState: true, needsNetwork: false, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 5_000, maxTimeoutMs: 10_000, idempotent: true },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
    {
      name: 'meeting-debrief',
      version: '1.0.0',
      aliases: ['debrief', 'meeting-notes'],
      displayName: '见客复盘',
      description: '记录和分析客户会面要点，提取需求信号和下一步行动',
      tags: ['gov', 'sales', 'notes', 'analysis'],
      category: 'intelligence',
      domains: ['EXTRACTION', 'SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL'],
      capabilities: { readOnly: false, needsNetwork: false, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 10_000, maxTimeoutMs: 30_000, idempotent: true },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
    {
      name: 'weak-signal-monitor',
      version: '1.0.0',
      aliases: ['signal-monitor', 'opportunity-monitor'],
      displayName: '弱信号监控',
      description: '监控政府采购预告、招标公告、竞争动态等弱信号',
      tags: ['gov', 'monitoring', 'signal', 'opportunity'],
      category: 'intelligence',
      domains: ['SEARCH', 'EXTRACTION'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['NETWORK_EXTERNAL', 'BROWSER_READ'],
      capabilities: { readOnly: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 60_000, maxTimeoutMs: 120_000 },
      exposure: { blockModes: ['safe-mode'] },
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },

    // ========== 知识图谱/本体（LOW）==========
    {
      name: 'ontology',
      version: '1.0.0',
      aliases: ['ontology-core'],
      displayName: '知识图谱本体',
      description: '政府B2G知识本体定义：客户/项目/竞争/机会实体及关系',
      tags: ['knowledge', 'ontology', 'graph'],
      category: 'knowledge',
      domains: ['EXTRACTION', 'SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL'],
      capabilities: { readOnly: true, needsNetwork: false, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 5_000, maxTimeoutMs: 15_000 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
    {
      name: 'knowledge-graph-builder',
      version: '1.0.0',
      aliases: ['kg-builder', 'graph-builder'],
      displayName: '知识图谱构建',
      description: '从非结构化文本构建知识图谱实体和关系',
      tags: ['knowledge', 'graph', 'nlp'],
      category: 'knowledge',
      domains: ['EXTRACTION', 'SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL', 'NETWORK_EXTERNAL'],
      capabilities: { readOnly: false, needsNetwork: false, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 30_000, maxTimeoutMs: 90_000 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },

    // ========== 自我进化（LOW）==========
    {
      name: 'self-improving-agent',
      version: '1.0.0',
      aliases: ['self-improving'],
      displayName: '自我改进Agent',
      description: '捕获学习、错误纠正、持续改进，评估工作质量并永久优化',
      tags: ['self-improvement', 'learning', 'memory'],
      category: 'memory',
      domains: ['SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL', 'BROWSER_READ'],
      capabilities: { readOnly: false, mutatesRemoteState: true, needsNetwork: false, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 15_000, maxTimeoutMs: 60_000, idempotent: true },
      exposure: { hiddenFromPlanner: false, hiddenFromUI: false },
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },

    // ========== 社交媒体（LOW）==========
    {
      name: 'social-media-agent',
      version: '1.0.0',
      aliases: ['social-agent'],
      displayName: '社交媒体运营',
      description: 'X发推/评论/点赞/转发，内容浏览总结，竞品监控',
      tags: ['social', 'media', 'twitter', 'content'],
      category: 'social',
      domains: ['BROWSE', 'NAVIGATION', 'FORM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['BROWSER_READ', 'BROWSER_WRITE', 'CLICK', 'NETWORK_EXTERNAL'],
      capabilities: { readOnly: false, mutatesPage: false, needsLoginState: true, needsNetwork: true },
      execution: { defaultTimeoutMs: 30_000, maxTimeoutMs: 90_000, pagePoolRequired: true },
      exposure: { blockModes: ['safe-mode'] },
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true, requiresConfirmation: true },
    },
    {
      name: 'news-monitor',
      version: '1.0.0',
      aliases: [],
      displayName: '新闻监控',
      description: '科技媒体/政府公告RSS监控，弱信号发现',
      tags: ['news', 'monitoring', 'rss'],
      category: 'social',
      domains: ['SEARCH', 'EXTRACTION'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['NETWORK_EXTERNAL', 'BROWSER_READ'],
      capabilities: { readOnly: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 20_000, maxTimeoutMs: 60_000 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },

    // ========== 工作流（MEDIUM）==========
    {
      name: 'n8n-workflow-patterns',
      version: '1.0.0',
      aliases: ['n8n'],
      displayName: 'n8n工作流模式库',
      description: 'n8n自动化工作流模板：微信监控/邮件通知/HTTP请求',
      tags: ['n8n', 'workflow', 'automation'],
      category: 'workflow',
      domains: ['SYSTEM', 'NAVIGATION'],
      riskLevel: 'MEDIUM',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL', 'NETWORK_EXTERNAL', 'BROWSER_READ'],
      capabilities: { readOnly: false, mutatesRemoteState: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 30_000, maxTimeoutMs: 120_000 },
      exposure: { blockModes: ['safe-mode'] },
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },

    // ========== 工具集成（MEDIUM）==========
    {
      name: 'trello',
      version: '1.0.0',
      aliases: [],
      displayName: 'Trello集成',
      description: '管理Trello看板、列表和卡片',
      tags: ['trello', 'integration', 'task'],
      category: 'integration',
      domains: ['SYSTEM'],
      riskLevel: 'MEDIUM',
      status: 'ENABLED',
      permissions: ['NETWORK_EXTERNAL'],
      capabilities: { readOnly: false, mutatesRemoteState: true, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 15_000, maxTimeoutMs: 45_000, retryable: true, maxRetries: 1 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true, requiresConfirmation: false },
    },
    {
      name: 'delivery-list-generator',
      version: '1.0.0',
      aliases: [],
      displayName: '发货清单生成',
      description: '根据订单生成标准发货清单PDF',
      tags: ['delivery', 'document', 'pdf'],
      category: 'integration',
      domains: ['SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL'],
      capabilities: { readOnly: false, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 10_000, maxTimeoutMs: 30_000 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
    {
      name: 'minimax-mcp',
      version: '1.0.0',
      aliases: [],
      displayName: 'MiniMax多模态MCP',
      description: 'MiniMax API多模态接口：语音合成/图像生成',
      tags: ['minimax', 'mcp', 'multimodal'],
      category: 'integration',
      domains: ['SYSTEM', 'DOWNLOAD'],
      riskLevel: 'MEDIUM',
      status: 'ENABLED',
      permissions: ['NETWORK_EXTERNAL'],
      capabilities: { readOnly: false, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 30_000, maxTimeoutMs: 90_000 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },

    // ========== 辅助技能（LOW）==========
    {
      name: 'prompt-engineering',
      version: '1.0.0',
      aliases: ['prompt'],
      displayName: '提示词工程',
      description: '提示词优化、few-shot示例生成、输出格式控制',
      tags: ['prompt', 'llm', 'engineering'],
      category: 'prompt',
      domains: ['SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL'],
      capabilities: { readOnly: true, needsNetwork: false, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 10_000, maxTimeoutMs: 30_000 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
    {
      name: 'agent-teams-playbook',
      version: '1.0.0',
      aliases: [],
      displayName: '多Agent协作手册',
      description: '多Agent任务分解、并行执行、结果汇总',
      tags: ['multi-agent', 'teams', 'coordination'],
      category: 'general',
      domains: ['SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL'],
      capabilities: { readOnly: false, mutatesRemoteState: true, needsNetwork: false, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 60_000, maxTimeoutMs: 180_000 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
    {
      name: 'clawhub-agent',
      version: '1.0.0',
      aliases: [],
      displayName: 'ClawHub自我武装指南',
      description: 'ClawHub技能安装、安全审查、注册流程',
      tags: ['clawhub', 'skill', 'self-improve'],
      category: 'general',
      domains: ['SYSTEM'],
      riskLevel: 'LOW',
      status: 'ENABLED',
      permissions: ['SYSTEM_INTERNAL', 'NETWORK_EXTERNAL'],
      capabilities: { readOnly: false, needsNetwork: true, producesStructuredOutput: true },
      execution: { defaultTimeoutMs: 30_000, maxTimeoutMs: 90_000 },
      exposure: {},
      guardrails: { allowPlannerAutoSelect: true, allowManualCall: true },
    },
  ]);

  return registry;
}

