
### `traefik_secrets` structure

```yaml
traefik_secrets:
  - name: 'traefik_secret_key'
    data: "{{ secret_variable_with_secret_value }}"
    target: 'NAME_OF_ENV_VAR_WITHIN_CONTAINER'
```

### Whole configuration example

```yaml
# Set mandatory variables to plausible values
traefik_home: '/srv/container/traefik'
traefik_hostname: 'traefik.localhost'
traefik_ip: '192.168.99.12'
traefik_ipv6: 'fd00::99:12'
traefik_network: 'podman99'
traefik_timezone: 'Europe/Berlin'

# Use full traefik_config instead of template
traefik_config:
  api:
    dashboard: true
    insecure: true
    debug: false
  entryPoints:
    web:
      address: ':80'
      http:
        redirections:
          entryPoint:
            to: 'websecure'
            scheme: 'https'
    websecure:
      address: ':443'
    protected:
      address: ':8000'
  serversTransport:
    insecureSkipVerify: false
  certificatesResolvers:
    letsencrypt:
      acme:
        email: 'security@beine-computer.de'
        storage: '/etc/traefik/acme.json'
        httpChallenge:
          entryPoint: 'web'
  log:
    level: 'WARN'
  providers:
    docker:
# Use TCP API instead of docker.sock
      endpoint: "tcp://192.168.99.1:2376"
      exposedByDefault: false

```
