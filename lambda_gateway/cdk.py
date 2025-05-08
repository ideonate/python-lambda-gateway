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

    def get_env_var_mapping(self):
        """
        Parse getLambdaEnv function to map env var names to props keys.
        Returns a dict: { ENV_VAR: props_key, ... }
        """
        mapping = {}
        # Find start of getLambdaEnv function
        m = re.search(r'function\s+getLambdaEnv\([^)]*\)\s*{', self.ts_code)
        if not m:
            m = re.search(r'def\s+getLambdaEnv\([^)]*\)\s*{', self.ts_code)
        if not m:
            return mapping
        start = m.end() - 1  # position of the opening brace
        code = self.ts_code
        brace_count = 0
        body = ''
        i = start
        while i < len(code):
            c = code[i]
            if c == '{':
                brace_count += 1
            elif c == '}':
                brace_count -= 1
                if brace_count == 0:
                    body += c
                    break
            body += c
            i += 1
        # Now parse lines for ENV_VAR: props.propsKey
        for line in body.splitlines():
            line = line.strip().rstrip(',')
            m2 = re.match(r'([A-Z0-9_]+)\s*:\s*props\.([a-zA-Z0-9_]+)\s*(,|$)', line)
            if m2:
                env_var, props_key = m2.group(1), m2.group(2)
                mapping[env_var] = props_key
            else:
                # Match lines like DDBTableName: table.tableName,
                m3 = re.match(r'([A-Za-z0-9_]+)\s*:\s*[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+\s*(,|$)', line)
                if m3:
                    env_var = m3.group(1)
                    mapping[env_var] = os.environ.get(env_var, "")
        return mapping 