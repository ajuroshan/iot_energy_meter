#!/bin/bash
set -e

# Log all output
exec > >(tee /var/log/user-data.log|logger -t user-data -s 2>/dev/console) 2>&1

echo "Starting user data script..."

# Update system
apt-get update
apt-get upgrade -y

# Install Docker
apt-get install -y apt-transport-https ca-certificates curl software-properties-common
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

# Create .env file
cat > .env << 'ENVEOF'
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

# Create docker-compose file
cat > docker-compose.yml << 'COMPOSEEOF'
services:
  db:
    image: postgres:16-alpine
    volumes:
      - pg_data:/var/lib/postgresql/data
    environment:
      POSTGRES_DB: $${POSTGRES_DB}
      POSTGRES_USER: $${POSTGRES_USER}
      POSTGRES_PASSWORD: $${POSTGRES_PASSWORD}
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"]
      interval: 5s
      timeout: 5s
      retries: 5
    restart: unless-stopped

  mqtt:
    image: eclipse-mosquitto:2
    ports:
      - "1883:1883"
      - "9001:9001"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf
      - mqtt_data:/mosquitto/data
      - mqtt_log:/mosquitto/log
    restart: unless-stopped

  web:
    image: ghcr.io/your-org/iot-energy-meter:latest
    build:
      context: ./app
      dockerfile: docker/Dockerfile
    expose:
      - "8000"
    depends_on:
      db:
        condition: service_healthy
    environment:
      - DJANGO_SETTINGS_MODULE=$${DJANGO_SETTINGS_MODULE}
      - DATABASE_URL=postgres://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@db:5432/$${POSTGRES_DB}
      - MQTT_BROKER=mqtt
      - MQTT_PORT=1883
      - SECRET_KEY=$${SECRET_KEY}
      - ALLOWED_HOSTS=$${ALLOWED_HOSTS}
      - CSRF_TRUSTED_ORIGINS=$${CSRF_TRUSTED_ORIGINS}
    volumes:
      - static_data:/app/staticfiles
    restart: unless-stopped
    command: >
      sh -c "uv run python manage.py migrate --noinput &&
             uv run python manage.py collectstatic --noinput &&
             uv run gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 2"

  mqtt_listener:
    image: ghcr.io/your-org/iot-energy-meter:latest
    build:
      context: ./app
      dockerfile: docker/Dockerfile
    depends_on:
      db:
        condition: service_healthy
      mqtt:
        condition: service_started
    environment:
      - DJANGO_SETTINGS_MODULE=$${DJANGO_SETTINGS_MODULE}
      - DATABASE_URL=postgres://$${POSTGRES_USER}:$${POSTGRES_PASSWORD}@db:5432/$${POSTGRES_DB}
      - MQTT_BROKER=mqtt
      - MQTT_PORT=1883
      - SECRET_KEY=$${SECRET_KEY}
      - ALLOWED_HOSTS=$${ALLOWED_HOSTS}
    command: uv run python manage.py mqtt_listener
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - static_data:/app/staticfiles:ro
    depends_on:
      - web
    restart: unless-stopped

volumes:
  pg_data:
  mqtt_data:
  mqtt_log:
  static_data:
COMPOSEEOF

# Create Mosquitto config
cat > mosquitto.conf << 'MQTTEOF'
persistence true
persistence_location /mosquitto/data/
log_dest stdout
listener 1883
protocol mqtt
listener 9001
protocol websockets
allow_anonymous true
MQTTEOF

# Create Nginx config
cat > nginx.conf << 'NGINXEOF'
events {
    worker_connections 1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    sendfile        on;
    keepalive_timeout  65;

    gzip on;
    gzip_types text/plain text/css application/json application/javascript text/xml application/xml;

    upstream django {
        server web:8000;
    }

    server {
        listen 80;
        server_name _;

        location /static/ {
            alias /app/staticfiles/;
            expires 30d;
        }

        location / {
            proxy_pass http://django;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
}
NGINXEOF

# Set permissions
chown -R ubuntu:ubuntu /opt/energy-meter

echo "User data script completed!"
echo "To deploy the application:"
echo "1. Clone your repository to /opt/energy-meter/app"
echo "2. Run: cd /opt/energy-meter && docker compose up -d"
