.. _basics:

Getting Started
===============

This document is meant to give you a quick overview of Pavilion features, and some setup
instructions. For a more in-depth tutorial, see :ref:`tutorials.basic`.

.. contents:: Table of Contents

IMPORTANT
~~~~~~~~~

If you're using Pavilion on a cluster (which is the point) make sure to install the source,
configs, and working directory (see below) on a filesystem accessible from all nodes. An NFS
file system is preferred. See :ref:`install` for full requirements (it will probably just work
though).

Setup
~~~~~

See the :ref:`install` if you need to install Pavilion*

Add the PAV bin directory to your Path.

.. code:: bash

    PATH=<PVINSTALL_PATH>/bin:${PATH}

Pavilion figures out paths to everything else on its own.

Then simply run pavilion:

.. code:: bash

    pav --help

.. _basics.create_config:

Create a Config Directory
~~~~~~~~~~~~~~~~~~~~~~~~~

Pavilion needs a config directory where it can find tests and other configuration files. To create
one, use the ``pav config`` command.

.. code::

    # Create a new config directory
    pav config setup <path to my configs> <path to working_dir>

    # Point Pavilion to this configuration directory.
    export PAV_CONFIG_DIR=<path to my configs>

    export PATH=$PATH:<pav source dir>/bin

This will:

- Create the config directory and all used subdirectories. (See :ref:`config` for more on that
  structure).
- Create a pavilion.yaml, for general pavilion configuration (see :ref:`config`)
- Create a working directory, where Pavilion will store run tests, builds, etc.

Multiple Config Directories
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Pavilion supports having multiple configuration directories. You can use this to package a set of
tests as a unit, or use it to handle access restrictions by setting group permissions on each.

The Pavilion `pav config` command can manage these for you, with it's ``add``, ``delete``, and
``list`` sub-commands. See ``pav config --help`` for more. You can also manage them manually via
the ``pavilion.yaml`` config file.

Configure Tests
~~~~~~~~~~~~~~~

Pavilion doesn't come with any tests itself (though it does come with
example tests in ``examples/``); it's just a system for
running them on HPC clusters. Each test needs a configuration script,
and most will need some source files. Both of these will live in one of
your :ref:`config.config_dirs` under the ``tests/`` and ``test_src/``
sub-directories.

Test configs tell pavilion what environment it needs to build and run
your test, the commands to run it, how to schedule it on a cluster, and
how to parse the results. Don't worry if it seems like a lot, tests can
be as simple as a single command, just about everything in the config is
optional.

.. code:: yaml

    # Tests are in a strictly defined YAML format.

    # This defines a test, and names it.
    mytest:

      # The scheduler to use to schedule the test on a cluster.
      # In this case, we'll use the raw (local system) scheduler
      scheduler: raw
      run:
        cmds: 'test -d /var/log/messages'

The above test checks to see if the ``/var/log/messages`` directory
exits.

- The test is named 'mytest'. The name of the yaml file determines the
  test's *suite*.
