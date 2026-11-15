# Kitsune Private Layer (KPL) - Devnet Orchestration Script (PowerShell)
param (
    [ValidateSet("up", "down", "logs", "status", "stress")]
    [string]$Action = "status",
    [int]$Count = 50
)

switch ($Action) {
    "up" {
        Write-Host "=== Starting 4-node KPL BFT Devnet Cluster ===" -ForegroundColor Cyan
        docker compose up -d --build
        Start-Sleep -Seconds 3
        & $PSCommandPath -Action status
    }
    "down" {
        Write-Host "=== Stopping KPL Devnet Cluster ===" -ForegroundColor Yellow
        docker compose down -v
    }
    "logs" {
        docker compose logs -f
    }
    "status" {
        Write-Host "=== KPL Local Devnet Node Status ===" -ForegroundColor Green
        foreach ($port in @(9201, 9202, 9203, 9204)) {
            Write-Host -NoNewline "Port $port : "
            try {
                $resp = Invoke-RestMethod -Uri "http://127.0.0.1:$port/status" -TimeoutSec 2
                Write-Host "$($resp.node_id) | Height: #$($resp.height) | Hash: $($resp.latest_hash.Substring(0,16))..." -ForegroundColor Green
            } catch {
                Write-Host "OFFLINE" -ForegroundColor Red
            }
        }
    }
    "stress" {
        Write-Host "=== Running Devnet Stress Benchmark ($Count TXs) ===" -ForegroundColor Cyan
        $env:KPL_NODES = "127.0.0.1:9201,127.0.0.1:9202,127.0.0.1:9203,127.0.0.1:9204"
        python scripts/stress_cluster.py $Count
    }
}
