# Azure WebJob Deployment Script
# This script deploys a WebJob without starting the App Service

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [Parameter(Mandatory=$true)]
    [string]$AppServiceName,
    
    [Parameter(Mandatory=$true)]
    [string]$WebJobName,
    
    [Parameter(Mandatory=$true)]
    [string]$ZipFilePath,
    
    [Parameter(Mandatory=$false)]
    [string]$WebJobType = "triggered"  # triggered or continuous
)

Write-Host "🚀 Deploying WebJob to Azure..." -ForegroundColor Cyan

# Check if Azure CLI is installed
if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Azure CLI is not installed. Please install it first." -ForegroundColor Red
    Write-Host "Download from: https://aka.ms/installazurecliwindows" -ForegroundColor Yellow
    exit 1
}

# Check if logged in
$account = az account show 2>$null
if (-not $account) {
    Write-Host "🔐 Please login to Azure..." -ForegroundColor Yellow
    az login
}

# Check if ZIP file exists
if (-not (Test-Path $ZipFilePath)) {
    Write-Host "❌ ZIP file not found: $ZipFilePath" -ForegroundColor Red
    exit 1
}

Write-Host "📦 ZIP File: $ZipFilePath" -ForegroundColor Green
Write-Host "🎯 Target: $AppServiceName (Resource Group: $ResourceGroup)" -ForegroundColor Green
Write-Host "📝 WebJob Name: $WebJobName" -ForegroundColor Green
Write-Host "⚙️  WebJob Type: $WebJobType" -ForegroundColor Green

# Deploy WebJob using Kudu API (doesn't require App Service to be running)
Write-Host "`n🔄 Uploading WebJob..." -ForegroundColor Cyan

$result = az webapp deployment source config-zip `
    --resource-group $ResourceGroup `
    --name $AppServiceName `
    --src $ZipFilePath `
    2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ WebJob deployed successfully!" -ForegroundColor Green
    Write-Host "`n📋 Next Steps:" -ForegroundColor Cyan
    Write-Host "1. Start your App Service in Azure Portal" -ForegroundColor White
    Write-Host "2. Go to WebJobs section to run or schedule the job" -ForegroundColor White
    Write-Host "3. Configure environment variables (AZURE_STORAGE_CONNECTION_STRING)" -ForegroundColor White
} else {
    Write-Host "❌ Deployment failed!" -ForegroundColor Red
    Write-Host $result -ForegroundColor Red
    exit 1
}
