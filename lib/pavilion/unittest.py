"""This module provides a base set of utilities for creating unittests
for Pavilion."""

import copy
import fnmatch
import inspect
import os
import pprint
import tempfile
import time
import types
import unittest
import warnings
from hashlib import sha1
from pathlib import Path
from typing import List

import pavilion.schedulers
from pavilion import arguments
from pavilion import config
from pavilion import dir_db
from pavilion import resolve
from pavilion import pavilion_variables
from pavilion import plugins
from pavilion.sys_vars import base_classes
from pavilion.output import dbg_print
from pavilion.variables import VariableSetManager
from pavilion.resolver import TestConfigResolver
from pavilion.test_config.file_format import TestConfigLoader
from pavilion.test_run import TestRun


class PavTestCase(unittest.TestCase):
    """A unittest.TestCase with a lot of useful Pavilion features baked in.
All pavilion unittests (in test/tests) should use this as their
base class.

:cvar Path PAV_LIB_DIR: The Path to Pavilion's lib directory (where this
    module resides).
:cvar Path PAV_ROOT_DIR: The Path to Pavilion's root directory (the root of the
    git repo).
:cvar Path TEST_DATA_ROOT: The unit test data directory.
:cvar Path PAV_CONFIG_PATH: The path to the configuration used by unit tests.
:cvar dict QUICK_TEST_BASE_CFG: The base configuration for tests generated
    by the ``_quick_test()`` and ``_quick_test_cfg()`` methods.

:ivar yaml_config.ConfigDict pav_cfg: A pavilion config setup properly for
    use by unit tests. Unit tests should **always** use this pav_cfg. If it
    needs to be modified, copy it using copy.deepcopy.
"""

    PAV_LIB_DIR = Path(__file__).resolve().parent  # type: Path
    PAV_ROOT_DIR = PAV_LIB_DIR.parents[1]  # type: Path
    TEST_DATA_ROOT = PAV_ROOT_DIR/'test'/'data'  # type: Path

    PAV_CONFIG_PATH = TEST_DATA_ROOT/'pav_config_dir'/'pavilion.yaml'

    TEST_URL = ('https://raw.githubusercontent.com/hpc/'
                'pavilion2/2.1.1/README.md')
    TEST_URL2 = ('https://raw.githubusercontent.com/hpc/'
                 'pavilion2/2.1.1/RELEASE.txt')
    TEST_URL_HASH = '0a3ad5bec7c8f6929115d33091e53819ecaca1ae'

    # Skip any tests that match these globs.
    SKIP = []
    # Only run tests that match these globs.
    ONLY = []

    # Working dirs
    WORKING_DIRS = [
        'builds',
        'test_runs',
        'series',
        'users',
        ]

    def __init__(self, *args, **kwargs):
        """Setup the pav_cfg object, and do other initialization required by
        pavilion."""

        self.pav_cfg: config.PavConfig = self.make_pav_config()

        # We have to get this to set up the base argument parser before
        # plugins can add to it.
        _ = arguments.get_parser()
        super().__init__(*args, **kwargs)

    def setUp(self) -> None:
        """Moving from the old camel case names to the standard naming scheme."""
        self.set_up()

    def tearDown(self) -> None:
        self.tear_down()

    def set_up(self):
        """By default, initialize plugins before every test."""

        _ = self

        plugins.initialize_plugins(self.pav_cfg)

    def tear_down(self):
        """By default, reset plugins after every test."""

        _ = self

        # pylint: disable=protected-access
        plugins._reset_plugins()

    def make_pav_config(self, config_dirs: List[Path] = None):
        """Create a pavilion config for use with tests. By default uses the `data/pav_config_dir`
        as the config directory.
        """

        if config_dirs is None:
            config_dirs = [self.TEST_DATA_ROOT / 'pav_config_dir']

        # Open the default pav config file (found in
        # test/data/pav_config_dir/pavilion.yaml), modify it, and then
        # save the modified file to a temp location and read it instead.
        with self.PAV_CONFIG_PATH.open() as cfg_file:
            raw_pav_cfg = config.PavilionConfigLoader().load(cfg_file)

        raw_pav_cfg.config_dirs = config_dirs

        raw_pav_cfg.working_dir = self.PAV_ROOT_DIR/'test'/'working_dir'
        raw_pav_cfg.user_config = False

        raw_pav_cfg.result_log = raw_pav_cfg.working_dir/'results.log'

        if not raw_pav_cfg.working_dir.exists():
            raw_pav_cfg.working_dir.mkdir()

        cfg_dir = raw_pav_cfg.working_dir/'pav_cfgs'
        if not cfg_dir.exists():
            cfg_dir.mkdir()

        cfg_path = Path(tempfile.mktemp(
            suffix='.yaml',
            dir=str(cfg_dir)))

        with cfg_path.open('w') as pav_cfg_file:
            config.PavilionConfigLoader().dump(pav_cfg_file,
                                               raw_pav_cfg)

        pav_cfg = config.find_pavilion_config(target=cfg_path, warn=False)
        pav_cfg.pav_vars = pavilion_variables.PavVars()

        return pav_cfg

    def __getattribute__(self, item):
        """Override the builtin __getattribute__ so that tests skipped via command line
        options are properly 'wrapped'."""
        attr = super().__getattribute__(item)

        cls = super().__getattribute__('__class__')
        cname = cls.__name__.lower()
        fname = Path(inspect.getfile(cls)).with_suffix('').name.lower()

        # Wrap our test functions in a function that dynamically wraps
        # them so they only execute under certain conditions.
        if (isinstance(attr, types.MethodType) and
                attr.__name__.startswith('test_')):

            name = attr.__name__[len('test_'):].lower()

            if self.SKIP:
                for skip_glob in self.SKIP:
                    skip_glob = skip_glob.lower()
                    if (fnmatch.fnmatch(name, skip_glob) or
                            fnmatch.fnmatch(cname, skip_glob) or
                            fnmatch.fnmatch(fname, skip_glob)):
                        return unittest.skip("via cmdline")(attr)
                return attr

            if self.ONLY:
                for only_glob in self.ONLY:
                    only_glob = only_glob.lower()
                    if (fnmatch.fnmatch(name, only_glob) or
                            fnmatch.fnmatch(cname, only_glob) or
                            fnmatch.fnmatch(fname, only_glob)):
                        return attr
                return unittest.skip("via cmdline")(attr)

        # If it isn't altered or explicitly returned above, just return the
        # attribute.
        return attr

    @classmethod
    def set_skip(cls, globs):
        """Skip tests whose names match the given globs."""

        cls.SKIP = globs

    @classmethod
    def set_only(cls, globs):
        """Only run tests whos names match the given globs."""
        cls.ONLY = globs

    def _is_softlink_dir(self, path):
        """Verify that a directory contains nothing but softlinks whose files
exist. Directories in a softlink dir should be real directories
though."""

        for base_dir, cdirs, cfiles in os.walk(str(path)):
            base_dir = Path(base_dir)
            for cdir in cdirs:
                self.assert_((base_dir/cdir).is_dir(),
                             "Directory in softlink dir is a softlink (it "
                             "shouldn't be).")

            for file in cfiles:
                file_path = base_dir/file
                self.assert_(file_path.is_symlink(),
                             "File in softlink dir '{}' is not a softlink."
                             .format(file_path))

                target_path = file_path.resolve()
                self.assert_(target_path.exists(),
                             "Softlink target '{}' for link '{}' does not "
                             "exist."
                             .format(target_path, file_path))

    def _cmp_files(self, a_path, b_path):
        """Compare the contents of two files.

        :param Path a_path:
        :param Path b_path:
        """

        with a_path.open('rb') as a_file, b_path.open('rb') as b_file:
            self.assertEqual(a_file.read(), b_file.read(),
                             "File contents mismatch for {} and {}."
                             .format(a_path, b_path))

    def _cmp_tree(self, path_a, path_b):
        """Compare two directory trees, including the contents of all the
        files."""

        a_walk = list(os.walk(str(path_a)))
        b_walk = list(os.walk(str(path_b)))

        # Make sure these are in the same order.
        a_walk.sort()
        b_walk.sort()

        while a_walk and b_walk:
            a_dir, a_dirs, a_files = a_walk.pop(0)
            b_dir, b_dirs, b_files = b_walk.pop(0)
            a_dir = Path(a_dir)
            b_dir = Path(b_dir)

            self.assertEqual(
                sorted(a_dirs), sorted(b_dirs),
                "Extracted archive subdir mismatch for '{}' {} != {}"
                .format(path_a, a_dirs, b_dirs))

            # Make sure these are in the same order.
            a_files.sort()
            b_files.sort()

            self.assertEqual(a_files, b_files,
                             "Extracted archive file list mismatch. "
                             "{} != {}".format(a_files, b_files))

            for file in a_files:
                # The file names have are been verified as the same.
                a_path = a_dir/file
                b_path = b_dir/file

                # We know the file exists in a, does it in b?
                self.assert_(b_path.exists(),
                             "File missing from archive b '{}'".format(b_path))

                self._cmp_files(a_path, b_path)

        self.assert_(not a_walk and not b_walk,
                     "Left over directory contents in a or b: {}, {}"
                     .format(a_walk, b_walk))

    @staticmethod
    def get_hash(filename):
        """ Get a sha1 hash of the file at the given path.

        :param Path filename:
        :return: The sha1 hexdigest of the file contents.
        :rtype: str
        """
        with filename.open('rb') as file:
            sha = sha1()
            sha.update(file.read())
            return sha.hexdigest()

    dbg_print = staticmethod(dbg_print)

    QUICK_TEST_BASE_CFG = {
        'cfg_label': 'test',
        'scheduler': 'raw',
        'suite': 'unittest',
        'build': {
            'verbose': 'false',
            'timeout': '30',
        },
        'run': {
            'cmds': [
                'echo "Hello World."'
            ],
            'verbose': 'false',
            'timeout': '300',
        },
        'result_parse': {},
        'result_evaluate': {},
        'schedule': {},
    }

    def _quick_test_cfg(self):
        """Return a pre-populated test config to use with
``self._quick_test``. This can be used as is, or modified for
desired effect.

The default config is: ::

{}
"""

        cfg = copy.deepcopy(self.QUICK_TEST_BASE_CFG)

        loc_sched = (self.TEST_DATA_ROOT/'pav_config_dir'/'modes' /
                     'local_sched.yaml')

        if loc_sched.exists():
            with loc_sched.open() as loc_slurm_file:
                sched_cfg = TestConfigLoader().load(loc_slurm_file,
                                                    partial=True)

            cfg['schedule'].update(sched_cfg['schedule'])

        return cfg

    def _load_test(self, name: str, host: str = 'this',
                   modes: List[str] = None,
                   build=True, finalize=True) -> List[TestRun]:
        """Load the named test config from file. Returns a list of the
        resulting configs."""

        if modes is None:
            modes = []

        res = TestConfigResolver(self.pav_cfg)
        test_cfgs = res.load([name], host, modes)

        tests = []
        for ptest in test_cfgs:
            test = TestRun(self.pav_cfg, ptest.config, var_man=ptest.var_man)
            test.save()

            if build:
                test.build()

            if finalize:
                fin_sys = base_classes.SysVarDict(unique=True)
                fin_var_man = VariableSetManager()
                fin_var_man.add_var_set('sys', fin_sys)
                scheduler = pavilion.schedulers.get_plugin(test.scheduler)
                fin_sched_vars = scheduler.get_final_vars(test)
                fin_var_man.add_var_set('sched', fin_sched_vars)
                test.finalize(fin_var_man)

            tests.append(test)

        return tests

    __config_lines = pprint.pformat(QUICK_TEST_BASE_CFG).split('\n')
    # Code analysis indicating format isn't found for 'bytes' is a Pycharm bug.
    _quick_test_cfg.__doc__ = _quick_test_cfg.__doc__.format(
        '\n'.join(['    ' + line for line in __config_lines]))
    del __config_lines

    def _quick_test(self, cfg=None, name="quick_test",
                    build=True, finalize=True):
        """Create a test run object to work with.
        The default is a simple hello world test with the raw scheduler.

        :param dict cfg: An optional config dict to create the test from.
        :param str name: The name of the test.
        :param bool build: Build this test, while we're at it.
        :param bool finalize: Finalize this test.
        :rtype: TestRun
        """

        if cfg is None:
            cfg = self._quick_test_cfg()

        cfg = copy.deepcopy(cfg)

        loader = TestConfigLoader()
        cfg = loader.validate(loader.normalize(cfg))

        cfg['name'] = name

        var_man = VariableSetManager()
        var_man.add_var_set('var', cfg['variables'])
        var_man.add_var_set('sys', base_classes.SysVarDict(unique=True, defer=True))
        var_man.add_var_set('pav', self.pav_cfg.pav_vars)

        sched = pavilion.schedulers.get_plugin(cfg.get('scheduler', 'raw'))
        sched_vars = sched.get_initial_vars(cfg.get('schedule', {}))
        var_man.add_var_set('sched', sched_vars)

        var_man.resolve_references()

        cfg = resolve.test_config(cfg, var_man)

        test = TestRun(pav_cfg=self.pav_cfg, config=cfg, var_man=var_man)
        if test.skipped:
            # You can't proceed further with a skipped test.
            return test

        test.save()

        if build:
            test.build()
        if finalize:
            fin_sys = base_classes.SysVarDict(unique=True)
            fin_var_man = VariableSetManager()
            fin_var_man.add_var_set('sys', fin_sys)
            fin_sched_vars = sched.get_final_vars(test)
            fin_var_man.add_var_set('sched', fin_sched_vars)
            test.finalize(fin_var_man)
        return test

    def wait_tests(self, working_dir: Path, timeout=5):
        """Wait on all the tests under the given path to complete.

        :param working_dir: The path to a working directory.
        :param timeout: How long to wait before giving up.
        """

        def is_complete(path: Path):
            """Return True if test is complete."""

            return (path/TestRun.COMPLETE_FN).exists()

        runs_dir = working_dir / 'test_runs'
        end_time = time.time() + timeout
        while time.time() < end_time:

            completed = [is_complete(test)
                         for test in dir_db.select(self.pav_cfg, runs_dir).paths]

            if not completed:
                self.fail("No tests started.")

            if all(completed):
                break
            else:
                time.sleep(0.1)
                continue
        else:
            raise TimeoutError(
                "Waiting on tests: {}"
                .format(test.name for test in dir_db.select(self.pav_cfg,
                                                            runs_dir).paths
                        if is_complete(test)))


