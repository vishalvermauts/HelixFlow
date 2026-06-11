param (
    [Parameter(Mandatory=$true, HelpMessage="Path to your private SSH key file (e.g. C:\Users\mcmur\Desktop\Router\HelixFlow\HelixFlow)")]
    [string]$PrivateKeyPath,
    
    [string]$IpAddress = "165.227.185.117"
)

$ErrorActionPreference = 'Stop'

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "🚀 DEPLOYING DEDICATED INFERENCE ROUTER (HELIXFLOW) TO $IpAddress" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Test SSH Connection
Write-Host "Checking SSH connection..." -ForegroundColor Yellow
$connectionTest = ssh -i $PrivateKeyPath -o StrictHostKeyChecking=no -o ConnectTimeout=5 helix@$IpAddress "echo 'Connection Successful'"
if ($connectionTest -ne "Connection Successful") {
    Write-Error "Could not connect to the droplet. Please verify the Private Key Path or Droplet IP."
    exit
}
Write-Host "✅ SSH Connection Verified!" -ForegroundColor Green

# 2. Restart Helix Engine (to pick up routing changes if needed)
Write-Host "Restarting Helix Engine..." -ForegroundColor Yellow
$cleanupCommand = @"
sudo systemctl restart helixflow-gateway || true
"@
ssh -i $PrivateKeyPath helix@$IpAddress $cleanupCommand

# 3. Setup Target Directory
Write-Host "Preparing target directories on Droplet..." -ForegroundColor Yellow
ssh -i $PrivateKeyPath helix@$IpAddress "sudo mkdir -p /opt/helixflow-gateway && sudo chown -R helix:helix /opt/helixflow-gateway"

# 4. Compress HelixFlow locally
Write-Host "Compressing HelixFlow Gateway locally..." -ForegroundColor Yellow
if (Test-Path "helixflow-gateway.tar.gz") { Remove-Item "helixflow-gateway.tar.gz" }
# Exclude keys and virtual environments
tar -czf helixflow-gateway.tar.gz --exclude="venv" --exclude="__pycache__" --exclude=".git" --exclude="HelixFlow" --exclude="HelixFlow.pub" --exclude="helixflow-gateway.tar.gz" -C "C:\Users\mcmur\Desktop\Router\HelixFlow" .

# 5. Upload archive to Droplet via SCP
Write-Host "Uploading archive..." -ForegroundColor Yellow
scp -i $PrivateKeyPath -o StrictHostKeyChecking=no "helixflow-gateway.tar.gz" "helix@${IpAddress}:/tmp/helixflow-gateway.tar.gz"

# 6. Extract files on Droplet
Write-Host "Extracting archive on Droplet..." -ForegroundColor Yellow
ssh -i $PrivateKeyPath helix@$IpAddress "sudo rm -rf /opt/helixflow-gateway/* && tar -xzf /tmp/helixflow-gateway.tar.gz -C /opt/helixflow-gateway/"

# Clean up local archive
Remove-Item "helixflow-gateway.tar.gz"

# 7. Run setup commands on droplet (Install Redis, create virtual environment, configure systemd)
Write-Host "Running remote installation and startup commands on Droplet..." -ForegroundColor Yellow

$remoteCommand = @"
set -e
echo 'Installing Redis Server...'
sudo apt-get update && sudo apt-get install -y redis-server
sudo systemctl enable redis-server
sudo systemctl start redis-server

echo 'Building HelixFlow Gateway Virtual Environment...'
cd /opt/helixflow-gateway
python3 -m venv venv
./venv/bin/pip install --upgrade pip setuptools wheel
./venv/bin/pip install -r helixflow_gateway/requirements.txt

echo 'Configuring HelixFlow Gateway systemd service (Port 8000)...'
cat << 'EOF' | sudo tee /etc/systemd/system/helixflow-gateway.service > /dev/null
[Unit]
Description=HelixFlow Gateway Router
After=network.target redis-server.service

[Service]
User=helix
WorkingDirectory=/opt/helixflow-gateway
Environment="PATH=/opt/helixflow-gateway/venv/bin"
ExecStart=/opt/helixflow-gateway/venv/bin/uvicorn helixflow_gateway.bootstrap:create_app --host 0.0.0.0 --port 8000 --factory --loop uvloop --workers 4
Restart=always

[Install]
WantedBy=multi-user.target
EOF

echo 'Reloading Systemd & Starting HelixFlow Gateway...'
sudo systemctl daemon-reload
sudo systemctl enable helixflow-gateway
sudo systemctl restart helixflow-gateway

# Clean up remote archive
rm -f /tmp/helixflow-gateway.tar.gz

echo '=== Setup Completed Successfully! ==='
"@

ssh -i $PrivateKeyPath helix@$IpAddress $remoteCommand

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "🎉 DEDICATED INFERENCE ROUTER SUCCESSFULLY DEPLOYED!" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "HelixFlow Gateway Stream: http://$IpAddress:8000/stream" -ForegroundColor Cyan
Write-Host "HelixFlow Gateway Health: http://$IpAddress:8000/health" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Green
