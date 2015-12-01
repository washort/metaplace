from __future__ import division

import csv
import json
import os
import time
import urllib

from collections import defaultdict, OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal
from itertools import groupby

import boto
from boto.s3.key import Key

import grequests
import pingdomlib
import requests

from curling.lib import API, safe_parser
from flask import (abort, Flask, redirect, render_template, request, session,
                   Response)
from gevent.pywsgi import WSGIServer
from werkzeug.contrib.cache import MemcachedCache

import local

log_cache = os.path.join(os.path.dirname(__file__), 'cache')
import pylibmc

servers = os.environ.get('MEMCACHIER_SERVERS', ['localhost:11211']).split(',')
user = os.environ.get('MEMCACHIER_USERNAME', '')
passwd = os.environ.get('MEMCACHIER_PASSWORD', '')

mc = pylibmc.Client(servers, binary=True, username=user, password=passwd)
cache = MemcachedCache(mc)
CACHE_TIMEOUT = 600

app = Flask(__name__)


servers = {
    'dev': 'https://marketplace-dev.allizom.org',
    'stage': 'https://marketplace.allizom.org',
    'prod': 'https://marketplace.firefox.com',
    'altpay': 'https://payments-alt.allizom.org'
}

api = {
    'tiers': '/api/v1/webpay/prices',
    'tier': '/api/v1/services/price-currency/'
}

regions = {
    # Casting int as strings because its easier.
    '1': 'Worldwide', '2': 'US', '4': 'UK', '7': 'Brazil', '8': 'Spain',
    '9': 'Colombia', '10': 'Venezuela', '11': 'Poland', '12': 'Mexico',
    '13': 'Hungary', '14': 'Germany', '31': 'Bangladesh', '23': 'Chile',
    '18': 'Peru', '19': 'Uruguay', '17': 'Greece', '37': 'South Africa',
    '22': 'Italy', '30': 'France', '38': 'Lithuania', '71': 'Austria',
    '77': 'Belgium', '105': 'Cyprus', '112': 'Estonia', '117': 'Finland',
    '140': 'Ireland', '151': 'Latvia', '157': 'Luxembourg', '163': 'Malta',
    '178': 'Netherlands', '178': 'Portugal', '214': 'Slovakia',
    '215': 'Slovenia', '37': 'Netherlands'
}

methods = {
    0: 'operator',
    1: 'card',
    2: 'both'
}

provider_lookup = {
    '': 'none',
    '0': 'paypal',
    '1': 'bango',
    '2': 'reference',
    '3': 'boku'
}

regions_sorted = sorted(regions.keys())

builds = {
    'jenkins': [],
    'travis': ['andymckay/receipts', 'mozilla/fireplace',
               'mozilla/commonplace', 'mozilla/zamboni',
               'mozilla/spartacus', 'mozilla/solitude',
               'mozilla/webpay',
               'andymckay/django-paranoia', 'andymckay/curling',
               'andymckay/django-statsd', 'andymckay/mozilla-logger']
}

statuses = {
    '0': ['pending', 'warning'],
    '1': ['completed', 'success'],
    '2': ['checked', 'info'],
    '3': ['received', 'info'],
    '4': ['error', 'danger'],
    '5': ['cancelled', 'danger'],
    '6': ['started', 'warning'],
    '7': ['errored', 'danger'],
}


