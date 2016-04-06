#!/usr/bin/env python

from __future__ import absolute_import

import os
import datetime
import tempfile
import time

from fabric import utils
from fabric.api import env
from fabric.api import put
from fabric.api import run
from fabric.api import runs_once
from fabric.api import task
from fabric.contrib import console


# Default calls to stop/start the service
env.stop_call = 'sudo service {} stop'
env.start_call = 'sudo service {} start'
env.script_file = None

# Default callbacks before/after stopping/starting the cluster/service
env.pre_stop_callback = lambda f: True
env.pre_start_callback = lambda f: True
env.post_stop_callback = lambda f: True
env.post_start_callback = lambda f: True

# We don't like autocommit
env.commit = False

# But we aren't paranoid by default
env.paranoid = False

# Initialize this run's timestamp
env.timestamp = '{}'.format(time.mktime(datetime.datetime.now().timetuple()))


def do_stop():
    """
    This actually calls the given stop call for the service, provided the
    commit bit is on. Otherwise it will only print what is supposed to happen
    """

    utils.puts('pre-stop callback: {}'.format(env.pre_stop_callback))
    env.pre_stop_callback(env.host_string)
    if env.commit:
        # Not using sudo() because it is entirely possible
        # you are not running things as root
        run(env.stop_call.format(env.service_name))
    else:
        utils.puts(
            'stop (noop): {}'.format(env.stop_call).format(env.service_name)
        )

    utils.puts('post-stop callback: {}'.format(env.post_stop_callback))
    env.post_stop_callback(env.host_string)


def do_start():
    utils.puts('pre-start callback: {}'.format(env.pre_start_callback))
    env.pre_start_callback(env.host_string)
    if env.commit:
        run(env.start_call.format(env.service_name))
    else:
        utils.puts(
            'start (noop): {}'.format(env.start_call).format(env.service_name)
        )
    utils.puts('post-start callback: {}'.format(env.post_start_callback))
    env.post_start_callback(env.host_string)


@runs_once
@task
def stop(stop_call):
    """
    Change the call to stop the service. This does *not* stop the service
    """

    env.stop_call = stop_call


@runs_once
@task
def start(start_call):
    """
    Change the call to start the service. This does *not* start the service
    """

    env.start_call = start_call


@runs_once
@task
def paranoid():
    """
    Ask for confirmation between each restart
    """

    env.paranoid = True


@runs_once
@task(alias='do')
def commit():
    """
    Execute the commands instead of performing a dry-run
    """

    env.commit = console.confirm(
        'Are you sure you want to commit changes?',
        False
    )
    if not env.commit:
        utils.puts('Proceeding in dry-run mode')


@task
def script(path):
    """
    Copy and run the given script *while the service is down*

    Useful for when you need to make adjustments to the service between stop
    and start. This script gets copied to all the target nodes, turned on the
    execution bit, then called without any parameters.

    Arguments:

    * ``path``: Path to the local file to be uploaded. This file has to exist
      and will be uploaded to a temporary location (which will be cleaned up
      upon exit)

    """

    fp = os.path.abspath(os.path.expanduser(path))
    if not os.path.isfile(fp):
        raise IOError('Local script {} is not a file'.format(fp))

    remote_dir = os.path.join(
        tempfile.gettempdir(), 'burlybeetle',
        env.service_name, env.timestamp,
    )
    env.script_file = os.path.join(remote_dir, os.path.basename(fp))
    if env.commit:
        run('mkdir -pv {}'.format(remote_dir))
        put(fp, env.script_file)
        run('chmod -v +x {}'.format(env.script_file))
    else:
        utils.puts('put (noop): {} -> {}'.format(fp, env.script_file))


def do_run_script():
    if env.commit:
        run(env.script_file)
    else:
        utils.puts('run (noop): {}'.format(env.script_file))


@task
def roll():
    """
    Restart the list of nodes in the order they got acquired

    This task will:

    #. Stop the service
    #. Execute some call back function
    #. If there was a "maintenance" script to be used, run it
    #. Start the service
    #. Execute some call back function

    """
    proceed = True
    if env.commit and env.paranoid:
        proceed = console.confirm(
            'Restarting {}, press "y" to proceed, "n" to skip'.format(
                env.host_string
            ), False
        )
    if proceed:
        do_stop()
        if env.script_file:
            do_run_script()
        do_start()
