#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_forgejo_admin
short_description: Creates the administrator of Forgejo and keeps its password and email up to date
description:
  - Checks the password with the API of Forgejo (GET /api/v1/user with basic authentication).
  - Creates a missing administrator with the CLI of Forgejo in the container and a random password, no secret is an argument of a process.
  - Sets the password, the email and the administrator flag with the API (PATCH /api/v1/admin/users/<name>) and a temporary access token
    created with the CLI, the token is deleted afterwards.
  - The password is only set if the check fails, so the module only reports changed for real changes.
options:
  container:
    description: The name of the container of Forgejo.
    type: str
    required: true
  url:
    description: The URL of Forgejo reachable from the host, e.g. http://10.89.0.90:3000.
    type: str
    required: true
  name:
    description: The name of the administrator.
    type: str
    required: true
  email:
    description: The email address of the administrator.
    type: str
    required: true
  password:
    description: The password of the administrator.
    type: str
    required: true
  user:
    description: The user of the image running Forgejo.
    type: str
    default: git
requirements:
  - ENABLE_BASIC_AUTHENTICATION of Forgejo is true (the default)
'''

EXAMPLES = r'''
- name: 'Create the administrator'
  app_forgejo_admin:
    container: 'forgejo'
    url: 'http://10.89.0.90:3000'
    name: 'admin'
    email: 'admin@example.org'
    password: 'secret-admin-password'
'''

RETURN = r'''
created:
  description: Whether the administrator was created.
  returned: always
  type: bool
updated:
  description: Whether the password, the email or the administrator flag was set.
  returned: always
  type: bool
'''

import base64
import json
import secrets

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.urls import open_url
from ansible.module_utils.six.moves.urllib.error import HTTPError, URLError


def api(module, method, path, auth=None, token=None, data=None):
    headers = {'Accept': 'application/json'}
    if auth is not None:
        headers['Authorization'] = 'Basic ' + base64.b64encode(('%s:%s' % auth).encode('utf-8')).decode('ascii')
    if token is not None:
        headers['Authorization'] = 'token ' + token
    body = None
    if data is not None:
        headers['Content-Type'] = 'application/json'
        body = json.dumps(data)
    try:
        response = open_url(module.params['url'].rstrip('/') + path, method=method, headers=headers, data=body, timeout=30)
        content = response.read()
        return response.getcode(), json.loads(content) if content else {}
    except HTTPError as error:
        return error.code, {}
    except URLError as error:
        module.fail_json(msg='Forgejo is not reachable at %s: %s' % (module.params['url'], error))


def cli(module, args):
    command = ['podman', 'exec', '--user', module.params['user'], module.params['container'], 'forgejo'] + args
    rc, out, err = module.run_command(command)
    if rc != 0:
        module.fail_json(msg='forgejo %s failed: %s' % (' '.join(args[:3]), err.strip() or out.strip()))
    return out


def user_exists(module, name):
    lines = cli(module, ['admin', 'user', 'list']).strip().splitlines()
    if not lines:
        return False
    header = lines[0].split()
    column = header.index('Username') if 'Username' in header else 1
    return any(len(line.split()) > column and line.split()[column] == name for line in lines[1:])


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            url=dict(type='str', required=True),
            name=dict(type='str', required=True),
            email=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
            user=dict(type='str', default='git'),
        ),
        supports_check_mode=True,
    )
    params = module.params
    auth = (params['name'], params['password'])

    status, current = api(module, 'GET', '/api/v1/user', auth=auth)
    if status == 200 and current.get('email') == params['email'] and current.get('is_admin'):
        module.exit_json(changed=False, created=False, updated=False)
    if module.check_mode:
        module.exit_json(changed=True, created=False, updated=True)

    created = False
    if not user_exists(module, params['name']):
        cli(module, ['admin', 'user', 'create', '--admin', '--username', params['name'], '--email', params['email'],
                     '--random-password', '--must-change-password=false'])
        created = True

    token_name = 'ansible-' + secrets.token_hex(8)
    token = cli(module, ['admin', 'user', 'generate-access-token', '--username', params['name'], '--token-name', token_name,
                         '--scopes', 'write:admin', '--raw']).strip().splitlines()[-1].strip()
    status, result = api(module, 'PATCH', '/api/v1/admin/users/' + params['name'], token=token, data={
        'login_name': params['name'],
        'source_id': 0,
        'email': params['email'],
        'password': params['password'],
        'admin': True,
        'must_change_password': False,
    })
    if status != 200:
        api(module, 'DELETE', '/api/v1/users/%s/tokens/%s' % (params['name'], token_name), token=token)
        module.fail_json(msg='Forgejo refused to update the administrator %s (HTTP %s), check the password rules of Forgejo.' % (params['name'], status))
    status, result = api(module, 'DELETE', '/api/v1/users/%s/tokens/%s' % (params['name'], token_name), auth=auth)
    if status not in (204, 404):
        module.fail_json(msg='Forgejo refused to delete the temporary token %s (HTTP %s).' % (token_name, status))
    module.exit_json(changed=True, created=created, updated=True)


if __name__ == '__main__':
    main()
