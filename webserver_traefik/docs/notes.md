`traefik_home` contains only two files: `traefik.yml` and `acme.json` and potentially the files in `./dynamic`.
Both will be mounted as volumes under `/etc/traefik` into the container.


### Default `traefik_config`

```yaml
webserver_traefik__config_default:
  api:
    dashboard: false
    insecure: false
    debug: false
  entryPoints:
    web:
      address: ":80"
      http:
        redirections:
          entryPoint:
            to: "websecure"
            scheme: "https"
    websecure:
      address: ":443"
  serversTransport:
    insecureSkipVerify: false
  log:
    level: 'WARN'
  providers:
    docker:
      endpoint: "unix:///var/run/docker.sock"
      exposedByDefault: false
```
