/**
 * Watchdog.kt - 看门狗（Kotlin）
 * 
 * 用途：健康检查 + 自动重启Chrome
 * 依赖：kotlin-stdlib, kotlinx-coroutines
 * 编译：kotlinc Watchdog.kt -include-runtime -d Watchdog.jar
 * 
 * 关键设计：
 * - 双层健康检查（进程检查 + CDP检查）
 * - 检查周期：30秒
 * - 失败3次触发Recovery
 * - JSON结构化日志（可接ELK/Loki）
 */

import kotlinx.coroutines.*
import java.io.*
import java.net.HttpURLConnection
import java.net.URL
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import java.util.concurrent.ConcurrentHashMap
import kotlin.system.exitProcess

data class HealthResult(
    val timestamp: String,
    val sessionId: String,
    val processAlive: Boolean,
    val cdpReachable: Boolean,
    val consecutiveFailures: Int,
    val status: String // HEALTHY, DEGRADED, RECOVERING, CRITICAL
)

data class RecoveryEvent(
    val timestamp: String,
    val sessionId: String,
    val action: String, // QUARANTINE, KILL, RESTART, RECONNECT
    val success: Boolean,
    val error: String?
)

class Watchdog(
    private val checkIntervalMs: Long = 30_000,  // 30秒检查一次
    private val maxConsecutiveFailures: Int = 3,   // 连续3次失败触发恢复
    private val quarantineMs: Long = 15_000         // 隔离15秒
) {
    private val healthState = ConcurrentHashMap<String, Int>() // sessionId -> consecutiveFailures
    private val logDir = File(System.getProperty("user.home"), ".watchdog_logs")
    private val healthLog = File(logDir, "health.jsonl")
    private val recoveryLog = File(logDir, "recovery.jsonl")
    
    private val CHROME_PROCESS_NAMES = listOf("Google Chrome", "chrome", "Chromium")
    private val CDP_BASE_URL = "http://localhost:9222"

    init {
        logDir.mkdirs()
        println("[Watchdog] 启动, 检查间隔=${checkIntervalMs/1000}秒, 最大连续失败=$maxConsecutiveFailures")
        println("[Watchdog] 日志目录: ${logDir.absolutePath}")
    }

    /**
     * 主循环：定期检查所有Chrome进程
     */
    suspend fun run(sessions: List<String>) = coroutineScope {
        // 启动日志刷新协程
        launch { flushLogsPeriodically() }
        
        while (isActive) {
            val now = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)
            
            for (sessionId in sessions) {
                val result = checkHealth(sessionId)
                logHealth(result)
                
                if (result.status == "CRITICAL") {
                    launch { triggerRecovery(sessionId) }
                }
            }
            
            delay(checkIntervalMs)
        }
    }

    /**
     * 双层健康检查
     */
    private fun checkHealth(sessionId: String): HealthResult {
        val now = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)
        
        // Layer 1: 进程检查
        val processAlive = checkProcessAlive()
        
        // Layer 2: CDP可达性检查
        val cdpReachable = checkCDPReachable()
        
        // 更新失败计数
        val failures = if (!processAlive || !cdpReachable) {
            healthState.merge(sessionId, 1) { old, _ -> old + 1 } ?: 1
        } else {
            healthState.put(sessionId, 0) ?: 0
            0
        }
        
        val status = when {
            failures >= maxConsecutiveFailures -> "CRITICAL"
            !processAlive || !cdpReachable -> "DEGRADED"
            failures > 0 -> "RECOVERING"
            else -> "HEALTHY"
        }
        
        return HealthResult(
            timestamp = now,
            sessionId = sessionId,
            processAlive = processAlive,
            cdpReachable = cdpReachable,
            consecutiveFailures = failures,
            status = status
        )
    }

    /**
     * Layer 1: 进程级检查（ps aux | grep Chrome）
     */
    private fun checkProcessAlive(): Boolean {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("ps", "aux"))
            val reader = BufferedReader(InputStreamReader(process.inputStream))
            var found = false
            
            reader.use { lines ->
                lines.forEach { line ->
                    if (CHROME_PROCESS_NAMES.any { line.contains(it) && !line.contains("grep") }) {
                        found = true
                    }
                }
            }
            found
        } catch (e: Exception) {
            println("[Watchdog] 进程检查异常: ${e.message}")
            false
        }
    }

    /**
     * Layer 2: CDP可达性检查（HTTP GET localhost:9222/json）
     */
    private fun checkCDPReachable(): Boolean {
        return try {
            val url = URL("$CDP_BASE_URL/json")
            val conn = url.openConnection() as HttpURLConnection
            conn.requestMethod = "GET"
            conn.connectTimeout = 5000
            conn.readTimeout = 5000
            val responseCode = conn.responseCode
            conn.disconnect()
            responseCode == 200
        } catch (e: Exception) {
            println("[Watchdog] CDP检查异常: ${e.message}")
            false
        }
    }

    /**
     * Recovery流程：quarantine → kill → restart → reconnect
     */
    private suspend fun triggerRecovery(sessionId: String) {
        val now = LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME)
        
        // Step 1: Quarantine（隔离15秒）
        println("[Watchdog] [$now] 开始Recovery, session=$sessionId")
        logRecovery(RecoveryEvent(now, sessionId, "QUARANTINE", true, null))
        delay(quarantineMs)
        
        // Step 2: Kill Chrome进程
        val killResult = killChrome()
        logRecovery(RecoveryEvent(now, sessionId, "KILL", killResult, if (!killResult) "kill命令失败" else null))
        
        if (!killResult) {
            println("[Watchdog] Kill失败，跳过")
            return
        }
        
        // Step 3: 等待进程完全退出
        delay(2000)
        
        // Step 4: 重启Chrome（带关键参数）
        val startResult = startChrome()
        logRecovery(RecoveryEvent(now, sessionId, "RESTART", startResult, if (!startResult) "start命令失败" else null))
        
        // Step 5: 等待CDP就绪
        delay(3000)
        
        // Step 6: 通知BrowserService重连（通过HTTP回调或文件信号）
        notifyBrowserService(sessionId)
        logRecovery(RecoveryEvent(now, sessionId, "RECONNECT", true, null))
        
        // 重置失败计数
        healthState.put(sessionId, 0)
        println("[Watchdog] Recovery完成, session=$sessionId")
    }

    /**
     * Kill所有Chrome进程
     */
    private fun killChrome(): Boolean {
        return try {
            val process = Runtime.getRuntime().exec(arrayOf("pkill", "-9", "-i", "chrome"))
            process.waitFor()
            println("[Watchdog] Chrome进程已终止")
            true
        } catch (e: Exception) {
            println("[Watchdog] Kill异常: ${e.message}")
            false
        }
    }

    /**
     * 重启Chrome（带关键稳定性参数）
     */
    private fun startChrome(): Boolean {
        return try {
            val cmd = listOf(
                "open", "/Applications/Google Chrome.app",
                "--args",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--remote-debugging-port=9222"
            )
            val process = Runtime.getRuntime().exec(cmd.toTypedArray())
            println("[Watchdog] Chrome重启命令已执行")
            true
        } catch (e: Exception) {
            println("[Watchdog] 重启异常: ${e.message}")
            false
        }
    }

    /**
     * 通知BrowserService重连（写信号文件）
     */
    private fun notifyBrowserService(sessionId: String) {
        val signalFile = File(logDir, "reconnect_$sessionId.signal")
        signalFile.writeText(LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME))
        println("[Watchdog] 已发送重连信号: $sessionId")
    }

    /**
     * 记录健康日志（JSONL格式）
     */
    private fun logHealth(result: HealthResult) {
        val json = """
            {"timestamp":"${result.timestamp}","sessionId":"${result.sessionId}",
             "processAlive":${result.processAlive},"cdpReachable":${result.cdpReachable},
             "consecutiveFailures":${result.consecutiveFailures},"status":"${result.status}"}
        """.trimIndent().replace("\n", "")
        
        try {
            healthLog.appendText(json + "\n")
            println("[Watchdog] [${result.timestamp}] ${result.sessionId}: ${result.status} (failures=${result.consecutiveFailures})")
        } catch (e: Exception) {
            println("[Watchdog] 日志写入失败: ${e.message}")
        }
    }

    /**
     * 记录Recovery日志
     */
    private fun logRecovery(event: RecoveryEvent) {
        val json = """
            {"timestamp":"${event.timestamp}","sessionId":"${event.sessionId}",
             "action":"${event.action}","success":${event.success},
             "error":${event.error?.let { "\"$it\"" } ?: "null"}}
        """.trimIndent().replace("\n", "")
        
        try {
            recoveryLog.appendText(json + "\n")
        } catch (e: Exception) {
            println("[Watchdog] Recovery日志写入失败: ${e.message}")
        }
    }

    private fun flushLogsPeriodically() {
        // 日志每秒刷新（可选，接ELK时启用）
    }
}

/**
 * 主入口
 */
fun main(args: Array<String>) {
    val sessions = args.toList().ifEmpty { listOf("default") }
    
    val watchdog = Watchdog()
    
    // Ctrl+C 处理
    Runtime.getRuntime().addShutdownHook(Thread {
        println("\n[Watchdog] 收到退出信号，正在关闭...")
    })
    
    // 启动主循环（使用runBlocking保持主线程存活）
    runBlocking {
        watchdog.run(sessions)
    }
}
