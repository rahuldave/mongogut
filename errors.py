#from http://flask.pocoo.org/snippets/97/
#usage:
# @app.route("/test")
# def view():
#     abort(422, {'errors': dict(password="Wrong password")})
WEBMODE=False
#from werkzeug.exceptions import default_exceptions, HTTPException
#from flask import make_response, abort as flask_abort, request
#from flask.exceptions import JSONHTTPException

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

# def abort(status_code, body=None, headers={}):
#     """
#     Content negiate the error response.

#     """

#     if 'text/html' in request.headers.get("Accept", ""):
#         error_cls = HTTPException
#     else:
#         error_cls = JSONHTTPException
#     #error_cls = JSONHTTPException
#     class_name = error_cls.__name__
#     bases = [error_cls]
#     attributes = {'code': status_code}
#     #print default_exceptions
#     if status_code in default_exceptions:
#         # Mixin the Werkzeug exception
#         bases.insert(0, default_exceptions[status_code])

#     error_cls = type(class_name, tuple(bases), attributes)
#     print "BODY", body, error_cls, bases
#     errori=error_cls()
#     if body==None:
#         body={}
#     errori=error_cls(dict(body, code=errori.code, error=errori.name))
#     #This is just a hack to get the code and the name in currently
#     flask_abort(make_response(errori, status_code, headers))

# webabort=abort

import sys, traceback

class Error(Exception):
    pass

def codeabort(status_code, reason):
    raise Error(status_code, reason)

#Implement flask error handling outside
webabort=codeabort
abort=codeabort

def doabort(codestring, reason):
    x=sys.exc_info()
    print '==============================='
    print x
    print traceback.print_tb(x[2])
    print '==============================='
    if WEBMODE:
        webabort(ERRGUT[codestring], {'reason':reason})
    else:
        codeabort(ERRGUT[codestring], reason)
        #print ERRGUT[codestring], {'reason':reason}
        #sys.exit(0)
        # try:
        #     print sys.exc_info()
        #     codeabort(ERRGUT[codestring], reason)
        # except Error, e:
        #     print e[0], e[1]
        #     sys.exit(0)