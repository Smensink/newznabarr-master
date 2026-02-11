#!/bin/bash
set -e

# Configuration
IMAGE_NAME="newznabarr"
TAG="latest"
DOCKER_USER="" # Leave empty to prompt or set via env var

# Check for docker
if ! command -v docker &> /dev/null; then
    echo "Error: docker is not installed or not in PATH"
    exit 1
fi

# Get Docker Hub username
if [ -z "$DOCKER_USER" ]; then
    read -p "Enter Docker Hub username: " DOCKER_USER
fi

FULL_IMAGE_NAME="$DOCKER_USER/$IMAGE_NAME:$TAG"

echo "========================================"
echo "📦 Building Docker Image: $FULL_IMAGE_NAME"
echo "ℹ️  Note: YouTube plugin and dependencies have been removed for a lighter image."
echo "========================================"

# Build the image
docker build -t "$FULL_IMAGE_NAME" .

echo ""
echo "✅ Build successful!"
echo ""
echo "========================================"
echo "🚀 Pushing to Docker Hub"
echo "========================================"

# Push the image
read -p "Do you want to push to Docker Hub now? (y/n) " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker push "$FULL_IMAGE_NAME"
    echo ""
    echo "✅ Successfully pushed $FULL_IMAGE_NAME"
else
    echo "Skipping push."
fi

echo ""
echo "To run the image locally:"
echo "docker run -d \\"
echo "  --name newznabarr \\"
echo "  -p 10000:10000 \\"
echo "  -v \$(pwd)/config:/config \\"
echo "  -v \$(pwd)/downloads:/data/downloads/downloadarr \\"
echo "  $FULL_IMAGE_NAME"
