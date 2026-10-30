- The role needs the filters `hostname_short` and `ipv4_netmask2prefixlength` from `common_filters`, so add `common_filters` to the play before `bootstrap_debian`:

```yaml
- name: 'Configure host42.example.org'
  become: 'yes'
  hosts: 'host42'
  roles:
    - 'common_filters'
    - 'bootstrap_debian'
```

- Repositories, packages, timezone and hostname/hosts are always configured. Storage and accounts run when their lists are not empty. Networking, logrotate and unattended upgrades have to be enabled with `debian_networking_enable`, `debian_logrotate_enable` and `debian_unattended_upgrades_enable`, because they overwrite system configuration files completely.
- `debian_hostname` is mandatory.
- `debian_repositories` replaces the default Debian repositories completely. The entries are written as deb822 files to `/etc/apt/sources.list.d/<name>.sources`:

```yaml
debian_repositories:
  - name: 'debian'
    types: 'deb'
    uris: 'http://deb.debian.org/debian'
    suites: [ 'trixie', 'trixie-updates' ]
    components: [ 'main', 'contrib', 'non-free-firmware' ]
  - name: 'example'
    uris: 'https://repo.example.org/debian'
    suites: [ 'stable' ]
    components: [ 'main' ]
    signed_by: 'https://repo.example.org/key.asc'
```

- On Debian 12 the installer writes `/etc/apt/sources.list`, which is not removed. Remove it manually to avoid duplicate sources.
- Bind mounts in `debian_mounts` default to `fs: none` and `options: rw,bind`.
- This role replaces the former roles `bootstrap_hosts`, `bootstrap_logrotate`, `bootstrap_networking`, `bootstrap_packages`, `bootstrap_repositories`, `bootstrap_storage`, `bootstrap_timezone`, `bootstrap_accounts`, `apt_common` and `apt_unattended_upgrades`. The inventory variables were renamed:

| Former variable | New variable |
|---|---|
| `packages` | `debian_packages` |
| `local_packages` | `debian_local_packages` |
| `timezone` | `debian_timezone` |
| `dns_hostname` | `debian_hostname` |
| `hosts` | `debian_hosts` |
| `cloud_manage_etc_hosts` | `debian_cloud_manage_etc_hosts` |
| `storage` | `debian_storage` |
| `mount` | `debian_mounts` |
| `bootstrap_networking_interfaces` | `debian_network_interfaces` |
| `bootstrap_groups` | `debian_groups` |
| `bootstrap_users` | `debian_users` |
| `logrotate_files` | `debian_logrotate_files` |
| `unattended_upgrades_*` | `debian_unattended_upgrades_*` |
| `bootstrap_<area>_enable` (role `bootstrap`) | `debian_networking_enable`, `debian_logrotate_enable`, `debian_unattended_upgrades_enable` |
