
.. _installing-pavilion:
.. _install:

Installing Pavilion
===================

Installing Pavilion is mostly a matter of placing it's source somewhere,
providing its (few) dependencies, and creating a pavilion.yaml config
file.

.. contents::

Requirements
------------

Pavilion has very few dependencies and requirements:

- Python 3.6 or newer
- A writeable space on a filesystem shared across all hosts (to be tested) in
  each cluster. (Assuming you're scheduling jobs across a cluster).

  - The path to this directory must be consistent across all cluster hosts.
  - It must support atomic file creation and appends of < 4kb.

- Lmod or 'environment modules' is recommended.


Filesystems
~~~~~~~~~~~

Pavilion works by recursively running itself in different modes at
different points in the testing process. This means certain paths, like
the Pavilion **source directory**, **working directory**, and used
**config directories** must have paths that are consistent across the
nodes and front-ends of any given system.

Pavilion places all builds, test working spaces, and lockfiles in a
**working directory** specified in the pavilion configuration (defaults
to ``~/.pavilion/``).

- Atomic (O\_EXCL) file creation is needed here for the creation of lock files.
- Atomic small appends are needed for writing to the status file. Not having
  this has a small chance of resulting in corrupted test status files.
- Both of these requirements are probably already satisfied by one or more of
  your cluster NFS partitions. Lustre filesystems are not recommended, mostly
  due to the type of load Pavilion presents to these.

Testing Filesystems
~~~~~~~~~~~~~~~~~~~

If you're unsure if your shared filesystem is reliable, there's a test for
that in `test/utils`.

.. code-block:: bash

    $ python3 lock_test.py --help

Result Log
~~~~~~~~~~

The result log can be configured to write to an arbitrary filesystem.
That filesystem should be shared and have consistent paths as well, as
the log is written as the final on-node step in tests.

Recommended Directory Structure
-------------------------------

We recommend the following directory structure for Pavilion.

- ``<root>/pavilion/src`` - Clone/install pavilion here.
- ``<root>/pavilion/config`` - Your pavilion configuration files. See
  :ref:`config`.
- ``<root>/pavilion/working_dir`` - Where test runs and builds will be written.

The ``<root>/pavilion/config`` directory will contain all of your site
specific tests, plugins, and test source files. If you organize your tests in
separate repositories, you may check them out here, and simply link the
appropriate files into ``config/tests`` and ``config/test_src``.
Alternatively, you can make the entire config directory, source tarballs and
all, its own repository.

Install
-------

Pavilion installs are meant to be dropped into place as a complete
directory that contains the source and any
`dependencies <#dependencies>`__ missing on your system. This generally
starts with a git pull of the latest release of Pavilion.

.. code:: bash

    git clone https://github.com/hpc/pavilion2.git
    cd pavilion2
    # You can also, optionally, check out a specific release version.
    git checkout tags/v2.4

You can also simply download and extract the source.

.. _RELEASE.txt: _static/RELEASE.txt

Releases
~~~~~~~~

You should probably pick the latest Pavilion *release* when installing
Pavilion for a couple reasons.

 1) While we try to maintain backwards compatibility as much as possible,
    the reality is that every release contains several major compatibility
    breaks both for test configurations and plugins. These are documented
    per-release in the `RELEASE.txt`_ file.
 2) We run a large bevy of unit tests against every change in Pavilion, but
    each release is used in production before it is actually tagged. This
    often reveals bugs, regressions, and practical usage issues. We fix those
    issues, then tag the release. Bugfix releases are provided as needed.

Dependencies
------------

Pavilion has a few dependencies, and most aren't required. Pavilion was
designed and tested against fairly recent (as of 2022-01) versions of
these, but it's likely that older, system provided versions may work
just as well. Conversely, the latest version should be fine as well. The
supported and tests versions for each are recorded in ``requirements.txt``.

-  `yaml\_config <https://github.com/lanl/yaml_config>`__ **(required)**
   - Used to define the test and pavilion configurations.
-  `yapsy <http://yapsy.sourceforge.net/>`__ **(required)** - The basis
   for Pavilion's plugin architecture.
-  `lark <https://github.com/lark-parser/lark>`__ **(required)** - Used for
   Pavilion string value and expression parsing.
-  `matplotlib <https://matplotlib.org/>`__ - Needed for the graph command.
-  `requests <https://pypi.org/project/requests/2.7.0/>`__ - Used for
   automatic downloads of test source files. This feature is disabled in
   the absence of this library, and tests that use it will fail with an
   error. The remaining dependencies are needed by requests. The following are sub-dependencies of
   requests.

  -  `chardet <https://pypi.org/project/chardet/>`__
  -  `idna <https://github.com/kjd/idna>`__
  -  `python-certifi <https://pypi.org/project/certifi/>`__
  -  `urllib3 <https://urllib3.readthedocs.io/en/latest/>`__

Installing Dependencies
~~~~~~~~~~~~~~~~~~~~~~~

To install the pavilion dependencies simply run the included:

.. code:: bash

    bin/setup_pav_deps

If you downloaded Pavilion as a git repository, this will simply run ``submodule update --init``
on that repository, which will fetch the dependencies (not including matplotlib).

If you downloaded Pavilion as zip/tarball, The command will tell you to rerun it with
a path to where it should create (or reuse) a virtual environment. The script will then install
most needed dependencies via pip. A few non-pip dependencies will be downloaded and installed
in the pavilion directory directly.

Environment Modules
-------------------

Pavilion uses the ``module`` command to load modules for tests. It will work
with either lmod or the tcl based 'environment modules' systems. This is
generally only needed if your cluster/s have a complex software environment
that supports multiple compilers and conflicting builds of libraries.

It is assumed that the module environment is set up before you run Pavilion. If
you need to set up this environment separately on allocations, use the
'env_setup' option in the :ref:`config` to add the commands
to do so.







