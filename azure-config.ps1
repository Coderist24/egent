# Azure Web App Configuration Script
# Bu script'i PowerShell'de çalıştırarak environment variables'ları Azure Web App'e set edebilirsiniz

$resourceGroup = "your-resource-group-name"  # Resource group adınızı buraya yazın
$webAppName = "egentapp-b4gqeudnc3h8emd3"

Write-Host "🔧 Azure Web App Configuration Script" -ForegroundColor Blue
Write-Host "================================================" -ForegroundColor Blue

# Azure authentication check
Write-Host "🔍 Azure CLI authentication kontrol ediliyor..." -ForegroundColor Yellow
$account = az account show --output json 2>$null
if (-not $account) {
    Write-Host "❌ Azure CLI'ye giriş yapmanız gerekiyor!" -ForegroundColor Red
    Write-Host "Lütfen 'az login' komutunu çalıştırın." -ForegroundColor Yellow
    exit 1
}

Write-Host "✅ Azure CLI authenticated" -ForegroundColor Green

# Application Settings
$appSettings = @{
    "AZURE_CLIENT_ID" = "c7790b94-d830-4746-961f-8c715a380c5e"
    "AZURE_TENANT_ID" = "7ae3526a-96fa-407a-9b02-9fe5bdff6217"
    "AZURE_CLIENT_SECRET" = "6Jl8Q~Kue3BfEbXdbc3O-68WVEIPZeNFD-Bkub2p"
    "REDIRECT_URI" = "https://egentapp-b4gqeudnc3h8emd3.westeurope-01.azurewebsites.net/"
    "DEV_MODE" = "false"
    "USE_MANAGED_IDENTITY" = "true"
    "AZURE_STORAGE_CONNECTION_STRING" = "DefaultEndpointsProtocol=https;AccountName=egenthub7616267901;AccountKey=gQPagF4oAGn3KToKSSIXdtPDxGlW1pHYjBLiAR8VldtfaLOO4iZ1D6gNidyqnjGP6yKDRleJTeOJ+AStYe2LTQ==;EndpointSuffix=core.windows.net"
    "AZURE_SEARCH_SERVICE_ENDPOINT" = "https://egesearchindex.search.windows.net"
    "AZURE_SEARCH_ADMIN_KEY" = "IVMK9OMEVHJxlOLBI88BMIpYr3AeP95zwfDmSfD1k1AzSeCinJJT"
    "AZURE_STORAGE_ACCOUNT_NAME" = "egenthub7616267901"
    "OPENAI_API_KEY" = "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"
    "WEBSITE_SITE_NAME" = "egentapp-b4gqeudnc3h8emd3"
    "PORT" = "8000"
    "PYTHONPATH" = "/home/site/wwwroot"
    "PYTHONUNBUFFERED" = "1"
    "WEBSITE_RUN_FROM_PACKAGE" = "1"
    "SCM_DO_BUILD_DURING_DEPLOYMENT" = "true"
    "STREAMLIT_SERVER_PORT" = "8000"
    "STREAMLIT_SERVER_ADDRESS" = "0.0.0.0"
    "STREAMLIT_BROWSER_GATHER_USAGE_STATS" = "false"
    "STREAMLIT_SERVER_HEADLESS" = "true"
    "STREAMLIT_SERVER_ENABLE_CORS" = "false"
    "STREAMLIT_SERVER_ENABLE_XSRF_PROTECTION" = "false"
}

Write-Host "📝 Application Settings ayarlanıyor..." -ForegroundColor Yellow

foreach ($setting in $appSettings.GetEnumerator()) {
    Write-Host "   Setting: $($setting.Name)" -ForegroundColor Gray
    $result = az webapp config appsettings set --name $webAppName --resource-group $resourceGroup --settings "$($setting.Name)=$($setting.Value)" --output none
    if ($LASTEXITCODE -eq 0) {
        Write-Host "   ✅ $($setting.Name) = $($setting.Value)" -ForegroundColor Green
    } else {
        Write-Host "   ❌ Failed to set $($setting.Name)" -ForegroundColor Red
    }
}

# Startup Command
Write-Host "🚀 Startup command ayarlanıyor..." -ForegroundColor Yellow
$startupResult = az webapp config set --name $webAppName --resource-group $resourceGroup --startup-file "python app_startup.py" --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Startup command set: python app_startup.py" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to set startup command" -ForegroundColor Red
}

# Restart Web App
Write-Host "🔄 Web App restart ediliyor..." -ForegroundColor Yellow
$restartResult = az webapp restart --name $webAppName --resource-group $resourceGroup --output none

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Web App restarted successfully" -ForegroundColor Green
} else {
    Write-Host "❌ Failed to restart Web App" -ForegroundColor Red
}

Write-Host "================================================" -ForegroundColor Blue
Write-Host "🎉 Configuration completed!" -ForegroundColor Green
Write-Host "🌐 Web App URL: https://$webAppName.azurewebsites.net" -ForegroundColor Cyan
Write-Host "📋 Log monitoring: az webapp log tail --name $webAppName --resource-group $resourceGroup" -ForegroundColor Yellow

# Optional: Open logs
$openLogs = Read-Host "📋 Canlı logları açmak ister misiniz? (y/n)"
if ($openLogs -eq "y" -or $openLogs -eq "Y") {
    Write-Host "📋 Log stream açılıyor... (Ctrl+C ile kapatabilirsiniz)" -ForegroundColor Yellow
    az webapp log tail --name $webAppName --resource-group $resourceGroup
}
