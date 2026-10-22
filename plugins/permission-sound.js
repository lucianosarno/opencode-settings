// Toca um som no Windows quando o OpenCode pede permissao para executar algo.
// Configuracao: ~/.config/opencode/permission-sound.json (enabled, soundFile, fallbackSystemSound, events).
// O processo PowerShell roda em segundo plano (nao bloqueia a interface do OpenCode).
import { spawn } from "node:child_process"
import { readFileSync, existsSync } from "node:fs"
import { join } from "node:path"
import { homedir } from "node:os"

const CONFIG_PATH = join(homedir(), ".config", "opencode", "permission-sound.json")

const DEFAULTS = {
  enabled: true,
  soundFile: "C:\\Windows\\Media\\Alarm01.wav",
  fallbackSystemSound: "Exclamation",
  events: ["permission.asked"],
}

function loadSettings() {
  try {
    if (existsSync(CONFIG_PATH)) {
      return { ...DEFAULTS, ...JSON.parse(readFileSync(CONFIG_PATH, "utf8")) }
    }
  } catch {
    // Config invalida: usa os padroes em vez de quebrar o OpenCode.
  }
  return DEFAULTS
}

// Aspas simples dentro de string PowerShell se escapam dobrando.
const psQuote = (s) => `'${String(s).replace(/'/g, "''")}'`

function buildScript(settings) {
  const file = settings.soundFile
  const fallback = settings.fallbackSystemSound
  return (
    `if (Test-Path -LiteralPath ${psQuote(file)}) {` +
    ` $p = New-Object System.Media.SoundPlayer ${psQuote(file)}; $p.PlaySync()` +
    ` } else { [System.Media.SystemSounds]::${fallback}.Play() }`
  )
}

// Registra no log do OpenCode (persistido em ~/.local/share/opencode/log) o resultado real
// do som: codigo de saida do PowerShell e qualquer erro, em vez de assumir sucesso.
function playSound(settings, client, eventType) {
  if (process.platform !== "win32") return
  const child = spawn(
    "powershell.exe",
    ["-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", buildScript(settings)],
    { stdio: ["ignore", "ignore", "pipe"], windowsHide: true },
  )

  let stderr = ""
  child.stderr.on("data", (chunk) => {
    stderr += chunk.toString()
  })

  const report = (level, message, extra) =>
    client.app
      .log({ body: { service: "permission-sound", level, message, extra: { event: eventType, ...extra } } })
      .catch(() => {})

  child.on("error", (err) => {
    report("error", "Falha ao iniciar o PowerShell para tocar o som", { error: err.message })
  })
  child.on("close", (code) => {
    if (code === 0) {
      report("info", "Som de notificacao concluido", { exitCode: code })
    } else {
      report("error", "PowerShell terminou com erro ao tocar o som", { exitCode: code, stderr: stderr.trim() })
    }
  })
}

export const PermissionSoundPlugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      const settings = loadSettings()
      if (!settings.enabled) return
      if (!settings.events.includes(event.type)) return

      playSound(settings, client, event.type)
    },
  }
}
