# Rejection Feedback Engine - one-command setup for Windows (PowerShell).
#
# Checks prerequisites, sets up an isolated environment, starts the server,
# and opens the web UI. Safe to re-run.
#
#   Right-click run.ps1 > "Run with PowerShell", or:
#   powershell -ExecutionPolicy Bypass -File run.ps1
#
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

$Port     = if ($env:RFE_PORT)      { $env:RFE_PORT }      else { "8000" }
$LlmModel = if ($env:RFE_LLM_MODEL) { $env:RFE_LLM_MODEL } else { "llama3" }

function Say  ($m) { Write-Host "`n==> $m" -ForegroundColor Cyan }
function Warn ($m) { Write-Host "!  $m"   -ForegroundColor Yellow }
function Die  ($m) { Write-Host "X  $m"   -ForegroundColor Red; exit 1 }

# --- 1. Python ---------------------------------------------------------------
Say "Checking for Python 3.12+"
$Py = $null
foreach ($c in @("python", "python3", "py")) {
  if (Get-Command $c -ErrorAction SilentlyContinue) {
    $ok = & $c -c "import sys; print(1 if sys.version_info>=(3,12) else 0)" 2>$null
    if ($ok -eq "1") { $Py = $c; break }
  }
}
if (-not $Py) {
  Warn "Python 3.12+ not found."
  if (Get-Command winget -ErrorAction SilentlyContinue) {
    Say "Installing Python via winget"
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    $Py = "python"
    Warn "If 'python' is still not found, close and reopen PowerShell, then re-run run.ps1"
  } else {
    Die "Please install Python 3.12+ from https://www.python.org/downloads/ then re-run run.ps1"
  }
}
& $Py --version

# --- 2. Virtualenv + dependencies -------------------------------------------
if (-not (Test-Path ".venv")) {
  Say "Creating virtual environment (.venv)"
  & $Py -m venv .venv
}
$VPy = ".\.venv\Scripts\python.exe"
Say "Installing dependencies (first run downloads packages, please wait)"
& $VPy -m pip install --quiet --upgrade pip
& $VPy -m pip install --quiet -e . uvicorn

# --- 3. Local LLM (Ollama) ---------------------------------------------------
if (Get-Command ollama -ErrorAction SilentlyContinue) {
  try { Invoke-RestMethod "http://localhost:11434/api/version" -TimeoutSec 2 | Out-Null }
  catch { Say "Starting Ollama"; Start-Process -WindowStyle Hidden ollama -ArgumentList "serve"; Start-Sleep 2 }
  if (-not (ollama list 2>$null | Select-String "^$LlmModel")) {
    Say "Downloading the '$LlmModel' model (one-time, a few GB)"
    ollama pull $LlmModel
  }
  $env:RFE_LLM_BASE_URL = "http://localhost:11434/v1"
  $env:RFE_LLM_MODEL    = $LlmModel
  Write-Host "   LLM: local Ollama ($LlmModel) - free, private"
} else {
  Warn "Ollama not found (the engine needs an LLM to write feedback)."
  Warn "Easiest free option: install from https://ollama.com/download then re-run run.ps1"
  Warn "Or set RFE_LLM_BASE_URL / RFE_LLM_API_KEY / RFE_LLM_MODEL for any OpenAI-compatible API."
  if (-not $env:RFE_LLM_BASE_URL) { Die "No LLM configured. Install Ollama or set RFE_LLM_BASE_URL, then re-run." }
}

# --- 4. Start the server + open the browser ----------------------------------
$Url = "http://localhost:$Port"
Say "Starting the Rejection Feedback Engine at $Url"
Write-Host "   The web page will open in your browser. Press Ctrl+C here to stop."

Start-Job -ScriptBlock {
  param($u)
  for ($i=0; $i -lt 30; $i++) {
    try { Invoke-WebRequest $u -UseBasicParsing -TimeoutSec 1 | Out-Null; Start-Process $u; break }
    catch { Start-Sleep 1 }
  }
} -ArgumentList $Url | Out-Null

& $VPy -m uvicorn rfe.main:app --port $Port
