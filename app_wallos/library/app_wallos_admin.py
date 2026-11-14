#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_wallos_admin
short_description: Creates the administrator of Wallos and keeps its name, email and password up to date
description:
  - Runs php as the user of PHP-FPM (C(www-data), set to C(PUID) by the image) in the container of Wallos
    and changes the database C(db/wallos.db), so no file of the database belongs to root.
    The username, the email and the password are passed on stdin, they are never arguments of a process.
  - Waits until the user may write the database, the image creates it as root and hands it over after the migrations.
  - Without users Wallos lets the first visitor register as administrator. The module registers the administrator
    with the registration form of Wallos on C(http://127.0.0.1/registration.php) inside the container,
    so Wallos creates the user with its household and default names and the password does not leave the container.
  - With users the user with the id 1 is the administrator of Wallos. The module checks the password with
    C(password_verify) and only sets the username, the email or the password (C(password_hash) like Wallos) if they differ.
options:
  container:
    description: The name of the container of Wallos.
    type: str
    required: true
  username:
    description: The username of the administrator.
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
  language:
    description: The language of the administrator, only used when the administrator is registered.
    type: str
    default: en
  currency:
    description: The code of the main currency of the administrator, only used when the administrator is registered.
    type: str
    default: EUR
  user:
    description: The user running php in the container, the user of PHP-FPM.
    type: str
    default: www-data
  timeout:
    description: Seconds to wait until Wallos created its database and handed it to I(user).
    type: int
    default: 60
'''

EXAMPLES = r'''
- name: 'Create the administrator'
  app_wallos_admin:
    container: 'wallos'
    username: 'admin'
    email: 'admin@example.org'
    password: 'secret-admin-password'
    language: 'de'
    currency: 'EUR'
'''

RETURN = r'''
created:
  description: Whether the administrator was registered.
  returned: always
  type: bool
updated:
  description: The fields of the administrator that were changed, username, email or password.
  returned: always
  type: list
  elements: str
'''

import json

from ansible.module_utils.basic import AnsibleModule

WORKDIR = '/var/www/html'

# Reads {username, email, password, language, currency, timeout} from stdin, writes the result as the last line of stdout
SCRIPT = r'''
function result($data, $code = 0) {
    echo "\n" . json_encode($data) . "\n";
    exit($code);
}

// startup.sh creates the database as root and hands it to www-data after the migrations,
// the database is ready when www-data may write it and its directory
function open_database($timeout) {
    $deadline = time() + $timeout;
    while (true) {
        clearstatcache();
        if (file_exists('db/wallos.db') && is_writable('db/wallos.db') && is_writable('db')) {
            $db = new SQLite3('db/wallos.db');
            $db->busyTimeout(10000);
            $table = $db->querySingle("SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'user'");
            if ($table === 'user') {
                return $db;
            }
            $db->close();
        }
        if (time() >= $deadline) {
            result(['error' => 'the database db/wallos.db with the table user is not writable for ' . get_current_user_name() . ' after ' . $timeout . ' seconds'], 1);
        }
        sleep(1);
    }
}

function get_current_user_name() {
    return function_exists('posix_geteuid') ? (string) posix_geteuid() : 'the user of the script';
}

function find_other($db, $field, $value) {
    $stmt = $db->prepare("SELECT id FROM user WHERE $field = :value AND id != 1");
    $stmt->bindValue(':value', $value, SQLITE3_TEXT);
    return $stmt->execute()->fetchArray(SQLITE3_ASSOC) !== false;
}

function register($data) {
    $body = http_build_query([
        'username' => $data['username'],
        'firstname' => '',
        'lastname' => '',
        'email' => $data['email'],
        'password' => $data['password'],
        'confirm_password' => $data['password'],
        'main_currency' => $data['currency'],
        'language' => $data['language'],
    ]);
    $context = stream_context_create(['http' => [
        'method' => 'POST',
        'header' => "Content-Type: application/x-www-form-urlencoded\r\n",
        'content' => $body,
        'follow_location' => 0,
        'ignore_errors' => true,
        'timeout' => 60,
    ]]);
    $response = @file_get_contents('http://127.0.0.1/registration.php', false, $context);
    if ($response === false) {
        result(['error' => 'the registration form of Wallos did not answer'], 1);
    }
    return [$http_response_header[0] ?? 'no response', $response];
}

// The reason of a failed registration: the error box of the form or the messages of PHP, otherwise the beginning of the page
function reason($response) {
    if (preg_match('/<ul class="error-box">(.*?)<\/ul>/s', $response, $match)) {
        return trim(preg_replace('/\s+/', ' ', strip_tags($match[1])));
    }
    if (preg_match_all('/(?:Fatal error|Warning|Notice|Deprecated|Parse error)\b.{0,300}/', strip_tags($response), $matches)) {
        return implode(' ', array_slice($matches[0], 0, 5));
    }
    return substr(trim(preg_replace('/\s+/', ' ', strip_tags($response))), 0, 500);
}

$data = json_decode(stream_get_contents(STDIN), true);
if (!is_array($data)) {
    result(['error' => 'no data on stdin'], 1);
}

$db = open_database((int) $data['timeout']);
$count = $db->querySingle('SELECT COUNT(*) FROM user');

if ($count == 0) {
    $db->close();
    // Success is the administrator in the database, not the status of the answer:
    // a message of PHP before the redirect keeps the status 200
    [$status, $response] = register($data);
    $db = open_database((int) $data['timeout']);
    $user = $db->querySingle('SELECT username, email FROM user WHERE id = 1', true);
    if (!$user || $user['username'] !== $data['username'] || $user['email'] !== $data['email']) {
        result(['error' => 'the registration of the administrator failed (' . $status . '): ' . reason($response)], 1);
    }
    result(['changed' => true, 'created' => true, 'updated' => []]);
}

$user = $db->querySingle('SELECT username, email, password FROM user WHERE id = 1', true);
if (!$user) {
    result(['error' => 'Wallos has users, but no administrator with the id 1'], 1);
}

$updated = [];
if ($user['username'] !== $data['username']) {
    if (find_other($db, 'username', $data['username'])) {
        result(['error' => 'the username ' . $data['username'] . ' belongs to another user of Wallos'], 1);
    }
    $updated[] = 'username';
}
if ($user['email'] !== $data['email']) {
    if (find_other($db, 'email', $data['email'])) {
        result(['error' => 'the email ' . $data['email'] . ' belongs to another user of Wallos'], 1);
    }
    $updated[] = 'email';
}
$password = $user['password'];
if (!password_verify($data['password'], (string) $user['password'])) {
    $password = password_hash($data['password'], PASSWORD_DEFAULT);
    $updated[] = 'password';
}

if (count($updated) > 0) {
    $stmt = $db->prepare('UPDATE user SET username = :username, email = :email, password = :password WHERE id = 1');
    $stmt->bindValue(':username', $data['username'], SQLITE3_TEXT);
    $stmt->bindValue(':email', $data['email'], SQLITE3_TEXT);
    $stmt->bindValue(':password', $password, SQLITE3_TEXT);
    if (!$stmt->execute()) {
        result(['error' => 'the administrator could not be updated: ' . $db->lastErrorMsg()], 1);
    }
}
$db->close();
result(['changed' => count($updated) > 0, 'created' => false, 'updated' => $updated]);
'''


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            username=dict(type='str', required=True),
            email=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
            language=dict(type='str', default='en'),
            currency=dict(type='str', default='EUR'),
            user=dict(type='str', default='www-data'),
            timeout=dict(type='int', default=60),
        ),
        supports_check_mode=False,
    )
    params = module.params

    args = ['podman', 'exec', '-i', '--user', params['user'], '-w', WORKDIR, params['container'], 'php', '-r', SCRIPT]
    data = dict((key, params[key]) for key in ('username', 'email', 'password', 'language', 'currency', 'timeout'))
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
        module.fail_json(msg='Wallos returned no result (rc %s): %s' % (rc, ' '.join((err.strip() or out.strip()).splitlines()[-20:])))
    if rc != 0 or 'error' in result:
        module.fail_json(msg='Wallos failed: %s' % result.get('error', 'rc %s' % rc))

    module.exit_json(changed=result['changed'], created=result['created'], updated=result['updated'])


if __name__ == '__main__':
    main()
