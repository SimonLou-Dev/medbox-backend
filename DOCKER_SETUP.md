# Docker Setup for MedBox Backend

## Overview

The MedBox backend consists of 3 services:

1. **API Service** - FastAPI application server (port 8000)
2. **Scheduler Worker** - APScheduler + Dramatiq (triggers daily sync tasks)
3. **Queue Worker** - Dramatiq worker (executes background tasks)

Supporting services:
- **PostgreSQL** - Database (port 5432)
- **Redis** - Task queue broker (port 6379)

## Prerequisites

- Docker Engine 20.10+
- Docker Compose 2.0+
- 4GB+ RAM available

## Quick Start

### 1. Clone and Setup

```bash
cd /workspaces/medbox-backend
cp .env.example .env
```

### 2. Configure Environment

Edit `.env` with your configuration:

```bash
# Required changes:
SECRET_KEY=your-production-secret-key
KEYCLOAK_URL=your-keycloak-server
KEYCLOAK_CLIENT_SECRET=your-keycloak-secret
```

### 3. Build Services

```bash
docker-compose build
```

### 4. Start All Services

```bash
docker-compose up -d
```

### 5. Run Database Migrations

```bash
# In first terminal, check API is ready
docker-compose logs -f api

# In another terminal, run migrations
docker-compose exec api python -m alembic upgrade head
```

### 6. Verify Services

```bash
# Check service health
docker-compose ps

# View logs
docker-compose logs api              # API logs
docker-compose logs scheduler-worker # Scheduler logs
docker-compose logs queue-worker     # Queue worker logs

# Test API
curl http://localhost:8000/health

# Check Redis
docker-compose exec redis redis-cli ping

# Check PostgreSQL
docker-compose exec postgres psql -U medbox -d medbox_db -c "SELECT version();"
```

## Service Details

### API Service

- **Port**: 8000 (configurable via API_PORT)
- **Base URL**: http://localhost:8000
- **Endpoints**: /docs (Swagger), /redoc (ReDoc), /openapi.json
- **Dependencies**: PostgreSQL, Redis
- **Health Check**: GET /health

```bash
# Tail logs
docker-compose logs -f api

# Run shell
docker-compose exec api bash

# Install additional dependencies (dev)
docker-compose exec api pip install pytest pytest-asyncio
```

### Scheduler Worker

- **Role**: Sends medication sync tasks daily at 2 AM
- **Technology**: APScheduler + Dramatiq
- **Dependencies**: PostgreSQL, Redis
- **No exposed ports** (internal communication only)

```bash
# Tail logs
docker-compose logs -f scheduler-worker
```

### Queue Worker

- **Role**: Executes background tasks from Redis queue
- **Technology**: Dramatiq with 4 processes, 4 threads
- **Tasks**: Medication sync, data processing, etc.
- **Dependencies**: PostgreSQL, Redis
- **No exposed ports** (internal communication only)

```bash
# Tail logs
docker-compose logs -f queue-worker

# Check task queue status
docker-compose exec redis redis-cli
> KEYS dramatiq:*
> HGETALL dramatiq:tasks
```

## Common Commands

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service (follow)
docker-compose logs -f api

# Last 100 lines
docker-compose logs --tail=100 api

# No colors
docker-compose logs --no-color api
```

### Database Operations

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U medbox -d medbox_db

# List tables
docker-compose exec postgres psql -U medbox -d medbox_db -c "\dt"

# Create migration
docker-compose exec api python -m alembic revision --autogenerate -m "Your migration name"

# Check migration status
docker-compose exec api python -m alembic current

# Downgrade migration
docker-compose exec api python -m alembic downgrade -1
```

### Redis Operations

```bash
# Redis CLI
docker-compose exec redis redis-cli

# Get queue length
docker-compose exec redis redis-cli LLEN dramatiq:queue

# Monitor queue
docker-compose exec redis redis-cli --monitor

# Clear queue (DANGEROUS)
docker-compose exec redis redis-cli FLUSHDB
```

