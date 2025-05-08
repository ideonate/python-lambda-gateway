#!/usr/bin/env python3
# usage:
#   python server.py --help
import argparse
import os
import sys
from aiohttp import web
import asyncio
import nest_asyncio
from watchfiles import awatch

from lambda_gateway.event_proxy import EventProxy
from lambda_gateway.request_handler import LambdaRequestHandler

from lambda_gateway import __version__
from lambda_gateway.sam import SAM, load_env_vars
from lambda_gateway.cdk import CDKParser

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
        '-w', '--watch',
        dest='watch',
        help='Watch the base python path and exit if files change.',
        action="store_true"
    )
    parser.add_argument(
        '-e', '--env-vars',
        dest='env_vars_json',
        help='JSON file containing environment variables',
        metavar='PATH',
    )
    parser.add_argument(
        'SAM_TEMPLATE',
        help='Path to SAM YAML template',
    )
    return parser.parse_args()


async def run_server(app, bind, port, path, quit_on_change=True):
    """
    Run Lambda Gateway server.
    """
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, bind, port)
    await site.start()

    stop_event = asyncio.Event()

    # Wait for a source file to change, then quit
    async for changes in awatch(path, stop_event=stop_event, raise_interrupt=False):
        print(f"Source file changed: {changes}")
        if quit_on_change:
            print('Exiting so you can reload')
            stop_event.set() # `break` would probably be enough BTW
        else:
            print("No reload or quit - try -w flag")

    await runner.cleanup()

def get_cors_options_handler(extra_headers):
    async def cors_options_handler(request):
        r = web.Response(status=204, headers=extra_headers)
        return r
    return cors_options_handler
    
def main():
    """
    Main entrypoint.
    """
    # Parse opts
    opts = get_opts()

    base_python_path = os.path.abspath(opts.base_python_path or os.path.curdir)

    # Load env vars
    if opts.env_vars_json and opts.SAM_TEMPLATE.endswith('.ts'):
        sam = CDKParser(opts.SAM_TEMPLATE)
        mapping = sam.get_env_var_mapping()
        env_vars = load_env_vars(opts.env_vars_json, mapping)
        os.environ.update(env_vars)
    else:
        env_vars = load_env_vars(opts.env_vars_json)
        os.environ.update(env_vars)

    # Load SAM Template or CDK Stack
    if opts.SAM_TEMPLATE.endswith('.ts'):
        sam = CDKParser(opts.SAM_TEMPLATE)
    else:
        sam = SAM(opts.SAM_TEMPLATE)

    # TODO Maybe take an origin as a parameter
    extra_headers = {
        'Access-Control-Allow-Headers': 'authorization',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET,HEAD,PUT,PATCH,POST,DELETE',
    }

    # Setup handler
    routes = []
    for endpoint in sam.get_endpoints():
        proxy = EventProxy(endpoint.Handler, os.path.join(base_python_path, endpoint.CodeUri), opts.timeout)
        handler = LambdaRequestHandler(proxy, opts.payload_version, extra_headers)
        print(f"Registering route {endpoint}")
        routes.append(web.RouteDef(endpoint.Method.upper(), endpoint.Path, handler.invoke, {}))

    app = web.Application()

    app.add_routes(routes)

    # Add a generic OPTIONS handler to encourage CORS to work
    app.add_routes([web.RouteDef("OPTIONS", r'/{path:.*}', get_cors_options_handler(extra_headers), {})])

    print(f"Run server at {opts.bind} port {opts.port}")

    asyncio.run(run_server(app, opts.bind, opts.port, base_python_path, opts.watch))

    os._exit(0) # OS exit because awatch thread seems to still be locked; without this it hangs

 
if __name__ == '__main__':  # pragma: no cover
    main()
