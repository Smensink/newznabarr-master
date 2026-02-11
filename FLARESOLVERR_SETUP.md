# FlareSolverr Setup Instructions

## Prerequisites

FlareSolverr requires Docker to run. If you don't have Docker installed:

### Install Docker Desktop (Mac)
1. Download from: https://www.docker.com/products/docker-desktop
2. Install and start Docker Desktop
3. Verify: `docker --version`

## Starting FlareSolverr

Once Docker is installed, start FlareSolverr with:

```bash
cd /Users/sebastianmensink/Downloads/newznabarr-master
docker compose up -d flaresolverr
```

Or run manually without docker-compose:

```bash
docker run -d \
  --name=flaresolverr \
  -p 8191:8191 \
  -e LOG_LEVEL=info \
  --restart unless-stopped \
  ghcr.io/flaresolverr/flaresolverr:latest
```

## Verify It's Running

```bash
curl http://localhost:8191/v1
```

You should see a JSON response.

## Testing

Run the test script to verify FlareSolverr integration works:

```bash
python test_flaresolverr.py
```

This will:
1. Check if FlareSolverr is running
2. Test ManyBooks search (Cloudflare bypass)
3. Test Anna's Archive download (DDoS-Guard bypass)

## What Was Changed

### Files Modified:
1. **docker-compose.yaml** - Added FlareSolverr service
2. **selenium_helper.py** - Added `get_page_source_flaresolverr()` method
3. **manybooks.py** - Updated to use FlareSolverr with fallback
4. **annas_archivedl.py** - Updated to use FlareSolverr with fallback

### How It Works:
- Plugins first try FlareSolverr (to bypass protections)
- If FlareSolverr fails or isn't running, falls back to regular Selenium
- No changes needed if you don't want to use FlareSolverr

## Stopping FlareSolverr

```bash
docker compose down flaresolverr
# or
docker stop flaresolverr && docker rm flaresolverr
```
