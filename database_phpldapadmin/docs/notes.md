phpLDAPadmin runs in the container image [phpldapadmin/phpldapadmin](https://hub.docker.com/r/phpldapadmin/phpldapadmin) (`latest` by default) as podman quadlet,
FrankenPHP answers on port 8080 of the container. phpLDAPadmin 2 is a Laravel application, it keeps no data of its own, the role creates no directories.
The users log in with their own entry of the directory, by default with `uid` in the object class `posixAccount`.

### Configuration

phpLDAPadmin is configured with `phpldapadmin_environment`, merged over the default of the role, see the
[configuration](https://github.com/leenooks/phpLDAPadmin/wiki/Configuration-Variables).
Laravel reads its options only from the environment and from `.env` of the image, the environment takes precedence.
`LDAP_HOST` is mandatory, without it phpLDAPadmin connects to `127.0.0.1` in the container.
The default sets `APP_TIMEZONE` to `phpldapadmin_timezone`, Laravel reads its time zone from it and uses UTC otherwise.
Values are strings, booleans are written as `'true'` or `'false'`.

```yaml
phpldapadmin_environment:
  LDAP_HOST: 'ldap.example.org'
  LDAP_PORT: '636'
  LDAP_CONNECTION: 'ldaps'
  LDAP_BASE_DN: 'dc=example,dc=org'
  LDAP_NAME: 'Example'
  LDAP_USERNAME: 'cn=reader,dc=example,dc=org'
  LDAP_LOGIN_ATTR: 'uid'
  LDAP_LOGIN_OBJECTCLASS: 'posixAccount'
```

`LDAP_USERNAME` and the secret `LDAP_PASSWORD` are the entry phpLDAPadmin uses to search the user of a login,
without them it searches anonymously. With `LDAP_LOGIN_ATTR: 'dn'` the users log in with their DN.

### Secrets

`phpldapadmin_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is the variable of phpLDAPadmin.
Laravel reads its configuration only from the environment and `.env` (`config/*.php` of phpLDAPadmin 2.3.13), there are no file variables,
so the secrets are passed in the environment of the container with `type=env,target=<target>`, they are not part of the quadlet unit.

| Target | Description |
|---|---|
| `APP_KEY` | The key of Laravel, mandatory, it encrypts the sessions and the password of the login |
| `LDAP_PASSWORD` | The password of `LDAP_USERNAME` |
| `MEMCACHED_PASSWORD` | The password of Memcached for the cache |
| `AWS_SECRET_ACCESS_KEY` | The key of DynamoDB for the cache |

`APP_KEY` is `base64:` followed by 32 random bytes in base64, without it the image generates a new key for every container,
after an update every user would have to log in again:

```shell
echo "base64:$(openssl rand -base64 32)"
```

```yaml
phpldapadmin_secrets:
  - name: 'phpldapadmin_app_key'
    data: "{{ vault_phpldapadmin_app_key }}"
    target: 'APP_KEY'
  - name: 'phpldapadmin_ldap_password'
    data: "{{ vault_phpldapadmin_ldap_password }}"
    target: 'LDAP_PASSWORD'
```

None of the targets may be set in `phpldapadmin_environment`.

### Allowed variables

The role only allows the variables in `database_phpldapadmin__environment_allowed` and the secrets listed above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password that has to be passed as secret.
The list is generated from the `env()` calls of `config/*.php` of phpLDAPadmin 2.3.13 without the secrets,
`SERVER_NAME` (the port of FrankenPHP) and the variables of `/sbin/init-docker` are set by the image, new versions of the image may add variables.
The check uses the environment of the container after merging `phpldapadmin_container`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `phpldapadmin_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.
The merge is not recursive, `phpldapadmin_container.environment` replaces the environment, use `phpldapadmin_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `phpldapadmin_labels`, the address is `http://<phpldapadmin_ip>:8080`.
Laravel trusts the proxies of the private networks by default (`APP_TRUST_PROXIES`).

```yaml
phpldapadmin_container:
  wants: [ 'slapd.service' ]
  after: [ 'slapd.service' ]
```

### Validation

The role checks before any change:

- `phpldapadmin_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `LDAP_HOST` is set, the secret `APP_KEY` is set and has the format of Laravel
- no secret is set in `phpldapadmin_environment`, secrets are not empty and contain no line breaks
- only allowed environment variables without line breaks and allowed secrets are set in the container

If `phpldapadmin_container` or `phpldapadmin_environment` is no dictionary, merging it fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the secrets and the quadlet unit.
The start and the wait for phpLDAPadmin do not run in check mode.

### Restart and updates

phpLDAPadmin is restarted if it was running and a secret or the quadlet unit changed, otherwise it is started and enabled.
Afterwards the role waits until phpLDAPadmin shows the login form and shows the journal of the service if it does not.
Updates of the image are done by `container_update` with `phpldapadmin_autoupdate_enabled: true` and `phpldapadmin_autoupdate_schedule`,
without `phpldapadmin_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role is new, there are no former variables. phpLDAPadmin 2 replaces the configuration of phpLDAPadmin 1 (`config.php`) by the environment.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.
`prepare` creates the podman network, pulls the image and installs `slapd` of Debian with the domain `molecule.test` on the VMs,
the container reaches it through the gateway of the network. On every VM it creates the user `uid=molecule,ou=people,dc=molecule,dc=test`.

| Platform | Test case |
|---|---|
| `molecule-phpldapadmin-default` | Only `LDAP_HOST`, `LDAP_BASE_DN` and the secret `APP_KEY` |
| `molecule-phpldapadmin` | IPv6, labels, `LDAP_NAME`, `LDAP_USERNAME` with the secret `LDAP_PASSWORD`, `SESSION_LIFETIME` |

`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `phpldapadmin_container` and `phpldapadmin_environment` not a dictionary, `phpldapadmin_secrets` not a list,
a secret without `target`, without `LDAP_HOST`, without `APP_KEY` and with an invalid `APP_KEY`, `LDAP_PASSWORD` in the environment,
`SERVER_NAME` and an unknown variable in the environment, a line break in a value and an unknown secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `SESSION_LIFETIME` on `molecule-phpldapadmin`, the quadlet unit changes and phpLDAPadmin has to restart,
`molecule-phpldapadmin-default` runs again without a change and must not restart.
`verify` checks the quadlet unit with the secrets in the environment without their values, the service without automatic restarts,
the addresses, the time zone and `APP_TIMEZONE` and the login form.
On `molecule-phpldapadmin` it logs in with a wrong password (back to `/login`) and with the right password of `molecule`
and reads the start page and the base DNs of the directory (`/ajax/bases`) with the session (the cookies are read from `Set-Cookie`, the uri module keeps no cookies of a redirect it does not follow).

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_phpldapadmin
MOLECULE_TART_IMAGE='debian' molecule test
```
