# Lambda Gateway

Test AWS Lambda functions invoked as API Gateway proxy integrations locally.

This is based on https://github.com/amancevice/python-lambda-gateway but accepts a SAM template.yaml so all lambda/gateway definitions (Python and HttpApi only for now) can be run.

It also runs in async and watches the Python files for changes so you can reload.

After installing, navigate to the directory where your SAM template is defined and invoke it with the CLI tool using the configured handler, eg:

```bash
lambda-gateway [-p PORT] [-t SECONDS] template.yaml
# => Serving HTTP on :: port 8000 (http://[::]:8000/) ...
```

## Installation

Install with pip.

```bash
pip install lambda-gateway
```

## Usage

Create a Lambda function handler in Python 3 (in `testapp` subfolder)

```python
# ./testapp/lambda_function.py
import json


def lambda_handler(event, context=None):
    # Get name from qs
    params = event.get('queryStringParameters') or {}
    name = params.get('name') or 'Pythonista'
    # Return response
    return {
        'body': json.dumps({'text': f'Hello, {name}! ~ Lambda Gateway'}),
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
        },
    }
```

And a template.yaml for AWS SAM - this will not be fully verified:
```yaml
Resources:
  TestApiFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: testapp/
      Handler: lambda_function.lambda_handler
      Runtime: python3.8
      Events:
        TestApi:
          Type: HttpApi
          Properties:
            Path: /
            Method: get
```

Start a local server with the signature of your Lambda handler as the argument.

_Note — the handler must be importable from the CodeUri working directory (testapp)_

```bash
lambda-gateway [-B PATH] [-b ADDR] [-p PORT] [-t SECONDS] [-w] template.yaml
lambda-gateway -p 3000 -w template.yaml
# => Registering route Endpoint(CodeUri='testapp/', Handler='lambda_function.lambda_handler', Path='/', Method='get')
```

Test the function with cURL.

```bash
curl http://localhost:8000/?name=Pythonista
# => {"text": "Hello, Pythonista! ~ Lambda Gateway"}
```

## Watch files

The server will watch your Python files for changes and (if `-w` flag is set) will exit. This allows you to reload. For example:

```bash
while sleep 1; do lambda-gateway -p 3000 --watch ./template.yaml; done
```

Server reloading would be better if done within lambda-gateway to avoid this outer loop in bash, but forcing a full reload (e.g. import of Python modules) is easier this way.

Provide a path to the Python code base folder using the `-B` argument. This should be to your base Python folder (which will be watched for changes), and then there may still be CodeUri values specifying a further subfolder for the function code.

## Timeouts

API Gateway imposes a 30 second timeout on Lambda responses. This constraint is implemented in this project using Python's async/await syntax.

The timeout length can be adjusted using the `-t / --timeout` CLI option.

```bash
lambda-gateway -t 3 lambda_function.lambda_handler
```

## API Gateway Payloads

API Gateway supports [two versions](https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-develop-integrations-lambda.html) of proxied JSON payloads to Lambda integrations, `1.0` and `2.0`.

Versions `0.8+` of Lambda Gateway use `2.0` by default, but this can be changed at startup time using the `-V / --payload-version` option:

```bash
lambda-gateway -V1.0 lambda_function.lambda_handler
```

