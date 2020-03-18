#!/usr/bin/env python

import time

from fabric.api import env
from fabric.api import task
from fabric.api import settings

from fabric import colors
from fabric import utils
from fabric.contrib import console

from turtletoss.http import curl_and_json


DEFAULT_INTERVAL = 5  # seconds
DEFAULT_TRIES = 360  # multiply by above is 1800: 30 minutes


# default name of the service
env.service_name = 'elasticsearch'

# set of nodes that have data
env.has_data = set()

# list of APIs to hit for querying
env.apis = []

# To be populated later
env.hosts = []
env.roledefs = {
    'all': [],
    'almost': [],
    'masters': [],
    'data': [],
    'clients': [],
    'active': [],
}


def pre_stop_callback(node):
    """If the node has data in it, disable unneeded shard relocation"""

    if node in env.has_data:
        if env.commit:
            switch_balancer(False)
        else:
            utils.puts('shard relocation (noop): False')


def post_stop_callback(node):
    """Wait until the node leaves the cluster"""

    if env.commit:
        wait_for_node(node, leave=True)
    else:
        utils.puts('wait for node {} (noop): to leave'.format(node))


def pre_start_callback(node):
    """If the node has data in it, wait until cluster health is yellow"""

    if node in env.has_data:
        if env.commit:
            wait_for_health('yellow')
        else:
            utils.puts('wait for health (noop): yellow')


def post_start_callback(node):
    """
    Wait until the node is back, if it had data, enable shard relocation
    and wait until health is green again
    """

    if env.commit:
        wait_for_node(node)
        if node in env.has_data:
            switch_balancer(True)
            wait_for_health('green')
    else:
        utils.puts('wait for node {} (noop): to come back'.format(node))
        if node in env.has_data:
            utils.puts('shard relocation (noop): True')
            utils.puts('wait for health (noop): green')


# Override callbacks
env.pre_stop_callback = pre_stop_callback
env.post_stop_callback = post_stop_callback
env.pre_start_callback = pre_start_callback
env.post_start_callback = post_start_callback


@task(default=True)
def do(url='http://localhost:9200', fallback_url=None):
    """
    Populates the node list based on elasticsearch API information

    This will connect to a given API endpoint and possibly fill out three
    role definitions:

        * ``clients``: All elasticsearch nodes where ``master`` is false
          and ``data`` is false
        * ``data``: All elasticsearch nodes where ``data`` is true
        * ``masters``: all elasticsearch nodes where ``master`` is true
          and ``data`` is false

    Arguments:

        * ``url``: The HTTP(S) endpoint to connect to
        * ``fallback_url``: Optional. The HTTP(S) endpoint to connect to when
            the process inevitably can't connect to the first endpoint. It is
            optional because you may very well exclude the node hosting the
            endpoint from the restart
    """
    data = None
    env.apis = [url]
    if fallback_url:
        env.apis.append(fallback_url)
    try:
        data = curl_and_json(env.apis, '/_nodes/_all/settings')
    except Exception as e:
        utils.error('Could not get data', exception=e)
    if data is None:
        raise ValueError('Could not fetch the data from provided endpoint(s)')
    client_nodes = []
    data_nodes = []
    master_nodes = []
    for node_id, conf in data['nodes'].iteritems():
        host = conf['host']
        # does this node have data?
        # funny story the attributes are not actually booleans W-T-F
        if conf['settings']['node']['data'] == 'true':
            env.has_data.add(host)
            # one of these could be the active master
            if host in get_active_master():
                pass
            else:
                data_nodes.append(host)
        else:
            # is this node a master?
            if conf['settings']['node']['master'] == 'true':
                if host in get_active_master():
                    pass
                else:
                    master_nodes.append(host)
            else:
                client_nodes.append(host)

    # I like order over chaos
    client_nodes.sort()
    data_nodes.sort()
    master_nodes.sort()

    # Populate the role definitions
    env.roledefs['clients'] = client_nodes
    env.roledefs['data'] = data_nodes
    env.roledefs['masters'] = master_nodes

    env.hosts = []
    # Only populate the list of hosts with those roles you passed (if any)
    # The order matters, this is the order in which the restarts will happen
    if 'clients' in env.effective_roles:
        env.hosts.extend(client_nodes)
    if 'masters' in env.effective_roles:
        env.hosts.extend(master_nodes)
    if 'data' in env.effective_roles:
        env.hosts.extend(data_nodes)
    if 'active' in env.effective_roles:
        env.hosts.extend(get_active_master())

    almost = client_nodes + master_nodes + data_nodes

    # Two special role definitions for convenience
    if 'almost' in env.effective_roles:
        env.hosts = almost
    if 'all' in env.effective_roles:
        env.hosts = almost + get_active_master()

    # By default, do them all!
    if len(env.effective_roles) == 0:
        env.hosts = almost + get_active_master()

    # Figure out if we're at some point going to lose access to the API
    data = curl_and_json(env.apis, '/_nodes/_local/settings')
    for node_id, conf in data['nodes'].iteritems():
        me = conf['host']

    if me in env.hosts and me not in env.exclude_hosts and len(env.apis) < 2:
        with settings(warn_only=True):
            utils.error(
                'The host you are connecting to {} is part of the list of '
                'nodes to be restarted, and you only have 1 API to connect '
                'to. This means at some point you will lose connection to the '
                'API and will not have a fallback to poll. This is probably '
                'A Bad Idea (TM). You should probably add an excludes via -x '
                'or add a fallback API URL.'.format(me)
            )
        if env.commit:
            if not console.confirm(
                'Do you want to continue anyway?',
                default=False
            ):
                raise(SystemExit('Aborted'))
        else:
            time.sleep(DEFAULT_INTERVAL)


