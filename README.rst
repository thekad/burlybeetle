Overview
========

This is a framework to perform rolling restarts of distributed databases.

Most distributed databases that require a rolling restart follow some basic
principles:

* You grab a list of nodes to be restarted from some source of truth
* These nodes are sorted in some way, usually
* You may execute some pre-cluster-roll action
* For each of the nodes to be restarted:
  * You may execute some pre-stop action
  * You stop the service
  * You may execute some post-stop action
  * You may execute some custom script
  * You may execute some pre-start action
  * You start the service
  * You may execute some post-start action
* You may execute some post-cluster-roll action


Requirements
============

* SSH access to all the target servers where the service is running
* sudo access on said servers. This is kind of optional, depending how you're
  running your services, the default call uses ``sudo service``
* `Python <http://python.org>`
* `Python Fabric <http://fabfile.org>`


Install
=======

* Create a virtual environment (I recommend virtualenvwrapper but whatever
  fits your bill)
* ``pip install -r requirements.txt``


General Usage
=============

Each database has its own quirks and peculiarities however the general usage
of this tool is as follows::

    burlybeetle [options] [stop:"<call>"] [start:"<call>"] [commit] [paranoid] <service> [pre-tasks] restart [post-tasks]

Order is important since Fabric evaluates these tasks in the order they are
called, explanation follows:

* ``options`` are Fabric valid options since ``burlybeetle`` is just a thin
    wrapper around Fabric
* ``stop:"<call>"`` will override the default ``sudo service <foo> stop`` call
    to be executed in each of the nodes
* ``start"<call>"`` will override the default ``sudo service <foo> start`` call
    to be executed in each of the nodes
* ``commit`` is an optional task that turns on the commit bit for the restart
    to actually do stuff. If you don't set this then it will basically do a dry
    run. The default is to run in dry-run mode because that's the safest approach
* ``paranoid`` is an optional task that pauses the execution after each service
    has been restarted and waits for confirmation from the operator. This is
    turned off by default
* ``service`` is one of the supported databases in the section below. This task
    populates the hosts/roles lists (and sorts them if necessary) for Fabric to
    proceed during the restart
* ``pre-tasks`` are custom tasks per service that you may define to be executed
    prior to a cluster-wide rolling restart
* ``roll`` is the actual rolling-restart task, remember that if you didn't set
    the commit before before to this call it won't actually do anything. Also
    remember that if you didn't call the service population task the list of
    hosts will be empty
* ``post-tasks`` are custom tasks per service that you may define to be executed
    after a cluster-wide rolling restart


Supported databases
===================


Elasticsearch
-------------

The way this service populates its data is by polling a given elasticsearch
cluster API and pulling the list of nodes currently in the cluster. There are
a few restrictions though:

* All nodes in the cluster need to be named. Meaning that the ``node.name``
    attribute has a unique ID. If you are not naming your nodes this is probably
    because your environment is dynamic (maybe you're using ephemeral containers
    or whatnot) so a rolling restart is probably not how you'd do a cluster
    restart anyway
* The way you can SSH and stop/start services in the target hosts is homogeneous

Elasticsearch populates some roles (as understood by Fabric) to make it easy
to interact with it:

* ``clients`` are all the client nodes (``node.data: false`` and
  ``node.master: false``)
* ``masters`` are all the stand-by masters (``node.master: true`` and
  ``node.data: false`` and they are not the active master)
* ``data`` are all data nodes (``node.data: true`` and they are not the active
    master)
* ``active`` is the active master node
* ``almost`` are all nodes but the active master
* ``all`` are all nodes

By default this interacts with *all* nodes, if you don't want that you can
very easily use ``-R <list of roles>`` in the options


The elasticsearch rolling-restart strategy is as follows:

#. Restart all client nodes 
#. Restart all stand-by master nodes
#. For each data node:

  #. Disable shard relocation
  #. Restart
  #. Enable shard relocation

#. Restart the active master