- The test will PASS if that command returns 0.
- It will run as a process on the local machine, as your user (because the 'raw' scheduler was
  chosen.
- Pavilion doesn't have any special privileges. It's meant to test
  from a normal user's perspective. If you want to test stuff as root, you'll
  have to run pavilion as root.

Host Configs
^^^^^^^^^^^^

Every system (host) that you run tests on can have a host configuration
file. These are located in ``hosts/<sys_name>.yaml`` in a pavilion
config directory. (To find the ``sys_name`` of your current system, run ``pav show sys_vars``.)

This config is used to override the Pavilion defaults for values in
every test config run on that system. You can use these to set default
values for things like the max nodes per job in a given scheduler,
or setting useful :ref:`tests.variables` for that system. The
format is the same as a test config file, except with only one test and
without the name for that test.

.. code:: bash

    $ cat hosts/my_host.yaml

    scheduler: slurm
    variables:
        foo: "bar"

The above host config would set the default scheduler to 'slurm' for
tests kicked off on a host with a ``sys_name`` of ``my_host``, and also add a
"foo" pavilion variable for all tests run on that system. Pavilion uses
the contents of the ``sys_name`` test config variable to determine the
current host, which is provided via a built-in
:ref:`plugins.sys_vars`. This behaviour can be overridden by
providing your own sys\_var plugin, typically to use more colloquial names for
systems.

Running tests
~~~~~~~~~~~~~

Running tests is easy. All you need is the test suite name (the name of
the test file, minus the ``.yaml`` extension), and the test name (the name of the test in the
suite). Did you forget what you named them? That's ok! Just ask Pavilion.

.. code:: bash

    $ pav show tests
    -----------------------+----------------------------------------------------
     Name                  | Summary
    -----------------------+----------------------------------------------------
     hello_mpi.hello_mpi   | Builds and runs an MPI-based Hello, World program.
     hello_mpi.hello_worse | Builds and runs MPI-based Hello, World, but badly.
     supermagic.supermagic | Run all supermagic tests.

    $ pav run supermagic.supermagic
    1 tests started as test series s33.

If you want to run every test in the suite, you can just give the suite
name. You can also run whatever combinations of tests you want. You also
list tests in a file and have Pavilion read that.

.. code:: bash

    $ pav run hello_mpi
    2 tests started as test series s34.

    $ pav run hello_mpi.hello_mpi supermagic
    2 tests started as test series s35.

    $ pav run -f mytests
    347 tests started as test series s36.

Test Status
^^^^^^^^^^^

If you want to know what's going on with your tests, just use the
``pav  status`` command.

.. code:: bash


    $ pav status
    ------+------------+----------+------------------+------------------------------
     Test | Name       | State    | Time             | Note
    ------+------------+----------+------------------+------------------------------
     41   | supermagic | COMPLETE | 16 May 2019 10:38| Test completed successfully.

It will display the status of all the tests in the last test series you
ran.

Test Series and ID's
~~~~~~~~~~~~~~~~~~~~

From the above, you may have noticed that each test gets a series id
like ``s24`` and a test id like ``41``. You can use these id's to
reference tests or suites of tests to get their status, results, and
logs through the pavilion interface. The ID's are unique for a given
Pavilion :ref:`config.working_dir` but they will
get reused as old tests are cleaned up.

Test Results
~~~~~~~~~~~~

Pavilion builds a mapping of result keys and values for every test that
runs. You can view the results of any tests using the ``pav results``
command.

.. code:: bash

    $ pav results
    Test Results
    ------------+----+--------
    Name        | Id | Result
    ------------+----+--------
    supermagic  | 41 | PASS

    # Use '--full' or '-f' to get the full result json with all fields.
    $ pav results --full Test Results
    {
        "name": "supermagic",
        "id": 41,
        "result": "PASS",
        "duration": 3.825,
        "created": 2019-05-15 10:38,
        "started": 2019-05-15 10:41,
        "finished": 2019-05-15 10:42,
    }

Every test has a results object that contains a variety of useful,
automatically populated keys. Additional keys can be defined through
:ref:`result parsing and result evaluations <results.basics>`.

Results are saved alongside each test, as well being written to a
central result log that is suitable for import into Splunk or other
tools.

The Overall Result
^^^^^^^^^^^^^^^^^^

By default, a test passes if its last command returns ``0``, but this can be
easily overridden.

.. code-block:: yaml

    mytest:
        run:
            cmds:
                # We'll use the result parsers below to parse values from
                # the output of the run script.
                - './test_script.sh'

        result_parse:
            regex:
                # Use the regex parser to extract a speed key and add it to
                # the results.
                speed:
                    regex: '^speed (\d+)'

        result_evaluate:
            # The test will PASS if the speed (extracted above) is more than 50.
            result: 'speed > 50'