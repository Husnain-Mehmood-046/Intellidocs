# IntelliDocs Client (React/Vite) - Multi-stage Dockerfile
#
# Why nginx for serving?
# - Vite builds static assets (HTML, JS, CSS) - no Node.js needed at runtime
# - nginx is lightweight, fast, and battle-tested for static file serving
# - Handles gzip, caching headers, SPA routing (fallback to index.html)
# - Much smaller than Node.js runtime (~20MB vs ~100MB)

# =============================================================================
# Stage 1: Builder - Build the Vite application
# =============================================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install all dependencies (including devDependencies for build)
RUN npm ci

# Copy source code
COPY . .

# Build the application
# Vite outputs to /app/dist by default
RUN npm run build

# =============================================================================
# Stage 2: Runtime - Serve with nginx
# =============================================================================
FROM nginx:alpine AS runtime

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy built assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# nginx runs as non-root by default in alpine image
CMD ["nginx", "-g", "daemon off;"]