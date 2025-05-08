import re
from collections import namedtuple
import os

Endpoint = namedtuple("Endpoint", "CodeUri Handler Path Method")

class CDKException(Exception):
    pass

class CDKParser:
    def __init__(self, ts_filename):
        with open(ts_filename, "rt") as f:
            self.ts_code = f.read()

    def get_endpoints(self):
        # 1. Map variable names to (handler, code_uri)
        lambda_vars = {}
        create_lambda_pattern = re.compile(r"const\s+(\w+)\s*=\s*createLambda\([^,]+,\s*['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"][^)]*\)")
        for match in create_lambda_pattern.finditer(self.ts_code):
            varname = match.group(1)
            id_ = match.group(2)
            handler = match.group(3)
            code_uri = self._infer_code_uri()
            lambda_vars[varname] = (handler, code_uri)

        # 2. Find httpApi.addRoutes calls
        # Example: httpApi.addRoutes({ path: '/configuration/start', methods: [HttpMethod.GET], integration: new HttpLambdaIntegration('CanvaConfigurationStartIntegration', canvaConfigurationStartFn), });
        add_routes_pattern = re.compile(
            r"addRoutes\s*\(\s*{[^}]*path:\s*['\"]([^'\"]+)['\"],[^}]*methods:\s*\[([^\]]+)\][^}]*integration:\s*new HttpLambdaIntegration\([^,]+,\s*(\w+)\)[^}]*}\s*\)",
            re.DOTALL)
        for match in add_routes_pattern.finditer(self.ts_code):
            path = match.group(1)
            methods_str = match.group(2)
            integration_var = match.group(3)
            # Parse methods (e.g., HttpMethod.GET, HttpMethod.POST)
            methods = re.findall(r'HttpMethod\.([A-Z]+)', methods_str)
            if not methods:
                methods = ['GET']  # Default to GET if not found
            for method in methods:
                method = method.lower()
                if integration_var in lambda_vars:
                    handler, code_uri = lambda_vars[integration_var]
                    yield Endpoint(code_uri, handler, path, method)

        # 3. Fallback: yield any createLambda not referenced in addRoutes (with guessed path/method)
        for varname, (handler, code_uri) in lambda_vars.items():
            # If not already yielded
            # (This is a simple fallback; could be improved)
            pass  # Do not yield fallback for now, only yield those with routes

    def _infer_code_uri(self):
        # Naive: look for Code.fromAsset('...') in the file
        m = re.search(r"Code\.fromAsset\(['\"]([^'\"]+)['\"]\)", self.ts_code)
        if m:
            return m.group(1)
        return '.' 