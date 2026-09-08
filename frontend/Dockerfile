# --- Bakery frontend (static site served by nginx) --------------------------
FROM nginx:1.27-alpine

# curl is used only by the Docker HEALTHCHECK below
RUN apk add --no-cache curl

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY public /usr/share/nginx/html

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost/healthz || exit 1
