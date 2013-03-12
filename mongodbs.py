#Just a listing of collections and basic collection schema
import pymongo as pym
import pymongo.errors as pymerr
import sys
errprint=sys.stderr.write

def getConnection():
    try:
        c=pym.Connection()
    except pymerr.ConnectionFailure, e:
        errprint("Coumdnt connect to Mongo %s" % e)
    return c

class Database(object):

    def __init__(self, dbase, connection=None):
        if connection:
            #should assert here that connection is of type connection
            assert type(connection)==pym.connection.Connection
            self.c=connection
        else:
            self.c=getConnection()
        self.d=self.c[dbase]
        assert self.d.connection == self.c



#collections
#   groups: a bunch of group documents
#   apps: a bunch of app documents
#   users: a bunch of user documents
#
#group

if __name__=="__main__":
    d=Database('adsgut')