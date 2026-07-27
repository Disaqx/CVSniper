# release.ps1 - Publica una nueva version de CVSniper en GitHub
#
# Uso: .\release.ps1 v1.1.0
# Requisitos: gh auth login hecho previamente

param(
    [Parameter(Mandatory=$true)]
    [string]$Version
)

$Root = $PSScriptRoot
$ZipPath = "$Root\CVSniper_Release.zip"
$NotesFile = "$Root\_release_notes_tmp.md"

# ── Validar formato de version ─────────────────────────────────────────────────
if ($Version -notmatch '^v\d+\.\d+\.\d+$') {
    Write-Host "[ERROR] Formato invalido. Usa: .\release.ps1 v1.2.0" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  CVSniper - Publicando release $Version" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

Set-Location $Root

# ── Paso 1: Generar el ZIP limpio ──────────────────────────────────────────────
Write-Host "[1/4] Generando release limpio..."
python scripts/build_release.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo build_release.py" -ForegroundColor Red; exit 1
}
Write-Host "[OK] ZIP generado`n" -ForegroundColor Green

# ── Paso 2: Commit + Tag ───────────────────────────────────────────────────────
Write-Host "[2/4] Creando tag $Version..."
$dirty = git status --short
if ($dirty) {
    Write-Host "  Hay cambios sin commitear. Commiteando automaticamente..."
    git add -A
    git commit -m "chore: release $Version"
}
git tag -a $Version -m "CVSniper $Version"
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] El tag $Version ya existe. Borralo con: git tag -d $Version" -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Tag creado`n" -ForegroundColor Green

# ── Paso 3: Push ──────────────────────────────────────────────────────────────
Write-Host "[3/4] Pusheando a GitHub..."
git push origin main
git push origin $Version
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo el push. Verifica tu conexion y credenciales." -ForegroundColor Red
    exit 1
}
Write-Host "[OK] Push completado`n" -ForegroundColor Green

# ── Paso 4: GitHub Release ────────────────────────────────────────────────────
Write-Host "[4/4] Publicando release en GitHub..."

@"
## CVSniper $Version

### Instalacion rapida en Windows
1. Descarga CVSniper_Release.zip y descomprime
2. Doble click en SETUP.bat (descarga Python y todo lo necesario automaticamente)
3. Doble click en START_CVSniper.bat
4. Configura tu perfil en el panel web que se abre automaticamente

### Requisitos
- Windows 10/11
- Google Chrome instalado
- Conexion a internet durante el primer setup (descarga Python y dependencias)

No necesitas instalar Python. El instalador lo configura automaticamente dentro de la carpeta del app.

### IA gratuita recomendada
Usa Groq: crea una cuenta gratis en https://console.groq.com, genera una API Key y pegala en el panel web.
"@ | Out-File -FilePath $NotesFile -Encoding utf8

gh release create $Version "$ZipPath#CVSniper_Release.zip" `
    --title "CVSniper $Version" `
    --notes-file $NotesFile

Remove-Item $NotesFile -ErrorAction SilentlyContinue

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Fallo gh release create. Ejecuta: gh auth login" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  RELEASE PUBLICADO" -ForegroundColor Green
Write-Host "  https://github.com/Disaqx/CVSniper/releases/tag/$Version" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
