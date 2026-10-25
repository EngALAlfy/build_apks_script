"""Start the LAN build server, or an isolated build worker when invoked internally."""
import argparse
import os
import socket
import sys
import threading
import webbrowser
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description='APK Builder LAN server')
    parser.add_argument('--host', default='0.0.0.0')
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--data-dir', type=Path)
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--secure-cookies', action='store_true', help='Require HTTPS cookies when deployed behind a TLS reverse proxy')
    parser.add_argument('--worker', help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.data_dir:
        root = options.data_dir.resolve()
    else:
        from utils.app_paths import DATA_DIR
        root = DATA_DIR.parent / 'APKBuilderServer'
    if options.worker:
        from server.worker import run_worker
        return run_worker(root, options.worker)
    from server.app import create_app
    from server.processes import InstanceLock
    from server.runtime import Runtime
    from waitress import create_server
    app = create_app(root, options.secure_cookies)
    lock = InstanceLock(root / 'server.lock')
    runtime = Runtime(app.config['STORE'])
    http = None
    try:
        http = create_server(app, host=options.host, port=options.port, threads=8,
                             max_request_body_size=64 * 1024, channel_timeout=60, ident='APK Build Server')
        runtime.start()
        local = f'http://localhost:{options.port}'
        print(f'\nAPK BUILDER / CENTRAL BUILD SERVER\n\nLocal dashboard: {local}\nData directory: {root}', flush=True)
        if options.host not in ('127.0.0.1', 'localhost', '::1'):
            try:
                addresses = sorted({item[4][0] for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)})
            except OSError:
                addresses = []
            for address in addresses:
                if not address.startswith('127.'):
                    print(f'LAN dashboard:   http://{address}:{options.port}', flush=True)
        if not app.config['STORE'].has_users():
            print('\nOpen the LOCAL dashboard on this PC to create the first administrator. No default password is installed.', flush=True)
        print('\nKeep this window open and the PC awake. Press Ctrl+C to stop.\n', flush=True)
        if not options.no_browser:
            threading.Timer(1, lambda: webbrowser.open(local)).start()
        http.run()
    except KeyboardInterrupt:
        print('\nStopping the server and active build...', flush=True)
    finally:
        runtime.stop()
        if http:
            http.close()
        lock.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
