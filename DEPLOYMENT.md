# Deployment Guide

This guide covers deploying the Stock News API to production.

## Pre-Deployment Checklist

### 1. Environment Configuration

Create a production `.env` file in the `backend/` directory:

```env
# Application
DEBUG=false
LOG_LEVEL=WARNING

# Database (use absolute paths in production)
DATABASE_URL=sqlite:////app/data/news.db
SCHEDULER_DB_URL=sqlite:////app/data/scheduler.db

# Ollama
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODEL_ANALYSIS=llama3.1
OLLAMA_MODEL_NER=llama3.1
OLLAMA_MODEL_WHISPER=whisper
OLLAMA_TIMEOUT=300

# Processing
MAX_CONCURRENT_FETCHES=3
DATA_RETENTION_DAYS=90
AUTO_DISABLE_THRESHOLD=5

# CORS (add your production domain)
CORS_ORIGINS=["https://yourdomain.com"]
```

### 2. Security Hardening

**a) Update docker-compose.yml for production:**

```yaml
services:
  backend:
    restart: always
    environment:
      - DEBUG=false
    # Remove port exposure if using a reverse proxy
    # ports:
    #   - "8000:8000"

  frontend:
    restart: always
    # Expose only through reverse proxy
    # ports:
    #   - "3000:80"

  ollama:
    restart: always
    # Don't expose Ollama port publicly
    # Remove or comment out:
    # ports:
    #   - "11434:11434"
```

**b) Add resource limits:**

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '1'
          memory: 2G

  ollama:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 6G
```

**c) Use secrets for sensitive data:**

Instead of environment variables, consider using Docker secrets for production.

### 3. Reverse Proxy Setup

Example Nginx configuration:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    # Frontend
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }

    # Backend API
    location /api {
        proxy_pass http://localhost:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API docs
    location /docs {
        proxy_pass http://localhost:8000;
    }
}
```

### 4. SSL/TLS Certificates

**Option A: Let's Encrypt (Recommended)**

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d yourdomain.com

# Auto-renewal is configured automatically
```

**Option B: Manual Certificates**

Place your certificates in a secure location and reference them in your Nginx config.

### 5. Monitoring Setup

**a) Enable application logs:**

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

**b) Set up health checks:**

```yaml
services:
  backend:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/api/v1/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
```

**c) Monitor with external tools:**

Consider using:
- **Uptime monitoring**: UptimeRobot, Pingdom
- **Log aggregation**: ELK Stack, Grafana Loki
- **Metrics**: Prometheus + Grafana

### 6. Backup Strategy

**a) Database backups:**

```bash
# Create backup script
cat > backup.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Backup databases
docker cp newsapi-backend-1:/app/data/news.db $BACKUP_DIR/news_$TIMESTAMP.db
docker cp newsapi-backend-1:/app/data/scheduler.db $BACKUP_DIR/scheduler_$TIMESTAMP.db

# Keep only last 30 days
find $BACKUP_DIR -name "*.db" -mtime +30 -delete
EOF

chmod +x backup.sh

# Add to cron
crontab -e
# Add: 0 2 * * * /path/to/backup.sh
```

**b) Volume backups:**

```bash
# Backup volumes
docker run --rm \
  -v newsapi_ollama-data:/source \
  -v /backups:/backup \
  alpine tar czf /backup/ollama_$(date +%Y%m%d).tar.gz -C /source .
```

## Deployment Steps

### 1. Server Preparation

```bash
# Update system
sudo apt-get update && sudo apt-get upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Install Docker Compose
sudo apt-get install docker-compose-plugin

# Create application user
sudo useradd -m -s /bin/bash newsapi
sudo usermod -aG docker newsapi
```

### 2. Deploy Application

```bash
# Switch to application user
sudo su - newsapi

# Clone repository
git clone <repository-url> newsapi
cd newsapi

# Create data directories
mkdir -p data downloads

# Copy and configure environment
cp backend/.env.example backend/.env
nano backend/.env  # Edit for production

# Start services
docker-compose up -d

