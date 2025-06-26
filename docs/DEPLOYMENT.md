# Deployment Guide

## Overview

This guide covers deploying the SlackOpsBot Slack Bot to various environments, from local development to production servers.

## Prerequisites

- Python 3.13+
- Django 4.2+
- PostgreSQL (for production)
- Redis (optional, for caching)
- SSL certificate (for production)
- Domain name with DNS control

## Environment Configurations

### Development

**Local Development with ngrok:**

1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up ngrok**
   ```bash
   ./deployment/setup_ngrok.sh
   ```

3. **Configure environment**
   ```bash
   cp config/environment.example .env
   # Edit .env with your credentials
   ```

4. **Start development server**
   ```bash
   ./start_dev.sh
   ```

**Development URLs:**
- Django: `http://localhost:8000`
- ngrok: `https://secretly-pretty-swine.ngrok-free.app`

### Staging

**Docker-based staging environment:**

1. **Create Dockerfile**
   ```dockerfile
   FROM python:3.13-slim

   WORKDIR /app

   # Install system dependencies
   RUN apt-get update && apt-get install -y \
       gcc \
       && rm -rf /var/lib/apt/lists/*

   # Install Python dependencies
   COPY requirements.txt .
   RUN pip install --no-cache-dir -r requirements.txt

   # Copy application
   COPY . .

   # Collect static files
   RUN python manage.py collectstatic --noinput

   # Expose port
   EXPOSE 8000

   # Run server
   CMD ["gunicorn", "--bind", "0.0.0.0:8000", "slack_bot.wsgi:application"]
   ```

2. **Create docker-compose.yml**
   ```yaml
   version: '3.8'
   services:
     web:
       build: .
       ports:
         - "8000:8000"
       environment:
         - DEBUG=False
         - DATABASE_URL=postgresql://user:pass@db:5432/slackbot
       depends_on:
         - db
       volumes:
         - ./logs:/app/logs

     db:
       image: postgres:15
       environment:
         POSTGRES_DB: slackbot
         POSTGRES_USER: user
         POSTGRES_PASSWORD: pass
       volumes:
         - postgres_data:/var/lib/postgresql/data

     nginx:
       image: nginx:alpine
       ports:
         - "80:80"
         - "443:443"
       volumes:
         - ./nginx.conf:/etc/nginx/nginx.conf
         - ./ssl:/etc/ssl
       depends_on:
         - web

   volumes:
     postgres_data:
   ```

3. **Deploy to staging**
   ```bash
   docker-compose up -d
   ```

### Production

**AWS EC2 with PostgreSQL RDS:**

#### Server Setup

1. **Launch EC2 instance**
   - Ubuntu 22.04 LTS
   - t3.medium or larger
   - Security groups: HTTP (80), HTTPS (443), SSH (22)

2. **Install dependencies**
   ```bash
   sudo apt update
   sudo apt install -y python3.13 python3-pip nginx postgresql-client supervisor
   ```

3. **Create application user**
   ```bash
   sudo useradd -m -s /bin/bash slackbot
   sudo su - slackbot
   ```

4. **Deploy application**
   ```bash
   git clone <repository-url> /home/slackbot/app
   cd /home/slackbot/app
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   pip install gunicorn psycopg2-binary
   ```

#### Database Setup

1. **Create RDS PostgreSQL instance**
   - PostgreSQL 15+
   - Multi-AZ for production
   - Backup retention: 7+ days

2. **Configure database**
   ```bash
   export DATABASE_URL="postgresql://username:password@rds-endpoint:5432/dbname"
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```

#### Web Server Configuration

1. **Create Gunicorn service**
   ```ini
   # /etc/supervisor/conf.d/slackbot.conf
   [program:slackbot]
   command=/home/slackbot/app/venv/bin/gunicorn --workers 3 --bind unix:/home/slackbot/app/gunicorn.sock slack_bot.wsgi:application
   directory=/home/slackbot/app
   user=slackbot
   autostart=true
   autorestart=true
   redirect_stderr=true
   stdout_logfile=/var/log/slackbot.log
   environment=PATH="/home/slackbot/app/venv/bin"
   ```

2. **Configure Nginx**
   ```nginx
   # /etc/nginx/sites-available/slackbot
   server {
       listen 80;
       server_name your-domain.com;
       return 301 https://$server_name$request_uri;
   }

   server {
       listen 443 ssl http2;
       server_name your-domain.com;

       ssl_certificate /path/to/ssl/cert.pem;
       ssl_certificate_key /path/to/ssl/private.key;

       location / {
           proxy_pass http://unix:/home/slackbot/app/gunicorn.sock;
           proxy_set_header Host $host;
           proxy_set_header X-Real-IP $remote_addr;
           proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
           proxy_set_header X-Forwarded-Proto $scheme;
       }

       location /static/ {
           alias /home/slackbot/app/staticfiles/;
       }
   }
   ```

3. **Enable and start services**
   ```bash
   sudo supervisorctl reread
   sudo supervisorctl update
   sudo supervisorctl start slackbot
   sudo ln -s /etc/nginx/sites-available/slackbot /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl restart nginx
   ```

## Environment Variables

### Production Environment Variables

