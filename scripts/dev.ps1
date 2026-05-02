# PowerShell helper para Windows — equivalente al Makefile.
# Uso: .\scripts\dev.ps1 <comando>
param(
    [Parameter(Position=0)]
    [ValidateSet("up", "down", "logs", "rebuild", "test", "seed", "eval", "ragas", "security", "clean", "help")]
    [string]$Command = "help"
)

$ErrorActionPreference = "Stop"

switch ($Command) {
    "up"       { docker compose up --build -d }
    "down"     { docker compose down }
    "logs"     { docker compose logs -f backend }
    "rebuild"  {
        docker compose build --no-cache backend frontend
        docker compose up -d
    }
    "test"     { docker compose exec backend pytest -q }
    "seed"     { docker compose exec backend python -m app.scripts.seed_tenants }
    "eval"     { python evaluation/scripts/run_evaluation.py }
    "ragas"    { python evaluation/scripts/ragas_eval.py }
    "security" { python evaluation/scripts/security_eval.py }
    "clean"    {
        docker compose down -v
        Remove-Item -Force -ErrorAction SilentlyContinue evaluation/results/*.json
        Remove-Item -Force -ErrorAction SilentlyContinue evaluation/results/*.csv
    }
    default {
        Write-Host "Comandos disponibles:" -ForegroundColor Cyan
        Write-Host "  up        - docker compose up --build -d"
        Write-Host "  down      - detener contenedores"
        Write-Host "  logs      - seguir logs del backend"
        Write-Host "  rebuild   - rebuild backend + frontend"
        Write-Host "  test      - pytest dentro del backend"
        Write-Host "  seed      - re-ejecutar seed"
        Write-Host "  eval      - run_evaluation.py"
        Write-Host "  ragas     - ragas_eval.py"
        Write-Host "  security  - security_eval.py"
        Write-Host "  clean     - borrar volumenes + resultados"
    }
}
