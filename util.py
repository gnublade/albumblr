
import os
from functools import wraps

from google.appengine.ext.webapp import template

from django.utils import simplejson as json

from config import *

class ToJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if callable(getattr(obj, '__json__', None)):
            return obj.__json__()
        elif hasattr(obj, '__str__'):
            return obj.__str__()
        else:
            raise TypeError(repr(obj) + " is not JSON serializable")

def dumps(o):
    return json.dumps(o, indent=JSON_INDENT, cls=ToJSONEncoder)

def expose(templatename=None, format=None):
    if templatename:
        path = os.path.join(TMPL_PATH, templatename)
        default_renderer = lambda v: template.render(path, v)
    else:
        default_renderer = lambda v: v
    formats = {
        'json' : ('text/javascript', dumps),
        None   : (None, default_renderer) }
    content_type, renderer = formats.get(format, formats[None])
    def wrapper(func):
        @wraps(func)
        def wrapped(self, *args, **kwargs):
            if content_type:
                self.response.headers['Content-Type'] = content_type
            values = func(self, *args, **kwargs)
            self.response.out.write(renderer(values))
        # :TODO: Restrict the methods.
        wrapped.exposed_methods = [ 'GET', 'POST' ]
        return wrapped
    return wrapper


