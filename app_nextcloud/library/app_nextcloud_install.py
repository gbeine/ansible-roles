#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_nextcloud_install
short_description: Installs Nextcloud with its database and the first administrator
description:
  - Runs PHP in the container of Nextcloud with podman exec as the user of the image, the data and the passwords are passed on stdin.
  - Nextcloud is installed if installed is not set in config.php, otherwise the module changes nothing.
  - The installation runs occ maintenance:install inside PHP, the passwords are part of the arguments of occ in PHP only,
    they are never arguments of a process.
options:
  container:
    description: The name of the container of Nextcloud.
    type: str
    required: true
  database:
    description: The database with dbtype (mysql or pgsql), dbhost, dbname, dbuser and optional dbport.
    type: dict
    required: true
  database_password:
    description: The password of the database user.
    type: str
    required: true
  admin_user:
    description: The name of the first administrator.
    type: str
    required: true
  admin_password:
    description: The password of the first administrator.
    type: str
    required: true
  admin_email:
    description: The email address of the first administrator.
    type: str
  data_dir:
    description: The data directory in the container.
    type: str
    default: /data
  user:
    description: The user of the image running Nextcloud.
    type: str
    default: abc
'''

EXAMPLES = r'''
- name: 'Install Nextcloud'
  app_nextcloud_install:
    container: 'nextcloud'
    database:
      dbtype: 'mysql'
      dbhost: 'mariadb'
      dbname: 'nextcloud'
      dbuser: 'nextcloud'
    database_password: 'secret-database-password'
    admin_user: 'admin'
    admin_password: 'secret-admin-password'
'''

RETURN = r'''
installed:
  description: Whether the module installed Nextcloud.
  returned: always
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule

CONFIG = '/config/www/nextcloud/config/config.php'
CONSOLE = '/app/www/public/console.php'

# Reports whether config.php says that Nextcloud is installed
STATUS = r'''
$CONFIG = [];
if (is_file('%(config)s')) {
    include '%(config)s';
}
echo "\n" . json_encode(['installed' => !empty($CONFIG['installed'])]);
''' % {'config': CONFIG}

# Reads the options of occ maintenance:install from stdin and runs the console of Nextcloud with them
INSTALL = r'''
$in = json_decode(stream_get_contents(STDIN), true);
$argv = ['occ', 'maintenance:install', '--no-interaction', '--no-warnings'];
foreach ($in as $option => $value) {
    if ($value !== null && $value !== '') {
        $argv[] = '--' . $option . '=' . $value;
    }
}
$argc = count($argv);
$_SERVER['argv'] = $argv;
$_SERVER['argc'] = $argc;
require '%(console)s';
''' % {'console': CONSOLE}


def php(module, code, data=None):
    args = ['podman', 'exec', '-i', '--user', module.params['user'], module.params['container'], 'php', '-r', code]
    return module.run_command(args, data=json.dumps(data if data is not None else {}), binary_data=True)


def installed(module):
    rc, out, err = php(module, STATUS)
    try:
        return json.loads(out.strip().splitlines()[-1])['installed']
    except (ValueError, IndexError, KeyError):
        module.fail_json(msg='Nextcloud returned no state: %s %s' % (out.strip(), err.strip()))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            database=dict(type='dict', required=True),
            database_password=dict(type='str', required=True, no_log=True),
            admin_user=dict(type='str', required=True),
            admin_password=dict(type='str', required=True, no_log=True),
            admin_email=dict(type='str'),
            data_dir=dict(type='str', default='/data'),
            user=dict(type='str', default='abc'),
        ),
        supports_check_mode=True,
    )
    params = module.params
    if installed(module):
        module.exit_json(changed=False, installed=False)
    if module.check_mode:
        module.exit_json(changed=True, installed=True)

    database = params['database']
    options = {
        'database': database.get('dbtype'),
        'database-host': database.get('dbhost'),
        'database-port': database.get('dbport'),
        'database-name': database.get('dbname'),
        'database-user': database.get('dbuser'),
        'database-pass': params['database_password'],
        'admin-user': params['admin_user'],
        'admin-pass': params['admin_password'],
        'admin-email': params['admin_email'],
        'data-dir': params['data_dir'],
    }
    options = dict((key, None if value is None else str(value)) for key, value in options.items())
    rc, out, err = php(module, INSTALL, options)
    if rc != 0 or not installed(module):
        module.fail_json(msg='The installation of Nextcloud failed: %s %s' % (out.strip(), err.strip()))
    module.exit_json(changed=True, installed=True)


if __name__ == '__main__':
    main()
