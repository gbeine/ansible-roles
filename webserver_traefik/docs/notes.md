Traefik runs in the official container image [traefik](https://hub.docker.com/_/traefik) as podman quadlet,
it publishes the ports 80 and 443 of the host. `traefik_home` contains `traefik.yml`, `acme.json`, the files of the dynamic configuration in `dynamic`,
the htpasswd files in `users` and the certificates of the realms in `certs`, they are mounted to `/etc/traefik`.

### Configuration

`traefik_config` contains the options of `traefik.yml`, the static configuration of Traefik.
It is merged recursively over the default of the role, `null` removes an option or a whole section, `{}` enables a section without options (e.g. `ping: {}`).
Lists replace the lists of the default.

```yaml
traefik_config:
  api:
    dashboard: true
  entryPoints:
    protected:
      address: ':8000'
  certificatesResolvers:
    letsencrypt:
      acme:
        email: 'security@example.org'
        storage: '/etc/traefik/acme.json'
        httpChallenge:
          entryPoint: 'web'
  providers:
    file:
      directory: '/etc/traefik/dynamic'
      watch: true
  serversTransport: ~
```

The default of the role:

```yaml
api:
  dashboard: false
  insecure: false
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
serversTransport:
  insecureSkipVerify: false
log:
  level: 'WARN'
```

`traefik_dynamic` contains the files of the dynamic configuration, the name of the file without `.yml` and its content.
The files are written to `<traefik_home>/dynamic`, mounted to `/etc/traefik/dynamic`.
Traefik reads them with the file provider, `providers.file.directory` has to be `/etc/traefik/dynamic` in `traefik_config`,
with `providers.file.watch: true` Traefik loads changed files without a restart.
`null` removes a file, files that are not listed are not changed.

```yaml
traefik_dynamic:
  example:
    http:
      routers:
        example:
          rule: 'Host(`example.org`)'
          entryPoints: [ 'websecure' ]
          service: 'example'
          tls:
            certResolver: 'letsencrypt'
      services:
        example:
          loadBalancer:
            servers:
              - url: 'http://192.168.99.20:8080'
  old: ~
```

`acme.json` is created empty with mode `0600` and never changed by the role, Traefik stores the certificates of ACME in it.

### Users

`traefik_usersfile` contains the htpasswd files of the middleware `basicAuth`, the name of the file without `.htpasswd` and the passwords of its users by their names.
The role writes them to `<traefik_home>/users/<name>.htpasswd` with mode `0600`, the directory is mounted read-only to `/etc/traefik/users`.
The module `webserver_traefik_htpasswd` of the role hashes the passwords with bcrypt (`$2y$`), it keeps the hash of a password that did not change,
so the file only changes if a user or a password changes. Users missing in `traefik_usersfile` are removed from the file, `null` removes the whole file.
The role installs `python3-bcrypt` for the module. bcrypt only uses 72 bytes, longer passwords are rejected.

```yaml
traefik_usersfile:
  dashboard:
    admin: "{{ vault_traefik_admin_password }}"
    viewer: "{{ vault_traefik_viewer_password }}"
  old: ~
traefik_dynamic:
  dashboard:
    http:
      routers:
        dashboard:
          rule: 'Host(`traefik.example.org`)'
          entryPoints: [ 'websecure' ]
          service: 'api@internal'
          middlewares: [ 'dashboard-auth' ]
          tls: {}
      middlewares:
        dashboard-auth:
          basicAuth:
            usersFile: '/etc/traefik/users/dashboard.htpasswd'
```

The middleware can also be set with the labels of a container, e.g. `traefik.http.middlewares.auth.basicauth.usersfile=/etc/traefik/users/dashboard.htpasswd`.

### Certificates

`traefik_realms` is a list of realms of the PKI with local certificates, e.g. of `pki_easyrsa_deploy`.
Every realm has `<realm>/fullchain.pem` and `<realm>/privkey.pem` in the directory of the realms (`common_globals__pki_realms_dir`, default `/etc/pki/realms`).
The quadlet unit installs them on every start of Traefik with `ExecStartPre` to `<traefik_home>/certs/<realm>.crt` (`0644`) and `<realm>.key` (`0400`),
`install` follows the links of the source. The directory is mounted read-only to `/etc/traefik/certs`.
The role writes the dynamic file `realms.yml` with the certificates and adds the file provider to `traefik.yml`, Traefik chooses the certificate by the name of the server (SNI):

```yaml
traefik_realms: [ 'example.org', 'example.net' ]
```

```yaml
# <traefik_home>/dynamic/realms.yml
tls:
  certificates:
    - certFile: '/etc/traefik/certs/example.org.crt'
      keyFile: '/etc/traefik/certs/example.org.key'
    - certFile: '/etc/traefik/certs/example.net.crt'
      keyFile: '/etc/traefik/certs/example.net.key'
```

```yaml
# Added to traefik.yml with traefik_realms
providers:
  file:
    directory: '/etc/traefik/dynamic'
    watch: true
```

`realms` is no name of `traefik_dynamic`, a file provider with another directory in `traefik_config` does not read `realms.yml`.
Without `traefik_realms` the role removes `realms.yml`, the certificates of removed realms are removed from `<traefik_home>/certs`.
A renewed certificate is used after the next restart of Traefik. With `traefik_pki_update_enabled: true` (default) the role installs `pki_update`,
its timer (`traefik_pki_update_schedule`, default `*-*-* 00/4:00:00`) restarts Traefik if one of the `fullchain.pem` of the realms is newer than the start of Traefik.
The timer stays if the realms are removed later.

### Secrets

The role has no secrets. `traefik.yml` cannot read options from files and Traefik ignores its `TRAEFIK_*` variables
as soon as a configuration file exists (the loaders of Traefik v3.7.19 use the first source found: file, flags, environment).
The options of Traefik are written to `traefik.yml` on the host.

### Containers of the host

With `traefik_provider_podman: true` (default) Traefik routes to the containers of the host with the docker provider.
The role mounts the podman socket `/run/podman/podman.sock` read-only to `/var/run/docker.sock` and adds to the configuration:

```yaml
providers:
  docker:
    endpoint: 'unix:///var/run/docker.sock'
    exposedByDefault: false
```

The containers are routed with labels, e.g. `traefik.enable=true` and `traefik.http.routers.<name>.rule=Host(...)`.
The podman socket has to be enabled, e.g. with `podman_socket_enabled: true` of `container_podman`.
With `traefik_provider_podman: false` the socket is not mounted and the docker provider is not configured,
another endpoint (e.g. `tcp://192.168.99.1:2376` of the podman API via TCP) is set in `traefik_config.providers.docker`.

### Allowed variables

The role only allows the options of `traefik.yml` in `webserver_traefik__config_schema` and the environment variables in `webserver_traefik__environment_allowed`,
it stops before any change if unknown options or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo in an option or an option that Traefik would ignore.
The schema is generated from `docs/content/reference/static-configuration/file.yaml` of Traefik v3.7.19 and contains the types of the options,
the names of entry points, certificate resolvers and plugins are free, the configuration of a plugin is not checked.

`traefik_environment` has no default and only takes the variables of lego, the ACME client of Traefik (lego v5.6.0), e.g. `LEGO_DISABLE_CNAME_SUPPORT`.
The options of Traefik (`TRAEFIK_*`) are rejected, Traefik ignores them with `traefik.yml`.
The check of the environment uses the environment of the container after merging `traefik_container`.

### Container

Ports, volumes, labels, additional hosts (`etc_hosts`) and dependencies are changed with `traefik_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`traefik_container.environment` replaces `traefik_environment`.
The dependencies of the quadlet unit are lists in `traefik_container`: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
written as `Requires=`, `Wants=`, `After=`, `PartOf=` and `BindsTo=` to `[Unit]`, `requires_mounts_for` are paths, written as `RequiresMountsFor=`,
e.g. for `traefik_home` on a device that is mounted later:

```yaml
traefik_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
  requires_mounts_for: [ '/mnt/storage' ]
```

| Host | Container |
|---|---|
| `<traefik_home>/traefik.yml` | `/etc/traefik/traefik.yml` (read-only) |
| `<traefik_home>/dynamic` | `/etc/traefik/dynamic` (read-only) |
| `<traefik_home>/acme.json` | `/etc/traefik/acme.json` |
| `<traefik_home>/users` | `/etc/traefik/users` (read-only) |
| `<traefik_home>/certs` | `/etc/traefik/certs` (read-only) |
| `/run/podman/podman.sock` | `/var/run/docker.sock` (read-only, with `traefik_provider_podman`) |

### Validation

The role checks before any change:

- the former variable `traefik_secrets` is not set
- `traefik_config` is a dictionary of known options with the types of the schema (booleans, numbers, durations, strings, lists, dictionaries) and values without line breaks
- `traefik_dynamic` is a dictionary, the names of the files consist of letters, digits, `_`, `.` and `-`, the contents are dictionaries or `null`, `realms` is no file
- `traefik_usersfile` is a dictionary, the names of the files consist of letters, digits, `_`, `.` and `-`, the users of a file are a dictionary or `null`,
  the names of the users consist of letters, digits, `_`, `.`, `@` and `-`, the passwords are strings or numbers of 1 to 72 bytes without line breaks
- `traefik_realms` is a list of unique names of letters, digits, `_`, `.` and `-`, `fullchain.pem` and `privkey.pem` of every realm exist
  (in check mode missing certificates are reported, another role may create them only in a real run)
- `traefik_environment`, if set, is a dictionary without options of Traefik and line breaks, only allowed environment variables are set in the container

If `traefik_container` or `traefik_config` is no dictionary, merging it with the default fails before anything changes.
Traefik itself checks the values at the start, the role waits until the entry points on all addresses (e.g. `:80`) accept connections and shows the journal otherwise.

### Check mode

The role runs with `--check`, also on a host where it never ran, and compares `traefik.yml`, the dynamic configuration, the htpasswd files and the quadlet unit.
The htpasswd files are not compared while `python3-bcrypt` is not installed yet.
The start of Traefik and the wait for the entry points do not run in check mode.

### Restart and updates

Traefik is restarted if it was running and `traefik.yml`, the quadlet unit or an htpasswd file changed, otherwise it is started and enabled.
Traefik reads an htpasswd file only when it builds the middleware, a changed file needs a restart.
The files of the dynamic configuration need no restart, Traefik watches them with `providers.file.watch`.
The certificates of the realms are installed on every start, `pki_update` restarts Traefik after a renewal.
Updates of the image are done by `container_update` with `traefik_autoupdate_enabled: true` and `traefik_autoupdate_schedule` (default `*-*-* 00/4:00:00`).

### Migration

- `traefik_config` is merged recursively over the default of the role, it does not replace the default anymore.
  Options of the default that are not wanted are removed with `null`, e.g. `serversTransport: ~`.
- `providers.docker` is no part of the default anymore, it is set with `traefik_provider_podman` (default `true`), which mounts the podman socket.
  The former default used `unix:///var/run/docker.sock` without mounting a socket. A configuration with another endpoint keeps working,
  `traefik_provider_podman: false` removes the socket.
- `traefik_secrets` is removed, the role rejects it. The former secrets were passed in the environment, the options of Traefik are set in `traefik_config`.
- `traefik_environment` only takes the variables of lego, `TRAEFIK_*` are rejected.
- `podman___update_mode` is not evaluated anymore, Traefik is restarted only if it was running and `traefik.yml` or the quadlet unit changed,
  updates are done by `container_update`.
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set with `traefik_timezone`.
- A file of `traefik_dynamic` set to `null` is removed, the files are written with mode `0644`.
- The tags are `webserver` and `webserver_traefik`.
- The dependencies `requires`, `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` are set with `traefik_container`.
- `traefik_usersfile` (htpasswd files) and `traefik_realms` (local certificates) are new.
  The directories `<traefik_home>/users` and `<traefik_home>/certs` are always mounted, the quadlet unit changes once and Traefik restarts.
  `volumes` in `traefik_container` replaces the default and needs the two volumes for these features.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-traefik-default` | The mandatory values only, IPv4, the docker provider routes to a labeled container through the podman socket |
| `molecule-traefik` | IPv4 and IPv6, `traefik_provider_podman: false`, the file provider with a file of `traefik_dynamic`, a file removed with `null`, `serversTransport` removed with `null`, `traefik_environment`, dependencies of the quadlet unit (`wants`, `after`, `requires_mounts_for`), an htpasswd file for the dashboard and one removed with `null`, two realms with local certificates |

`prepare` sets up podman with the socket and the network `podman-molecule` with the role `container_podman`, pulls the images
and starts the container `molecule-whoami` (`docker.io/traefik/whoami`) with the labels of the docker provider as backend of the routes.
On `molecule-traefik` it creates self-signed certificates of the realms `realm1` and `realm2` with `openssl`, an htpasswd file and a certificate that the role removes.
`check` runs `converge` with `--check` on the VMs where the role never ran.
`side_effect` runs the role with `traefik_container` and `traefik_config` not a dictionary, unknown options and sections, options of the wrong type and line breaks,
an invalid dynamic configuration, `traefik_dynamic` not a dictionary, the former variable `traefik_secrets`, `TRAEFIK_LOG_LEVEL` in `traefik_environment`
and an unknown variable in `traefik_container.environment`, invalid htpasswd files (name of the file, user, line break, too long password, no users),
`traefik_usersfile` not a dictionary, `traefik_realms` not a list, invalid and duplicate realms, `realms` in `traefik_dynamic` and a realm without certificates
and checks that it fails with the expected message and the quadlet unit and `traefik.yml` are unchanged (tasks marked `expect ERROR`),
then it changes `log.level` on `molecule-traefik`, `traefik.yml` changes and Traefik has to restart,
then it changes the password of `admin`, the htpasswd file changes and Traefik has to restart.
`verify` checks the quadlet unit, `traefik.yml`, the files of the dynamic configuration, the service, the container addresses, the redirect from http to https
and the routes on port 443: the route of the docker provider or of the dynamic configuration has to answer with whoami, the other one with 404.
It checks the htpasswd files (users, bcrypt, mode `0600`, the removed file), the certificates in `<traefik_home>/certs` and `realms.yml`,
the certificate served for every realm (`openssl s_client` with the name of the realm), the certificates watched by `pki_update`
and the login on the dashboard: `401` without a password and with the former password, `200` with the changed password.
The VMs need access to Docker Hub for `docker.io/traefik:v3` and `docker.io/traefik/whoami`.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `containers.podman`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd webserver_traefik
MOLECULE_TART_IMAGE='debian' molecule test
```
