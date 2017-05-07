import json

import requests
import logging

import sqlite3


class BaseSMSHandler:
    """
    Interface for SMSHandlers

    Example of usage:
    >>> sms_handler = SomeSMSHandler(...)
    >>> sms_handler.send(...)
    """

    def __init__(self, login, password, sender=None):
        """
        Store initial data for interacting with sms service

        login -- login for sms service
        password -- password for sms service or hash of real password
        sender -- phone number or name of sender
        """
        self.login = login
        self.password = password
        self.sender = sender

    def send(self, user_data):
        """
        Sending sms via sms service

        user_data -- this dict must include `phone` and `message`
        """
        raise NotImplementedError

    def _log(self, result):
        """
        Internal method for logging result of `send` method

        response -- it's a dict with 2 variants of data:
            {'status':'ok','phone':'79149009900'}
            {'status':'error','phone':'79149009900','error_code':3500,'error_msg':'description'}
        """
        raise NotImplementedError


class SimpleLoggingMixin:
    """
    Logging result of call `send` method use standard python library 
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.logger = logging.getLogger('sms')

    def _log(self, result):
        status = result.get('status')
        if status is None:
            raise ValueError('Could not find "status" field')
        elif status == 'ok':
            self.logger.info('status: OK, phone: %s', result['phone'])
        elif status == 'error':
            self.logger.info('status: ERROR, phone: %s, message: %s', result['phone'], result['error_msg'])
        else:
            raise RuntimeError('Unexpected value of status')


class SQLiteLoggingMixin:
    """
    Logging result of call `send` method use SQLite
    """

    DDL = """
    CREATE TABLE Results (
        success real NOT NULL CHECK (success IN (0, 1)),
        phone text NOT NULL,
        error_code integer,
        error_msg text
    )
    """

    def __init__(self, db_uri, **kwargs):
        """
        db_uri must contains URI path to SQLite file
        Example: file:path/to/database?mode=rw'
        """
        super().__init__(**kwargs)
        conn = sqlite3.connect(db_uri, uri=True)
        self.c = conn.cursor()

    def _log(self, response):
        status = response.get('status')
        if status is None:
            raise ValueError('Could not find "status" field')
        elif status == 'ok':
            self.c.execute("INSERT INTO Results VALUES (?, ?, NULL, NULL)", (1, response['phone']))
            self.c.connection.commit()
        elif status == 'error':
            self.c.execute("INSERT INTO Results VALUES (?, ?, ?, ?)",
                           (0, response['phone'], response['error_code'], response['error_msg']))
            self.c.connection.commit()
        else:
            raise ValueError('Unexpected value of status')


class SMSCRU_SMSHandlerMixin:
    """
    Handler for smsc.ru

    Real smsc.ru uses next schema API
    https://smsc.ru/sys/send.php?login=<login>&psw=<password>&phones=<phones>&mes=<message>
    As you can see all the data are query params
    Let's do the same
    """

    request_url = 'http://smsc.ru/someapi/message/'

    def send(self, user_data):
        params = {'login': self.login, 'psw': self.password}
        params.update(user_data)
        r = requests.get(self.request_url, params=params)
        if r.status_code != 200:
            self._log({
                'status': 'error',
                'phone': user_data.get('phone', '-'),
                'error_code': None,
                'error_msg': 'data: {}'.format(user_data)
            })
        else:
            response = r.json()
            self._log(response)


class SMSTRAFFIC_SMSHandlerMixin:
    """
    Handler for smstraffic.ru

    I didn't read documentation of smstraffic.ru but I designed next schema:
    * getting auth token
    * send data using POST method (smth like ajax without additional header)
    * all responses from server are the string representation of python dict
    """

    request_url = 'http://smstraffic.ru/superapi/message/'
    auth_url = 'http://smstraffic.ru/superapi/auth/'

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.token = self._get_token()

    def _get_token(self):
        data = {
            'login': self.login,
            'pass': self.password
        }
        r = requests.post(self.auth_url, data=data)
        if r.status_code != 200:
            raise RuntimeError('Invalid response status code: {} != 200'.format(r.status_code))
        token = json.loads(r.text).get('token')
        if token is None:
            raise RuntimeError('Response from server does not contain token')
        return token

    def send(self, user_data):
        data = {'token': self.token}
        data.update(user_data)
        r = requests.post(self.request_url, data=data)
        if r.status_code != 200:
            self._log({
                'status': 'error',
                'phone': user_data.get('phone', '-'),
                'error_code': None,
                'error_msg': 'data: {}'.format(user_data)
            })
        else:
            response = json.loads(r.text)
            self._log(response)


def get_handler(handler_name, logger_name='simple', handler_data=None):
    """
    Example:
    >>> sms_handler = get_handler(handler_name)
    >>> sms_handler.send(user_data)

    handler_name -- name of sms service
    logger_name -- type of logging
    handler_data -- additional data for initialization
    """
    handlers = {
        # 'handler_name': (ExampleSMSHandlerMixin, {'login': 'login': 'password': 'pass', 'sender': None})
        'smsr.ru': (SMSCRU_SMSHandlerMixin, {'login': 'login', 'password': 'pass'}),
        'smstraffic.ru': (SMSTRAFFIC_SMSHandlerMixin, {'login': 'login', 'password': 'pass'}),
    }
    loggers = {
        # 'logger_name': ExampleLoggingMixin
        'simple': SimpleLoggingMixin,
        'sqlite': SQLiteLoggingMixin,
    }

    handler, auth_data = handlers.get(handler_name, (None,  None))
    logger = loggers.get(logger_name)
    if handler is None or logger is None:
        raise ValueError('Invalid handler_name or logger_name')
    class_name = handler.__name__[:-len('Mixin')]
    cls = type(class_name, (logger, handler, BaseSMSHandler), {})
    initial_data = {}
    initial_data.update(auth_data)
    if handler_data is None:
        handler_data = {}
        if logger_name == 'sqlite':
            handler_data = {'db_uri': 'file:/tmp/testdb.sqlite?mode=rw'}
    initial_data.update(handler_data)
    return cls(**initial_data)
