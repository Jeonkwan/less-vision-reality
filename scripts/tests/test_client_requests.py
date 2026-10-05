"""Network retries retain required successful samples and reject persistent failures."""
import contextlib
import importlib.util
import io
import pathlib
import subprocess
import unittest
from unittest.mock import Mock

spec=importlib.util.spec_from_file_location('clients',pathlib.Path(__file__).resolve().parents[1]/'check-native-clients.py')
clients=importlib.util.module_from_spec(spec)
spec.loader.exec_module(clients)

class Requests(unittest.TestCase):
    def request(self,codes):
        run=Mock(side_effect=[subprocess.CompletedProcess([],code,'200' if code==0 else '000','') for code in codes])
        sleep=Mock()
        with contextlib.redirect_stdout(io.StringIO()):result=clients.request_https(12345,'https://example.com',run,sleep)
        return result,run,sleep

    def test_transient_proxy_error_retries_same_request(self):
        result,run,sleep=self.request([97,0])
        self.assertEqual(result.returncode,0)
        self.assertEqual(run.call_count,2)
        self.assertEqual(run.call_args_list[0],run.call_args_list[1])
        sleep.assert_called_once_with(1)

    def test_persistent_network_failure_remains_failure(self):
        result,run,sleep=self.request([97,97,97])
        self.assertEqual(result.returncode,97)
        self.assertEqual(run.call_count,3)
        self.assertEqual([call.args for call in sleep.call_args_list],[(1,),(2,)])

    def test_http_or_configuration_failure_is_not_retried(self):
        for code in [22,3,60]:
            with self.subTest(code=code):
                result,run,sleep=self.request([code])
                self.assertEqual(result.returncode,code)
                self.assertEqual(run.call_count,1)
                sleep.assert_not_called()

if __name__=='__main__':unittest.main()
