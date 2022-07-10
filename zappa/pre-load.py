import base64
import collections
import datetime
import importlib
import inspect
import json
import logging
import os
import sys
import traceback
from builtins import str


from werkzeug.wrappers import Response

# This file may be copied into a project's root,
# so handle both scenarios.
try:
    from zappa.middleware import ZappaWSGIMiddleware
    from zappa.utilities import merge_headers
    from zappa.wsgi import common_log, create_wsgi_request
except ImportError as e:  # pragma: no cover
    from .middleware import ZappaWSGIMiddleware
    from .utilities import merge_headers
    from .wsgi import common_log, create_wsgi_request

try:
    from oci_setting import OCISetting
except ImportError:
    from .oci_setting import OCISetting


# Set up logging
logging.basicConfig()
logger = logging.getLogger()
logger.setLevel(logging.INFO)


class FNHandle:
      """
    Singleton for avoiding duplicate setup.

    Pattern provided by @benbangert.
    """

    __instance = None
    settings = None
    settings_name = None
    session = None

    # Application
    app_module = None
    wsgi_app = None
    trailing_slash = False

    def __new__(cls, settings_name="oci_settings", session=None):
        """Singleton instance to avoid repeat setup"""
        if FNHandle.__instance is None:
            print("Instancing..")
            FNHandle.__instance = object.__new__(cls)
        return FNHandle.__instance

    def __init__(self, settings_name="oci_settings", session=None):

        # We haven't cached our settings yet, load the settings and app.
        if not self.settings:
            # Loading settings from a python module
            self.settings = OCISetting()
            self.settings_name = settings_name
            self.session = session

            # Custom log level
            if self.settings.LOG_LEVEL:
                level = logging.getLevelName(self.settings.LOG_LEVEL)
                logger.setLevel(level)

            # Let the system know that this will be a Lambda/Zappa/Stack
            os.environ["SERVERTYPE"] = "OCI fn"
            os.environ["FRAMEWORK"] = "OCI FN"
            try:
                os.environ["PROJECT"] = self.settings.PROJECT_NAME
                os.environ["STAGE"] = self.settings.API_STAGE
            except Exception:  # pragma: no cover
                pass

            # Set any locally defined env vars
            # Environment variable keys can't be Unicode
            # https://github.com/Miserlou/Zappa/issues/604
            for key in self.settings.ENVIRONMENT_VARIABLES.keys():
                os.environ[str(key)] = self.settings.ENVIRONMENT_VARIABLES[key]

            # This is a non-WSGI application
            # https://github.com/Miserlou/Zappa/pull/748
            if (
                not hasattr(self.settings, "APP_MODULE")
                and not self.settings.DJANGO_SETTINGS
            ):
                self.app_module = None
                wsgi_app_function = None
            # This is probably a normal WSGI app (Or django with overloaded wsgi application)
            # https://github.com/Miserlou/Zappa/issues/1164
            elif hasattr(self.settings, "APP_MODULE"):
                if self.settings.DJANGO_SETTINGS:
                    sys.path.append("/var/task")
                    from django.conf import (
                        ENVIRONMENT_VARIABLE as SETTINGS_ENVIRONMENT_VARIABLE,
                    )

                    # add the Lambda root path into the sys.path
                    self.trailing_slash = True
                    os.environ[
                        SETTINGS_ENVIRONMENT_VARIABLE
                    ] = self.settings.DJANGO_SETTINGS
                else:
                    self.trailing_slash = False

                # The app module
                self.app_module = importlib.import_module(self.settings.APP_MODULE)

                # The application
                wsgi_app_function = getattr(self.app_module, self.settings.APP_FUNCTION)
            # Django gets special treatment.
            else:
                try:  # Support both for tests
                    from zappa.ext.django_zappa import get_django_wsgi
                except ImportError:  # pragma: no cover
                    from django_zappa_app import get_django_wsgi

                # Get the Django WSGI app from our extension
                wsgi_app_function = get_django_wsgi(self.settings.DJANGO_SETTINGS)
                self.trailing_slash = True

            self.wsgi_app = ZappaWSGIMiddleware(wsgi_app_function)

   

    @staticmethod
    def import_module_and_get_function(whole_function):
        """
        Given a modular path to a function, import that module
        and return the function.
        """
        module, function = whole_function.rsplit(".", 1)
        app_module = importlib.import_module(module)
        app_function = getattr(app_module, function)
        return app_function

    @classmethod
    def lambda_handler(cls, event, context):  # pragma: no cover
        handler = global_handler or cls()
        exception_handler = handler.settings.EXCEPTION_HANDLER
        try:
            return handler.handler(event, context)
        except Exception as ex:
            exception_processed = cls._process_exception(
                exception_handler=exception_handler,
                event=event,
                context=context,
                exception=ex,
            )
            if not exception_processed:
                # Only re-raise exception if handler directed so. Allows handler to control if lambda has to retry
                # an event execution in case of failure.
                raise

    @classmethod
    def _process_exception(cls, exception_handler, event, context, exception):
        exception_processed = False
        if exception_handler:
            try:
                handler_function = cls.import_module_and_get_function(exception_handler)
                exception_processed = handler_function(exception, event, context)
            except Exception as cex:
                logger.error(msg="Failed to process exception via custom handler.")
                print(cex)
        return exception_processed

    def handler(self, event, context):
        """
        An AWS Lambda function which parses specific API Gateway input into a
        WSGI request, feeds it to our WSGI app, processes the response, and returns
        that back to the API Gateway.

        """
        settings = self.settings

        # If in DEBUG mode, log all raw incoming events.
        if settings.DEBUG:
            logger.debug("FN Event: {}".format(event))

        # Normal web app flow
        try:
            # Timing
            time_start = datetime.datetime.now()

            # This is a normal HTTP request
            if event.get("httpMethod", None):
                script_name = ""
                is_elb_context = False
                headers = merge_headers(event)
                if headers:
                    host = headers.get("Host")
                else:
                    host = None
                logger.debug("host found: [{}]".format(host))

                if host:
                    if "amazonaws.com" in host:
                        logger.debug("amazonaws found in host")
                        # The path provided in th event doesn't include the
                        # stage, so we must tell Flask to include the API
                        # stage in the url it calculates. See https://github.com/Miserlou/Zappa/issues/1014
                        script_name = "/" + settings.API_STAGE
                else:
                    # This is a test request sent from the AWS console
                    if settings.DOMAIN:
                        # Assume the requests received will be on the specified
                        # domain. No special handling is required
                        pass
                    else:
                        # Assume the requests received will be to the
                        # amazonaws.com endpoint, so tell Flask to include the
                        # API stage
                        script_name = "/" + settings.API_STAGE

                base_path = getattr(settings, "BASE_PATH", None)

                # Create the environment for WSGI and handle the request
                environ = create_wsgi_request(
                    event,
                    script_name=script_name,
                    base_path=base_path,
                    trailing_slash=self.trailing_slash,
                    binary_support=settings.BINARY_SUPPORT,
                    context_header_mappings=settings.CONTEXT_HEADER_MAPPINGS,
                )

                # We are always on https on Lambda, so tell our wsgi app that.
                environ["HTTPS"] = "on"
                environ["wsgi.url_scheme"] = "https"
                environ["fn.context"] = context
                environ["fn.event"] = event

                # Execute the application
                with Response.from_app(self.wsgi_app, environ) as response:
                    # This is the object we're going to return.
                    # Pack the WSGI response into our special dictionary.
                    zappa_returndict = dict()

                    # Issue #1715: ALB support. ALB responses must always include
                    # base64 encoding and status description
                    if is_elb_context:
                        zappa_returndict.setdefault("isBase64Encoded", False)
                        zappa_returndict.setdefault(
                            "statusDescription", response.status
                        )

                    if response.data:
                        if (
                            settings.BINARY_SUPPORT
                            and not response.mimetype.startswith("text/")
                            and response.mimetype != "application/json"
                        ):
                            zappa_returndict["body"] = base64.b64encode(
                                response.data
                            ).decode("utf-8")
                            zappa_returndict["isBase64Encoded"] = True
                        else:
                            zappa_returndict["body"] = response.get_data(as_text=True)

                    zappa_returndict["statusCode"] = response.status_code
                    if "headers" in event:
                        zappa_returndict["headers"] = {}
                        for key, value in response.headers:
                            zappa_returndict["headers"][key] = value
                    if "multiValueHeaders" in event:
                        zappa_returndict["multiValueHeaders"] = {}
                        for key, value in response.headers:
                            zappa_returndict["multiValueHeaders"][
                                key
                            ] = response.headers.getlist(key)

                    # Calculate the total response time,
                    # and log it in the Common Log format.
                    time_end = datetime.datetime.now()
                    delta = time_end - time_start
                    response_time_ms = delta.total_seconds() * 1000
                    response.content = response.data
                    common_log(environ, response, response_time=response_time_ms)

                    return zappa_returndict
        except Exception as e:  # pragma: no cover
            # Print statements are visible in the logs either way
            print(e)
            exc_info = sys.exc_info()
            message = (
                "An uncaught exception happened while servicing this request. "
                "You can investigate this with the `zappa tail` command."
            )

            # If we didn't even build an app_module, just raise.
            if not settings.DJANGO_SETTINGS:
                try:
                    self.app_module
                except NameError as ne:
                    message = "Failed to import module: {}".format(ne.message)

            # Call exception handler for unhandled exceptions
            exception_handler = self.settings.EXCEPTION_HANDLER
            self._process_exception(
                exception_handler=exception_handler,
                event=event,
                context=context,
                exception=e,
            )

            # Return this unspecified exception as a 500, using template that API Gateway expects.
            content = collections.OrderedDict()
            content["statusCode"] = 500
            body = {"message": message}
            if settings.DEBUG:  # only include traceback if debug is on.
                body["traceback"] = traceback.format_exception(
                    *exc_info
                )  # traceback as a list for readability.
            content["body"] = json.dumps(str(body), sort_keys=True, indent=4)
            return content