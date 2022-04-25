import json
from collections import namedtuple
from ruamel.yaml import YAML

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

def load_env_vars(env_vars_json_path):
    if not env_vars_json_path:
        return {}

    with open(env_vars_json_path, "rt") as f:
        env_vars_all = json.load(f)

    env_vars_consolidated = {}
    for k,v in env_vars_all.items():
        env_vars_consolidated.update(v)
    
    return env_vars_consolidated
