from ruamel.yaml import YAML
from collections import namedtuple

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

