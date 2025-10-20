#!/bin/bash
# Azure WebJob Deployment Script (Bash version for Linux/Mac)

# Configuration
RESOURCE_GROUP="$1"
APP_SERVICE_NAME="$2"
WEBJOB_NAME="$3"
ZIP_FILE_PATH="$4"

# Check parameters
if [ -z "$RESOURCE_GROUP" ] || [ -z "$APP_SERVICE_NAME" ] || [ -z "$WEBJOB_NAME" ] || [ -z "$ZIP_FILE_PATH" ]; then
    echo "❌ Usage: $0 <resource-group> <app-service-name> <webjob-name> <zip-file-path>"
    echo "📝 Example: $0 my-rg my-webapp sales-job ./webjob_HR_Agent_1234.zip"
    exit 1
fi

echo "🚀 Deploying WebJob to Azure..."
echo "📦 ZIP File: $ZIP_FILE_PATH"
echo "🎯 Target: $APP_SERVICE_NAME (Resource Group: $RESOURCE_GROUP)"
echo "📝 WebJob Name: $WEBJOB_NAME"

# Check if Azure CLI is installed
if ! command -v az &> /dev/null; then
    echo "❌ Azure CLI is not installed. Please install it first."
    echo "Visit: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi

# Check if logged in
az account show > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "🔐 Please login to Azure..."
    az login
fi

# Check if ZIP file exists
if [ ! -f "$ZIP_FILE_PATH" ]; then
    echo "❌ ZIP file not found: $ZIP_FILE_PATH"
    exit 1
fi

# Deploy using Kudu API
echo ""
echo "🔄 Uploading WebJob via Kudu API..."

# Get publishing credentials
PUBLISH_CREDS=$(az webapp deployment list-publishing-credentials \
    --resource-group "$RESOURCE_GROUP" \
    --name "$APP_SERVICE_NAME" \
    --query "{username:publishingUserName, password:publishingPassword}" \
    -o tsv)

USERNAME=$(echo "$PUBLISH_CREDS" | cut -f1)
PASSWORD=$(echo "$PUBLISH_CREDS" | cut -f2)

# Upload WebJob
curl -X PUT \
    --user "$USERNAME:$PASSWORD" \
    --data-binary "@$ZIP_FILE_PATH" \
    "https://$APP_SERVICE_NAME.scm.azurewebsites.net/api/triggeredwebjobs/$WEBJOB_NAME"

if [ $? -eq 0 ]; then
    echo "✅ WebJob deployed successfully!"
    echo ""
    echo "📋 Next Steps:"
    echo "1. Start your App Service in Azure Portal (if not running)"
    echo "2. Go to WebJobs section to run or schedule the job"
    echo "3. Configure environment variables (AZURE_STORAGE_CONNECTION_STRING)"
else
    echo "❌ Deployment failed!"
    exit 1
fi