@app.route('/apikiosk/')
def apikiosk():
    pingdom = pingdomlib.Pingdom(local.PINGDOM_USER,
                                 local.PINGDOM_PASS,
                                 local.PINGDOM_APIKEY,
                                 local.PINGDOM_ACCOUNT_EMAIL);

    checks = cache.get('apikiosk.checks')
    if not checks:
        checks = pingdom.getChecks()
        cache.set('apikiosk.checks', checks, timeout=60 * 60)

    fireplace = cache.get('apikiosk.fireplace')
    other = cache.get('apikiosk.other')

    if not (fireplace and other):
        fireplace = []
        other = []
        results = {}
        for check in checks:
            if check.name.startswith("MKT;"):
                # This takes the average response time from the past 24hr
                # pingdomlib uses a reserved keyword (from) as a kwarg :(
                avg = check.averages(**{'from': int(time.time())-86400})
                avg = avg['responsetime']['avgresponse']

                name = check.name[5:].replace('; CDN','')

                if name in results:
                    c = results[name]
                else:
                    c = {'area': "",
                         'cdn_avg': "",
                         'cdn_url': "",
                         'name': name,
                         'source_avg': "",
                         'source_url': ""}

                d = check.getDetails()
                if check.name.endswith('CDN'):
                    c['cdn_avg'] = avg
                    c['cdn_url'] = "%s%s" % (check.hostname,
                                             d['type']['http']['url'])
                else:
                    c['source_avg'] = avg
                    c['source_url'] = "%s%s" % (check.hostname,
                                                d['type']['http']['url'])

                if 'Fireplace' in check.name:
                    c['area'] = 'fireplace'

                results[name] = c

        for j, k in results.iteritems():
            if k['area'] == 'fireplace':
                fireplace.append(k)
            else:
                other.append(k)

    cache.set('apikiosk.fireplace', fireplace, timeout=60 * 60)
    cache.set('apikiosk.other', other, timeout=60 * 60)

    return render_template('apikiosk.html', fireplace=fireplace, other=other)


def notify(msg, *args):
    esc = urllib.urlencode(dict(['args', a] for a in args), doseq=True)
    url = 'https://notify.paas.allizom.org/notify/{0}/?{1}'.format(msg, esc)
    requests.post(url, headers={'Authorization':
                                'Basic {0}'.format(local.NOTIFY_AUTH)})


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


def get_webqa_status(results):
    resp = requests.get('http://mozilla.github.io/marketplace-tests/status.json').json()
    for job, details in resp.iteritems():
        results['results']['mozwebqa/%s' % job] = details['status']

    return results


def get_build():
    result = cache.get('build')

    if not result:
        result = {'when': datetime.now(), 'results': {}}
        get_jenkins(builds['jenkins'], result)
        get_travis(builds['travis'], result)
        get_webqa_status(result)
        cache.set('build', result, timeout=60 * 5)

    result['results'] = OrderedDict(sorted(result['results'].items()))
    passing = all(result['results'].values())
    last = bool(cache.get('last-build'))

    cache.set('last-build', True)
    if last is None:
        cache.set('last-build', bool(passing))

    elif last != passing:
        #notify('builds', 'passing' if passing else 'failing')
        cache.set('last-build', bool(passing))

    return result, passing

@app.route('/bugskiosk/')
def bugskiosk():
    return render_template('bugskiosk.html')


@app.route('/waffles/')
def waffles():
    return render_template('waffles.html')


@app.route('/build/')
def build():
    result, passing = get_build()

    if 'application/json' in request.headers['Accept']:
        result['when'] = result['when'].isoformat()
        return json.dumps({'all': passing, 'result': result})

    return render_template('build.html', result=result, request=request,
                           all=passing)


@app.route('/jump/')
def jump():
    return render_template('jump.html')


@app.route('/manifest.webapp')
def manifest():
    data = json.dumps({
        "name": "Metaplace",
        "description": "Information about the marketplace",
        "launch_path": "/",
        "icons": {
            "32": "/static/img/icon-32.png",
            "48": "/static/img/icon-48.png",
            "64": "/static/img/icon-64.png",
            "128": "/static/img/icon-128.png"
        },
        "developer": {
            "name": "Andy McKay",
            "url": "https://mozilla..org"
        },
        "default_locale": "en"
    })
    return Response(data, mimetype='application/x-web-app-manifest+json')


def fill_tiers(result, region=None):
    for tier in result['objects']:
        prices = {}
        for price in tier['prices']:
            if region and str(price['region']) != region:
                continue
            prices[str(price['region'])] = price
        tier['prices'] = prices

    return result


