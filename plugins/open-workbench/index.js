/**
 * dsh-open-workbench —— Host 侧：工作台进程管理。
 * 提供三个已认证路由：
 *   GET  /api/workbench/status → { running, port }
 *   POST /api/workbench/start  → 后台启动 ui/server.py（pythonw 无窗口），返回 { ok, port }
 *   POST /api/workbench/stop   → 调工作台 /api/shutdown 优雅退出，返回 { ok }
 * 工作台目录与 pythonw 路径从本包内 workbench-path.json 读取（部署脚本写入）。
 */
import { spawn, execFile } from 'node:child_process'
import { readFileSync, existsSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'

const __dirname = dirname(fileURLToPath(import.meta.url))

function readConfig() {
  try {
    return JSON.parse(readFileSync(join(__dirname, 'workbench-path.json'), 'utf8'))
  } catch {
    return {}
  }
}

/** 定位 DSH_HOME：环境变量优先，其次从插件所在位置向上找（profiles + skills 同时存在的目录）。 */
function findDshHome() {
  const env = process.env.DSH_HOME
  if (env && existsSync(env)) return env
  let p = __dirname
  for (let i = 0; i < 8; i++) {
    p = dirname(p)
    if (existsSync(join(p, 'profiles')) && existsSync(join(p, 'skills'))) return p
  }
  return null
}

/** 工作台 ui 目录：优先 config 指定；否则用 .dspack 导入后的固定位置 $DSH_HOME/wta/ui。 */
function uiDir() {
  const cfg = readConfig()
  if (cfg.uiDir) return cfg.uiDir
  const home = findDshHome()
  if (home) {
    const candidate = join(home, 'wta', 'ui')
    if (existsSync(join(candidate, 'server.py'))) return candidate
  }
  return null
}

/** 探测可用的 pythonw.exe 绝对路径（GUI 子系统，不弹控制台）；找不到返回 null。 */
async function resolvePythonw() {
  const cfg = readConfig()
  if (cfg.pythonw && cfg.pythonw.toLowerCase().endsWith('.exe') && existsSync(cfg.pythonw)) {
    return cfg.pythonw
  }
  const env = process.env.PYTHONW_EXE
  if (env && existsSync(env)) return env
  // 扫描 %LOCALAPPDATA%\Programs\Python\<版本>\pythonw.exe（新版本优先）
  const local = process.env.LOCALAPPDATA
  if (local) {
    const base = join(local, 'Programs', 'Python')
    try {
      if (existsSync(base)) {
        const dirs = readdirSync(base).sort().reverse()
        for (const d of dirs) {
          const c = join(base, d, 'pythonw.exe')
          if (existsSync(c)) return c
        }
      }
    } catch { /* 忽略扫描失败 */ }
  }
  // 通过 py 启动器推导出 pythonw 同目录路径
  try {
    const exe = await new Promise((resolve) => {
      execFile('py', ['-3', '-c', 'import sys;print(sys.executable)'],
        { windowsHide: true },
        (err, stdout) => resolve(err ? null : String(stdout).trim()))
    })
    if (exe && exe.toLowerCase().endsWith('python.exe')) {
      const w = exe.slice(0, -'python.exe'.length) + 'pythonw.exe'
      if (existsSync(w)) return w
    }
  } catch { /* 忽略 */ }
  return null
}

export const name = 'dsh-open-workbench'
export const inject = ['webServer', 'connection']

const START_PORT = 8618
const END_PORT = 8628
let serverProc = null

function sendJson(res, status, payload) {
  res.statusCode = status
  res.setHeader('content-type', 'application/json; charset=utf-8')
  res.setHeader('cache-control', 'no-store')
  res.end(JSON.stringify(payload))
}

async function findRunning() {
  for (let port = START_PORT; port <= END_PORT; port++) {
    try {
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 700)
      const r = await fetch(`http://127.0.0.1:${port}/api/health`, { signal: ctrl.signal })
      clearTimeout(timer)
      if (r.ok) {
        const j = await r.json().catch(() => null)
        if (j && j.name === 'integration-pack-workbench') return port
      }
    } catch {
      /* 未运行，继续 */
    }
  }
  return null
}

