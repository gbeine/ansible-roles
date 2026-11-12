#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_freshrss_user
short_description: Creates a FreshRSS user and keeps its passwords and settings up to date
description:
  - Runs PHP in the container of FreshRSS with podman exec as the user of the image, the passwords are passed on stdin.
  - Creates the user without default feeds if it does not exist.
  - Checks the password and the API password with password_verify and only sets them if they differ,
    the API password also updates the key of the Fever API.
  - Keeps the language, the email (mail_login) and is_admin of the user up to date.
options:
  container:
    description: The name of the container of FreshRSS.
    type: str
    required: true
  name:
    description: The name of the user.
    type: str
    required: true
  password:
    description: The password of the user.
    type: str
    required: true
  api_password:
    description: The API password of the user, no API password without it.
    type: str
  language:
    description: The language of the user.
    type: str
  email:
    description: The email address of the user.
    type: str
  admin:
    description: Whether the user is an administrator.
    type: bool
    default: false
  user:
    description: The user of the image running FreshRSS.
    type: str
    default: abc
'''

EXAMPLES = r'''
- name: 'Create the user'
  app_freshrss_user:
    container: 'freshrss'
    name: 'alice'
    password: 'secret-password'
    admin: true
'''

RETURN = r'''
created:
  description: Whether the user was created.
  returned: always
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule

# Reads {name, password, api_password, language, email, admin} from stdin
USER = r'''
require '/app/www/cli/_cli.php';
$in = json_decode(stream_get_contents(STDIN), true);
$name = $in['name'];
$changed = false;
$created = false;
if (!FreshRSS_user_Controller::checkUsername($name)) {
    fail('FreshRSS: invalid user name ' . $name);
}
if (!FreshRSS_user_Controller::userExists($name)) {
    $values = array_filter(['language' => $in['language'], 'is_admin' => $in['admin']], fn($v) => $v !== null);
    if (!FreshRSS_user_Controller::createUser($name, $in['email'], $in['password'], $values, false)) {
        fail('FreshRSS: cannot create the user ' . $name);
    }
    $changed = $created = true;
}
$conf = FreshRSS_UserConfiguration::getForUser($name);
if ($conf === null) {
    fail('FreshRSS: invalid configuration of the user ' . $name);
}
$updated = [];
if ($in['language'] !== null && $conf->language !== $in['language']) {
    $updated['language'] = $in['language'];
}
if ((bool)$conf->is_admin !== $in['admin']) {
    $updated['is_admin'] = $in['admin'];
}
$email = ($in['email'] !== null && $conf->mail_login !== $in['email']) ? $in['email'] : null;
$password = password_verify($in['password'], (string)$conf->passwordHash) ? '' : $in['password'];
if ($updated !== [] || $email !== null || $password !== '') {
    if (!FreshRSS_user_Controller::updateUser($name, $email, $password, $updated)) {
        fail('FreshRSS: cannot update the user ' . $name);
    }
    $changed = true;
}
if ($in['api_password'] !== null) {
    $conf = FreshRSS_UserConfiguration::getForUser($name);
    if (!password_verify($in['api_password'], (string)$conf->apiPasswordHash)) {
        cliInitUser($name);
        $error = FreshRSS_api_Controller::updatePassword($in['api_password']);
        if ($error !== false) {
            fail('FreshRSS: cannot set the API password of ' . $name . ': ' . $error);
        }
        $changed = true;
    }
}
echo "\n" . json_encode(['changed' => $changed, 'created' => $created]);
'''


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            name=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
            api_password=dict(type='str', no_log=True),
            language=dict(type='str'),
            email=dict(type='str'),
            admin=dict(type='bool', default=False),
            user=dict(type='str', default='abc'),
        ),
        supports_check_mode=False,
    )
    params = module.params
    data = dict((key, params[key]) for key in ('name', 'password', 'api_password', 'language', 'email', 'admin'))
    args = ['podman', 'exec', '-i', '--user', params['user'], params['container'], 'php', '-r', USER]
    rc, out, err = module.run_command(args, data=json.dumps(data), binary_data=True)
    if rc != 0:
        module.fail_json(msg='FreshRSS failed: %s' % (err.strip() or out.strip()))
    try:
        result = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        module.fail_json(msg='FreshRSS returned no result: %s %s' % (out.strip(), err.strip()))
    module.exit_json(changed=result['changed'], created=result['created'])


if __name__ == '__main__':
    main()