@app.route('/tiers/')
def tiers():
    get = request.values.get
    server, provider, region = get('server'), get('provider'), get('region')
    if server and provider:
        res = requests.get('{0}{1}?provider={2}'.format(
            servers[server], api['tiers'], provider))
        result = fill_tiers(res.json(), region)
        return render_template('tiers.html', result=result.get('objects', []),
                               regions=regions,
                               sorted=[region] if region else regions_sorted,
                               methods=methods, server=server,
                               provider=provider,
                               # Form population.
                               servers=servers, all_regions=regions_sorted)

    return render_template('tiers.html',
        servers=servers, all_regions=regions_sorted, regions=regions)


def _tier(server, tier):
    srv = API(servers[server])
    if server not in session['oauth']:
        raise ValueError('No key in session for %s.' % server)
    auth = session['oauth'][server]
    srv.activate_oauth(auth['key'], auth['secret'])
    return srv.by_url('/api/v1/services/price-currency/{0}/'.format(tier),
                      parser=safe_parser)


@app.route('/tiers/<server>/<tier>/', methods=['GET'])
def tier_get(server=None, tier=None):
    if not server or not tier:
        return redirect('/tiers/')

    return render_template('tiers-edit.html',
        tier=_tier(server, tier).get(),
        server=server)


@app.route('/tiers/')
@app.route('/tiers/<server>/<tier>/', methods=['POST'])
def tier_edit(server=None, tier=None):
    if not server or not tier:
        return redirect('/tiers/')

    srv = _tier(server, tier)
    obj = srv.get()
    for k in ['paid', 'dev', 'method', 'currency']:
        obj[k] = request.form.get(k)
        if k in ['paid', 'dev']:
            obj[k] = bool(obj[k])
    srv.put(obj)
    return redirect(request.url)


def s3_get(server, src_filename, dest_filename):
    conn = boto.connect_s3(local.S3_AUTH[server]['key'],
                           local.S3_AUTH[server]['secret'])
    bucket = conn.get_bucket(local.S3_BUCKET[server])
    dest = os.path.join(log_cache, dest_filename)
    k = Key(bucket)
    k.key = src_filename
    k.get_contents_to_filename(dest)
    # Reset the modified time, to be the time we wrote it for caching.
    # This is probably the wrong way to do it.
    os.utime(dest, (time.time(), time.time()))


def list_to_dict_multiple(listy):
    return reduce(lambda x, (k,v): x[k].append(v)
                  or x, listy, defaultdict(list))


