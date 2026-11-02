Certbot runs in the container image `c0d3.sh/container/certbot` as podman quadlet.
The container idles, certbot is run with `podman exec certbot certbot …`, e.g. by the role and by the renew timer.
The configuration, accounts and certificates are in `<certbot_home>/etc` (mounted as `/etc/letsencrypt`),
the certificates of a realm are in `<certbot_home>/etc/live/<realm>`.

### CA certificates

`/etc/ssl/certs` of the host is mounted as `/etc/ssl/host-certs` and used with `REQUESTS_CA_BUNDLE`,
so ACME servers with certificates of an own CA (e.g. a Step CA) are trusted if the CA is trusted by the host, e.g. with `debian_pki_enable` of `bootstrap_debian`.

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

The role fails before it changes anything if `certbot_plugins` is not a dict of `dns-*` plugins with credentials,
if `certbot_provider` is not in `certbot_provider_server`, if a realm has no `realm` or uses a DNS plugin that is not configured.

### Restarting containers in a post_hook

The image contains podman, with `certbot_podman_socket: true` the podman socket of the host is mounted and `CONTAINER_HOST` is set,
so `podman restart <container>` in a `post_hook` restarts the container on the host.
The podman socket must be enabled, e.g. with `podman_socket_enabled: true` of `container_podman`.

### Standalone authenticator

The `standalone` authenticator answers the HTTP challenge in the container on port 80, publish the port with `certbot_publish` if the ACME server cannot reach the address of the container:

```yaml
certbot_publish:
  - '80:80'
```

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
| `certbot_plugins` as list, `certbot_dns_hetzner_api_token`, `certbot_dns_powerdns_api_url`, `certbot_dns_powerdns_api_key` | `certbot_plugins` as dict with the credentials |
| `authenticator_options: "{{ pki_certbot__authenticator['dns-hetzner'] }}"` | not needed, the credentials are added by the role |
| accounts for all providers | accounts for the servers used |
| `<certbot_home>/etc/ca-bundle.pem` | removed, `/etc/ssl/certs` of the host is mounted |
| `systemd_services` and `systemd_timers` for the renew units | units are created by the role |

### Tests

The molecule scenario `default` uses tart with one VM `molecule-certbot`.
`prepare` starts [Pebble](https://github.com/letsencrypt/pebble) as ACME server and adds its TLS root to the CA certificates of the host.
`converge` registers an account and requests a certificate from Pebble, `idempotence` checks that both are not repeated.
`side_effect` checks the credentials of `dns-hetzner`, then enables the podman socket and removes the plugin, Certbot has to be restarted.
`verify` checks the quadlet unit, the podman socket in the container, the issuer of the certificate, that the credentials were removed and runs the renew service.
The VM needs access to `c0d3.sh` and `ghcr.io`.

```
cd pki_certbot
MOLECULE_TART_IMAGE='debian' molecule test
```
