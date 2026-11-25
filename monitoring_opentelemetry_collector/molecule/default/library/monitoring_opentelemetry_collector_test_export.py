#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: monitoring_opentelemetry_collector_test_export
short_description: Sends a trace to the collector and receives its export
description:
  - Listens for one HTTP request on the address of an otlphttp exporter of the collector,
    sends an OTLP/JSON trace to the HTTP receiver of the collector and waits until the collector exports it.
  - Returns the path and the headers of the export, e.g. to check the headers set with secrets.
  - Only for the molecule tests of monitoring_opentelemetry_collector.
options:
  receiver:
    description: The URL of the traces of the HTTP receiver of the collector.
    type: str
    default: 'http://127.0.0.1:4318/v1/traces'
  listen_host:
    description: The address the exporter sends to.
    type: str
    default: '127.0.0.1'
  listen_port:
    description: The port the exporter sends to.
    type: int
    default: 4319
  timeout:
    description: Seconds to wait for the export.
    type: int
    default: 30
'''

EXAMPLES = r'''
- name: 'Send a trace and receive the export'
  monitoring_opentelemetry_collector_test_export:
    receiver: 'http://127.0.0.1:4318/v1/traces'
    listen_port: 4319
  register: 'export'
'''

RETURN = r'''
path:
  description: The path of the export request.
  returned: success
  type: str
headers:
  description: The headers of the export request, the names in lower case.
  returned: success
  type: dict
'''

import json
import os
import threading
import time

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves import BaseHTTPServer
from ansible.module_utils.six.moves.urllib.request import Request, urlopen


def trace():
    now = int(time.time() * 1e9)
    return {
        'resourceSpans': [{
            'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'molecule'}}]},
            'scopeSpans': [{
                'spans': [{
                    'traceId': os.urandom(16).hex(),
                    'spanId': os.urandom(8).hex(),
                    'name': 'molecule',
                    'kind': 1,
                    'startTimeUnixNano': str(now),
                    'endTimeUnixNano': str(now + 1000000),
                }],
            }],
        }],
    }


def main():
    module = AnsibleModule(
        argument_spec=dict(
            receiver=dict(type='str', default='http://127.0.0.1:4318/v1/traces'),
            listen_host=dict(type='str', default='127.0.0.1'),
            listen_port=dict(type='int', default=4319),
            timeout=dict(type='int', default=30),
        ),
        supports_check_mode=False,
    )
    params = module.params
    received = []

    class Handler(BaseHTTPServer.BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get('Content-Length') or 0)
            self.rfile.read(length)
            received.append({'path': self.path, 'headers': dict((k.lower(), v) for k, v in self.headers.items())})
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', '2')
            self.end_headers()
            self.wfile.write(b'{}')

        def log_message(self, *args):
            pass

    try:
        server = BaseHTTPServer.HTTPServer((params['listen_host'], params['listen_port']), Handler)
    except Exception as e:
        module.fail_json(msg='Cannot listen on %s:%s: %s' % (params['listen_host'], params['listen_port'], e))
    server.timeout = 1
    stop = threading.Event()

    # Handles requests until the export arrived or the wait ended
    def serve():
        while not received and not stop.is_set():
            server.handle_request()

    thread = threading.Thread(target=serve)
    thread.daemon = True
    thread.start()

    try:
        request = Request(params['receiver'], data=json.dumps(trace()).encode('utf-8'), headers={'Content-Type': 'application/json'})
        urlopen(request, timeout=10).read()
    except Exception as e:
        stop.set()
        thread.join(2)
        server.server_close()
        module.fail_json(msg='The receiver %s refused the trace: %s' % (params['receiver'], e))

    deadline = time.time() + params['timeout']
    while not received and time.time() < deadline:
        time.sleep(0.2)
    stop.set()
    thread.join(2)
    server.server_close()

    if not received:
        module.fail_json(msg='The collector exported nothing to %s:%s within %s seconds'
                         % (params['listen_host'], params['listen_port'], params['timeout']))
    module.exit_json(changed=False, path=received[0]['path'], headers=received[0]['headers'])


if __name__ == '__main__':
    main()
