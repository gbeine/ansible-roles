#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_linkding_admin
short_description: Creates the administrator of linkding and keeps its password and email up to date
description:
  - Runs the Django shell of linkding in the container as www-data, the user of linkding,
    the name, the email and the password are passed on stdin, they are never arguments of a process.
  - Creates the user if it does not exist, checks the password with check_password and only sets it if it differs.
  - Keeps the email up to date and makes the user an active superuser.
options:
  container:
    description: The name of the container of linkding.
    type: str
    required: true
  name:
    description: The name of the administrator.
    type: str
    required: true
  email:
    description: The email address of the administrator, empty for none.
    type: str
    default: ''
  password:
    description: The password of the administrator.
    type: str
    required: true
'''

EXAMPLES = r'''
- name: 'Create the administrator'
  app_linkding_admin:
    container: 'linkding'
    name: 'admin'
    email: 'admin@example.org'
    password: 'secret-admin-password'
'''

RETURN = r'''
created:
  description: Whether the administrator was created.
  returned: always
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule

# Reads {name, email, password} from stdin
ADMIN = r'''
import json, sys
from django.contrib.auth import get_user_model
data = json.load(sys.stdin)
User = get_user_model()
user = User.objects.filter(username=data['name']).first()
created = changed = False
if user is None:
    user = User(username=data['name'])
    created = changed = True
if not user.check_password(data['password']):
    user.set_password(data['password'])
    changed = True
for attribute, value in (('email', data['email']), ('is_superuser', True), ('is_staff', True), ('is_active', True)):
    if getattr(user, attribute) != value:
        setattr(user, attribute, value)
        changed = True
if changed:
    user.save()
print()
print(json.dumps({'changed': changed, 'created': created}))
'''


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            name=dict(type='str', required=True),
            email=dict(type='str', default=''),
            password=dict(type='str', required=True, no_log=True),
        ),
        supports_check_mode=False,
    )
    params = module.params
    # The working directory and the virtual environment are set by the image
    args = ['podman', 'exec', '-i', '--user', 'www-data', params['container'],
            'python', 'manage.py', 'shell', '-c', ADMIN]
    data = dict((key, params[key]) for key in ('name', 'email', 'password'))
    rc, out, err = module.run_command(args, data=json.dumps(data), binary_data=True)
    if rc != 0:
        module.fail_json(msg='linkding failed: %s' % (err.strip() or out.strip()))
    try:
        result = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError, KeyError):
        module.fail_json(msg='linkding returned no result: %s %s' % (out.strip(), err.strip()))
    module.exit_json(changed=result['changed'], created=result['created'])


if __name__ == '__main__':
    main()
