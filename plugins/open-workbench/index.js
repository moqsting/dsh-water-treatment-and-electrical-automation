/**
 * dsh-open-workbench —— Host 侧：工作台进程管理。
 * 提供三个已认证路由：
 *   GET  /api/workbench/status → { running, port }
 *   POST /api/workbench/start  → 后台启动 ui/server.py（pythonw 无窗口），返回 { ok, port }
 *   POST /api/workbench/stop   → 调工作台 /api/shutdown 优雅退出，返回 { ok }
 * 工作台目录与 pythonw 路径从本包内 workbench-path.json 读取（部署脚本写入）。
 */
import { spawn } from 'node:child_process'
import { readFileSync, existsSync } from 'node:fs'
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

function pythonw() {
  const cfg = readConfig()
  if (cfg.pythonw) return cfg.pythonw
  return process.env.PYTHONW_EXE || 'pythonw'
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
        if (!dir) { sendJson(res, 500, { ok: false, error: '工作台目录未配置（workbench-path.json 缺 uiDir）' }); return }
        const portFile = join(tmpdir(), `dsh-workbench-${process.pid}-${Date.now()}.port`)
        try {
          serverProc = spawn(pythonw(), [join(dir, 'server.py'), '--port-file', portFile], {
            detached: true,
            stdio: 'ignore',
          })
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
