- The role needs the filters `hostname_short` and `ipv4_netmask2prefixlength` from `common_filters`, so add `common_filters` to the play before `bootstrap_debian`:

```yaml
- name: 'Configure host42.example.org'
  become: 'yes'
  hosts: 'host42'
  roles:
    - 'common_filters'
    - 'bootstrap_debian'
```

- The role starts with `apt-get update` and the installation of the packages required by the apt modules, followed by the repositories and storage, so packages can rely on mounted directories.
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

### Tests

The molecule scenario `default` runs the role in [tart](https://tart.run) VMs on a macOS controller.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.

| Platform | Tested |
|---|---|
| `molecule-bootstrap-debian-minimal` | repositories, packages, timezone, hostname and hosts with defaults |
| `molecule-bootstrap-debian-full` | additionally storage (additional disk `/dev/vdb`) and bind mounts, networking (`dummy0`), accounts, logrotate and unattended upgrades |

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and the collection `ansible.posix`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd bootstrap_debian
MOLECULE_TART_IMAGE='debian' molecule test
```

The test cases and expectations are defined in `molecule/default/test_cases.yml`.
If the additional disk does not appear as `/dev/vdb` in the VM, adjust the device there.
