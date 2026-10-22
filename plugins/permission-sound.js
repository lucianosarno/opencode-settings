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
  soundFile: "C:\\Windows\\Media\\Windows Notify System Generic.wav",
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

function playSound(settings) {
  if (process.platform !== "win32") return
  const child = spawn(
    "powershell.exe",
    ["-NoProfile", "-NonInteractive", "-WindowStyle", "Hidden", "-Command", buildScript(settings)],
    { detached: true, stdio: "ignore", windowsHide: true },
  )
  child.on("error", () => {})
  child.unref()
}

export const PermissionSoundPlugin = async ({ client }) => {
  return {
    event: async ({ event }) => {
      const settings = loadSettings()
      if (!settings.enabled) return
      if (!settings.events.includes(event.type)) return

      playSound(settings)

      await client.app.log({
        body: {
          service: "permission-sound",
          level: "info",
          message: "Som de notificacao tocado",
          extra: { event: event.type },
        },
      })
    },
  }
}