def wait_for_node(node, leave=False):
    """
    Waits for a node to leave or join the cluster

    Continually poll the elasticsearch cluster status API for the node
    """

    tries = DEFAULT_TRIES
    while tries > 0:
        utils.puts(
            'Waiting for node {} to {}'.format(
                node, 'leave' if leave else 'come back',
            )
        )
        data = curl_and_json(env.apis, '/_nodes/_all/info')
        for node_id, node_conf in data['nodes'].items():
            if 'host' in node_conf:
                if not leave and node_conf['host'] == node:
                    return
        else:
            if leave:
                return
            else:
                tries -= 1
                time.sleep(DEFAULT_INTERVAL)
    console.confirm(
        'Node {} never {}! Press Enter to continue, '
        'CTRL+C to abort (check output of {}/_nodes/_all/info?pretty)'.
        format(
            node,
            'left' if leave else 'came back',
            env.apis[0],
        )
    )


def get_cluster_health():
    """
    Returns the current cluster health

    In elasticsearch a cluster can be either green, yellow, or red
    """

    data = curl_and_json(env.apis, '/_cluster/health')
    return data['status']


def wait_for_health(status):
    """
    Waits for the cluster's health to match what we want

    Continually poll the elasticsearch cluster health API for health
    to match what we want
    """

    # wait (limit * sleep) seconds
    tries = DEFAULT_TRIES
    while tries > 0:
        st = get_cluster_health()
        utils.puts(
            'Waiting for cluster health to be {}, currently {}'.format(
                getattr(colors, status)(status),
                getattr(colors, st)(st),
            )
        )
        if st == status:
            return
        else:
            tries -= 1
            time.sleep(DEFAULT_INTERVAL)
    console.confirm(
        'Cluster status never got {}! Press Enter to continue, '
        'CTRL+C to abort (check output of {}/_cluster/health?pretty)'.
        format(status, env.apis[0])
    )


def switch_balancer(toggle):
    kw = 'all' if toggle else 'none'
    data = {
        'transient': {
            'cluster.routing.allocation.enable': kw
        }
    }
    utils.puts('Setting balancer to {}'.format(kw))
    if env.commit:
        curl_and_json(
            env.apis, '/_cluster/settings', method='PUT', data=data
        )


def get_node_host(node_id):
    """Get the hostname based on a node ID"""

    data = curl_and_json(env.apis, '/_nodes/{}/info'.format(node_id))
    return data['nodes'][node_id]['host']


def get_active_master():
    """
    Loads the active master node into an env attribute and returns the value.
    The value is loaded as a list because that's how role definitions are done
    """

    if env.roledefs['active']:
        return env.roledefs['active']
    data = curl_and_json(env.apis, '/_cluster/state/master_node')
    node_id = data['master_node']

    active_master = get_node_host(node_id)
    utils.puts('Active master node: {}'.format(active_master))
    env.roledefs['active'] = [active_master]
    return env.roledefs['active']
