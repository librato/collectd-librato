import collectd
import errno
import json
import urllib2
import time
import os
import sys
import base64
from string import maketrans

version = "0.0.1"

#config = { 'url' : 'https://metrics-api.librato.com/v1/metrics.json' }
plugin_name = 'collectd-librato.py'
config = { 'url' : 'http://localhost:9292/v1/metrics.json',
           'types_db' : '/usr/share/collectd/types.db',
           'metric_prefix' : 'collectd',
           'metric_separator' : '.',
           'flush_interval_secs' : 10,
           'flush_max_measurements' : 600,
           'flush_timeout_secs' : 15
           }
types = {}

def build_user_agent():
    try:
        uname = os.uname()
        system = "; ".join([uname[0], uname[4]])
    except:
        system = os.name()

    pver = sys.version_info
    user_agent = 'Collectd-Librato.py/%s (%s) Python-Urllib2/%d.%d' % \
                 (version, system, pver.major, pver.minor)
    return user_agent

def build_http_auth():
    base64string = base64.encodestring('%s:%s' % \
                                       (config['email'],
                                        config['api_token']))[:-1]
    return base64string

def get_time():
    """
    Return the current time as epoch seconds.
    """

    return int(time.mktime(time.localtime()))

def sanitize_field(field):
    """
    Santize Metric Fields: delete paranthesis and split on periods
    """
    field = field.strip()

    # convert spaces to underscores
    trans = maketrans(' ', '_')

    # Strip ()
    field = field.translate(trans, '()')

    # Split based on periods
    return field.split(".")

#
# Parse the types.db(5) file to determine metric types.
#
def librato_parse_types_file(path):
    global types

    f = open(path, 'r')

    for line in f:
        fields = line.split()
        if len(fields) < 2:
            continue

        type_name = fields[0]

        if type_name[0] == '#':
            continue

        v = []
        for ds in fields[1:]:
            ds = ds.rstrip(',')
            ds_fields = ds.split(':')

            if len(ds_fields) != 4:
                collectd.warning('%s: cannot parse data source ' \
                                 '%s on type %s' %
                                 (plugin_name, ds, type_name))
                continue

            v.append(ds_fields)

        types[type_name] = v

    f.close()

def librato_config(c):
    global config

    for child in c.children:
        if child.key == 'APIToken':
            config['api_token'] = child.values[0]
        elif child.key == 'Email':
            config['email'] = child.values[0]
        elif child.key == 'MetricPrefix':
            config['metric_prefix'] = child.values[0]
        elif child.key == 'TypesDB':
            collectd.warning("typesdb = %s" % child.values[0])

    if not config.has_key('api_token'):
        raise Exception('APIToken not defined')

    if not config.has_key('email'):
        raise Exception('Email not defined')

    config['user_agent'] = build_user_agent()
    config['auth_header'] = build_http_auth()

def librato_flush_metrics(gauges, counters, data):
    """
    POST a collection of gauges and counters to Librato Metrics.
    """

    headers = {
        'Content-Type': 'application/json',
        'User-Agent': config['user_agent'],
        'Authorization': 'Basic %s' % config['auth_header']
        }

    body = json.dumps({ 'gauges' : gauges, 'counters' : counters })

    req = urllib2.Request(config['url'], body, headers)
    try:
        f = urllib2.urlopen(req, timeout = config['flush_timeout_secs'])
        response = f.read()
        f.close()
    except urllib2.HTTPError as error:
        collectd.warning('%s: Failed to send metrics to Librato (code %d)' % \
                         (plugin_name, error.code))
    except urllib2.IOError as error:
        collectd.warning('%s: IO Error when sending metrics Librato (%s)' % \
                         (plugin_name, error.reason))


def librato_queue_measurements(gauges, counters, data):
    # Updating shared data structures
    #
    data['lock'].acquire()

    data['gauges'].extend(gauges)
    data['counters'].extend(counters)

    curr_time = get_time()
    last_flush = curr_time - data['last_flush_time']
    length = len(data['gauges']) + len(data['counters'])

    if last_flush < config['flush_interval_secs'] and \
           length < config['flush_max_measurements']:
        data['lock'].release()
        return

    collectd.warning("flushing, last_flush: %d" % (last_flush))

    flush_gauges = data['gauges']
    flush_counters = data['counters']
    data['gauges'] = []
    data['counters'] = []
    data['last_flush_time'] = curr_time
    data['lock'].release()

    librato_flush_metrics(flush_gauges, flush_counters, data)

def librato_write(v, data=None):
    global plugin_name, types

    if v.type not in types:
        collectd.warning('%s: do not know how to handle type %s. ' \
                         'do you have all your types.db files configured?' % \
                         (plugin_name, v.type))
        return

    v_type = types[v.type]

    if len(v_type) != len(v.values):
        collectd.warning('%s: differing number of values for type %s' % \
                         (plugin_name, v.type))
        return

    name = []

    if len(config['metric_prefix']) > 0:
        name.append(config['metric_prefix'])

    name.append(v.plugin)
    if v.plugin_instance:
        name.extend(sanitize_field(v.plugin_instance))

    name.append(v.type)
    if v.type_instance:
        name.extend(sanitize_field(v.type_instance))

    gauges = []
    counters = []

    i = 0
    for value in v.values:
        ds_name = v_type[i][0]
        ds_type = v_type[i][1]

        if ds_type != 'GAUGE' and ds_type != 'COUNTER':
            continue

        # Can value be None?
        if value is None:
            continue

        measurement = {
            'name' : config['metric_separator'].join(name + [ds_name]),
            'source' : v.host,
            'measure_time' : int(v.time),
            'value' : value
            }

        if ds_type == 'GAUGE':
            gauges.append(measurement)
        else:
            counters.append(measurement)

    librato_queue_measurements(gauges, counters, data)

def librato_init():
    import threading

    librato_parse_types_file(config['types_db'])

    d = {
        'lock' : threading.Lock(),
        'last_flush_time' : get_time(),
        'gauges' : [],
        'counters' : []
        }

    collectd.register_write(librato_write, data = d)

collectd.register_config(librato_config)
collectd.register_init(librato_init)
