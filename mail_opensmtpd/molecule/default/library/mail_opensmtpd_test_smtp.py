#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: mail_opensmtpd_test_smtp
short_description: Tests an SMTP server for the molecule tests of mail_opensmtpd
description:
  - Connects to the server, reads the banner and the EHLO, optionally runs STARTTLS with the verification of the certificate,
    AUTH PLAIN and sends a mail.
  - The answers of the server are returned, refused commands do not fail the module, only a failed connection or TLS handshake does.
options:
  host:
    description: The address of the server, the certificate is verified against it.
    type: str
    required: true
  port:
    description: The port of the server.
    type: int
    default: 25
  starttls:
    description: Run STARTTLS after EHLO.
    type: bool
    default: false
  cafile:
    description: The CA certificate the certificate of the server is verified with.
    type: path
  username:
    description: The user of AUTH, without it no AUTH is done.
    type: str
  password:
    description: The password of AUTH.
    type: str
    no_log: true
  mail_from:
    description: The sender of the mail, without it no mail is sent.
    type: str
  rcpt_to:
    description: The recipient of the mail.
    type: str
'''

EXAMPLES = r'''
- name: 'Send a mail with AUTH'
  mail_opensmtpd_test_smtp:
    host: '10.89.0.11'
    port: 587
    starttls: true
    cafile: '/etc/pki/realms/mx.example.test/public/ca.crt'
    username: 'molecule'
    password: 'secret'
    mail_from: 'molecule@example.test'
    rcpt_to: 'test@example.org'
'''

RETURN = r'''
banner:
  description: The greeting of the server.
  returned: always
  type: str
features:
  description: The extensions of the EHLO, after STARTTLS the ones of the second EHLO.
  returned: always
  type: list
  elements: str
tls:
  description: Whether STARTTLS succeeded.
  returned: always
  type: bool
auth:
  description: The code and the answer of AUTH, code 0 without AUTH.
  returned: always
  type: dict
mail:
  description: The code and the answer of the refused command or of the end of the data, code 0 without a mail.
  returned: always
  type: dict
'''

import smtplib
import ssl

from ansible.module_utils.basic import AnsibleModule


def text(value):
    return value.decode('utf-8', 'replace') if isinstance(value, bytes) else str(value)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            host=dict(type='str', required=True),
            port=dict(type='int', default=25),
            starttls=dict(type='bool', default=False),
            cafile=dict(type='path'),
            username=dict(type='str'),
            password=dict(type='str', no_log=True),
            mail_from=dict(type='str'),
            rcpt_to=dict(type='str'),
        ),
        supports_check_mode=False,
    )
    params = module.params
    result = dict(changed=False, banner='', features=[], tls=False, auth=dict(code=0, message=''), mail=dict(code=0, message=''))

    try:
        smtp = smtplib.SMTP(timeout=30)
        # Only the constructor sets the host starttls() verifies the certificate against, connect() keeps the banner
        smtp._host = params['host']
        code, banner = smtp.connect(params['host'], params['port'])
        result['banner'] = text(banner)
        smtp.ehlo('molecule.test')
        if params['starttls']:
            context = ssl.create_default_context(cafile=params['cafile'])
            smtp.starttls(context=context)
            result['tls'] = True
            smtp.ehlo('molecule.test')
        result['features'] = sorted(smtp.esmtp_features.keys())
    except (OSError, smtplib.SMTPException, ssl.SSLError) as e:
        module.fail_json(msg='The connection to %s:%s failed: %s' % (params['host'], params['port'], e), **result)

    try:
        if params['username']:
            try:
                code, message = smtp.login(params['username'], params['password'] or '')
            except smtplib.SMTPAuthenticationError as e:
                code, message = e.smtp_code, e.smtp_error
            result['auth'] = dict(code=code, message=text(message))
        if params['mail_from'] and result['auth']['code'] in (0, 235):
            try:
                smtp.sendmail(params['mail_from'], [params['rcpt_to']],
                              'From: %s\r\nTo: %s\r\nSubject: molecule\r\n\r\nmolecule\r\n' % (params['mail_from'], params['rcpt_to']))
                result['mail'] = dict(code=250, message='accepted')
            except smtplib.SMTPRecipientsRefused as e:
                code, message = list(e.recipients.values())[0]
                result['mail'] = dict(code=code, message=text(message))
            except smtplib.SMTPResponseException as e:
                result['mail'] = dict(code=e.smtp_code, message=text(e.smtp_error))
        smtp.quit()
    except (OSError, smtplib.SMTPException) as e:
        module.fail_json(msg='The SMTP session with %s:%s failed: %s' % (params['host'], params['port'], e), **result)

    module.exit_json(**result)


if __name__ == '__main__':
    main()
