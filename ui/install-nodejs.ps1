# Node.js Installation Script for Windows
# Run this in PowerShell as Administrator

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Node.js Installation Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if running as Administrator
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
$isAdmin = $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $isAdmin) {
    Write-Host "⚠️  This script needs to run as Administrator" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Please:" -ForegroundColor Yellow
    Write-Host "1. Right-click PowerShell" -ForegroundColor White
    Write-Host "2. Select 'Run as Administrator'" -ForegroundColor White
    Write-Host "3. Run this script again" -ForegroundColor White
    Write-Host ""
    Write-Host "Or use the manual installation:" -ForegroundColor Yellow
    Write-Host "https://nodejs.org/dist/v20.18.0/node-v20.18.0-x64.msi" -ForegroundColor Cyan
    exit 1
}

Write-Host "✅ Running as Administrator" -ForegroundColor Green
Write-Host ""

# Check if Node.js is already installed
Write-Host "Checking for existing Node.js installation..." -ForegroundColor Cyan
try {
    $nodeVersion = node --version 2>$null
    if ($nodeVersion) {
        Write-Host "✅ Node.js is already installed: $nodeVersion" -ForegroundColor Green
        $npmVersion = npm --version 2>$null
        Write-Host "✅ npm version: $npmVersion" -ForegroundColor Green
        Write-Host ""
        Write-Host "You're ready to go! Run:" -ForegroundColor Green
        Write-Host "  cd ui" -ForegroundColor White
        Write-Host "  npm install" -ForegroundColor White
        Write-Host "  npm run dev" -ForegroundColor White
        exit 0
    }
} catch {
    Write-Host "Node.js not found. Installing..." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Installing Chocolatey package manager..." -ForegroundColor Cyan

# Install Chocolatey
Set-ExecutionPolicy Bypass -Scope Process -Force
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072
try {
    Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))
    Write-Host "✅ Chocolatey installed successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to install Chocolatey" -ForegroundColor Red
    Write-Host "Please install Node.js manually from: https://nodejs.org" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "Installing Node.js LTS..." -ForegroundColor Cyan

# Install Node.js using Chocolatey
try {
    choco install nodejs-lts -y
    Write-Host "✅ Node.js installed successfully" -ForegroundColor Green
} catch {
    Write-Host "❌ Failed to install Node.js" -ForegroundColor Red
    Write-Host "Please install Node.js manually from: https://nodejs.org" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Installation Complete! 🎉" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  IMPORTANT: Close this PowerShell window and open a new one" -ForegroundColor Yellow
Write-Host ""
Write-Host "Then run:" -ForegroundColor Cyan
Write-Host "  node --version" -ForegroundColor White
Write-Host "  npm --version" -ForegroundColor White
Write-Host ""
Write-Host "To start the UI:" -ForegroundColor Cyan
Write-Host "  cd ui" -ForegroundColor White
Write-Host "  npm install" -ForegroundColor White
Write-Host "  npm run dev" -ForegroundColor White
Write-Host ""