@app.route('/transactions/')
@app.route('/transactions/<server>/<date>/')
def transactions(server=None, date=''):
    if not session.get('mozillian'):
        abort(403)

    sfmt = '%Y-%m-%d'
    lfmt = sfmt + 'T%H:%M:%S'
    today = datetime.today()
    dates = (('today', today.strftime(sfmt)),
             ('-1 day', (today - timedelta(days=1)).strftime(sfmt)),
             ('-2 days', (today - timedelta(days=2)).strftime(sfmt)),
             ('-3 days', (today - timedelta(days=3)).strftime(sfmt)))

    if server and date:
        date = datetime.strptime(date, sfmt)
        src_filenames = (
            date.strftime(sfmt) + '.stats.log',
            date.strftime(sfmt) + '.log'
        )
        dest_filename = date.strftime(sfmt) + '.' + server + '.stats.log'

        dest = os.path.join(log_cache, dest_filename)
        if (not os.path.exists(dest)
            or ((time.time() - os.stat(dest).st_mtime) > CACHE_TIMEOUT)):
            for src_filename in src_filenames:
                if src_filename not in os.listdir(log_cache):
                    try:
                        s3_get(server, src_filename, dest_filename)
                        break
                    except boto.exception.S3ResponseError:
                        pass

        if not os.path.exists(dest):
            return render_template('transactions.html', dates=dates)

        with open(dest) as csvfile:
            rows = []
            stats = defaultdict(list)
            for row in csv.DictReader(csvfile):
                row['created'] = datetime.strptime(row['created'], lfmt)
                row['modified'] = datetime.strptime(row['modified'], lfmt)
                row['diff'] = row['modified'] - row['created']
                if row['diff']:
                    stats['diff'].append(row['diff'].total_seconds())
                stats['status'].append(row['status'])

                if row['currency'] and row['amount']:
                    stats['currencies'].append((row['currency'],
                                                Decimal(row['amount'])))

                row['provider'] = provider_lookup[row.get('provider', '1')]
                rows.append(row)

            if len(stats['diff']):
                stats['mean'] = '%.2f' % (
                    sum(stats['diff'])/len(stats['diff']))

            for status, group in groupby(sorted(stats['status'])):
                group = len(list(group))
                perc = (group / len(stats['status'])) * 100
                stats['statuses'].append((str(status), group, '%.2f' % perc))

            stats['currencies'] = list_to_dict_multiple(stats['currencies'])
            for currency, items in stats['currencies'].items():
                stats['currencies'][currency] = {'items': items}
                stats['currencies'][currency]['count'] = len(items)
                mean = (sum(items) / len(items))
                stats['currencies'][currency]['mean'] = '%.2f' % mean

            return render_template('transactions.html', rows=rows,
                                   server=server, dates=dates, stats=stats,
                                   statuses=statuses, filename=dest_filename,
                                   filedata=open(dest).read())

    return render_template('transactions.html', dates=dates)


@app.errorhandler(500)
def page_not_found(err):
    return render_template('500.html', err=err), 500


@app.errorhandler(403)
def page_not_allowed(err):
    return render_template('403.html', err=err), 403


@app.route('/auth/login', methods=['POST'])
def login():
    # The request has to have an assertion for us to verify
    if 'assertion' not in request.form:
        abort(400)

    # Send the assertion to Mozilla's verifier service.
    data = {'assertion': request.form['assertion'],
            'audience': 'https://metaplace.herokuapp.com/'}
    resp = requests.post('https://verifier.login.persona.org/verify',
                         data=data, verify=True)

    # Did the verifier respond?
    if resp.ok:
        # Parse the response
        verification_data = json.loads(resp.content)

        # Check if the assertion was valid
        if verification_data['status'] == 'okay':
            # Log the user in by setting a secure session cookie
            session.update({
                'email': verification_data['email'],
                'mozillian': verification_data['email'] in local.MOZS
            })
            return 'You are logged in'

    abort(500)


@app.route('/auth/oauth/', methods=['GET'])
@app.route('/auth/oauth/<server>', methods=['GET'])
def oauth_get(server=None):
    return render_template('oauth.html', server=server, servers=servers)


@app.route('/auth/oauth/<server>', methods=['POST'])
def oauth_save(server):
    # This will store it in the cookie. If someone wants to do the whole
    # 3 legged oauth dance, pull requests welcome.
    if not 'oauth' in session:
        session['oauth'] = {}
        for key in servers.keys():
            session['oauth'][key] = {}

    session['oauth'][server] = {
        'key': request.form.get('key').strip(),
        'secret': request.form.get('secret').strip()
    }
    return redirect('/')


@app.route('/auth/logout', methods=['POST', 'GET'])
def logout():
    session.update({'email': None, 'mozillian': False})
    return 'You are logged out'


@app.after_request
def after_request(response):
    response.headers.add('Strict-Transport-Security', 'max-age=31536000')
    return response


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.debug = bool(os.environ.get('FLASK_DEBUG', False))
    print 'App in debug mode?', bool(app.debug)
    app.secret_key = local.SECRET
    ip = '0.0.0.0'
    http = WSGIServer((ip, port), app)
    print 'Listening at http://{ip}:{port}'.format(ip=ip, port=port)
    http.serve_forever()