class ColorResult(unittest.TextTestResult):
    """Provides colorized results for the python unittest library."""

    COLOR_BASE = '\x1b[{}m'
    COLOR_RESET = '\x1b[0m'
    BLACK = COLOR_BASE.format(30)
    RED = COLOR_BASE.format(31)
    GREEN = COLOR_BASE.format(32)
    YELLOW = COLOR_BASE.format(33)
    BLUE = COLOR_BASE.format(34)
    MAGENTA = COLOR_BASE.format(35)
    CYAN = COLOR_BASE.format(36)
    GREY = COLOR_BASE.format(2)
    BOLD = COLOR_BASE.format(1)

    def __init__(self, *args, **kwargs):
        self.stream = None
        self.showAll = None
        super().__init__(*args, **kwargs)

    def startTest(self, test):
        """Write out the test description (with shading)."""
        super().startTest(test)
        if self.showAll:
            self.stream.write(self.GREY)
            self.stream.write(self.getDescription(test))
            self.stream.write(self.COLOR_RESET)
            self.stream.write(" ... ")
            self.stream.flush()

    def addSuccess(self, test):
        """Write the success text in green."""
        self.stream.write(self.GREEN)
        super().addSuccess(test)
        self.stream.write(self.COLOR_RESET)

    def addFailure(self, test, err):
        """Write the Failures in magenta."""
        self.stream.write(self.MAGENTA)
        super().addFailure(test, err)
        self.stream.write(self.COLOR_RESET)

    def addError(self, test, err):
        """Write errors in red."""
        self.stream.write(self.RED)
        super().addError(test, err)
        self.stream.write(self.COLOR_RESET)

    def addSkip(self, test, reason):
        """Note skips in cyan."""
        self.stream.write(self.CYAN)
        super().addSkip(test, reason)
        self.stream.write(self.COLOR_RESET)


