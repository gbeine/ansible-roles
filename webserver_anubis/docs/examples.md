```yaml
# Set mandatory variables to plausible values
anubis_home: '/srv/container/anubis'
anubis_hostname: 'anubis.localhost'
anubis_ip: '192.168.99.20'
anubis_ipv6: 'fd00::99:20'
anubis_network: 'podman99'
anubis_timezone: 'Europe/Berlin'

anubis_serve_robots_txt: true

# Use dynamic cookies and forward all traffic to a virtual hosts enabled server like SWS or Traefik
anubis_cookie_dynamic_domain: true
anubis_target: "http://192.168.99.21:80"

# Add additional environment variables
# See https://anubis.techaro.lol/docs/admin/installation#environment-variables for all available variables
anubis_environment:
  WEBMASTER_EMAIL: 'webmaster@example.org'

# Use full anubis_config instead of default botPolicy.yaml
# See https://anubis.techaro.lol/docs/category/configuration for details
anubis_config:
# ...

# Protect Traefik sites using anubis
anubis_labels:
  traefik.enable: 'true'
  traefik.http.routers.example-com.rule: 'Host(`example.com`)'
  traefik.http.routers.example-com.tls.certResolver: 'letsencrypt'
  traefik.http.routers.example-com.tls.domains[0].main: 'example.com'
  # Important: specify service to support multiple routers per container
  traefik.http.routers.example-com.service: 'example-com'
  # Important: specify entrypoints to protect
  traefik.http.routers.example-com.entrypoints: 'web,websecure'
  traefik.http.services.example-com.loadbalancer.server.port: 8923
  traefik.http.routers.example-org.rule: 'Host(`example.org`)'
  traefik.http.routers.example-org.tls.certResolver: 'letsencrypt'
  traefik.http.routers.example-org.tls.domains[0].main: 'example.org'
  # Important: specify service to support multiple routers per container
  traefik.http.routers.example-org.service: 'example-org'
  # Important: specify entrypoints to protect
  traefik.http.routers.example-org.entrypoints: 'websecure'
  traefik.http.services.example-org.loadbalancer.server.port: 8923

```
