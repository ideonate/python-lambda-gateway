import json
from collections import namedtuple
from ruamel.yaml import YAML
import re
import os

Endpoint = namedtuple("Endpoint", "CodeUri Handler Path Method")

class SamException(Exception):
    pass

class SAM:

    def __init__(self, config_filename):

        yaml = YAML()
        yaml.preserve_quotes = True
        yaml.default_flow_style = False

        with open(config_filename, "rt") as f:
            self.template = yaml.load(f.read())

    def get_endpoints(self):
        for name, resource in self.template.get('Resources', {}).items():
            if resource.get('Type', '') == 'AWS::Serverless::Function':
                resprops = resource.get('Properties', {})
                CodeUri = resprops.get('CodeUri', '')
                Handler = resprops.get('Handler', '')
                Events = resprops.get('Events', {})

                for eventname, event in Events.items():
                    if event.get('Type', '') == 'HttpApi':
                        eventprops = event.get('Properties', {})
                        Path = eventprops.get('Path', '/')
                        Method = eventprops.get('Method', 'get')

                        if Method not in ('get', 'post'):
                            raise SamException(f'{Method} not supported in {name} / {eventname}')
                        
                        yield Endpoint(CodeUri, Handler, Path, Method)

def load_env_vars(env_vars_path, mapping=None):
    if not env_vars_path:
        return {}

    if env_vars_path.endswith('.ts'):
        # Parse TypeScript export default object
        with open(env_vars_path, "rt") as f:
            ts_code = f.read()
        # Remove 'export default' and trailing semicolon
        ts_code = ts_code.strip()
        ts_code = re.sub(r'^export default', '', ts_code).strip()
        ts_code = ts_code.rstrip(';').strip()
        # Remove wrapping braces if present
        ts_code = ts_code.strip()
        # Quote all keys (unquoted keys at start of line or after comma)
        ts_code = re.sub(r'([,{]\s*)([a-zA-Z0-9_]+)\s*:', r'\1"\2":', ts_code)
        # Convert single quotes to double quotes
        ts_code = ts_code.replace("'", '"')
        # Remove trailing commas before closing brace
        ts_code = re.sub(r',\s*}', '}', ts_code)
        ts_code = re.sub(r',\s*]', ']', ts_code)
        # Now ts_code should be valid JSON
        import json
        config_vars = json.loads(ts_code)
        if mapping:
            env_vars = {}
            for env_var, props_key in mapping.items():
                if props_key is None:
                    env_vars[env_var] = os.environ.get(env_var, "")
                elif props_key in config_vars:
                    env_vars[env_var] = config_vars[props_key]
                else:
                    env_vars[env_var] = os.environ.get(env_var, "")
            return env_vars
        else:
            return config_vars
    else:
        with open(env_vars_path, "rt") as f:
            env_vars_all = json.load(f)

        env_vars_consolidated = {}
        for k,v in env_vars_all.items():
            env_vars_consolidated.update(v)
        return env_vars_consolidated
