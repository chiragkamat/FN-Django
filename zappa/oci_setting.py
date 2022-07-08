import json


class OCISetting:

    EXCEPTION_HANDLER=None
    DEBUG=True
    LOG_LEVEL='DEBUG'
    BINARY_SUPPORT=True
    CONTEXT_HEADER_MAPPINGS={}
    DOMAIN=None
    BASE_PATH=None
    ENVIRONMENT_VARIABLES={
        'AWS_REGION': 'ap-south-1', 
        'LOG_QUEUE': 'LOG_QUEUE', 
        'LOG_POLLING_QUEUE': 'LOG_POLLING_QUEUE', 
        'LOG_AGGREGATION_QUEUE': 'LOG_AGGREGATION_QUEUE', 
        'NEWRELIC_HOST': 'insights-collector.newrelic.com',
        'NEWRELIC_ACCOUNT': '3245987', 
        'NEWRELIC_APIKEY': 'NRII-Cv49edNwpV9VBVW9su2c2Ha-OEaJSzFX', 
        'CIPHER_KEY': 'R88En8LixFzYG2LlretV6a492qaFvkJ-Vbo9Ef8AMzw='
     }
    API_STAGE='gateway'
    PROJECT_NAME='plugin-monitoring'
    SETTINGS_FILE=None
    DJANGO_SETTINGS='plugins_monitoring_system.settings'
    AWS_EVENT_MAPPING={} 
    AWS_BOT_EVENT_MAPPING={}
    COGNITO_TRIGGER_MAPPING={}
    ASYNC_RESPONSE_TABLE=''


    def __new__(cls, settings="zappa_settings.json"):
        if OCISetting.__instance is None:
            print("Instancing..")
            OCISetting.__instance = object.__new__(cls)
        return OCISetting.__instance


    def __init__(cls, settings="zappa_settings.json"):
        """_summary_

        Args:
            settings (str, optional): _description_. Defaults to "zappa_settings.json".
        """
        self.stage_config = []    
        with open('data.json') as json_file:
            self.stage_config = json.load(json_file)
    

    def load(self):
        """_summary_
        """
        self.app_function = self.stage_config.get("app_function", None)
        self.exception_handler = self.stage_config.get("exception_handler", None)
        self.debug = self.stage_config.get("debug", True)
        self.profile_name = self.stage_config.get("profile_name", None)
        self.log_level = self.stage_config.get("log_level", "DEBUG")
        self.domain = self.stage_config.get("domain", None)
        self.base_path = self.stage_config.get("base_path", None)
        self.cognito = self.stage_config.get("cognito", None)
        self.remote_env = self.stage_config.get("remote_env", None)
        self.settings_file = self.stage_config.get("settings_file", None)
        self.django_settings = self.stage_config.get("django_settings", None)
        self.environment_variables = self.stage_config.get("environment_variables", {})
       