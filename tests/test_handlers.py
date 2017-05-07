import os
import unittest

import sqlite3

import sms
from unittest.mock import patch, PropertyMock, Mock


class SimpleLoggingMixinTestCase(unittest.TestCase):
    def test_log_without_status_in_response(self):
        mixin = sms.SimpleLoggingMixin()
        response = {}
        with self.assertRaises(ValueError):
            mixin._log(response)

    def test_log_unxpected_value_of_status_in_response(self):
        mixin = sms.SimpleLoggingMixin()
        response = {'status': None}
        with self.assertRaises(ValueError):
            mixin._log(response)

    @patch('logging.getLogger')
    def test_log_ok_response(self, mock_logging):
        mixin = sms.SimpleLoggingMixin()
        response = {'status': 'ok', 'phone': '79149009900'}
        mixin._log(response)
        self.assertTrue(mock_logging.return_value.info.called)

    @patch('logging.getLogger')
    def test_log_error_response(self, mock_logging):
        mixin = sms.SimpleLoggingMixin()
        response = {'status': 'error', 'phone': '79149009900', 'error_code': 3500, 'error_msg': 'description'}
        mixin._log(response)
        self.assertTrue(mock_logging.return_value.info.called)


class SQLiteLoggingMixinTestCase(unittest.TestCase):
    def test_creation_of_db(self, uri='file::memory:'):
        mixin = sms.SQLiteLoggingMixin(uri)
        mixin.c.execute(mixin.DDL)
        mixin.c.connection.commit()

        mixin.c.execute('SELECT Count(*) AS c FROM Results;')
        self.assertEqual(mixin.c.fetchone(), (0,))
        return mixin

    def test_creation_of_file_db(self):
        db_path = '/tmp/testdb.sqlite'
        try:
            os.remove(db_path)
        except OSError:
            pass
        self.test_creation_of_db('file:{}?mode=rwc'.format(db_path))
        self.assertTrue(os.path.isfile(db_path))
        os.remove(db_path)

    def test_log_without_status_in_response(self):
        mixin = self.test_creation_of_db()
        response = {}
        with self.assertRaises(ValueError):
            mixin._log(response)

    def test_log_unxpected_value_of_status_in_response(self):
        mixin = self.test_creation_of_db()
        response = {'status': None}
        with self.assertRaises(ValueError):
            mixin._log(response)

    def test_log_ok_response(self):
        mixin = self.test_creation_of_db()
        response = {'status': 'ok', 'phone': '79149009900'}
        mixin._log(response)
        mixin.c.execute('SELECT success, phone AS c FROM Results;')
        self.assertEqual(mixin.c.fetchone(), (1.0, response['phone']))

    def test_log_error_response(self):
        mixin = self.test_creation_of_db()
        response = {'status': 'error', 'phone': '79149009900', 'error_code': 3500, 'error_msg': 'description'}
        mixin._log(response)
        mixin.c.execute('SELECT success, phone, error_code, error_msg AS c FROM Results;')
        self.assertEqual(mixin.c.fetchone(), (0.0, response['phone'], response['error_code'], response['error_msg']))


class SMSCRU_SMSHandlerMixinTestCase(unittest.TestCase):
    @patch('requests.get', return_value=Mock(status_code=0))
    @patch('sms.SMSCRU_SMSHandlerMixin._log', create=True)
    @patch('sms.SMSCRU_SMSHandlerMixin.login', create=True, new_callable=PropertyMock, return_value='login')
    @patch('sms.SMSCRU_SMSHandlerMixin.password', create=True, new_callable=PropertyMock, return_value='pass')
    def test_send_invalid_HTTP_code_empty_user_data(self, mock_pass, mock_login, mock_log, mock_requests):
        mixin = sms.SMSCRU_SMSHandlerMixin()
        user_data = {}
        mixin.send(user_data)
        mock_log.assert_called_once_with({
            'status': 'error',
            'phone': '-',
            'error_code': None,
            'error_msg': 'data: {}'.format(user_data)
        })

    @patch('requests.get', return_value=Mock(status_code=0))
    @patch('sms.SMSCRU_SMSHandlerMixin._log', create=True)
    @patch('sms.SMSCRU_SMSHandlerMixin.login', create=True, new_callable=PropertyMock, return_value='login')
    @patch('sms.SMSCRU_SMSHandlerMixin.password', create=True, new_callable=PropertyMock, return_value='pass')
    def test_send_invalid_HTTP_code(self, mock_pass, mock_login, mock_log, mock_requests):
        mixin = sms.SMSCRU_SMSHandlerMixin()
        user_data = {'status': 'ok', 'phone': '79149009900'}
        mixin.send(user_data)
        mock_log.assert_called_once_with({
            'status': 'error',
            'phone': user_data['phone'],
            'error_code': None,
            'error_msg': 'data: {}'.format(user_data)
        })

    @patch('requests.get', return_value=Mock(status_code=200,
                                             json=lambda x=None: {'status': 'ok', 'phone': '79149009900'}))
    @patch('sms.SMSCRU_SMSHandlerMixin._log', create=True)
    @patch('sms.SMSCRU_SMSHandlerMixin.login', create=True, new_callable=PropertyMock, return_value='login')
    @patch('sms.SMSCRU_SMSHandlerMixin.password', create=True, new_callable=PropertyMock, return_value='pass')
    def test_send_valid_response(self, mock_pass, mock_login, mock_log, mock_requests):
        mixin = sms.SMSCRU_SMSHandlerMixin()
        user_data = {'status': 'ok', 'phone': '79149009900'}
        mixin.send(user_data)
        mock_log.assert_called_once_with(user_data)


