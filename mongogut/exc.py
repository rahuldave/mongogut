#from http://flask.pocoo.org/snippets/97/
#usage:
# @app.route("/test")
# def view():
#     abort(422, {'errors': dict(password="Wrong password")})


ERRGUT={}
ERRGUT['AOK_REQ']=200
ERRGUT['AOK_CRT']=201
ERRGUT['BAD_REQ']=400
ERRGUT['NOT_FND']=404
ERRGUT['SRV_ERR']=500
ERRGUT['SRV_UNA']=503
ERRGUT['NOT_AUT']=401
ERRGUT['FOR_BID']=403

adsgut_errtypes=[
    ('ADSGUT_AOK_REQ',ERRGUT['AOK_REQ'], 'Request Ok'),
    ('ADSGUT_AOK_CRT',ERRGUT['AOK_CRT'], 'Object Created'),
    ('ADSGUT_BAD_REQ',ERRGUT['BAD_REQ'], 'Bad Request'),
    ('ADSGUT_NOT_FND',ERRGUT['NOT_FND'], 'Not Found'),
    ('ADSGUT_SRV_ERR',ERRGUT['SRV_ERR'], 'Internal Server Error'),
    ('ADSGUT_SRV_UNA',ERRGUT['SRV_UNA'], 'Service Unavailable'),
    ('ADSGUT_NOT_AUT',ERRGUT['NOT_AUT'],'Not Authorized'),
    ('ADSGUT_FOR_BID',ERRGUT['FOR_BID'], 'Forbidden'),
]

import sys, traceback

class MongoGutError(Exception):

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['reason'] = self.message
        return rv

def codeabort(status_code, reasondict):
    raise MongoGutError(reasondict['reason'], status_code)

#Implement flask error handling outside
webabort=codeabort
abort=codeabort

def doabort(codestring, reason):
    #x=sys.exc_info()
    codeabort(ERRGUT[codestring], {'reason':reason})
