Certbot runs in the container image `c0d3cr.io/container/certbot` as podman quadlet.
The container idles, certbot is run with `podman exec certbot certbot …`, e.g. by the role and by the renew timer.
The configuration, accounts and certificates are in `<certbot_home>/etc` (mounted as `/etc/letsencrypt`),
the certificates of a realm are in `<certbot_home>/etc/live/<realm>`.

### CA certificates

`/etc/ssl/certs` of the host is mounted as `/etc/ssl/host-certs` and used with `REQUESTS_CA_BUNDLE`,
so ACME servers with certificates of an own CA (e.g. a Step CA) are trusted if the CA is trusted by the host, e.g. with `debian_pki_enable` of `bootstrap_debian`.

`certbot_ca_certificates` adds private CAs that only Certbot trusts, not the host. It is a dictionary of names and certificates in PEM format:

```yaml
certbot_ca_certificates:
  step-ca: "{{ lookup('ansible.builtin.file', 'step-ca-root.crt') }}"
  lab-ca: |
    -----BEGIN CERTIFICATE-----
    MIIB…
    -----END CERTIFICATE-----
```

Every CA is written to `<certbot_home>/ca/certs/<name>.crt`, CAs that are not listed anymore are removed.
The role writes the bundle `<certbot_home>/ca/ca-certificates.crt`: first `/etc/ssl/certs/ca-certificates.crt` of the host, then the private CAs sorted by their names.
`<certbot_home>/ca` is mounted read-only as `/etc/ssl/certbot-ca`, and `REQUESTS_CA_BUNDLE` points to `/etc/ssl/certbot-ca/ca-certificates.crt`,
so Certbot trusts the public CAs of the host and the private CAs.
The bundle is written on every run of the role. A change of the CAs of the host reaches the bundle with the next run of the role, the container needs no restart.
Without `certbot_ca_certificates` the role removes `<certbot_home>/ca` and uses the bundle of the host as before.

### Secrets

The credentials of the DNS plugins are files of the configuration of Certbot, `certonly` gets them with `--dns-<name>-credentials`
and the renewal configuration of every certificate (`<certbot_home>/etc/renewal/<realm>.conf`) stores their path.
They are written to `<certbot_home>/etc/<plugin>` with mode `0600` and are no podman secrets,
a secret would change the path and every renewal configuration would have to be rewritten.

### Allowed variables

`certbot_environment` and `certbot_container.environment` only take the variables of `pki_certbot__environment_allowed`:
`REQUESTS_CA_BUNDLE` and the proxies `HTTP_PROXY`, `HTTPS_PROXY` and `NO_PROXY` read by requests and `CONTAINER_HOST` read by podman-remote.
Certbot itself reads no options from the environment. The lists prevent unexpected behavior by accident.

### Container

Ports, volumes and dependencies are changed with `certbot_container`, it is merged over the default of the container, the merge is not recursive.
The dependencies of the quadlet unit are lists in `certbot_container`: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
written as `Requires=`, `Wants=`, `After=`, `PartOf=` and `BindsTo=` to `[Unit]`, `requires_mounts_for` are paths, written as `RequiresMountsFor=`,
e.g. for `certbot_home` on a device that is mounted later:

```yaml
certbot_container:
  wants: [ 'network-online.target' ]
  after: [ 'network-online.target' ]
  requires_mounts_for: [ '/mnt/storage' ]
```

### `certbot_provider_server`

A dict containing the URL of an ACME provider, e.g. a Step CA.

```yaml
certbot_provider_server:
  my-ca: 'https://ca.internal/acme/acme/directory'
```

The provider can now be selected as default provider by setting:

```yaml
certbot_provider: 'my-ca'
```

An ACME account is registered for the server of the default provider and for every `server` of the realms,
with `certbot_email` or without email if `certbot_email` is not set.

### `certbot_plugins`

A dict of the DNS plugins and their credentials, every plugin is written as `<certbot_home>/etc/<plugin>` with `key = value` lines and mode `0600`.
All DNS plugins of the image can be used, the keys are described in the documentation of the plugin.
Credentials of plugins that are not configured anymore are removed.

```yaml
certbot_plugins:
  dns-hetzner:
    dns_hetzner_api_token: "{{ vault_hetzner_api_token }}"
  dns-powerdns:
    dns_powerdns_api_url: 'https://dns.example.org'
    dns_powerdns_api_key: "{{ vault_powerdns_api_key }}"
```

### `certbot_realms`

A list of dicts following this structure

| Key                     | Default                                     | Description                                                                                      |
|-------------------------|---------------------------------------------|--------------------------------------------------------------------------------------------------|
| `realm`                 | -                                           | Used a name for the files and primary domain name of the certificate.                            |
| `server`                | `certbot_provider_server[certbot_provider]` | The URL of the ACME CA provider.                                                                 |
| `authenticator`         | 'standalone'                                | The name of the authenticator plugin to use.                                                     |
| `authenticator_options` | ''                                          | Additional options for the authenticator plugin.                                                 |
| `key_type`              | 'ecdsa'                                     | The type of key to generate. Can be 'ecdsa' (recommended) or 'rsa' (not recommended).            |
| `elliptic_curve`        | -                                           | Only for `key_type` 'ecdsa': If not set, 'secp256r1' is used. See RFC 8446 for supported values. |
| `key_size`              | 2048                                        | Only for `key_type` 'rsa': The size of the RSA key.                                              |
| `domains`               | []                                          | A list of domains to add to the certificate.                                                     |
| `post_hook`             | -                                           | A command run in the container after the certificate was issued or renewed.                      |

