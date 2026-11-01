The role installs [Icinga 2](https://icinga.com/docs/icinga-2/latest/) from the Debian packages as agent of a parent zone, e.g. a master installed with `monitoring_icinga_master`,
together with the monitoring plugins of Debian.
Additional plugins and their `CheckCommand`s are installed by `monitoring_plugins`.

| File | Content |
|---|---|
| `/etc/icinga2/constants.conf` | `NodeName`, `ZoneName`, `TicketSalt`, the plugin directories, `PluginLocalDir` and `PluginContribDir` are `/usr/local/lib/nagios/plugins` |
| `/etc/icinga2/icinga2.conf` | ITL, plugins, enabled features and everything below `/usr/local/etc/icinga2` |
| `/etc/icinga2/zones.conf` | Endpoint and zone of the parent, endpoint and zone of the agent, global zones `global-templates` and `director-global` |
| `/etc/icinga2/features-available/{api,checker,mainlog}.conf` | The features of the agent |
| `/etc/systemd/system/icinga2.service.d/override.conf` | Copies the certificates before every start |

### Required settings

```yaml
icinga_node_name: 'agent.example.org'
icinga_zone_name: 'master'
icinga_parent_name: 'master.example.org'
icinga_ticket_salt: 'secret'
icinga_cert_source_dir: '/etc/letsencrypt/live'
```

The role fails before it changes anything if one of these settings is missing.

### Certificates

The agent uses certificates of an external CA, e.g. certbot or step-ca, the role does not use the CSR signing of Icinga 2.
The certificates are expected in the layout of certbot below `icinga_cert_source_dir`:

| Source | Target in `/var/lib/icinga2/certs` |
|---|---|
| `<icinga_cert_source_dir>/<icinga_node_name>/chain.pem` (`icinga_cert_ca_file`) | `ca.crt` |
| `<icinga_cert_source_dir>/<icinga_node_name>/fullchain.pem` (`icinga_cert_cert_file`) | `<icinga_node_name>.crt` |
| `<icinga_cert_source_dir>/<icinga_node_name>/privkey.pem` (`icinga_cert_key_file`) | `<icinga_node_name>.key` |

The role copies the certificates to check the configuration before Icinga 2 starts,
the systemd override copies newer certificates on every start of Icinga 2, so a restart after the renewal is enough.
The certificates belong to the Icinga user, the key has mode `0400`.

### Connection to the parent

By default the endpoint of the parent has no `host`, only the parent connects to the agent.
With `icinga_parent_host` the agent connects to the parent as well, e.g. if the agent is not reachable from the parent:

```yaml
icinga_parent_host: 'master.example.org'
icinga_parent_port: 5665   # default
```

### Features

The role enables the features `api`, `checker` and `mainlog` and removes all other files from `features-enabled`,
e.g. the feature `notification` enabled by the Debian package.

### Restart

The role checks the configuration with `icinga2 daemon -C` if the configuration, the certificates, the features or the systemd override changed,
an invalid configuration fails the role before Icinga 2 is restarted.
Icinga 2 is restarted only if it was running and something changed, otherwise it is started and enabled.

### Migration

| Before | Now |
|---|---|
| `icinga_cert_source_dir` optional, without it no systemd override | `icinga_cert_source_dir` is required, the systemd override is always written |
| endpoint of the parent without `host` | unchanged by default, `icinga_parent_host` lets the agent connect to the parent |
| fixed list of disabled features | all features except `api`, `checker` and `mainlog` are disabled |
| Debian 12 | only Debian 13 |
| handler `Restart Icinga` | restart in the role after `icinga2 daemon -C` |

### Tests

The molecule scenario `default` uses tart with one VM `molecule-icinga-agent`.
`prepare` installs Icinga 2 with the defaults of the package (feature `notification` enabled, service running) and creates a CA and the certificates of the agent in the layout of certbot.
`side_effect` changes `icinga_main_log_severity` and checks that Icinga 2 was restarted.
`verify` checks the service, `icinga2 daemon -C`, the enabled features, `zones.conf`, owner and mode of the certificates
and connects to the API with `openssl s_client` to check the certificate of the agent against the CA.

```
cd monitoring_icinga_agent
MOLECULE_TART_IMAGE='debian' molecule test
```