### Stop and Cleanup

```bash
# Stop services (keep data)
docker-compose stop

# Remove services (keep data)
docker-compose down

# Remove everything including volumes (DELETE DATA)
docker-compose down -v

# Remove images too
docker-compose down -v --rmi all
```

### Rebuild Services

```bash
# Rebuild specific service
docker-compose build api

# Rebuild all
docker-compose build

# Rebuild without cache
docker-compose build --no-cache

# Rebuild and restart
docker-compose up --build -d
```

## Environment Variables

See `.env.example` for all available options. Key variables:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:password@postgres:5432/db

# Redis
REDIS_URL=redis://redis:6379

# Security
SECRET_KEY=your-random-secret-key
ALGORITHM=HS256

# Keycloak OAuth2
KEYCLOAK_URL=http://keycloak:8080
KEYCLOAK_REALM=medbox
KEYCLOAK_CLIENT_ID=medbox-api
KEYCLOAK_CLIENT_SECRET=secret

# APIs
MEDICATIONS_API_URL=https://medicaments-api.giygas.dev

# Logging
LOG_LEVEL=INFO
ENV=production
```

## Troubleshooting

### API won't start

```bash
# Check logs
docker-compose logs api

# Common issues:
# - Redis not running: docker-compose ps redis
# - Database not ready: docker-compose logs postgres
# - Port already in use: lsof -i :8000
```

### Migration failed

```bash
# Check current state
docker-compose exec api python -m alembic current

# Reset to base (DANGEROUS - loses data)
docker-compose exec api python -m alembic downgrade base

# Check migration history
docker-compose exec api python -m alembic history
```

### Scheduler not triggering tasks

```bash
# Check scheduler logs
docker-compose logs scheduler-worker | grep -i "schedule\|cron"

# Check Redis connection
docker-compose exec scheduler-worker redis-cli -u redis://redis:6379 ping

# Check queue worker is running
docker-compose ps queue-worker
```

### Queue worker not processing tasks

```bash
# Check queue depth
docker-compose exec redis redis-cli LLEN dramatiq:queue

# Check worker logs
docker-compose logs -f queue-worker

# Restart worker
docker-compose restart queue-worker
```

### Permission denied errors

```bash
# Services run as user 1000, not root
# If file permission issues, adjust ownership:
sudo chown -R 1000:1000 ./medbox ./migrations

# Or run with different user
docker-compose exec -u root api bash
```

## Production Deployment

### Before deploying to production:

1. **Security**
   - Generate a strong `SECRET_KEY`
   - Set `KEYCLOAK_CLIENT_SECRET`
   - Use TLS/SSL certificates
   - Enable firewall rules

2. **Database**
   - Use external PostgreSQL (not Docker)
   - Enable backups
   - Set password-authenticated accounts
   - Configure read replicas

3. **Redis**
   - Use external Redis (not Docker)
   - Enable authentication
   - Configure persistence
   - Monitor memory usage

4. **Monitoring**
   - Set up application logging (ELK, etc.)
   - Monitor queue depth
   - Set up alerts for failed tasks
   - Monitor database performance

5. **Scaling**
   - Run multiple API instances behind load balancer
   - Run multiple queue workers
   - Use managed database service
   - Use managed Redis service

### Example production docker-compose.yml modifications:

```yaml
api:
  replicas: 3  # Multiple instances
  deploy:
    resources:
      limits:
        cpus: '1'
        memory: 512M
      reservations:
        cpus: '0.5'
        memory: 256M

queue-worker:
  replicas: 2  # Multiple workers
  # Same resource limits as API
```

## Support

For issues or questions, check:
- Application logs: `docker-compose logs`
- Database logs: `docker-compose logs postgres`
- Redis logs: `docker-compose logs redis`
- [MedBox Documentation](./docs/)
