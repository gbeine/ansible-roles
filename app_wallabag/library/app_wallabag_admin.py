#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_wallabag_admin
short_description: Installs wallabag once and keeps its administrator up to date
description:
  - Runs PHP in the container of wallabag with the kernel of wallabag as the user nobody,
    the configuration of the database comes from parameters.yml written by the image.
  - Checks whether the table of the users exists. If it does not, it runs C(wallabag:install --env=prod -n) once,
    which creates the schema, the default administrator wallabag and the internal settings.
  - Looks up the administrator by its name. If it does not exist, the default administrator wallabag is taken over
    and gets the name, so no administrator with the default password remains. Otherwise the user is created.
  - Checks the password with the sha512 encoder of wallabag and only sets it if it differs,
    keeps the email up to date and makes the user an enabled super administrator.
  - The name, the email and the password are passed on stdin, they are never arguments of a process.
options:
  container:
    description: The name of the container of wallabag.
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
  default_name:
    description: The name of the administrator created by wallabag:install.
    type: str
    default: wallabag
'''

EXAMPLES = r'''
- name: 'Install wallabag and create the administrator'
  app_wallabag_admin:
    container: 'wallabag'
    name: 'admin'
    email: 'admin@example.org'
    password: 'secret-admin-password'
'''

RETURN = r'''
installed:
  description: Whether wallabag:install ran.
  returned: always
  type: bool
created:
  description: Whether the administrator was created.
  returned: always
  type: bool
taken_over:
  description: Whether the default administrator got the name.
  returned: always
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule

WORKDIR = '/var/www/wallabag'

# Reads {mode, name, email, password, default_name} from stdin, mode is check or admin
SCRIPT = r'''
require 'vendor/autoload.php';
$data = json_decode(file_get_contents('php://stdin'), true);
$kernel = new AppKernel('prod', false);
$kernel->boot();
$container = $kernel->getContainer();
$doctrine = $container->get('doctrine');
if ($data['mode'] === 'check') {
    $connection = $doctrine->getConnection();
    $schema = method_exists($connection, 'createSchemaManager') ? $connection->createSchemaManager() : $connection->getSchemaManager();
    $table = $container->getParameter('database_table_prefix') . 'user';
    echo "\n" . json_encode(['schema' => $schema->tablesExist([$table])]) . "\n";
    exit(0);
}
$users = $container->get('fos_user.user_manager');
$user = $users->findUserByUsername($data['name']);
$created = $takenOver = $changed = false;
if (null === $user) {
    $user = $users->findUserByUsername($data['default_name']);
    if (null !== $user) {
        $user->setUsername($data['name']);
        $takenOver = $changed = true;
    }
}
if (null === $user) {
    $user = $users->createUser();
    $user->setUsername($data['name']);
    $user->setEmail($data['email']);
    $user->setPlainPassword($data['password']);
    $user->setEnabled(true);
    $user->addRole('ROLE_SUPER_ADMIN');
    $users->updateUser($user);
    // The listeners of wallabag create the configuration of the user like wallabag:install
    $container->get('event_dispatcher')->dispatch(new \FOS\UserBundle\Event\UserEvent($user), \FOS\UserBundle\FOSUserEvents::USER_CREATED);
    $doctrine->getManager()->flush();
    $created = $changed = true;
} else {
    $encoder = new \Symfony\Component\Security\Core\Encoder\MessageDigestPasswordEncoder('sha512', true, 5000);
    if (!$encoder->isPasswordValid((string) $user->getPassword(), $data['password'], $user->getSalt())) {
        $user->setPlainPassword($data['password']);
        $changed = true;
    }
    if ($user->getEmail() !== $data['email']) {
        $user->setEmail($data['email']);
        $changed = true;
    }
    if (!$user->isEnabled()) {
        $user->setEnabled(true);
        $changed = true;
    }
    if (!$user->hasRole('ROLE_SUPER_ADMIN')) {
        $user->addRole('ROLE_SUPER_ADMIN');
        $changed = true;
    }
    if ($changed) {
        $users->updateUser($user);
    }
}
echo "\n" . json_encode(['changed' => $changed, 'created' => $created, 'taken_over' => $takenOver]) . "\n";
'''


def run_script(module, data):
    args = ['podman', 'exec', '-i', '-u', 'nobody', '-w', WORKDIR, module.params['container'], 'php', '-r', SCRIPT]
    rc, out, err = module.run_command(args, data=json.dumps(data), binary_data=True)
    if rc != 0:
        module.fail_json(msg='wallabag failed: %s' % (err.strip() or out.strip()))
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        module.fail_json(msg='wallabag returned no result: %s %s' % (out.strip(), err.strip()))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            name=dict(type='str', required=True),
            email=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
            default_name=dict(type='str', default='wallabag'),
        ),
        supports_check_mode=False,
    )
    params = module.params
    installed = False
    if not run_script(module, dict(mode='check'))['schema']:
        args = ['podman', 'exec', '-u', 'nobody', '-w', WORKDIR, params['container'],
                'php', 'bin/console', 'wallabag:install', '--env=prod', '-n']
        rc, out, err = module.run_command(args)
        if rc != 0:
            module.fail_json(msg='wallabag:install failed: %s' % (err.strip() or out.strip()))
        installed = True
    data = dict((key, params[key]) for key in ('name', 'email', 'password', 'default_name'))
    data['mode'] = 'admin'
    result = run_script(module, data)
    module.exit_json(changed=installed or result['changed'], installed=installed,
                     created=result['created'], taken_over=result['taken_over'])


if __name__ == '__main__':
    main()
