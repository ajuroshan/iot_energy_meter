#!/bin/bash
set -e

# Log all output
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "Starting user data script..."

# Update system
apt-get update
apt-get upgrade -y

# Install Docker
apt-get install -y apt-transport-https ca-certificates curl software-properties-common git
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Start Docker
systemctl start docker
systemctl enable docker

# Add ubuntu user to docker group
usermod -aG docker ubuntu

# Create app directory
mkdir -p /opt/energy-meter
cd /opt/energy-meter

# Clone the repository
git clone https://github.com/ajuroshan/iot_energy_meter.git app

# Create .env file
cat > app/.env << 'ENVEOF'
POSTGRES_DB=energy_meter
POSTGRES_USER=postgres
POSTGRES_PASSWORD=${postgres_password}
SECRET_KEY=${django_secret_key}
ALLOWED_HOSTS=${allowed_hosts}
CSRF_TRUSTED_ORIGINS=${csrf_origins}
DJANGO_SETTINGS_MODULE=core.settings.production
MQTT_BROKER=mqtt
MQTT_PORT=1883
ENVEOF

# Set permissions
chown -R ubuntu:ubuntu /opt/energy-meter

# Start the application as ubuntu user
cd /opt/energy-meter/app
docker compose -f docker-compose.prod.yml up -d --build

echo "Deployment complete!"
