To run through bootstrapping, specify the role in a playbook.
Make sure to enable the common filters before.

```yaml

- name: 'Configure host42.example.org'
  become: 'yes'
  hosts: 'host42'
  roles:
    - 'common_filters'
    - 'bootstrap'
    - ... # other roles 
```
