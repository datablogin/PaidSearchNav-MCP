# PaidSearchNav Troubleshooting Guide

## 🚨 Common Issues & Solutions

### Issue 1: "Connection refused" Database Errors

**Symptoms:**
```
sqlalchemy.exc.InterfaceError: Can't create a connection to host localhost and port 5432
```

**Root Cause:** Mixed Docker/local database configuration

**Solutions:**

#### Option A: Use Docker Mode (Recommended)
```bash
# Start everything with Docker
./run-local.sh docker
```

#### Option B: Use Standalone Mode
```bash
# Run locally with SQLite (no Docker required)
./run-local.sh standalone
```

#### Option C: Manual Fix
1. **For Docker development:**
   ```bash
   cp .env.local .env  # Use Docker database config
   docker-compose up
   ```

2. **For local development:**
   ```bash
   cp .env.local.standalone .env  # Use SQLite config
   python -m uvicorn paidsearchnav.api.main:app --reload
   ```

---

### Issue 2: Docker Compose Version Warnings

**Symptoms:**
```
the attribute `version` is obsolete, it will be ignored
```

**Solution:** ✅ **FIXED** - Removed obsolete version attribute from docker-compose.yml

---

### Issue 3: Missing Environment Variables

**Symptoms:**
```
ValidationError: [env field] field required
```

**Solutions:**

1. **Check environment file exists:**
   ```bash
   ls -la .env*
   ```

2. **Use correct environment file:**
   ```bash
   # Docker mode
   cp .env.local .env
   
   # Standalone mode  
   cp .env.local.standalone .env
   ```

3. **Verify required variables:**
   ```bash
   grep PSN_GOOGLE_ADS .env
   ```

---

### Issue 4: Import Errors

**Symptoms:**
```
ModuleNotFoundError: No module named 'paidsearchnav'
```

**Solutions:**

1. **Activate virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

2. **Install in development mode:**
   ```bash
   uv pip install -e ".[dev,test]"
   ```

3. **Verify installation:**
   ```bash
   python -c "import paidsearchnav; print('✅ Import successful')"
   ```

---

### Issue 5: BigQuery Configuration Issues

**Symptoms:**
```
BigQuery authentication failed
```

**Solutions:**

1. **For local development (disable BigQuery):**
   ```bash
   echo "PSN_BIGQUERY__ENABLED=false" >> .env
   ```

2. **For BigQuery testing:**
   ```bash
   # Follow the BigQuery setup guide
   cat BIGQUERY_CONNECTION_GUIDE.md
   ```

---

## 🔧 Development Modes

### Docker Mode (Full Setup)
- ✅ PostgreSQL database
- ✅ Redis caching
- ✅ Production-like environment
- ❌ Requires Docker Desktop

```bash
./run-local.sh docker
```

### Standalone Mode (Lightweight)
- ✅ SQLite database  
- ✅ No Docker required
- ✅ Fast startup
- ❌ No Redis caching

```bash
./run-local.sh standalone
```

---

## 🔍 Diagnostic Commands

### Check Application Status
```bash
# Test health endpoint
curl http://localhost:8000/api/v1/health

# Check version
curl http://localhost:8000/api/v1/version

# View API documentation
open http://localhost:8000/docs
```

### Check Database Connection
```bash
# Docker mode
docker-compose exec postgres psql -U psn_user -d paidsearchnav -c "SELECT 1;"

# Standalone mode
sqlite3 ./data/paidsearchnav_local.db "SELECT 1;"
```

### Check Environment Configuration
```bash
# Show non-sensitive config
python -c "
from paidsearchnav.core.config import Settings
settings = Settings.from_env()
print(f'Environment: {settings.environment}')
print(f'Database type: {settings.storage.connection_string.split(\":\")[0]}')
print(f'BigQuery enabled: {bool(settings.bigquery)}')
"
```

### Check Dependencies
```bash
# List installed packages
pip list | grep -E "(fastapi|sqlalchemy|google)"

# Check for conflicts
pip check
```

---

## 🌐 Multi-Machine Setup

### For Your Other Machines:

1. **Clone repository:**
   ```bash
   git clone https://github.com/datablogin/PaidSearchNav.git
   cd PaidSearchNav
   ```

2. **Choose development mode:**
   ```bash
   # Option A: Docker (if Docker Desktop installed)
   ./run-local.sh docker
   
   # Option B: Standalone (no Docker required)
   ./run-local.sh standalone
   ```

3. **Test setup:**
   ```bash
   curl http://localhost:8000/api/v1/health
   ```

---

## 📱 Quick Fix Commands

```bash
# Reset to clean state
git clean -fdx .env*
cp .env.local.standalone .env

# Restart Docker services
docker-compose down && docker-compose up --build

# Reinstall dependencies
rm -rf .venv && python -m venv .venv && source .venv/bin/activate && uv pip install -e ".[dev,test]"

# Reset database
rm -f ./data/paidsearchnav_local.db && alembic upgrade head
```

---

## 🆘 Still Having Issues?

1. **Check this troubleshooting guide first**
2. **Review the logs:** `docker-compose logs app` or check terminal output
3. **Verify your environment:** Make sure you're using the correct `.env` file
4. **Test minimal setup:** Try standalone mode first, then Docker mode
5. **Check dependencies:** Ensure Python 3.10+ and required packages are installed

### Environment-Specific Issues:

- **macOS:** Make sure Docker Desktop is running if using Docker mode
- **Linux:** May need to run Docker commands with `sudo` 
- **Windows:** Use WSL2 for best compatibility

The application is designed to work in both Docker and standalone modes. Choose the mode that works best for your machine setup!