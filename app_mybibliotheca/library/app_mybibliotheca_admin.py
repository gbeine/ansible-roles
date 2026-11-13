#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_mybibliotheca_admin
short_description: Creates the administrator of MyBibliotheca and keeps its password and email up to date
description:
  - Runs Python in the container of MyBibliotheca with the user service of MyBibliotheca,
    the configuration of PostgreSQL comes from the environment of the container.
    The name, the email and the password are passed on stdin, they are never arguments of a process.
  - Fails if PostgreSQL is not the active backend of MyBibliotheca, e.g. for an existing Kuzu installation.
  - Looks up the user by its name and creates it if it does not exist, so the onboarding of MyBibliotheca is never open.
  - Checks the password with the password policy of MyBibliotheca and only sets it if it differs,
    keeps the email up to date and makes the user an active administrator without a forced password change.
options:
  container:
    description: The name of the container of MyBibliotheca.
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
'''

EXAMPLES = r'''
- name: 'Create the administrator'
  app_mybibliotheca_admin:
    container: 'mybibliotheca'
    name: 'admin'
    email: 'admin@example.org'
    password: 'secret-admin-password-1'
'''

RETURN = r'''
created:
  description: Whether the administrator was created.
  returned: always
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule

WORKDIR = '/app'

# Reads {name, email, password} from stdin, uses the services of MyBibliotheca like the onboarding
SCRIPT = r'''
import json
import sys
import traceback


class Failure(Exception):
    pass


def run(data):
    from werkzeug.security import generate_password_hash

    from app.domain.models import User
    from app.infrastructure.persistence_state import get_active_backend
    from app.services import user_service

    backend = get_active_backend()
    if backend != 'postgres':
        raise Failure('MyBibliotheca uses %s, not PostgreSQL' % backend)
    if not User.is_password_strong(data['password']):
        raise Failure('The password does not meet the password policy of MyBibliotheca')

    user = user_service.get_user_by_username_sync(data['name'])
    if user is None:
        user = user_service.create_user_sync(
            username=data['name'], email=data['email'], password_hash=generate_password_hash(data['password']),
            is_admin=True, is_active=True, password_must_change=False,
        )
        if user is None:
            raise Failure('The user could not be created, the email may belong to another user')
        return {'changed': True, 'created': True}

    changed = False
    if not user.check_password(data['password']):
        user.set_password(data['password'])
        changed = True
    if user.email != data['email']:
        user.email = data['email']
        changed = True
    for key in ('is_admin', 'is_active'):
        if not getattr(user, key):
            setattr(user, key, True)
            changed = True
    if user.password_must_change:
        user.password_must_change = False
        changed = True
    if changed and user_service.update_user_sync(user) is None:
        raise Failure('The user could not be updated')
    return {'changed': changed, 'created': False}


rc = 0
try:
    result = run(json.loads(sys.stdin.read()))
except Failure as error:
    result, rc = {'error': str(error)}, 1
except Exception as error:
    result, rc = {'error': '%s: %s' % (type(error).__name__, error), 'trace': traceback.format_exc().splitlines()[-15:]}, 1
finally:
    # The pool of PostgreSQL keeps threads, without close() the interpreter waits for them at the exit
    try:
        from app.infrastructure.postgres_store import get_postgres_store
        get_postgres_store().close()
    except Exception:
        pass
sys.stdout.write('\n' + json.dumps(result) + '\n')
sys.stdout.flush()
sys.exit(rc)
'''


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            name=dict(type='str', required=True),
            email=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
        ),
        supports_check_mode=False,
    )
    params = module.params
    args = ['podman', 'exec', '-i', '-w', WORKDIR, params['container'], 'python3', '-c', SCRIPT]
    data = dict((key, params[key]) for key in ('name', 'email', 'password'))
    rc, out, err = module.run_command(args, data=json.dumps(data), binary_data=True)
    result = None
    for line in reversed(out.strip().splitlines()):
        try:
            result = json.loads(line)
        except ValueError:
            continue
        if isinstance(result, dict):
            break
    if not isinstance(result, dict):
        # The imports of MyBibliotheca log to stdout and stderr, the hints of the pool are left out
        lines = [line for line in err.strip().splitlines() if 'pool' not in line and 'hint:' not in line]
        module.fail_json(msg='MyBibliotheca returned no result (rc %s): %s' % (rc, ' '.join(lines[-20:] or out.strip().splitlines()[-20:])))
    if rc != 0 or 'error' in result:
        module.fail_json(msg='MyBibliotheca failed: %s' % result.get('error', 'rc %s' % rc), trace=result.get('trace', []))
    module.exit_json(changed=result['changed'], created=result['created'])


if __name__ == '__main__':
    main()
