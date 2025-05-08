# Lambda Gateway

Test AWS Lambda functions invoked as API Gateway proxy integrations locally.

This is based on https://github.com/amancevice/python-lambda-gateway but accepts a SAM template.yaml **or a TypeScript CDK stack file** so all lambda/gateway definitions (Python and HttpApi only for now) can be run.

An env json file **or a TypeScript export default object file** can be supplied to set env vars.

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

You can use either a SAM template.yaml **or a TypeScript CDK stack file** as input.

### With a SAM template.yaml

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

And a template.yaml for AWS SAM:

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

Start a local server:

```bash
lambda-gateway [-B PATH] [-b ADDR] [-p PORT] [-t SECONDS] [-w] [-e .env.json] template.yaml
```

### With a TypeScript CDK stack file

Suppose you have a CDK stack file like this:

```typescript
// cdk-stack.ts
function createLambda(
  scope,
  id,
  handler,
  props,
  depsLayer,
  userActivitySqsUrl
) {
  return new Function(scope, id, {
    functionName: `${id}-${props.environment}`,
    runtime: Runtime.PYTHON_3_11,
    handler,
    code: Code.fromAsset("../bingocards"),
    environment: getLambdaEnv(props, userActivitySqsUrl),
    layers: [depsLayer],
    logRetention: RetentionDays.THREE_MONTHS,
  });
}

const saveAnalyticsFn = createLambda(
  this,
  "SaveAnalytics",
  "app.endpoints.analyticshandler",
  props,
  depsLayer,
  userAnalyticsSqs.queueUrl
);
// ...
```

Start a local server:

```bash
lambda-gateway [-B PATH] [-b ADDR] [-p PORT] [-t SECONDS] [-w] [-e env.dev.ts] cdk-stack.ts
```

### Environment Variables

You can provide environment variables as either a `.json` file or a TypeScript file exporting a default object.

#### JSON example

```
{
  "Parameters":
  {
    "Environment": "local"
  }
}
```

#### TypeScript example

```
export default {
  supportEmail: 'dev@example.com',
  domainNameApi: 'example.net',
  // ...
};
```

**Note:** The TypeScript file must export a plain object as `export default { ... }`. Only simple key-value pairs, arrays, and nested objects are supported. No functions or computed values.

Supply on the command line using the `-e` argument:

```bash
lambda-gateway -e env.dev.ts cdk-stack.ts
lambda-gateway -e .env.json template.yaml
```

Test the function with cURL.

```bash
curl http://localhost:8000/?name=Pythonista
# => {"text": "Hello, Pythonista! ~ Lambda Gateway"}
```

## Watch files

The server will watch your Python files for changes and (if `-w` flag is set) will exit. This allows you to reload. For example:

```bash
while; do lambda-gateway -p 3000 --watch ./template.yaml; done
```

Server reloading would be better if done within lambda-gateway to avoid this outer loop in bash, but forcing a full reload (e.g. import of Python modules) is easier this way.

Provide a path to the Python code base folder using the `-B` argument. This should be to your base Python folder (which will be watched for changes), and then there may still be CodeUri values specifying a further subfolder for the function code.

## Env Vars

You can provide an .env.json file looking like this:

```
{
  "Parameters":
  {
    "Environment": "local"
  }
}
```

Supply on the command line using the `-e .env.json` argument. If the file contains multiple sets of env vars, e.g. one per lambda function instead of just a single 'Parameters' entry, then these will all be consolidated together and all of them provided to all functions.

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