class SMSTRAFFIC_SMSHandlerMixinTestCase(unittest.TestCase):
    @patch('requests.post', return_value=Mock(status_code=0, text='{"token": "a"}'))
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.login', create=True, new_callable=PropertyMock, return_value='login')
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.password', create=True, new_callable=PropertyMock, return_value='pass')
    def test_init_with_invalid_HTTP_code(self, mock_pass, mock_login, mock_requests):
        with self.assertRaises(RuntimeError):
            mixin = sms.SMSTRAFFIC_SMSHandlerMixin()

    @patch('requests.post', return_value=Mock(status_code=200, text='{}'))
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.login', create=True, new_callable=PropertyMock, return_value='login')
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.password', create=True, new_callable=PropertyMock, return_value='pass')
    def test_init_with_response_without_token(self, mock_pass, mock_login, mock_requests):
        with self.assertRaises(RuntimeError):
            mixin = sms.SMSTRAFFIC_SMSHandlerMixin()

    @patch('requests.post', return_value=Mock(status_code=200, text='{"token": "a"}'))
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.login', create=True, new_callable=PropertyMock, return_value='login')
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.password', create=True, new_callable=PropertyMock, return_value='pass')
    def test_init_with_response_without_token(self, mock_pass, mock_login, mock_requests):
        mixin = sms.SMSTRAFFIC_SMSHandlerMixin()
        self.assertEqual(mixin.token, 'a')
        return mixin

    @patch('requests.post', return_value=Mock(status_code=0, text='{}'))
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin._log', create=True)
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.login', create=True, new_callable=PropertyMock, return_value='login')
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.password', create=True, new_callable=PropertyMock, return_value='pass')
    def test_send_invalid_HTTP_code_empty_user_data(self, mock_pass, mock_login, mock_log, mock_requests):
        mixin = self.test_init_with_response_without_token()
        user_data = {}
        mixin.send(user_data)
        mock_log.assert_called_once_with({
            'status': 'error',
            'phone': '-',
            'error_code': None,
            'error_msg': 'data: {}'.format(user_data)
        })

    @patch('requests.post', return_value=Mock(status_code=0, text='{"status": "ok", "phone": "79149009900"}'))
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin._log', create=True)
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.login', create=True, new_callable=PropertyMock, return_value='login')
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.password', create=True, new_callable=PropertyMock, return_value='pass')
    def test_send_invalid_HTTP_code(self, mock_pass, mock_login, mock_log, mock_requests):
        mixin = self.test_init_with_response_without_token()
        user_data = {'status': 'ok', 'phone': '79149009900'}
        mixin.send(user_data)
        mock_log.assert_called_once_with({
            'status': 'error',
            'phone': user_data['phone'],
            'error_code': None,
            'error_msg': 'data: {}'.format(user_data)
        })

    @patch('requests.post', return_value=Mock(status_code=200, text='{"status": "ok", "phone": "79149009900"}'))
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin._log', create=True)
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.login', create=True, new_callable=PropertyMock, return_value='login')
    @patch('sms.SMSTRAFFIC_SMSHandlerMixin.password', create=True, new_callable=PropertyMock, return_value='pass')
    def test_send_valid(self, mock_pass, mock_login, mock_log, mock_requests):
        mixin = self.test_init_with_response_without_token()
        user_data = {'status': 'ok', 'phone': '79149009900'}
        mixin.send(user_data)
        mock_log.assert_called_once_with(user_data)


class get_handlerMixinTestCase(unittest.TestCase):
    def test_invalid_handler_name(self):
        with self.assertRaises(ValueError):
            handler = sms.get_handler('a')

    def test_invalid_logger_name(self):
        with self.assertRaises(ValueError):
            handler = sms.get_handler('smsr.ru', 'a')

    def test_create_handler_with_simple_logger(self):
        handler = sms.get_handler('smsr.ru')
        self.assertIsInstance(handler, sms.SMSCRU_SMSHandlerMixin)
        self.assertIsInstance(handler, sms.BaseSMSHandler)
        self.assertIsInstance(handler, sms.SimpleLoggingMixin)

    def test_create_handler_with_db_logger(self):
        db_path = '/tmp/testdb.sqlite'
        try:
            os.remove(db_path)
        except OSError:
            pass
        conn = sqlite3.connect(db_path)
        conn.close()

        handler = sms.get_handler('smsr.ru', 'sqlite')
        self.assertIsInstance(handler, sms.SMSCRU_SMSHandlerMixin)
        self.assertIsInstance(handler, sms.BaseSMSHandler)
        self.assertIsInstance(handler, sms.SQLiteLoggingMixin)
        os.remove(db_path)

    def test_create_handler_with_db_logger_with_additional_params(self):
        db_path = '/tmp/testdb.sqlite'
        db_uri = 'file::memory:'
        try:
            os.remove(db_path)
        except OSError:
            pass
        handler = sms.get_handler('smsr.ru', 'sqlite', {'db_uri': db_uri})
        self.assertIsInstance(handler, sms.SMSCRU_SMSHandlerMixin)
        self.assertIsInstance(handler, sms.BaseSMSHandler)
        self.assertIsInstance(handler, sms.SQLiteLoggingMixin)
        self.assertFalse(os.path.isfile(db_path))