class BetterRunner(unittest.TextTestRunner):
    """A slightly better 'TextTestRunner' with nicer output."""

    # pylint: disable=invalid-name
    def run(self, test):
        "Run the given test case or test suite."
        result = self._makeResult()
        unittest.registerResult(result)
        result.failfast = self.failfast
        result.buffer = self.buffer
        result.tb_locals = self.tb_locals
        with warnings.catch_warnings():
            if self.warnings:
                # if self.warnings is set, use it to filter all the warnings
                warnings.simplefilter(self.warnings)
                # if the filter is 'default' or 'always', special-case the
                # warnings from the deprecated unittest methods to show them
                # no more than once per module, because they can be fairly
                # noisy.  The -Wd and -Wa flags can be used to bypass this
                # only when self.warnings is None.
                if self.warnings in ['default', 'always']:
                    warnings.filterwarnings('module',
                            category=DeprecationWarning,
                            message=r'Please use assert\w+ instead.')
            startTime = time.time()
            startTestRun = getattr(result, 'startTestRun', None)
            if startTestRun is not None:
                startTestRun()
            try:
                test(result)
            finally:
                stopTestRun = getattr(result, 'stopTestRun', None)
                if stopTestRun is not None:
                    stopTestRun()
            stopTime = time.time()
        timeTaken = stopTime - startTime
        result.printErrors()
        if hasattr(result, 'separator2'):
            self.stream.writeln(result.separator2)
        skipped = 0
        try:
            results = map(len, (result.expectedFailures,
                                result.unexpectedSuccesses,
                                result.skipped))
        except AttributeError:
            pass
        else:
            _, _, skipped = results

        run = result.testsRun - skipped

        self.stream.writeln("Ran %d test%s in %.3fs" %
                            (run, run != 1 and "s" or "", timeTaken))
        self.stream.writeln()
        failed, errored = len(result.failures), len(result.errors)
        passed = run - failed - errored
        run = 0.01 if run == 0 else run  # Deal with potential divide_by_zero errors
        self.stream.writeln(
            'Passed:  {:5d} -- {}%'
            .format(passed, round(float(passed)/run * 100)))
        self.stream.writeln(
            'Failed:  {:5d} -- {}%'
            .format(failed, round(float(failed)/run * 100)))
        self.stream.writeln(
            'Errors:  {:5d} -- {}%'
            .format(errored, round(float(errored)/run * 100)))
        self.stream.writeln(
            '\x1b[36mSkipped: {:5d} -- {}% (of run + skipped)\x1b[0m'
            .format(skipped, round(float(skipped)/(run+skipped) * 100)))

        self.stream.write('\n')
        infos = []
        if not result.wasSuccessful():
            self.stream.writeln("FAILED")
        else:
            self.stream.writeln("OK")

        return result
