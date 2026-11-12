#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_nextcloud_user
short_description: Creates a Nextcloud user and keeps its password, display name, email and groups up to date
description:
  - Runs PHP in the container of Nextcloud with podman exec as the user of the image, the password is passed on stdin.
  - Creates the user if it does not exist.
  - Checks the password with the user manager of Nextcloud and only sets it if it differs.
  - Keeps the display name and the email up to date, adds the user to its groups and creates missing groups.
  - With groups the user is removed from the groups that are not listed, the group admin is set with admin.
options:
  container:
    description: The name of the container of Nextcloud.
    type: str
    required: true
  name:
    description: The name (login) of the user.
    type: str
    required: true
  password:
    description: The password of the user.
    type: str
    required: true
  display_name:
    description: The display name of the user, not changed without it.
    type: str
  email:
    description: The email address of the user, not changed without it.
    type: str
  groups:
    description: The groups of the user without admin, the groups are not changed without it.
    type: list
    elements: str
  admin:
    description: Whether the user is a member of the group admin.
    type: bool
    default: false
  user:
    description: The user of the image running Nextcloud.
    type: str
    default: abc
'''

EXAMPLES = r'''
- name: 'Create the user'
  app_nextcloud_user:
    container: 'nextcloud'
    name: 'alice'
    password: 'secret-alice-password'
    display_name: 'Alice'
    email: 'alice@example.org'
    groups: [ 'family' ]
'''

RETURN = r'''
created:
  description: Whether the user was created.
  returned: always
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule

# Reads {name, password, display_name, email, groups, admin} from stdin
USER = r'''
$in = json_decode(stream_get_contents(STDIN), true);
require_once '/app/www/public/lib/base.php';
function fail(string $message): void {
    fwrite(STDERR, $message . "\n");
    exit(1);
}
$users = \OCP\Server::get(\OCP\IUserManager::class);
$groups = \OCP\Server::get(\OCP\IGroupManager::class);
$name = $in['name'];
$changed = false;
$created = false;
$user = $users->get($name);
if ($user === null) {
    $user = $users->createUser($name, $in['password']);
    if (!$user) {
        fail('Nextcloud: cannot create the user ' . $name);
    }
    $changed = $created = true;
} elseif ($users->checkPassword($name, $in['password']) === false) {
    if (!$user->setPassword($in['password'])) {
        fail('Nextcloud: cannot set the password of ' . $name);
    }
    $changed = true;
}
if ($in['display_name'] !== null && $user->getDisplayName() !== $in['display_name']) {
    if (!$user->setDisplayName($in['display_name'])) {
        fail('Nextcloud: cannot set the display name of ' . $name);
    }
    $changed = true;
}
if ($in['email'] !== null && $user->getSystemEMailAddress() !== $in['email']) {
    $user->setSystemEMailAddress($in['email']);
    $changed = true;
}
$wanted = $in['groups'];
if ($wanted !== null) {
    foreach ($wanted as $gid) {
        $group = $groups->get($gid) ?? $groups->createGroup($gid);
        if ($group === null) {
            fail('Nextcloud: cannot create the group ' . $gid);
        }
        if (!$group->inGroup($user)) {
            $group->addUser($user);
            $changed = true;
        }
    }
    foreach ($groups->getUserGroupIds($user) as $gid) {
        if ($gid !== 'admin' && !in_array($gid, $wanted, true)) {
            $groups->get($gid)->removeUser($user);
            $changed = true;
        }
    }
}
$admin = $groups->get('admin') ?? $groups->createGroup('admin');
if ($in['admin'] && !$admin->inGroup($user)) {
    $admin->addUser($user);
    $changed = true;
} elseif (!$in['admin'] && $admin->inGroup($user)) {
    $admin->removeUser($user);
    $changed = true;
}
echo "\n" . json_encode(['changed' => $changed, 'created' => $created]);
'''


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            name=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
            display_name=dict(type='str'),
            email=dict(type='str'),
            groups=dict(type='list', elements='str'),
            admin=dict(type='bool', default=False),
            user=dict(type='str', default='abc'),
        ),
        supports_check_mode=False,
    )
    params = module.params
    data = dict((key, params[key]) for key in ('name', 'password', 'display_name', 'email', 'groups', 'admin'))
    args = ['podman', 'exec', '-i', '--user', params['user'], params['container'], 'php', '-r', USER]
    rc, out, err = module.run_command(args, data=json.dumps(data), binary_data=True)
    if rc != 0:
        module.fail_json(msg='Nextcloud failed: %s' % (err.strip() or out.strip()))
    try:
        result = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError, KeyError):
        module.fail_json(msg='Nextcloud returned no result: %s %s' % (out.strip(), err.strip()))
    module.exit_json(changed=result['changed'], created=result['created'])


if __name__ == '__main__':
    main()
