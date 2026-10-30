### Access control

See [unbound Manual](https://unbound.docs.nlnetlabs.nl/en/latest/manpages/unbound.conf.html#unbound-conf-access-control) for details.

```yaml
unbound_access_control:
  - '192.168.98.0/24 allow' # Allow access from network 
  - '172.10.11.12/24 deny'  # Deny access from network
```
