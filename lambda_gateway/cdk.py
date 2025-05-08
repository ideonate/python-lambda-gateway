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
        # Regex to match createLambda calls
        # Example: createLambda(this, 'SaveAnalytics', 'app.endpoints.analyticshandler', props, depsLayer, userAnalyticsSqs.queueUrl)
        pattern = re.compile(r"createLambda\([^,]+,\s*'([^']+)',\s*'([^']+)'[^)]*\)")
        for match in pattern.finditer(self.ts_code):
            id_ = match.group(1)
            handler = match.group(2)
            # Try to infer CodeUri (assume '../bingocards' as in the example, or default to '.')
            code_uri = self._infer_code_uri()
            # Default path and method (could be improved with more parsing)
            path = f"/{id_.lower()}"
            method = 'post'  # Default to POST; could be improved
            yield Endpoint(code_uri, handler, path, method)

    def _infer_code_uri(self):
        # Naive: look for Code.fromAsset('...') in the file
        m = re.search(r"Code\.fromAsset\(['\"]([^'\"]+)['\"]\)", self.ts_code)
        if m:
            return m.group(1)
        return '.' 