import os

from flask import Flask, render_template, request
import requests

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

@app.route('/')
def base(name=None):
    return render_template('index.html', name=name)


def fill_tiers(result):
    for tier in result['objects']:
        prices = {}
        for price in tier['prices']:
            prices[price['region']] = price
        tier['prices'] = prices

    return result


@app.route('/tiers/', methods=['GET', 'POST'])
def tiers():
    if request.method == 'POST':
        res = requests.get('{0}{1}'.format(
            servers[request.form['server']], api['tiers']))
        result = fill_tiers(res.json())
        return render_template('tiers.html', result=result['objects'],
                               regions=regions, sorted=regions_sorted,
                               methods=methods, server=request.form['server'])

    return render_template('tiers.html')


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
