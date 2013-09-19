=========
Metaplace
=========

Formats output from the firefox marketplace API.

http://firefox-marketplace-api.readthedocs.org/en/latest/

Developers
----------

To install this app locally for development, clone the source,
set up a `virtualenv`_, and install it with `pip`_::

   pip install -r requirements.txt

Add a local settings file::

    cp local.py.dist local.py

Edit ``local.py`` to add some things like ``SECRET='something'``.
Run the development server::

    python app.py

.. _virtualenv: https://pypi.python.org/pypi/virtualenv
.. _pip: http://www.pip-installer.org/
