#!/usr/bin/env python

from fabric.utils import error
from fabric.utils import puts
try:
    import simplejson as json
except ImportError:
    import json
import time
import urllib2


DEFAULT_INTERVAL = 5  # seconds
DEFAULT_HTTP_TRIES = 60  # multiply by interval is 300: 5 minutes


class MethodRequest(urllib2.Request):
    def __init__(self, *args, **kwargs):
        if 'method' in kwargs:
            self._method = kwargs['method']
            del kwargs['method']
        else:
            self._method = None
        return urllib2.Request.__init__(self, *args, **kwargs)

    def get_method(self, *args, **kwargs):
        if self._method is not None:
            return self._method
        return urllib2.Request.get_method(self, *args, **kwargs)


def curl(apis=[], endpoint='/', *args, **kwargs):
    """
    Makes a curl request using the given method against a list of possible
    URLs. It will return the first successful request
    """
    r = None
    for api in apis:
        url = api + endpoint
        request = MethodRequest(url, *args, **kwargs)
        try:
            puts('Trying {}'.format(url), show_prefix=True)
            response = urllib2.urlopen(request)
            r = response.read()
            return r
        except:
            pass
    if not r:
        raise(Exception('Could not read URL(s) {}'.format(','.format(apis))))


def curl_and_json(apis, endpoint, **kwargs):
    """Convenience call for curl + json parse"""

    if 'data' in kwargs:
        kwargs['data'] = json.dumps(kwargs['data'])
    tries = DEFAULT_HTTP_TRIES
    resp = None
    while tries > 0:
        try:
            resp = curl(apis, endpoint, **kwargs)
            break
        except Exception as e:
            tries -= 1
            time.sleep(DEFAULT_INTERVAL)
    if tries == 0:
        msg = 'Could not connect to {} after {} tries, giving up'.format(
            ','.join(apis), DEFAULT_HTTP_TRIES
        )
        error(msg)
        raise(Exception(msg))

    try:
        data = json.loads(resp)
    except Exception as e:
        error('Invalid JSON: {}'.format(data), exception=e)
        raise

    return data
