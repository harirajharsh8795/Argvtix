# Argvtix Custom Domain Configuration & Deployment Guide

This guide details how to connect and configure custom domain names (e.g., `app.argvtix.ai` or `ai-guard.yourcompany.com`) for Argvtix production environments.

---

## 1. Architecture Overview

Argvtix utilizes a reverse proxy architecture where an edge ingress router (Caddy or Nginx) handles TLS termination, HTTP/2 multiplexing, and routing between:
1. **Frontend Web UI & Landing Page:** Served on internal port `3000` (production Nginx container) or `5173` (Vite dev).
2. **Backend FastAPI Gateway:** Served on internal port `8000`.
3. **WebSocket Event Hub:** Real-time event streaming over `ws://<domain>/ws/events`.

---

## 2. DNS Record Configuration

Point your custom domain DNS records to your server's public IPv4/IPv6 address:

| Type | Name | Value / Target | TTL |
| :--- | :--- | :--- | :--- |
| **A** | `app` (or `@` for apex) | `YOUR_SERVER_PUBLIC_IPV4` | 300s (Auto) |
| **AAAA** | `app` (optional IPv6) | `YOUR_SERVER_PUBLIC_IPV6` | 300s (Auto) |
| **CNAME** | `api` (if separate API domain) | `app.yourcompany.com` | 300s (Auto) |

Verify resolution using `dig` or `nslookup`:
```bash
dig +short app.yourcompany.com
```

---

## 3. Caddy Reverse Proxy Configuration (Automated Let's Encrypt TLS)

Argvtix includes a production [`Caddyfile`](../Caddyfile) configured for automated ACME TLS certificate issuance and renewal.

1. Set your custom domain in `.env`:
```env
CUSTOM_DOMAIN=app.yourcompany.com
VITE_APP_DOMAIN=https://app.yourcompany.com
```

2. Run with Docker Compose:
```bash
docker compose -f docker-compose.prod.yml up -d
```

Caddy automatically contacts Let's Encrypt, issues a valid TLS certificate, enables HSTS, and begins routing traffic with zero downtime.

---

## 4. Alternative: Nginx Configuration

If deploying behind an existing enterprise Nginx ingress or AWS ALB:

```nginx
server {
    listen 80;
    server_name app.yourcompany.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl http2;
    server_name app.yourcompany.com;

    ssl_certificate /etc/letsencrypt/live/app.yourcompany.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.yourcompany.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    # Security Headers
    add_header X-Frame-Options "DENY" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;

    # API Backend
    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket Real-Time Stream
    location /ws/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "Upgrade";
        proxy_set_header Host $host;
    }

    # Frontend Single Page App
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        try_files $uri $uri/ /index.html;
    }
}
```

---

## 5. Verification Checklist

- [x] Favicon is served from `/favicon.svg` (Geometric Argvtix dual bracket, zero purple).
- [x] Landing page is accessible at `https://<domain>/`.
- [x] Privacy policy is accessible at `https://<domain>/privacy`.
- [x] Terms of service are accessible at `https://<domain>/terms`.
- [x] Platform console is accessible at `https://<domain>/overview`.
- [x] REST documentation is accessible at `https://<domain>/docs`.
- [x] WebSocket streaming establishes on `wss://<domain>/ws/events`.