For a DNS authenticator (`dns-<name>`) the role adds `--dns-<name>-credentials /etc/letsencrypt/dns-<name>`, the plugin has to be configured in `certbot_plugins`.
A certificate is only requested if `<certbot_home>/etc/renewal/<realm>.conf` does not exist, changes of a realm are not applied to an existing certificate.

```yaml
certbot_realms:
  - realm: 'example.org'
    server: 'https://ca.internal/acme/acme/directory'
    authenticator: 'dns-hetzner'
    authenticator_options: '--dns-hetzner-propagation-seconds 60'
    domains: [ 'host1.example.org', 'www.example.org' ]
    post_hook: 'podman restart traefik'
```


### Restarting containers in a post_hook

The image contains podman, with `certbot_podman_socket: true` the podman socket of the host is mounted and `CONTAINER_HOST` is set,
so `podman restart <container>` in a `post_hook` restarts the container on the host.
The podman socket must be enabled, e.g. with `podman_socket_enabled: true` of `container_podman`.

### Standalone authenticator

The `standalone` authenticator answers the HTTP challenge in the container on port 80, publish the port with `certbot_container` if the ACME server cannot reach the address of the container:

```yaml
certbot_container:
  publish:
    - '80:80'
```

### Validation

The role checks before any change:

- `certbot_container`, `certbot_environment` and `certbot_provider_server` are dictionaries, merging them with the default fails otherwise
- the former variables `certbot_publish` and `certbot_volumes` are not set
- `certbot_plugins` is a dictionary of `dns-<name>` plugins with a non-empty dictionary of credentials without line breaks
- `certbot_provider` is in `certbot_provider_server`
- `certbot_realms` is a list, every realm has `realm` and only known keys, no line breaks, and its DNS plugin is configured
- `certbot_podman_socket` and `certbot_autoupdate_enabled` are booleans, the values of `certbot_environment` contain no line breaks
- `certbot_ca_certificates` is a dictionary, the names consist of letters, digits, `_`, `.` and `-`,
  the values are certificates in PEM format without private keys
- only allowed variables are set in the environment of the container

### Check mode

The role runs with `--check`, also on a host where it never ran, and compares the files, the bundle of the CAs, the quadlet unit and the renew units.
The start of the container, the accounts, the certificates and the start of the renew timer do not run in check mode.

### Renewal, restart and updates

The timer `certbot-podman-renew.timer` runs `certbot renew` daily with a random delay of up to one hour.
The container is restarted if it was running and the quadlet unit changed.
Updates of the image are done by `container_update` with `certbot_autoupdate_enabled: true` and optionally `certbot_autoupdate_schedule`,
without `certbot_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

| Before | Now |
|---|---|
| `certbot_use_podman` | removed, Certbot always runs in podman |
| `pki_certbot___certificates_only` | removed, the role is idempotent, use the tag `pki_certbot` |
| `podman___update_mode` | `certbot_autoupdate_enabled` |
| `certbot_publish` | `certbot_container.publish` |
| `certbot_volumes` | `certbot_container.volumes`, the list replaces all volumes of the role |
| tag `pki_certbot` | tags `pki` and `pki_certbot` |
| `certbot_plugins` as list, `certbot_dns_hetzner_api_token`, `certbot_dns_powerdns_api_url`, `certbot_dns_powerdns_api_key` | `certbot_plugins` as dict with the credentials |
| `authenticator_options: "{{ pki_certbot__authenticator['dns-hetzner'] }}"` | not needed, the credentials are added by the role |
| accounts for all providers | accounts for the servers used |
| `<certbot_home>/etc/ca-bundle.pem` | removed, `/etc/ssl/certs` of the host is mounted |
| `systemd_services` and `systemd_timers` for the renew units | units are created by the role |
| - | `certbot_ca_certificates` adds private CAs to the bundle of Certbot |
| - | the dependencies `requires`, `wants`, `after`, `part_of`, `binds_to` and `requires_mounts_for` are set with `certbot_container` |

### Tests

The molecule scenario `default` uses tart with two VMs with Debian 13, the VMs need access to `c0d3cr.io`, `ghcr.io` and Let's Encrypt staging.

| Platform | Test case |
|---|---|
| `molecule-certbot-default` | The mandatory values only, an account at Let's Encrypt staging without email, no realm |
| `molecule-certbot` | [Pebble](https://github.com/letsencrypt/pebble) as ACME server with its TLS root in `certbot_ca_certificates`, a realm, `dns-hetzner` and the dependencies `wants`, `after` and `requires_mounts_for` |

`prepare` starts pebble on `molecule-certbot` and copies its TLS root to the host, the host does not trust it.
`check` runs `converge` with `--check` on the VMs where the role never ran.
`converge` registers the accounts and requests the certificate from pebble, which only works with the bundle of the role. `idempotence` checks that nothing is repeated.
`side_effect` checks the credentials of `dns-hetzner`, runs the role with `certbot_container` not a dictionary, a plugin without `dns-`,
a line break in the credentials, a realm without `realm`, an unknown key of a realm, a DNS plugin of a realm that is not configured,
an unknown provider, the former variable `certbot_publish`, `certbot_podman_socket` no boolean, an unknown variable in `certbot_environment`
and a private key in `certbot_ca_certificates` and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`).
Then it enables the podman socket and removes the plugin on `molecule-certbot`, Certbot has to restart,
on `molecule-certbot-default` the role runs again without a change and Certbot must not restart.
`verify` checks the quadlet unit with the dependencies and the mounts, the bundle with the CAs of the host and the private CA,
the podman socket in the container, the issuer of the certificate, that the credentials were removed and runs the renew service.

```
cd pki_certbot
MOLECULE_TART_IMAGE='debian' molecule test
```
