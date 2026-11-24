The role contains Ansible modules used by several roles, it has no tasks and no variables.
A role using a module declares `common_library` as dependency in its `meta/main.yml`, Ansible loads the modules of the dependency:

```yaml
dependencies:
  - role: 'common_library'
```

### common_library_htpasswd

Writes an htpasswd file with bcrypt hashes (`$2y$`) of the passwords, users missing in `passwords` are removed from the file.
It keeps the hash of a password that did not change, so the file only changes if a user or a password changes,
the module reports `changed` only for a changed file, owner, group or mode. It supports check mode.

| Option | Default | Description |
|---|---|---|
| `path` | | The htpasswd file |
| `passwords` | | The passwords of the users by their names (`no_log`), the names must not contain `:` |
| `bcrypt_cost` | `10` | The cost of new bcrypt hashes |
| `owner`, `group` | `root` | Owner and group of the file |
| `mode` | `0600` | Mode of the file |

The module needs the Python library `bcrypt` on the host, the role using it installs `python3-bcrypt`.
bcrypt only uses 72 bytes of a password, the roles reject longer passwords.

```yaml
- name: 'Write the users of the dashboard'
  common_library_htpasswd:
    path: '/opt/traefik/users/dashboard.htpasswd'
    passwords:
      admin: "{{ vault_traefik_admin_password }}"
```

Used by `app_zot` (`zot_users`) and `webserver_traefik` (`traefik_usersfile`).

### Tests

The role has no molecule scenario, the modules are tested by the scenarios of the roles using them.
