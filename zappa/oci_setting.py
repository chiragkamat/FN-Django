import json


class OCISetting:


    @property
    def EXCEPTION_HANDLER(self):
        return self.exception_handler

    @property
    def DEBUG(self):
        return self.debug

    @property
    def LOG_LEVEL(self):
        return self.log_level

    @property
    def BINARY_SUPPORT(self):
        return True

    @property
    def DOMAIN(self):
        return self.domain

    @property
    def BASE_PATH(self):
        return self.base_path

    @property
    def ENVIRONMENT_VARIABLES(self):
        return self.environment_variables

    @property
    def API_STAGE(self):
        return ""

    @property
    def PROJECT_NAME(self):
        return ""

    @property
    def DJANGO_SETTINGS(self):
        return self.django_settings
    

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
        cls.stage_config = []    
        with open(settings) as json_file:
            cls.stage_config = json.load(json_file)
        cls.load()
    

    def load(self):
        """_summary_
        """
        self.app_function = self.stage_config.get("app_function", None)
        self.exception_handler = self.stage_config.get("exception_handler", None)
        self.debug = self.stage_config.get("debug", True)
        self.log_level = self.stage_config.get("log_level", "DEBUG")
        self.domain = self.stage_config.get("domain", None)
        self.base_path = self.stage_config.get("base_path", None)
        self.django_settings = self.stage_config.get("django_settings", None)
        self.environment_variables = self.stage_config.get("environment_variables", {})
    
    