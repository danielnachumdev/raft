# HTTP-01 challenge webroot (gate-only; App must not answer this path).
location ^~ /.well-known/acme-challenge/ {
    default_type text/plain;
    alias /etc/nginx/acme-www/;
    try_files $uri =404;
}