export function apply(ctx) {
  const connection = Reflect.get(ctx, 'connection')
  const rejected = (req, res) => {
    const rejection = connection?.requestRejection?.(req)
    if (rejection === undefined) return false
    res.statusCode = rejection
    res.end()
    return true
  }

  ctx.effect(
    () => ctx.webServer.register({
      kind: 'exact',
      path: '/api/workbench/status',
      handler: async (req, res) => {
        if (rejected(req, res)) return
        const port = await findRunning()
        sendJson(res, 200, { running: port !== null, port })
      },
    }),
    'dsh-open-workbench: GET /api/workbench/status',
  )

  ctx.effect(
    () => ctx.webServer.register({
      kind: 'exact',
      path: '/api/workbench/start',
      handler: async (req, res) => {
        if (rejected(req, res)) return
        if (req.method !== 'POST') { res.statusCode = 405; res.setHeader('allow', 'POST'); res.end(); return }
        const already = await findRunning()
        if (already) { sendJson(res, 200, { ok: true, port: already }); return }
        const dir = uiDir()
        if (!dir) { sendJson(res, 500, { ok: false, error: '未找到工作台（$DSH_HOME/wta/ui），请确认整合包已完整导入' }); return }
        const pyw = await resolvePythonw()
        if (!pyw) { sendJson(res, 500, { ok: false, error: '未找到 Python（pythonw.exe）。请先安装 Python 3.12（勾选 py launcher）后重试。' }); return }
        const portFile = join(tmpdir(), `dsh-workbench-${process.pid}-${Date.now()}.port`)
        try {
          serverProc = spawn(pyw, [join(dir, 'server.py'), '--port-file', portFile], {
            detached: true,
            stdio: 'ignore',
            windowsHide: true,
          })
          // 关键：捕获 spawn 失败（如可执行文件不存在），否则未处理异常会崩掉宿主 DSH
          serverProc.on('error', () => { serverProc = null })
          serverProc.unref()
          let port = null
          for (let i = 0; i < 60; i++) {
            await new Promise((r) => setTimeout(r, 250))
            if (existsSync(portFile)) {
              try { port = parseInt(readFileSync(portFile, 'utf8').trim(), 10) } catch {}
              if (port) break
            }
            if (serverProc.exitCode !== null) break
          }
          if (port) {
            sendJson(res, 200, { ok: true, port })
          } else {
            sendJson(res, 500, { ok: false, error: '工作台启动超时（15 秒内未就绪）' })
          }
        } catch (e) {
          sendJson(res, 500, { ok: false, error: e && e.message ? e.message : String(e) })
        }
      },
    }),
    'dsh-open-workbench: POST /api/workbench/start',
  )

  ctx.effect(
    () => ctx.webServer.register({
      kind: 'exact',
      path: '/api/workbench/stop',
      handler: async (req, res) => {
        if (rejected(req, res)) return
        if (req.method !== 'POST') { res.statusCode = 405; res.setHeader('allow', 'POST'); res.end(); return }
        const port = await findRunning()
        if (port) {
          try {
            const ctrl = new AbortController()
            const timer = setTimeout(() => ctrl.abort(), 3000)
            await fetch(`http://127.0.0.1:${port}/api/shutdown`, { method: 'POST', signal: ctrl.signal })
            clearTimeout(timer)
          } catch {}
          for (let i = 0; i < 20; i++) {
            await new Promise((r) => setTimeout(r, 250))
            if (!(await findRunning())) break
          }
        }
        if (serverProc) { try { serverProc.kill() } catch {} serverProc = null }
        sendJson(res, 200, { ok: true })
      },
    }),
    'dsh-open-workbench: POST /api/workbench/stop',
  )
}
