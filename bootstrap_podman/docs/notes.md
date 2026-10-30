There is one special variable: `podman___update_mode`.
It is intended to be used in playbooks or runs.
It's a boolean variable, the default is `false`.
See below for details.

### podman networks

It is required to define a default network for podman containers.

```yaml
podman_network: 'podman99'
```

The list of networks required at least four attributes for every network:
- the `name` of the network
- the networks IPv4 `address` 
- the `gateway` IPv4 address
- the `netmask` as number

```yaml
podman_networks:
  - name: 'podman99'
    address: '192.168.99.0'
    gateway: '192.168.99.1'
    netmask: 24
```

The DNS configuration can be disabled by setting `disable_dns` to `true`.

```yaml
podman_networks:
  - name: 'podman99'
    address: '192.168.99.0'
    gateway: '192.168.99.1'
    netmask: 24
    disable_dns: true
```

It is possible to specify optional IPv6 addresses
- setting `ipv6` to `true` is required
- the IPv6 gateway address: `ipv6_gateway`
- the prefix length for IPv6 addresses as number: `ipv6_prefixlength`

```yaml
podman_networks:
  - name: 'podman99'
    address: '192.168.99.0'
    gateway: '192.168.99.1'
    netmask: 24
    ipv6_gateway: 'fd00::99:0'
    ipv6_prefixlength: 112
    ipv6: true
```

### Dealing with container updates. 

The typical mode for podman containers is to be installed using the specific roles.

For updates, it is recommended to use the same roles while setting `podman___update_mode` to `true`.
This can be done either on the command line using `--extra-vars`, e.g.

```shell
ansible-playbook --ask-vault-pass --tags app_foundryvtt --extra-vars podman___update_mode=yes host42.yml
```
or for multiple hosts in a playbook like

```yaml

- name: 'Update podman container: Foundry VTT'
  become: 'yes'
  hosts:
    - 'host42'
    - 'host314'
  vars:
    podman___update_mode: true
  roles:
    - role: 'common_filters'
      tags: [ 'never' ]
    - role: 'bootstrap'
      tags: [ 'never' ]
    - 'app_foundryvtt'
```

Please not the usage of 'never' for the roles `common_filters` and `bootstrap`.
Both should not be executed during the run of this playbook, but provide variables required by `app_foundryvtt`.
