/**
 * BrowserService.ts - 浏览器服务层（Node.js/TypeScript）
 * 
 * 用途：CDP连接池管理 + 自动重连 + RPC接口
 * 依赖：playwright (npm install playwright)
 * 
 * 关键设计：
 * - 状态机：INIT → CONNECTING → READY → DEGRADED → RECONNECTING → CLOSED
 * - 指数退避重连：2/4/8/16/32秒，最多5次
 * - browser.on("disconnected") 事件监听 + 自动恢复
 * - 每个连接独立 context，避免污染
 */

import { chromium, Browser, BrowserContext, CDPSession, Page } from 'playwright';

type BrowserStatus = 'INIT' | 'CONNECTING' | 'READY' | 'DEGRADED' | 'RECONNECTING' | 'CLOSED';

interface Connection {
  id: string;
  browser: Browser;
  context: BrowserContext;
  page: Page;
  status: BrowserStatus;
  createdAt: number;
  lastHealthCheck: number;
}

class BrowserService {
  private connections: Map<string, Connection> = new Map();
  private reconnectAttempts: Map<string, number> = new Map();
  private readonly MAX_RECONNECT = 5;
  private readonly RECONNECT_DELAYS = [2000, 4000, 8000, 16000, 32000]; // 指数退避
  private readonly CHROME_ARGS = [
    '--disable-dev-shm-usage',
    '--no-sandbox',
    '--disable-gpu',
    '--remote-debugging-port=9222',
    '--disable-background-networking',
    '--disable-default-apps',
    '--disable-extensions',
    '--disable-sync',
    '--disable-translate',
    '--metrics-recording-only',
    '--mute-audio',
    '--no-first-run',
  ];

  /**
   * 启动Chrome并建立CDP连接
   */
  async startBrowser(sessionId: string): Promise<Connection> {
    console.log(`[BrowserService] 启动Chrome, session=${sessionId}`);
    
    const browser = await chromium.launch({
      headless: false, // Mac上建议false避免被检测
      args: this.CHROME_ARGS,
    });

    // 监听断连事件
    browser.on('disconnected', () => {
      console.log(`[BrowserService] Chrome断连, session=${sessionId}`);
      this.handleDisconnected(sessionId);
    });

    const context = await browser.newContext({
      // 已登录状态复用（可选）
      // storageState: './sessions/default.json',
    });
    
    const page = await context.newPage();
    
    const conn: Connection = {
      id: sessionId,
      browser,
      context,
      page,
      status: 'READY',
      createdAt: Date.now(),
      lastHealthCheck: Date.now(),
    };
    
    this.connections.set(sessionId, conn);
    console.log(`[BrowserService] Chrome启动成功, session=${sessionId}`);
    
    return conn;
  }

  /**
   * 停止指定session的浏览器
   */
  async stopBrowser(sessionId: string): Promise<void> {
    const conn = this.connections.get(sessionId);
    if (!conn) {
      console.warn(`[BrowserService] session不存在: ${sessionId}`);
      return;
    }
    
    conn.status = 'CLOSED';
    await conn.browser.close();
    this.connections.delete(sessionId);
    console.log(`[BrowserService] Chrome已关闭, session=${sessionId}`);
  }

  /**
   * 获取Page对象（供Agent调用）
   */
  async getPage(sessionId: string): Promise<Page> {
    const conn = this.connections.get(sessionId);
    if (!conn) {
      throw new Error(`Session不存在: ${sessionId}`);
    }
    if (conn.status === 'CLOSED') {
      throw new Error(`Session已关闭: ${sessionId}`);
    }
    return conn.page;
  }

  /**
   * 健康检查
   */
  async healthCheck(sessionId: string): Promise<boolean> {
    const conn = this.connections.get(sessionId);
    if (!conn) return false;
    
    try {
      // 简单探测：执行JS
      await conn.page.evaluate('1 + 1');
      conn.lastHealthCheck = Date.now();
      conn.status = 'READY';
      return true;
    } catch (e) {
      console.warn(`[BrowserService] 健康检查失败, session=${sessionId}:`, e);
      conn.status = 'DEGRADED';
      return false;
    }
  }

  /**
   * 处理Chrome断连（自动重连）
   */
  private async handleDisconnected(sessionId: string): Promise<void> {
    const conn = this.connections.get(sessionId);
    if (!conn) return;
    
    const attempts = this.reconnectAttempts.get(sessionId) || 0;
    if (attempts >= this.MAX_RECONNECT) {
      console.error(`[BrowserService] 重连次数超限, session=${sessionId}`);
      conn.status = 'CLOSED';
      this.connections.delete(sessionId);
      return;
    }
    
    conn.status = 'RECONNECTING';
    const delay = this.RECONNECT_DELAYS[attempts];
    console.log(`[BrowserService] ${delay/1000}秒后尝试重连 (${attempts + 1}/${this.MAX_RECONNECT}), session=${sessionId}`);
    
    await new Promise(resolve => setTimeout(resolve, delay));
    this.reconnectAttempts.set(sessionId, attempts + 1);
    
    try {
      // 重新启动
      await this.startBrowser(sessionId);
      this.reconnectAttempts.set(sessionId, 0); // 重置计数
      console.log(`[BrowserService] 重连成功, session=${sessionId}`);
    } catch (e) {
      console.error(`[BrowserService] 重连失败, session=${sessionId}:`, e);
      await this.handleDisconnected(sessionId);
    }
  }

  /**
   * RPC入口（可暴露为HTTP/gRPC）
   */
  async rpc(method: string, args: any): Promise<any> {
    switch (method) {
      case 'startBrowser':
        return this.startBrowser(args.sessionId);
      case 'stopBrowser':
        return this.stopBrowser(args.sessionId);
      case 'getPage':
        return this.getPage(args.sessionId);
      case 'healthCheck':
        return this.healthCheck(args.sessionId);
      default:
        throw new Error(`未知方法: ${method}`);
    }
  }
}

export { BrowserService };
