import csv
import json
import os

from collections import OrderedDict
from datetime import datetime, timedelta

import grequests
import requests

from flask import Flask, render_template, request
from gevent.pywsgi import WSGIServer
from werkzeug.contrib.cache import MemcachedCache

# Flag to flip once transactions are on S3.
TRANSACTIONS = False


app = Flask(__name__)

servers = {
    'dev': 'https://marketplace-dev.allizom.org',
    'stage': 'https://marketplace.allizom.org',
    'prod': 'https://marketplace.firefox.com'
}

api = {
    'tiers': '/api/v1/webpay/prices'
}

regions = {
    1: 'Worldwide', 2: 'US', 4: 'UK', 7: 'Brazil', 8: 'Spain', 9: 'Colombia',
    10: 'Venezuela', 11: 'Poland', 12: 'Mexico', 13: 'Hungary', 14: 'Germany'
}

methods = {
    0: 'operator',
    1: 'card',
    2: 'both'
}

regions_sorted = sorted(regions.keys())

builds = {
    'jenkins': ['solitude', 'marketplace', 'marketplace-api',
                'marketplace-webpay', 'amo-master', 'solitude'],
    'travis': ['andymckay/receipts', 'mozilla/fireplace',
               'andymckay/django-paranoia', 'andymckay/curling',
               'andymckay/django-statsd']
}

@app.route('/')
def base(name=None):
    return render_template('index.html', name=name)


def get_jenkins(keys, results):
    reqs = []
    for key in keys:
        url = ('https://ci.mozilla.org/job/{0}/lastCompletedBuild/api/json'
               .format(key))
        reqs.append(grequests.get(url, headers={'Accept': 'application/json'}))

    resps = grequests.map(reqs)
    for key, resp in zip(keys, resps):
        results['results'][key] = resp.json()['result'] == 'SUCCESS'

    return results

def get_travis(keys, results):
    reqs = []
    for key in keys:
        url = ('https://api.travis-ci.org/repositories/{0}.json'
               .format(key))
        reqs.append(grequests.get(url, headers={'Accept': 'application/json'}))

    resps = grequests.map(reqs)
    for key, resp in zip(keys, resps):
        results['results'][key] = resp.json()['last_build_result'] == 0

    return results


@app.route('/build/')
def build():
    cache = MemcachedCache([os.getenv('MEMCACHE_URL', 'localhost:11211')])
    result = cache.get('build')
    if not result:
        result = {'when': datetime.now(), 'results': {}}
        get_jenkins(builds['jenkins'], result)
        get_travis(builds['travis'], result)
        cache.set('build', result, timeout=60 * 5)

    result['results'] = OrderedDict(sorted(result['results'].items()))
    if 'application/json' in request.headers['Accept']:
        result['when'] = result['when'].isoformat()
        return json.dumps({'all': all(result['results'].values()),
                           'result': result})

    return render_template('build.html', result=result, request=request,
                           all=all(result['results'].values()))


def fill_tiers(result):
    for tier in result['objects']:
        prices = {}
        for price in tier['prices']:
            prices[price['region']] = price
        tier['prices'] = prices

    return result


@app.route('/tiers/')
@app.route('/tiers/<server>/')
def tiers(server=None):
    if server:
        res = requests.get('{0}{1}'.format(
            servers[server], api['tiers']))
        result = fill_tiers(res.json())
        return render_template('tiers.html', result=result['objects'],
                               regions=regions, sorted=regions_sorted,
                               methods=methods, server=server)

    return render_template('tiers.html')


@app.route('/transactions/')
@app.route('/transactions/<server>/<date>/')
def transactions(server=None, date=''):
    sfmt = '%Y-%m-%d'
    lfmt = sfmt + 'T%H:%M:%S'
    today = datetime.today()
    dates = (('Yesterday', (today - timedelta(days=1)).strftime(sfmt)),
             ('Day before', (today - timedelta(days=2)).strftime(sfmt)))

    if TRANSACTIONS and server and date:
        date = datetime.strptime(date, sfmt)
        src = '/Users/andy/sandboxes/solitude/{0}.log'.format(
            date.strftime(sfmt))

        with open(src) as csvfile:
            rows = []
            for row in csv.DictReader(csvfile):
                row['created'] = datetime.strptime(row['created'], lfmt)
                row['modified'] = datetime.strptime(row['modified'], lfmt)
                row['diff'] = (row['modified'] - row['created'])
                rows.append(row)

            return render_template('transactions.html', rows=rows,
                                   server=server, dates=dates)
    return render_template('transactions.html', dates=dates)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.debug = True
    http = WSGIServer(('0.0.0.0', port), app)
    http.serve_forever()
