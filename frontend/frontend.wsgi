#!/usr/bin/python3

# author: Ole Schuett

import sys
import logging
from os import path
logging.basicConfig(stream=sys.stderr)
sys.path.insert(0,path.dirname(__file__))


from frontend import app

# handler for mod_wsgi
def application(environ, start_response):
    return app(environ, start_response)

#EOF
