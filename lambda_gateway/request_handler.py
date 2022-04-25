from urllib import parse
from aiohttp import web

class LambdaRequestHandler:
    async def get_body(self, request):
        """
        Get request body to forward to Lambda handler.
        """
        if not request.can_read_body:
            return ''
        try:
            #content_length = request.content_length
            return await request.text()
        except TypeError:
            return ''

    async def get_event(self, request):
        """
        Get Lambda input event object.

        :param str httpMethod: HTTP request method
        :return dict: Lambda event object
        """
        if self.version == '1.0':
            return await self.get_event_v1(request)
        elif self.version == '2.0':
            return await self.get_event_v2(request)
        raise ValueError(  # pragma: no cover
            f'Unknown API Gateway payload version: {self.version}')

    async def get_event_v1(self, request):
        """
        Get Lambda input event object (v1).

        :param str httpMethod: HTTP request method
        :return dict: Lambda event object
        """
        url = parse.urlparse(request.path)
        path, *_ = url.path.split('?')
        return {
            'version': '1.0',
            'body': await self.get_body(request),
            'headers': dict(request.headers),
            'httpMethod': request.method,
            'path': path,
            'queryStringParameters': dict(parse.parse_qsl(url.query)),
        }

    async def get_event_v2(self, request):
        """
        Get Lambda input event object (v2).

        :param str httpMethod: HTTP request method
        :return dict: Lambda event object
        """
        url = parse.urlparse(request.path)
        path, *_ = url.path.split('?')
        route_key = request.headers.get('x-route-key') or f'{request.method} {path}'
        return {
            'version': '2.0',
            'body': await self.get_body(request),
            'routeKey': route_key,
            'rawPath': path,
            'rawQueryString': url.query,
            'headers': dict(request.headers),
            'queryStringParameters': dict(parse.parse_qsl(url.query)),
            'requestContext': {
                'http': {
                    'method': request.method,
                    'path': path,
                },
            },
        }

    async def invoke(self, request):
        """
        Proxy requests to Lambda handler

        :param dict event: Lambda event object
        :param Context context: Mock Lambda context
        :returns dict: Lamnda invocation result
        """
        # Get Lambda event
        event = await self.get_event(request)

        # Get Lambda result
        res = await self.proxy.invoke(event)

        # Parse response
        status = res.get('statusCode') or 500
        headers = res.get('headers') or {}
        body = res.get('body') or ''

        # Send response
        return web.Response(status=status, body=body.encode(), headers=headers)

    def __init__(self, proxy, version):
        """
        Set up LambdaRequestHandler.
        """
        self.proxy = proxy
        self.version = version
