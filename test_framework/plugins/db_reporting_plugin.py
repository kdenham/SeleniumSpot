"""
The Database test reporting plugin for recording all test run data in the database.
"""

import getpass
import time
import uuid
from optparse import SUPPRESS_HELP
from nose.plugins import Plugin
from nose.exc import SkipTest
from test_framework.core.application_manager import ApplicationManager
from test_framework.core.testcase_manager import ExecutionQueryPayload
from test_framework.core.testcase_manager import TestcaseDataPayload
from test_framework.core.testcase_manager import TestcaseManager
from test_framework.fixtures import constants
from test_framework.fixtures import errors


class DBReporting(Plugin):
    """
    The plugin for reporting test results in the database.
    """
    name = 'db_reporting'  # Usage: --with-db_reporting

    def __init__(self):
        """initialize some variables"""
        Plugin.__init__(self)
        self.execution_guid = str(uuid.uuid4())
        self.testcase_guid = None
        self.execution_start_time = 0
        self.case_start_time = 0
        self.application = None
        self.testcase_manager = None
        self.error_handled = False


    def options(self, parser, env):
        super(DBReporting, self).options(parser, env=env)
        parser.add_option('--database_environment', action='store', 
                          dest='database_env',
                          choices=('prod', 'qa', 'test'),
                          default='test',
                          help=SUPPRESS_HELP)


    #Plugin methods
    def configure(self, options, conf):
        """get the options"""
        super(DBReporting, self).configure(options, conf)
        self.options = options
        self.testcase_manager = TestcaseManager(self.options.database_env)


    def begin(self):
        """At the start of the run, we want to record the 
        execution information to the database."""
        exec_payload = ExecutionQueryPayload()
        exec_payload.execution_start_time = int(time.time() * 1000)
        self.execution_start_time = exec_payload.execution_start_time
        exec_payload.guid = self.execution_guid
        exec_payload.username = getpass.getuser()
        self.testcase_manager.insert_execution_data(exec_payload)


    def startTest(self, test):
        """at the start of the test, set the test case details"""
        data_payload = TestcaseDataPayload()
        self.testcase_guid = str(uuid.uuid4())
        data_payload.guid = self.testcase_guid
        data_payload.execution_guid = self.execution_guid
        if hasattr(test, "browser"):
            data_payload.browser = test.browser
        else:
            data_payload.browser = "N/A"
        data_payload.testcaseAddress = test.id()
        data_payload.application = \
            ApplicationManager.generate_application_string(test)
        data_payload.state = constants.State.NOTRUN
        self.testcase_manager.insert_testcase_data(data_payload)
        self.case_start_time = int(time.time() * 1000)
        # Make the testcase guid available to other plugins
        test.testcase_guid = self.testcase_guid


    def finalize(self, result):
        """At the end of the run, we want to 
        update that row with the execution time."""
        runtime = int(time.time() * 1000) - self.execution_start_time
        self.testcase_manager.update_execution_data(self.execution_guid, 
                                                    runtime)


    def addSuccess(self, test, capt):
        """
        After sucess of a test, we want to record the testcase run information.
        """
        self.__insert_test_result(constants.State.PASS, test)


    def addError(self, test, err, capt=None):
        """
        After error of a test, we want to record the testcase run information.
        """
        self.__insert_test_result(constants.State.ERROR, test, err)


    def handleError(self, test, err, capt=None):
        """
        After error of a test, we want to record the testcase run information.
        "Error" also encompasses any states other than Pass or Fail, so we
        check for those first.
        """
        if err[0] == errors.BlockedTest:
            self.__insert_test_result(constants.State.BLOCKED, test, err)
            self.error_handled = True
            raise SkipTest(err[1])
            return True
            
        elif err[0] == errors.DeprecatedTest:
            self.__insert_test_result(constants.State.DEPRECATED, test, err)
            self.error_handled = True
            raise SkipTest(err[1])
            return True
            
        elif err[0] == errors.SkipTest:
            self.__insert_test_result(constants.State.SKIP, test, err)
            self.error_handled = True
            raise SkipTest(err[1])
            return True


    def addFailure(self, test, err, capt=None, tbinfo=None):
        """
        After failure of a test, we want to record the testcase run information.
        """
        self.__insert_test_result(constants.State.FAILURE, test, err)  


    def __insert_test_result(self, state, test, err=None):
        data_payload = TestcaseDataPayload()
        data_payload.runtime = int(time.time() * 1000) - self.case_start_time
        data_payload.guid = self.testcase_guid
        data_payload.execution_guid = self.execution_guid
        data_payload.state = state
        if err is not None:
            data_payload.message = err[1].__str__().split('-------------------- >> begin captured logging << --------------------', 1)[0]
        self.testcase_manager.update_testcase_data(data_payload)
