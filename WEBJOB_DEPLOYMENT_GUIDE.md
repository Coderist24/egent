# 🚀 Azure WebJob Deployment Guide

## ⚠️ Problem: "The app container cannot be reached"

Bu hata, Azure App Service'in **durdurulmuş (stopped)** olduğunu gösterir. WebJob yüklemek için App Service'in çalışıyor olması gerekir.

---

## ✅ Çözüm 1: Azure Portal'dan Yükleme (Önerilen)

### Adım 1: App Service'i Başlatın
1. Azure Portal'da App Service'inize gidin (örn: `egent`)
2. Sol menüden **"Overview"** sekmesini açın
3. Üstteki **"Start"** butonuna tıklayın
4. Status'un **"Running"** olmasını bekleyin (1-2 dakika sürebilir)

### Adım 2: WebJob Yükleyin
1. Sol menüden **"WebJobs"** sekmesine gidin
2. Üstteki **"Add"** butonuna tıklayın
3. Aşağıdaki bilgileri girin:
   - **Name**: Örn: `sales-data-job`
   - **File Upload**: İndirdiğiniz ZIP dosyasını seçin
   - **Type**: `Triggered` (Zamanlanmış çalışma için)
   - **Triggers**: `Scheduled` seçin
   - **CRON Expression**: ZIP içindeki settings.job'dan alın (örn: `0 0 9 * * *`)
4. **"OK"** butonuna tıklayın

### Adım 3: Ortam Değişkenlerini Ayarlayın
1. Sol menüden **"Configuration"** → **"Application settings"**
2. **"New application setting"** tıklayın
3. Şu değişkenleri ekleyin:
   ```
   Name: AZURE_STORAGE_CONNECTION_STRING
   Value: DefaultEndpointsProtocol=https;AccountName=...
   ```
4. **"Save"** butonuna tıklayın

### Adım 4: WebJob'u Test Edin
1. **"WebJobs"** sekmesine dönün
2. WebJob'unuzu seçin
3. **"Run"** butonuna tıklayın
4. **"Logs"** linkinden çalışma durumunu kontrol edin

---

## ✅ Çözüm 2: Azure CLI ile Deployment (App Service kapalıyken)

### Ön Gereksinimler
```powershell
# Azure CLI kurulu mu kontrol edin
az --version

# Kurulu değilse:
# Windows: https://aka.ms/installazurecliwindows
# Mac: brew install azure-cli
# Linux: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
```

### Windows için (PowerShell)
```powershell
# Azure'a login olun
az login

# WebJob'u deploy edin
.\deploy-webjob.ps1 `
    -ResourceGroup "your-resource-group" `
    -AppServiceName "egent" `
    -WebJobName "sales-job" `
    -ZipFilePath ".\webjob_HR_Agent_1738247892.zip"
```

### Linux/Mac için (Bash)
```bash
# Azure'a login olun
az login

# Script'i çalıştırılabilir yapın
chmod +x deploy-webjob.sh

# WebJob'u deploy edin
./deploy-webjob.sh \
    your-resource-group \
    egent \
    sales-job \
    ./webjob_HR_Agent_1738247892.zip
```

---

## ✅ Çözüm 3: FTP ile Manuel Yükleme

### Adım 1: FTP Credentials Alın
```powershell
az webapp deployment list-publishing-credentials \
    --name egent \
    --resource-group your-resource-group
```

### Adım 2: FTP Client ile Bağlanın
- **Host**: `ftp://waws-prod-xyz.ftp.azurewebsites.windows.net`
- **Username**: Yukarıdaki komuttan aldığınız username
- **Password**: Yukarıdaki komuttan aldığınız password

### Adım 3: WebJob Dosyalarını Yükleyin
1. `/site/wwwroot/App_Data/jobs/triggered/` klasörüne gidin
2. WebJob için yeni bir klasör oluşturun (örn: `sales-job`)
3. ZIP içindeki tüm dosyaları bu klasöre yükleyin

---

## 📋 WebJob ZIP İçeriği

İndirdiğiniz ZIP paketi şunları içerir:

```
webjob_HR_Agent_xxx.zip
├── run.py                 # Ana Python scripti (Azure Blob'dan veri okur)
├── requirements.txt       # Python bağımlılıkları
├── settings.job          # WebJob yapılandırması (cron schedule)
├── config.json           # Agent ve data yapılandırması
└── README.md             # Deployment talimatları
```

---

## 🔧 Ortam Değişkenleri

WebJob'un çalışması için şu ortam değişkenlerinin ayarlanması gerekir:

| Variable Name | Description | Example |
|--------------|-------------|---------|
| `AZURE_STORAGE_CONNECTION_STRING` | Azure Storage bağlantı dizesi | `DefaultEndpointsProtocol=https;...` |
| `AZURE_AI_PROJECT_CONNECTION_STRING` | (Opsiyonel) AI Project bağlantısı | `...` |

### Ortam Değişkenlerini Ayarlama
```powershell
az webapp config appsettings set \
    --name egent \
    --resource-group your-resource-group \
    --settings AZURE_STORAGE_CONNECTION_STRING="your-connection-string"
```

---

## 📊 Monitoring & Logging

### Azure Portal'dan Logları Görüntüleme
1. **WebJobs** → WebJob'unuzu seçin → **"Logs"**
2. **Log Stream** → Gerçek zamanlı log akışı
3. **Application Insights** → Detaylı telemetri (eğer yapılandırılmışsa)

### Kudu Console ile Log Kontrolü
1. `https://egent.scm.azurewebsites.net` adresine gidin
2. **Debug console** → **CMD** veya **PowerShell**
3. Navigate: `site/wwwroot/App_Data/jobs/triggered/your-job-name`
4. Log dosyalarını görüntüleyin

---

## 🐛 Troubleshooting

### Problem: "The app container cannot be reached"
**Çözüm**: App Service'i başlatın (Start butonu)

### Problem: "WebJob fails to start"
**Çözüm**: 
- Ortam değişkenlerini kontrol edin
- Python runtime version uyumlu mu kontrol edin
- Logs'u inceleyin

### Problem: "Cannot find module 'azure.storage.blob'"
**Çözüm**: 
- `requirements.txt` dosyasını kontrol edin
- WebJob yeniden deploy edin

### Problem: "Connection string not found"
**Çözüm**: 
- `AZURE_STORAGE_CONNECTION_STRING` ortam değişkenini ayarlayın
- App Service'i restart edin

---

## 📞 Destek

Sorun yaşamaya devam ederseniz:
1. Azure Portal → App Service → **"Diagnose and solve problems"**
2. WebJob logs'u detaylı inceleyin
3. Application Insights ile telemetry toplayın

---

## 🎯 Özet

1. ✅ **App Service'i Başlatın** (Running durumda olmalı)
2. ✅ **WebJob'u Yükleyin** (Portal veya CLI)
3. ✅ **Ortam Değişkenlerini Ayarlayın** (Connection strings)
4. ✅ **Test Edin ve Logları Kontrol Edin**

**Başarılar! 🚀**
