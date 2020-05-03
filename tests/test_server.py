import asyncio
import http
import io
import json
import sys
from unittest import mock

import pytest

from lambda_gateway import server
from lambda_gateway.server import LambdaRequestHandler as Handler


class TestLambdaRequestHandler:
    def setup(self):
        self.subject = mock.Mock(Handler)
        self.subject.timeout = 30

        body = json.dumps({'data': 'POST_DATA'})
        self.reqs = {
            'GET': {
                'body': '',
                'httpMethod': 'GET',
                'path': '/',
                'headers': {},
            },
            'HEAD': {
                'body': '',
                'httpMethod': 'HEAD',
                'path': '/',
                'headers': {},
            },
            'POST': {
                'body': body,
                'httpMethod': 'POST',
                'path': '/',
                'headers': {
                    'Content-Length': len(body),
                }
            }
        }

        self.res = {
            'body': json.dumps({'fizz': 'buzz'}),
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
            },
        }

    def set_request(self, req):
        self.subject.headers = req['headers']
        self.subject.path = req['path']
        self.subject.rfile = io.BytesIO(req['body'].encode())
        self.subject.wfile = io.BytesIO()

    def test_set_handler(self):
        handler = 'lambda_function.lambda_handler'
        Handler.set_handler(handler)
        assert Handler.handler == handler

    def test_set_timeout(self):
        Handler.set_timeout(11)
        assert Handler.timeout == 11

    @pytest.mark.parametrize('verb', ['GET', 'HEAD', 'POST'])
    def test_do(self, verb):
        func = getattr(Handler, f'do_{verb}')
        func(self.subject)
        self.subject.invoke.assert_called_once_with(verb)

    @pytest.mark.parametrize('verb', ['GET', 'HEAD', 'POST'])
    def test_get_body(self, verb):
        req = self.reqs[verb]
        self.set_request(req)
        ret = Handler.get_body(self.subject)
        assert ret == req['body']

    @pytest.mark.parametrize('verb', ['GET', 'HEAD', 'POST'])
    def test_get_event(self, verb):
        req = self.reqs[verb]
        self.set_request(req)
        self.subject.get_body.return_value = req['body']
        ret = Handler.get_event(self.subject, verb)
        assert ret == req

    @pytest.mark.parametrize('verb', ['GET', 'HEAD', 'POST'])
    def test_invoke_async(self, verb):
        req = self.reqs[verb]
        self.set_request(req)

        with mock.patch('lambda_gateway.server.get_handler') as mock_handler:

            def handler(event, context=None):
                return self.res

            mock_handler.return_value = handler
            ret = asyncio.run(Handler.invoke_async(self.subject, req))
            assert ret == self.res

    @pytest.mark.parametrize('verb', ['GET', 'HEAD', 'POST'])
    def test_invoke_with_timeout(self, verb):
        req = self.reqs[verb]
        self.set_request(req)
        asyncio.run(Handler.invoke_with_timeout(self.subject, req))
        self.subject.invoke_async.assert_awaited_once_with(req, None)

    @pytest.mark.parametrize('verb', ['GET', 'HEAD', 'POST'])
    def test_invoke_with_timeout_err(self, verb):
        req = self.reqs[verb]
        self.set_request(req)
        with mock.patch('asyncio.wait_for') as mock_wait:
            mock_wait.side_effect = asyncio.TimeoutError
            ret = asyncio.run(Handler.invoke_with_timeout(self.subject, req))
            exp = {
                'body': json.dumps({'Error': 'TIMEOUT'}),
                'statusCode': 408,
            }
            assert ret == exp

    @pytest.mark.parametrize('verb', ['GET', 'HEAD', 'POST'])
    def test_invoke(self, verb):
        req = self.reqs[verb]
        self.set_request(req)
        with mock.patch('asyncio.run') as mock_run:
            mock_run.return_value = self.res
            Handler.invoke(self.subject, verb)
            self.subject.get_event.assert_called_once_with(verb)
            self.subject.send_response.assert_called_once_with(
                self.res['statusCode'],
            )
            self.subject.send_header.assert_has_calls([
                mock.call(*x) for x in self.res['headers'].items()
            ])
            self.subject.end_headers.assert_called_once_with()
            self.subject.wfile.seek(0)
            ret = self.subject.wfile.read().decode()
            exp = self.res['body']
            assert ret == exp


def test_get_opts():
    sys.argv = [
        'lambda-gateway',
        '-b', '0.0.0.0',
        '-p', '8888',
        '-t', '3',
        'index.handler',
    ]
    opts = server.get_opts()
    assert opts.bind == '0.0.0.0'
    assert opts.port == 8888
    assert opts.timeout == 3
    assert opts.HANDLER == 'index.handler'


@pytest.mark.parametrize(
    ('signature', 'exp'),
    [
        ('lambda_function.lambda_handler', 'lambda_handler'),
    ]
)
def test_get_handler(signature, exp):
    ret = server.get_handler(signature).__name__
    assert ret == exp


def test_get_handler_bad_sig():
    with pytest.raises(SystemExit):
        server.get_handler('lambda_function')


def test_get_handler_no_file():
    with pytest.raises(SystemExit):
        server.get_handler('not_a_file.handler')


def test_get_handler_no_handler():
    with pytest.raises(SystemExit):
        server.get_handler('lambda_function.not_a_function')


def test_setup():
    server.setup('0.0.0.0', 8000, 30, 'index.handler')
    assert Handler.timeout == 30
    assert Handler.handler == 'index.handler'


@mock.patch('http.server.ThreadingHTTPServer')
def test_run(mock_httpd):
    mock_httpd.socket.getsockname.return_value = ['host', 8000]
    server.run(mock_httpd)
    mock_httpd.serve_forever.assert_called_once_with()


@mock.patch('http.server.ThreadingHTTPServer')
def test_run_int(mock_httpd):
    mock_httpd.socket.getsockname.return_value = ['host', 8000]
    mock_httpd.serve_forever.side_effect = KeyboardInterrupt
    server.run(mock_httpd)
    mock_httpd.serve_forever.assert_called_once_with()
    mock_httpd.shutdown.assert_called_once_with()


@mock.patch('http.server.ThreadingHTTPServer.__enter__')
@mock.patch('lambda_gateway.server.run')
@mock.patch('lambda_gateway.server.setup')
@mock.patch('lambda_gateway.server.get_opts')
def test_main(mock_opts, mock_setup, mock_run, mock_httpd):
    mock_httpd.return_value = '<httpd>'
    mock_setup.return_value = (
        http.server.ThreadingHTTPServer,
        ('localhost', 8000),
        Handler,
    )
    server.main()
    mock_run.assert_called_once_with('<httpd>')
