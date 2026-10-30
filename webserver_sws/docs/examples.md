```yaml
# Set mandatory variables to plausible values
sws_home: "/srv/container/sws"
sws_hostname: "sws.localhost"
sws_ip: "192.168.99.21"
sws_ipv6: "fd00::99:21"
sws_network: "podman99"
sws_timezone: "Europe/Berlin"

# Add virtual hosts
sws_vhosts:
  - "example.com"
  - "example.org"

# Add SWS to traefik
sws_labels:
  traefik.enable: "true"
  traefik.http.routers.example-com.rule: "Host(`example.com`)"
  # Important: specify service to support multiple routers per container
  traefik.http.routers.example-com.service: "example-com"
  traefik.http.services.example-com.loadbalancer.server.port: 80
  traefik.http.routers.example-org.rule: "Host(`example.org`)"
  # Important: specify service to support multiple routers per container
  traefik.http.routers.example-org.service: "example-org"
  traefik.http.services.example-org.loadbalancer.server.port: 80
```
