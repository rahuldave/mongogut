import postables
import itemsandtags
from mongoengine import connect

#host="mongodb://%s:%s@localhost/adsgut" % (sys.argv[1], sys.argv[2])
#from mongogut import main
#main(dbhost, auth=True, dropdb=True)
def main(dbhost, auth=False, dropdb=True):
    dbname = dbhost.split('/')[-1]
    if auth==False:
        db_session=connect(dbname)
    else:
        db_session=connect(dbname, dbhost)
    if dropdb:
        db_session.drop_database(dbname)
    postables.initialize_application(db_session)
    itemsandtags.initialize_application(db_session)