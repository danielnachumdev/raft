# Shared gate → router proxy (HTTP default_server + per-SNI TLS servers).
# Docker embedded DNS so gate can boot before router and recover when it returns.

resolver 127.0.0.11 valid=10s ipv6=off;

location / {
    set $router_upstream http://router:80;
    proxy_pass $router_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 3s;
    proxy_read_timeout 60s;
    proxy_intercept_errors on;
    error_page 502 503 504 /offline.html;
}

location = /offline.html {
    internal;
    root /usr/share/nginx/errors;
}
