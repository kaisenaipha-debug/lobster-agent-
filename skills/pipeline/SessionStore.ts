/**
 * SessionStore.ts - 会话持久化（Node.js/TypeScript）
 * 
 * 用途：storageState持久化 + 自动恢复
 * 依赖：playwright, fs-extra
 * 
 * 关键设计：
 * - storageState JSON存储（cookies + localStorage）
 * - 每5分钟自动保存
 * - 启动时自动恢复session
 * - 路径：~/.chrome_sessions/default.json
 */

import { chromium, BrowserContext } from 'playwright';
import * as fs from 'fs';
import * as path from 'path';

interface SessionData {
  version: string;
  lastSaved: string;
  sessionId: string;
  storageState: any; // Playwright storageState格式
  metadata: {
    createdAt: string;
    lastUsed: string;
    url: string;
    title: string;
  };
}

class SessionStore {
  private sessionsDir: string;
  private saveIntervalMs: number = 5 * 60 * 1000; // 5分钟
  private saveTimers: Map<string, NodeJS.Timeout> = new Map();

  constructor(sessionsDir?: string) {
    this.sessionsDir = sessionsDir || path.join(
      process.env.HOME || '.',
      '.chrome_sessions'
    );
    this.ensureDir();
  }

  private ensureDir(): void {
    if (!fs.existsSync(this.sessionsDir)) {
      fs.mkdirSync(this.sessionsDir, { recursive: true });
      console.log(`[SessionStore] 目录创建: ${this.sessionsDir}`);
    }
  }

  private sessionPath(sessionId: string): string {
    return path.join(this.sessionsDir, `${sessionId}.json`);
  }

  /**
   * 保存session状态（手动触发）
   */
  async saveSession(sessionId: string, context: BrowserContext): Promise<void> {
    const filePath = this.sessionPath(sessionId);
    
    try {
      // 获取当前URL和标题
      const pages = context.pages();
      const currentPage = pages[pages.length - 1];
      const url = currentPage?.url() || '';
      const title = await currentPage?.title() || '';

      const sessionData: SessionData = {
        version: '1.0',
        lastSaved: new Date().toISOString(),
        sessionId,
        storageState: await context.storageState(),
        metadata: {
          createdAt: fs.existsSync(filePath) 
            ? JSON.parse(fs.readFileSync(filePath, 'utf-8')).metadata.createdAt 
            : new Date().toISOString(),
          lastUsed: new Date().toISOString(),
          url,
          title,
        },
      };

      fs.writeFileSync(filePath, JSON.stringify(sessionData, null, 2));
      console.log(`[SessionStore] 已保存: ${filePath} (${url})`);
    } catch (error) {
      console.error(`[SessionStore] 保存失败: ${error}`);
    }
  }

  /**
   * 加载session状态（启动恢复）
   */
  async loadSession(sessionId: string): Promise<any | null> {
    const filePath = this.sessionPath(sessionId);
    
    if (!fs.existsSync(filePath)) {
      console.log(`[SessionStore] session不存在: ${sessionId}`);
      return null;
    }

    try {
      const data: SessionData = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
      console.log(`[SessionStore] 已加载: ${sessionId} (上次使用: ${data.metadata.lastUsed})`);
      return data.storageState;
    } catch (error) {
      console.error(`[SessionStore] 加载失败: ${error}`);
      return null;
    }
  }

  /**
   * 启动自动保存（定期保存）
   */
  startAutoSave(sessionId: string, context: BrowserContext): void {
    if (this.saveTimers.has(sessionId)) {
      this.stopAutoSave(sessionId);
    }

    const timer = setInterval(async () => {
      await this.saveSession(sessionId, context);
    }, this.saveIntervalMs);

    this.saveTimers.set(sessionId, timer);
    console.log(`[SessionStore] 自动保存已启动: ${sessionId} (间隔=${this.saveIntervalMs / 1000}秒)`);
  }

  /**
   * 停止自动保存
   */
  stopAutoSave(sessionId: string): void {
    const timer = this.saveTimers.get(sessionId);
    if (timer) {
      clearInterval(timer);
      this.saveTimers.delete(sessionId);
      console.log(`[SessionStore] 自动保存已停止: ${sessionId}`);
    }
  }

  /**
   * 恢复session（用storageState恢复BrowserContext）
   */
  async restoreSession(sessionId: string, browser: any): Promise<BrowserContext | null> {
    const storageState = await this.loadSession(sessionId);
    if (!storageState) {
      console.log(`[SessionStore] 无可恢复session: ${sessionId}`);
      return null;
    }

    const context = await browser.newContext({ storageState });
    console.log(`[SessionStore] session已恢复: ${sessionId}`);
    return context;
  }

  /**
   * 列出所有保存的session
   */
  listSessions(): SessionData[] {
    if (!fs.existsSync(this.sessionsDir)) return [];

    return fs.readdirSync(this.sessionsDir)
      .filter(f => f.endsWith('.json'))
      .map(f => {
        try {
          return JSON.parse(fs.readFileSync(path.join(this.sessionsDir, f), 'utf-8')) as SessionData;
        } catch {
          return null;
        }
      })
      .filter((s): s is SessionData => s !== null)
      .sort((a, b) => new Date(b.metadata.lastUsed).getTime() - new Date(a.metadata.lastUsed).getTime());
  }
}

export { SessionStore, SessionData };
