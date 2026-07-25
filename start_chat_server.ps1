# Story Studio Chat Server
# Starts both the FastAPI backend and optionally the Next.js frontend

Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║     Story Studio Chat v0.3.0            ║" -ForegroundColor Cyan
Write-Host "║   Chat-centric animation studio          ║" -ForegroundColor Cyan
Write-Host "║   12 agents connected to unified chat    ║" -ForegroundColor Cyan
Write-Host "║   Output: Remotion code                  ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

$BACKEND_PORT = 8000

# Start backend
Write-Host "Starting backend on port $BACKEND_PORT ..." -ForegroundColor Yellow
$backend = Start-Process -NoNewWindow -PassThru -FilePath "python" -ArgumentList "-m", "uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", $BACKEND_PORT

Start-Sleep -Seconds 3

try {
    $health = Invoke-RestMethod -Uri "http://localhost:$BACKEND_PORT/api/health" -ErrorAction Stop
    Write-Host "✓ Backend is running. Sessions: $($health.sessions)" -ForegroundColor Green
    
    $agents = Invoke-RestMethod -Uri "http://localhost:$BACKEND_PORT/api/agents" -ErrorAction Stop
    Write-Host "✓ $($agents.agents.Count) agents registered" -ForegroundColor Green
    foreach ($a in $agents.agents) {
        Write-Host "  - $($a.name) [$($a.mode)]" -ForegroundColor DarkGray
    }
    
    Write-Host ""
    Write-Host "API:        http://localhost:$BACKEND_PORT" -ForegroundColor Cyan
    Write-Host "WebSocket:  ws://localhost:$BACKEND_PORT/ws/{session_id}" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Press Ctrl+C to stop" -ForegroundColor DarkGray
    
    # Wait for the backend process to exit
    $backend | Wait-Process
}
catch {
    Write-Host "✗ Backend failed to start: $_" -ForegroundColor Red
    $backend | Stop-Process -Force
    exit 1
}
