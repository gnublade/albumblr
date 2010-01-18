from google.appengine.ext.webapp import template
from django.utils import simplejson as json

register = template.create_template_register()

@register.filter
def jsonify(o):
    return json.dumps(o)

@register.filter
def heshe(gender):
    s = {'Male': "he", 'Female': "she"}
    return s.get(gender, "they")
