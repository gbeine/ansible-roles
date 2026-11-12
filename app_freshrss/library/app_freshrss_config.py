#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_freshrss_config
short_description: Installs FreshRSS and keeps data/config.php up to date
description:
  - Runs PHP in the container of FreshRSS with podman exec as the user of the image, the data and the passwords are passed on stdin.
  - Without data/applied_migrations.txt FreshRSS is not installed, the module writes data/config.custom.php and runs cli/do-install.php,
    it removes data/config.custom.php afterwards.
  - Merges the options recursively into data/config.php, null removes an option, lists replace the former value,
    the file is only written if an option changed.
options:
  container:
    description: The name of the container of FreshRSS.
    type: str
    required: true
  config:
    description: The options of data/config.php.
    type: dict
    default: {}
  secrets:
    description: The passwords of data/config.php by path, e.g. db.password.
    type: dict
    default: {}
  default_user:
    description: The default user, needed by the installation.
    type: str
    required: true
  user:
    description: The user of the image running FreshRSS.
    type: str
    default: abc
'''

EXAMPLES = r'''
- name: 'Configure FreshRSS'
  app_freshrss_config:
    container: 'freshrss'
    default_user: 'admin'
    config:
      title: 'News'
'''

RETURN = r'''
installed:
  description: Whether the module installed FreshRSS.
  returned: always
  type: bool
changed_options:
  description: The paths of the changed options, without values.
  returned: always
  type: list
'''

import json

from ansible.module_utils.basic import AnsibleModule

DATA = '/app/www/data'

# Reads {config, secrets, default_user} from stdin, writes config.custom.php and runs do-install.php if FreshRSS is not installed
INSTALL = r'''
$in = json_decode(stream_get_contents(STDIN), true);
$data = '%(data)s';
if (file_exists($data . '/applied_migrations.txt')) {
    echo json_encode(['installed' => false]);
    exit(0);
}
$config = $in['config'];
foreach ($in['secrets'] as $path => $value) {
    [$section, $key] = explode('.', $path, 2);
    $config[$section][$key] = $value;
}
$config = array_filter($config, fn($v) => $v !== null);
if (isset($config['db']) && is_array($config['db'])) {
    $config['db'] = array_filter($config['db'], fn($v) => $v !== null) + ['type' => 'sqlite'];
}
$custom = $data . '/config.custom.php';
umask(0027);
if (file_put_contents($custom, "<?php\nreturn " . var_export($config, true) . ";\n") === false) {
    fwrite(STDERR, "FreshRSS: cannot write $custom\n");
    exit(1);
}
exec('php /app/www/cli/do-install.php --default-user ' . escapeshellarg($in['default_user']) . ' 2>&1', $output, $code);
@unlink($custom);
if ($code !== 0) {
    fwrite(STDERR, implode("\n", $output) . "\n");
    exit(1);
}
echo json_encode(['installed' => true]);
''' % {'data': DATA}

# Reads {config, secrets} from stdin and merges the options into config.php
RECONCILE = r'''
$in = json_decode(stream_get_contents(STDIN), true);
$file = '%(data)s/config.php';
$current = include $file;
if (!is_array($current)) {
    fwrite(STDERR, "FreshRSS: $file is no configuration\n");
    exit(1);
}
$wanted = $in['config'];
foreach ($in['secrets'] as $path => $value) {
    [$section, $key] = explode('.', $path, 2);
    $wanted[$section][$key] = $value;
}
$changed = [];
function merge(array $current, array $wanted, string $prefix, array &$changed): array {
    foreach ($wanted as $key => $value) {
        $path = $prefix . $key;
        if ($value === null) {
            if (array_key_exists($key, $current)) {
                unset($current[$key]);
                $changed[] = $path;
            }
        } elseif (is_array($value) && $value !== [] && !array_is_list($value)
                  && is_array($current[$key] ?? null) && !array_is_list($current[$key])) {
            $current[$key] = merge($current[$key], $value, $path . '.', $changed);
        } elseif (!array_key_exists($key, $current) || $current[$key] !== $value) {
            $current[$key] = $value;
            $changed[] = $path;
        }
    }
    return $current;
}
$result = merge($current, $wanted, '', $changed);
if ($changed !== []) {
    $tmp = $file . '.tmp.php';
    if (file_put_contents($tmp, "<?php\nreturn " . var_export($result, true) . ";\n", LOCK_EX) === false || !rename($tmp, $file)) {
        @unlink($tmp);
        fwrite(STDERR, "FreshRSS: cannot write $file\n");
        exit(1);
    }
}
echo json_encode(['changed_options' => $changed]);
''' % {'data': DATA}


def php(module, code, data):
    args = ['podman', 'exec', '-i', '--user', module.params['user'], module.params['container'], 'php', '-r', code]
    rc, out, err = module.run_command(args, data=json.dumps(data), binary_data=True)
    if rc != 0:
        module.fail_json(msg='FreshRSS failed: %s' % (err.strip() or out.strip()))
    try:
        return json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError):
        module.fail_json(msg='FreshRSS returned no result: %s %s' % (out.strip(), err.strip()))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            config=dict(type='dict', default={}),
            secrets=dict(type='dict', default={}, no_log=True),
            default_user=dict(type='str', required=True),
            user=dict(type='str', default='abc'),
        ),
        supports_check_mode=False,
    )
    data = dict(config=module.params['config'], secrets=module.params['secrets'], default_user=module.params['default_user'])
    installed = php(module, INSTALL, data)['installed']
    changed_options = php(module, RECONCILE, data)['changed_options']
    module.exit_json(changed=installed or len(changed_options) > 0, installed=installed, changed_options=changed_options)


if __name__ == '__main__':
    main()