# Check status
docker-compose ps
```

### 3. Initialize Models

```bash
# Pull LLM models
docker exec -it newsapi-ollama-1 ollama pull llama3.1
docker exec -it newsapi-ollama-1 ollama pull whisper

# Verify models
docker exec -it newsapi-ollama-1 ollama list
```

### 4. Verify Deployment

```bash
# Check all services are running
docker-compose ps

# Check logs for errors
docker-compose logs --tail=50

# Test health endpoint
curl http://localhost:8000/api/v1/health

# Test frontend
curl http://localhost:3000
```

### 5. Set Up Reverse Proxy

Follow the Nginx configuration above and enable it:

```bash
sudo ln -s /etc/nginx/sites-available/newsapi /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

## Post-Deployment

### 1. Create First Data Source

```bash
curl -X POST https://yourdomain.com/api/v1/sources \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Yahoo Finance",
    "url": "https://finance.yahoo.com/news",
    "source_type": "website",
    "fetch_frequency_minutes": 120
  }'
```

### 2. Monitor Logs

```bash
# Watch backend logs
docker-compose logs -f backend

# Check for errors
docker-compose logs backend | grep ERROR

# Monitor resource usage
docker stats
```

### 3. Set Up Automated Maintenance

Create a maintenance script:

```bash
cat > maintenance.sh << 'EOF'
#!/bin/bash

# Backup databases
./backup.sh

# Clean up old Docker images
docker image prune -af --filter "until=72h"

# Restart services (optional, for memory leaks)
# docker-compose restart backend
EOF

chmod +x maintenance.sh

# Add to cron (runs weekly)
crontab -e
# Add: 0 3 * * 0 /home/newsapi/newsapi/maintenance.sh
```

## Scaling Considerations

### Horizontal Scaling

For high-traffic deployments:

1. **Separate Ollama**: Run Ollama on dedicated GPU server
2. **Load Balancer**: Use Nginx/HAProxy for multiple backend instances
3. **Shared Storage**: Use NFS or object storage for downloads
4. **Database**: Migrate from SQLite to PostgreSQL

Example multi-instance setup:

```yaml
services:
  backend-1:
    <<: *backend
    container_name: newsapi-backend-1

  backend-2:
    <<: *backend
    container_name: newsapi-backend-2

  nginx-lb:
    image: nginx:alpine
    ports:
      - "8000:80"
    volumes:
      - ./nginx-lb.conf:/etc/nginx/nginx.conf
```

### Vertical Scaling

If running on a single powerful server:

- Increase `MAX_CONCURRENT_FETCHES` (4-6)
- Allocate more CPU/memory to containers
- Use faster storage (SSD/NVMe)

## Updating the Application

```bash
# Pull latest code
git pull

# Rebuild containers
docker-compose build

# Restart with new images
docker-compose up -d

# Check logs for issues
docker-compose logs -f
```

## Rollback Procedure

If something goes wrong:

```bash
# Revert to previous version
git checkout <previous-commit>

# Rebuild and restart
docker-compose build
docker-compose up -d

# Restore database from backup if needed
docker cp /backups/news_TIMESTAMP.db newsapi-backend-1:/app/data/news.db
docker-compose restart backend
```

## Troubleshooting

### High Memory Usage

```bash
# Check stats
docker stats

# Restart ollama to free memory
docker-compose restart ollama
```

### Disk Space Issues

```bash
# Clean old downloads
docker exec newsapi-backend-1 find /app/downloads -mtime +7 -delete

# Clean Docker
docker system prune -a
```

### Failed Fetches

Check logs and increase timeouts:

```env
OLLAMA_TIMEOUT=600
```

## Security Checklist

- [ ] DEBUG mode disabled
- [ ] Strong firewall rules
- [ ] SSL/TLS enabled
- [ ] Ports not publicly exposed (except 80/443)
- [ ] Regular backups configured
- [ ] Log rotation enabled
- [ ] CORS properly configured
- [ ] Regular security updates
- [ ] Monitoring alerts set up

## Support

For deployment issues:
1. Check logs: `docker-compose logs`
2. Review health endpoint: `/api/v1/health`
3. Open an issue on GitHub

---

**Production Deployment Complete!** 🚀
