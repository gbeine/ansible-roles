### `certbot_provider_server`

A dict containing the URL of an ACME provider, e.g. a Step CA.

```
certbot_provider_server:
  my-ca: 'https://ca.internal/acme/acme/directory'
```

The provider can now be selected as default provider by setting:

```
certbot_provider: 'my-ca'
```

### `certbot_plugins`

A list of plugins that should be configured.

```
certbot_plugins:
  - 'dns-hetzner'
  - 'dns-powerdns'
```

Currently, only configurations for `dns-hetzner` and `dns-powerdns` will be created.

### `certbot_realms`

A list of dicts following this structure

| Key                     | Default                                     | Description                                                                                      |
|-------------------------|---------------------------------------------|--------------------------------------------------------------------------------------------------|
| `realm`                 | -                                           | Used a name for the files and primary domain name of the certificate.                            |
| `server`                | `certbot_provider_server[certbot_provider]` | The URL of the ACME CA provider.                                                                 |
| `authenticator`         | 'standalone'                                | The name of the authenticator plugin to use.                                                     |
| `authenticator_options` | ''                                          | Additional options for the authenticator plugin, e.g. the path to a credential file.             |
| `key_type`              | 'ecdsa'                                     | The type of key to generate. Can be 'ecdsa' (recommended) or 'rsa' (not recommended).            |
| `elliptic_curve`        | -                                           | Only for `key_type` 'ecdsa': If not set, 'secp256r1' is used. See RFC 8446 for supported values. |
| `key_size`              | 2048                                        | Only for `key_type` 'rsa': The size of the RSA key.                                              |
| `domains`               | []                                          | A list of domains to add to the certificate.                                                     |


```
certbot_realms:
  - realm: 'example.org'
    server: 'https://ca.internal/acme/acme/directory'
    authenticator: 'dns-hetzner'
    authenticator_options: "{{ pki_certbot__authenticator['dns-hetzner'] }}"
    domains: [ 'host1.example.org', 'www.example.org' ]
```
