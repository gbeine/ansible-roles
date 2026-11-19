forward-domain runs in the container image [willnode/forward-domain](https://github.com/willnode/forward-domain/pkgs/container/forward-domain) (`latest` by default) as podman quadlet.
The image is rebuilt from the main branch every two weeks as `latest`, releases are tagged like `3.0.2-beta`, see `forward_domain_version`.
forward-domain redirects a domain to the URL in its DNS TXT record and gets the certificates from Let's Encrypt itself.
`forward_domain_home` is mounted to `/app/.certs`, it contains the certificates, `db.sqlite` and `.env`.
The image runs as `nobody` (65534), the role creates the home with the owner `65534:65534` and mode `0750`.

### Configuration

forward-domain reads `/app/.env` with dotenv on start, the values of the file take precedence over the environment.
`forward_domain_config` is the content of `.env`, it is merged over the default of the role and written to `<forward_domain_home>/.env`
(owner `root`, group `65534`, mode `0640`), mounted read-only to `/app/.env`.
The default sets `HOME_DOMAIN` to `forward_domain_hostname`, `/health` and `/stat` answer for this host only.

- a string or number writes `KEY='value'`, single quotes are literal in dotenv, so `#` in a URL is kept
- a list writes the elements joined with commas, e.g. for `WHITELIST_HOSTS` and `BLACKLIST_HOSTS`
- `true` writes `KEY='true'`, `false` or `null` removes the option

```yaml
forward_domain_config:
  HOME_DOMAIN: 'r.example.org'
  BLACKLIST_HOSTS: [ 'bad.example', 'evil.example' ]
  BLACKLIST_REDIRECT: 'https://example.org/blacklisted'
  USE_LOCAL_DNS: true
  DEBUG_LEVEL: 1
```

If `WHITELIST_HOSTS` is set, `BLACKLIST_HOSTS` is ignored.
Without `BLACKLIST_REDIRECT` a blacklisted host gets 403 on HTTP and no certificate on HTTPS.
`HTTP_PORT` and `HTTPS_PORT` are set by the role, forward-domain listens on 8080 and 8443 in the container,
the ports of the host are set with `forward_domain_container.publish`.

### Secrets

forward-domain has no secrets, the account key of Let's Encrypt is created in `/app/.certs`.

### Allowed variables

The role only allows the options in `webserver_forward_domain__config_allowed` and the environment variables in `webserver_forward_domain__environment_allowed`,
it stops before any change if unknown names are set.
This prevents unexpected behavior by accident, e.g. by a typo.
The options are generated from `HOSTING.md`, `src/util.js` and `src/client.js` of forward-domain main f91f186,
new versions of forward-domain may add options, the list is generated again.
The environment only takes `TZ` and `NODE_OPTIONS`, the options of forward-domain are set in `.env`.
`forward_domain_environment` has no default, without it the quadlet unit has no environment.
The check uses the environment of the container after merging `forward_domain_container`, so variables set with `forward_domain_container.environment` are checked as well.

### Container

The container publishes the ports 8080 and 8443 on IPv4 and IPv6 (`8080:8080`, `[::]:8080:8080`, `8443:8443`, `[::]:8443:8443`).
forward-domain needs the ports 80 and 443 of the public addresses for the HTTP challenge and the redirects,
either published directly or forwarded by a proxy that passes TLS through (see `HOSTING.md` of forward-domain).
Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `forward_domain_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `forward_domain_container.publish` replaces all ports and `forward_domain_container.volumes` replaces `/app/.certs` and `/app/.env`.

```yaml
forward_domain_container:
  publish: [ '80:8080', '[::]:80:8080', '443:8443', '[::]:443:8443' ]
```

### Validation

The role checks before any change:

- `forward_domain_config` and `forward_domain_container` are dictionaries, merging them with the defaults fails otherwise
- `forward_domain_config` only contains allowed options and not `HTTP_PORT` or `HTTPS_PORT`
- the values are strings, numbers, booleans or lists of them without single quotes and line breaks
- `USE_LOCAL_DNS` is `true` or `false`, `CACHE_EXPIRY_SECONDS` is a number and `DEBUG_LEVEL` a number from 0 to 3
- `forward_domain_home` is an absolute path
- only allowed environment variables are set in the container, their values contain no line breaks

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of the directory, `.env` and the quadlet unit, the service is neither started nor restarted.

### Restart and updates

forward-domain is restarted if it was running and `.env` or the quadlet unit changed, otherwise it is started and enabled.
forward-domain watches `.env` itself, but the bind mount of a single file keeps the former file when the role replaces it, so the role restarts the service.
If the start fails, the role stops with the last lines of the journal of the service.
Updates of the image are done by `container_update` with `forward_domain_autoupdate_enabled: true` and `forward_domain_autoupdate_schedule`,
without `forward_domain_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role `app_forward_domain` is renamed to `webserver_forward_domain`, the inventory variables keep the prefix `forward_domain_`.
Playbooks have to include `webserver_forward_domain`, the tags are `webserver` and `webserver_forward_domain`.

| Former variable | Now |
|---|---|
| `forward_domain_whitelist_hosts` | `forward_domain_config.WHITELIST_HOSTS`, a list |
| `forward_domain_blacklist_hosts` | `forward_domain_config.BLACKLIST_HOSTS`, a list |
| `forward_domain_blacklist_redirect` | `forward_domain_config.BLACKLIST_REDIRECT` |
| `forward_domain_http_port`, `forward_domain_https_port` | `forward_domain_container.publish`, the defaults 8080 and 8443 stay |
| `forward_domain_etc_hosts` | `forward_domain_container.etc_hosts` |
| `bootstrap_timezone__timezone` | `forward_domain_timezone`, mandatory |
| `forward_domain_home`, `forward_domain_ip`, `forward_domain_network`, `forward_domain_hostname` | stay |

- The options are written to `/app/.env` instead of the environment, `HOME_DOMAIN` stays `forward_domain_hostname` by default.
- The default of `forward_domain_etc_hosts` was `podman__container_etc_hosts`, the variable does not exist anymore, so the former role failed without `forward_domain_etc_hosts`.
  There are no additional hosts by default now.
- The container was managed by the podman module with `restart_policy: always`, it is a quadlet unit now.
  The former container `forward-domain` has to be removed before the first run (`podman rm -f forward-domain`), the certificates in `forward_domain_home` stay.
- The ports are published on IPv6 as well, `forward_domain_ipv6` is new.
- `forward_domain_config`, `forward_domain_environment`, `forward_domain_labels`, `forward_domain_version`, `forward_domain_container`,
  `forward_domain_autoupdate_enabled` and `forward_domain_autoupdate_schedule` are new.
- The owner of the home is set as `65534:65534` instead of `nobody` and `nogroup`.
- The home directory and the container were skipped in check mode, they are compared now.
- `podman___update_mode` is removed.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-forward-domain-default` | Only the mandatory variables, `HOME_DOMAIN` is the hostname |
| `molecule-forward-domain` | IPv6, labels, dependencies, `HOME_DOMAIN`, `BLACKLIST_HOSTS` as a list, `BLACKLIST_REDIRECT` with `#`, `USE_LOCAL_DNS`, `DEBUG_LEVEL` and `NODE_OPTIONS` |

`prepare` creates the podman network and pulls the image.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `forward_domain_container` and `forward_domain_config` not a dictionary, an unknown option, `HTTP_PORT`,
a line break and a single quote in a value, `DEBUG_LEVEL` 5, `USE_LOCAL_DNS: 'yes'`, an unknown environment variable,
a line break in `forward_domain_container.environment` and a relative home
and checks that it fails with the expected message and the quadlet unit and `.env` are unchanged (tasks marked `expect ERROR`),
then it changes `DEBUG_LEVEL` on `molecule-forward-domain`, forward-domain has to restart,
`molecule-forward-domain-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the volumes, the ports and the dependencies, `.env` with its mode and owner, the home and `db.sqlite`,
the service without automatic restarts, the addresses, the environment and the time zone of the container
and `/health` and `/stat` with the host of `HOME_DOMAIN`, on `molecule-forward-domain` this proves that `.env` is read.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd webserver_forward_domain
MOLECULE_TART_IMAGE='debian' molecule test
```
