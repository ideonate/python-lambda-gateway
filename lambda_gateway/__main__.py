#!/usr/bin/env python3
# usage:
#   python server.py --help
import argparse
import os
import sys
from aiohttp import web
import nest_asyncio

from lambda_gateway.event_proxy import EventProxy
from lambda_gateway.request_handler import LambdaRequestHandler

from lambda_gateway import __version__
from lambda_gateway.sam import SAM

# So lambda functions can make use of asyncio without the problem
# of being nested within our outer http loop
nest_asyncio.apply()

def get_opts():
    """
    Get CLI options.
    """
    parser = argparse.ArgumentParser(
        prog='lambda-gateway',
        description='Start a simple Lambda Gateway server',
    )
    parser.add_argument(
        '-B', '--base-python-path',
        dest='base_python_path',
        help='Set base folder for Python handler spec',
        metavar='PATH',
    )
    parser.add_argument(
        '-b', '--bind',
        dest='bind',
        metavar='ADDR',
        help='Specify alternate bind address [default: all interfaces]',
    )
    parser.add_argument(
        '-p', '--port',
        dest='port',
        default=8000,
        help='Specify alternate port [default: 8000]',
        type=int,
    )
    parser.add_argument(
        '-t', '--timeout',
        dest='timeout',
        help='Lambda timeout.',
        metavar='SECONDS',
        type=int,
    )
    parser.add_argument(
        '-v', '--version',
        action='version',
        help='Print version and exit',
        version=f'%(prog)s {__version__}',
    )
    parser.add_argument(
        '-V', '--payload-version',
        choices=['1.0', '2.0'],
        default='2.0',
        help='API Gateway payload version [default: 2.0]',
    )
    parser.add_argument(
        'SAM_TEMPLATE',
        help='Path to SAM YAML template',
    )
    return parser.parse_args()


def run(httpd, base_url_path='/'):
    """
    Run Lambda Gateway server.

    :param object httpd: ThreadingHTTPServer instance
    :param str base_url_path: REST API base path
    """
    host, port = httpd.socket.getsockname()[:2]
    url_host = f'[{host}]' if ':' in host else host
    sys.stderr.write(
        f'Serving HTTP on {host} port {port} '
        f'(http://{url_host}:{port}{base_url_path}) ...\n'
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stderr.write('\nKeyboard interrupt received, exiting.\n')
    finally:
        httpd.shutdown()


def main():
    """
    Main entrypoint.
    """
    # Parse opts
    opts = get_opts()

    # Ensure base_url_path is wrapped in slashes
    base_python_path = opts.base_python_path or os.path.curdir

    # Load SAM Template
    sam = SAM(opts.SAM_TEMPLATE)

    # Setup handler
    routes = []
    for endpoint in sam.get_endpoints():
        proxy = EventProxy(endpoint.Handler,os.path.join(base_python_path, endpoint.CodeUri), opts.timeout)
        handler = LambdaRequestHandler(proxy, opts.payload_version)
        print(f"Registering route {endpoint}")
        routes.append(web.RouteDef(endpoint.Method.upper(), endpoint.Path, handler.invoke, {}))

    app = web.Application()

    app.add_routes(routes)

    # Start server
    web.run_app(app, host=opts.bind, port=opts.port)

 
if __name__ == '__main__':  # pragma: no cover
    main()
