import os
SECRET = os.getenv('FLASK_SECRET')
S3_AUTH = {'key': os.getenv('S3_AUTH_KEY'),
           'secret': os.getenv('S3_AUTH_SECRET')}
S3_BUCKET = os.getenv('S3_BUCKET')

# For use on the API Speed tab
PINGDOM_USER = os.getenv('PINGDOM_USER')
PINGDOM_PASS = os.getenv('PINGDOM_PASS')
PINGDOM_ACCOUNT_EMAIL = os.getenv('PINGDOM_ACCOUNT_EMAIL')
PINGDOM_APIKEY = os.getenv('PINGDOM_APIKEY')
