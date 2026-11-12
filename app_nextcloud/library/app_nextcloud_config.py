#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_nextcloud_config
short_description: Keeps the system values of config.php of Nextcloud up to date
description:
  - Runs PHP in the container of Nextcloud with podman exec as the user of the image, the values and the passwords are passed on stdin.
  - Compares every value with the system configuration of Nextcloud and only writes the values that differ, null removes a value.
  - Values that are not given are not changed.
options:
  container:
    description: The name of the container of Nextcloud.
    type: str
    required: true
  config:
    description: The system values of config.php.
    type: dict
    default: {}
  secrets:
    description: The passwords of config.php by key, e.g. dbpassword.
    type: dict
    default: {}
  user:
    description: The user of the image running Nextcloud.
    type: str
    default: abc
'''

EXAMPLES = r'''
- name: 'Configure Nextcloud'
  app_nextcloud_config:
    container: 'nextcloud'
    config:
      trusted_domains: [ 'cloud.example.org' ]
      default_language: 'de'
    secrets:
      dbpassword: 'secret-database-password'
'''

RETURN = r'''
changed_keys:
  description: The keys of the changed values, without values.
  returned: always
  type: list
'''

import json

from ansible.module_utils.basic import AnsibleModule

# Reads {config} from stdin and writes the values that differ
RECONCILE = r'''
$in = json_decode(stream_get_contents(STDIN), true);
require_once '/app/www/public/lib/base.php';
$config = \OCP\Server::get(\OC\SystemConfig::class);
$keys = $config->getKeys();
$values = [];
foreach ($in['config'] as $key => $value) {
    if ($value === null) {
        if (in_array($key, $keys, true)) {
            $values[$key] = null;
        }
    } elseif (!in_array($key, $keys, true) || $config->getValue($key) !== $value) {
        $values[$key] = $value;
    }
}
if ($values !== []) {
    $config->setValues($values);
}
echo "\n" . json_encode(['changed_keys' => array_keys($values)]);
'''


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            config=dict(type='dict', default={}),
            secrets=dict(type='dict', default={}, no_log=True),
            user=dict(type='str', default='abc'),
        ),
        supports_check_mode=False,
    )
    params = module.params
    config = dict(params['config'])
    config.update(params['secrets'])
    args = ['podman', 'exec', '-i', '--user', params['user'], params['container'], 'php', '-r', RECONCILE]
    rc, out, err = module.run_command(args, data=json.dumps({'config': config}), binary_data=True)
    if rc != 0:
        module.fail_json(msg='Nextcloud failed: %s' % (err.strip() or out.strip()))
    try:
        changed_keys = json.loads(out.strip().splitlines()[-1])['changed_keys']
    except (ValueError, IndexError, KeyError):
        module.fail_json(msg='Nextcloud returned no result: %s %s' % (out.strip(), err.strip()))
    module.exit_json(changed=len(changed_keys) > 0, changed_keys=changed_keys)


if __name__ == '__main__':
    main()
