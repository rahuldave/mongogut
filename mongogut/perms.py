from exc import abort, doabort
from mongoclasses import *
from utilities import *

AUTHTOKENS={
    'SAVE_ITEM_FOR_USER': (1001, "App or Group can save item for user"),
    'POST_ITEM_FOR_USER': (1002, "App or Group can post item for user into app or group"),
    'TAG_ITEM_FOR_USER':  (1003, "App or Group can tag item for user"),
    'POST_TAG_FOR_USER':  (1004, "App or Group can post tag for user on an item to app or group")
}
def permit(clause, reason):
    if clause==False:
        doabort('NOT_AUT', reason)

def permit_and(authstart, clausetuples):
    start=authstart
    reasons=[]
    for tup in clausetuples:
        start = start and tup[0]
        reasons.append(tup[1])
    if start==False:
        doabort('NOT_AUT', ' or '.join(reasons))

permit2=permit_and

def permit_or(authstart, clausetuples):
    start=authstart
    reasons=[]
    for tup in clausetuples:
        start = start or tup[0]
        reasons.append(tup[1])
    if start==False:
        doabort('NOT_AUT', ' or '.join(reasons))

#authorize with useras=currentuser will allow u through if u r either
#logged in or are superuser. useras=None will only allow you if u r systemuser
def authorize(authstart, db, currentuser, useras):
    permit(currentuser.nick!='anonymouse', "must be logged in")
    clause = (currentuser==useras, "User %s not authorized" % currentuser.nick)
    clausesys = (db.isSystemUser(currentuser), "User %s not superuser" % currentuser.nick)
    permit_or(authstart, [clausesys, clause])

def authorize_systemuser(authstart, db, currentuser):
    return authorize(authstart, db, currentuser, None)

def authorize_loggedin_or_systemuser(authstart, db, currentuser):
    return authorize(authstart, db, currentuser, currentuser)

def classname(instance):
    #return type(instance).__name__
    return instance.classname

def classtype(instance):
    return type(instance)

def authorize_membable_member(authstart, db, currentuser, memberable, cobj):

    if classtype(memberable)==User:
        clause=(currentuser==memberable, "User %s not authorized" % currentuser.nick)
        clause=(True,'') #BUG: corrently allow these to be different
    elif classtype(memberable) in [Group, App]:#is the memberable a membable
        #CHOICE:if you are testing membership, is it enough to be member? or should you be owner of memberable
        clause = (db.isMemberOfMembable(currentuser, currentuser, memberable), "%s must be member of membable %s %s" % (currentuser.adsid, classname(memberable), memberable.basic.fqin))
    else:
        clause=(False,"")
    permit(*clause)
    #BUG: what if useras is a group?
    clause3=(db.isMemberOfMembable(currentuser, memberable, cobj), "%s must be member of membable %s %s" % (currentuser.adsid, classname(cobj), cobj.basic.fqin))
    clausesys = (db.isSystemUser(currentuser), "User %s not superuser" % currentuser.nick)
    #print "clauses", clausesys[0], clause3[0], clause[0]
    if not clausesys[0]:
        #print "here", currentuser.nick, memberable.nick, clause3
        permit(*clause3)

authorize_postable_member=authorize_membable_member
#bug fix for useras being a memberable. would seem to be ok otherwise?
#

#NEW Ownables must be users so we should just go through directly
def authorize_ownable_owner(authstart, db, currentuser, memberable, cobj):
    #print ">>>",currentuser.basic.fqin, memberable.basic.fqin, cobj.basic.fqin
    #print "<<<", currentuser.basic.fqin, memberable.basic.fqin, cobj.basic.fqin
    permit(currentuser.adsid!='anonymouse', "must be logged in")
    #what if useras is a group? see the elif. otherwise user musr be currentuser
    if classtype(memberable)==User:
        clause = (currentuser==memberable, "User %s not authorized" % currentuser.nick)
        clause=(True,'') #BUG: corrently allow these to be different
    elif classtype(memberable) in [Group, App]:#this should NEVER BE True, owners
        #clause = (db.isOwnerOfMembable(currentuser, currentuser, memberable), "%s must be owner of membable %s %s" % (currentuser.adsid, classname(memberable), memberable.basic.fqin))
        clause=(False,"")
    else:
        clause=(False,"")
    permit(*clause)
    clause3=(db.isOwnerOfOwnable(currentuser, memberable, cobj), "%s must be owner of ownable %s %s" % (currentuser.adsid, classname(cobj), cobj.basic.fqin))
    clausesys = (db.isSystemUser(currentuser), "User %s not superuser" % currentuser.nick)
    #print "clauses", clausesys[0], clause3[0], clause[0]
    if not clausesys[0]:
        permit(*clause3)

authorize_membable_owner=authorize_ownable_owner
authorize_postable_owner=authorize_ownable_owner