```bash
# Required
SLACK_BOT_TOKEN=xoxb-production-token
SLACK_SIGNING_SECRET=production-signing-secret
GEMINI_API_KEY=production-gemini-key
DJANGO_SECRET_KEY=production-secret-key

# Production settings
DEBUG=False
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
DATABASE_URL=postgresql://user:pass@rds-endpoint:5432/dbname

# Optional: Enhanced features
SENTRY_DSN=https://sentry-dsn-url
REDIS_URL=redis://localhost:6379/0

# Security
SECURE_SSL_REDIRECT=True
SECURE_PROXY_SSL_HEADER=HTTP_X_FORWARDED_PROTO,https
```

## Monitoring & Logging

### Application Monitoring

1. **Sentry for error tracking**
   ```python
   # Add to settings.py
   import sentry_sdk
   from sentry_sdk.integrations.django import DjangoIntegration

   sentry_sdk.init(
       dsn=os.getenv('SENTRY_DSN'),
       integrations=[DjangoIntegration()],
       traces_sample_rate=0.1,
   )
   ```

2. **Health check monitoring**
   ```bash
   # Add to crontab
   */5 * * * * curl -f https://your-domain.com/health/ || echo "Health check failed"
   ```

### Log Management

1. **Configure Django logging**
   ```python
   # settings.py
   LOGGING = {
       'version': 1,
       'disable_existing_loggers': False,
       'handlers': {
           'file': {
               'level': 'INFO',
               'class': 'logging.handlers.RotatingFileHandler',
               'filename': '/var/log/slackbot/django.log',
               'maxBytes': 1024*1024*10,  # 10MB
               'backupCount': 5,
           },
       },
       'loggers': {
           '': {
               'handlers': ['file'],
               'level': 'INFO',
               'propagate': True,
           },
       },
   }
   ```

2. **Log rotation**
   ```bash
   # /etc/logrotate.d/slackbot
   /var/log/slackbot/*.log {
       daily
       missingok
       rotate 30
       compress
       delaycompress
       notifempty
       create 644 slackbot slackbot
   }
   ```

## SSL Certificate

### Let's Encrypt (Free)

```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d your-domain.com

# Auto-renewal
sudo crontab -e
# Add: 0 12 * * * /usr/bin/certbot renew --quiet
```

### Custom Certificate

```bash
# Copy certificate files
sudo cp your-cert.pem /etc/ssl/certs/
sudo cp your-key.pem /etc/ssl/private/
sudo chmod 600 /etc/ssl/private/your-key.pem
```

## Performance Optimization

### Database Optimization

1. **Connection pooling**
   ```python
   # settings.py
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.postgresql',
           'OPTIONS': {
               'MAX_CONNS': 20,
               'CONN_MAX_AGE': 60,
           }
       }
   }
   ```

2. **Query optimization**
   ```python
   # Use select_related and prefetch_related
   # Index frequently queried fields
   # Use database-level constraints
   ```

### Caching

1. **Redis caching**
   ```python
   # settings.py
   CACHES = {
       'default': {
           'BACKEND': 'django_redis.cache.RedisCache',
           'LOCATION': 'redis://127.0.0.1:6379/1',
           'OPTIONS': {
               'CLIENT_CLASS': 'django_redis.client.DefaultClient',
           }
       }
   }
   ```

## Backup Strategy

### Database Backups

```bash
#!/bin/bash
# backup-db.sh
DATE=$(date +%Y%m%d_%H%M%S)
pg_dump $DATABASE_URL > /backups/slackbot_$DATE.sql
find /backups -name "slackbot_*.sql" -mtime +7 -delete
```

### Application Backups

```bash
#!/bin/bash
# backup-app.sh
DATE=$(date +%Y%m%d_%H%M%S)
tar -czf /backups/app_$DATE.tar.gz /home/slackbot/app --exclude=venv
find /backups -name "app_*.tar.gz" -mtime +30 -delete
```

## Scaling Considerations

### Horizontal Scaling

1. **Load balancer configuration**
2. **Database read replicas**
3. **Shared Redis cache**
4. **Session store externalization**

### Vertical Scaling

1. **CPU optimization**: Gunicorn workers tuning
2. **Memory optimization**: Connection pooling
3. **I/O optimization**: SSD storage, database indexing

## Security Checklist

- [ ] Environment variables secured
- [ ] SSL/TLS enabled
- [ ] Firewall configured
- [ ] Database access restricted
- [ ] Regular security updates
- [ ] Backup encryption
- [ ] Access logs monitored
- [ ] Rate limiting implemented
- [ ] Input validation enabled
- [ ] Error information sanitized

## Troubleshooting

### Common Issues

1. **502 Bad Gateway**
   - Check Gunicorn service status
   - Verify socket permissions
   - Check Nginx configuration

2. **Database Connection Errors**
   - Verify DATABASE_URL
   - Check network connectivity
   - Confirm credentials

3. **SSL Certificate Issues**
   - Verify certificate validity
   - Check certificate chain
   - Confirm private key permissions

### Debugging Commands

```bash
# Check service status
sudo supervisorctl status slackbot
sudo systemctl status nginx

# View logs
sudo tail -f /var/log/slackbot.log
sudo tail -f /var/log/nginx/error.log

# Test configuration
sudo nginx -t
python manage.py check --deploy
```

## Rollback Procedures

1. **Application rollback**
   ```bash
   git checkout previous-version
   sudo supervisorctl restart slackbot
   ```

2. **Database rollback**
   ```bash
   python manage.py migrate app_name migration_name
   ```

3. **Full system rollback**
   ```bash
   # Restore from backup
   # Update DNS if necessary
   # Verify functionality
   ```