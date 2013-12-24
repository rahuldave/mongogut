from errors import abort, doabort
from classes import *
from commondefs import *

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
#add permission helpers here to refactor permits
#example group membership etc

#(1) user must be defined

#perhaps we'll need multiple authorizers.
#Where do we check for oauth? not here. That must come in via authstart,
#somehow knocked into g.db and then computed upon.
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
#For next two, for additions and such, switch between useras=currentuser and useras=None
#where a useras is not required

# #BUG: need to add types here!!!!!!!!!
# def authorize_context_owner(authstart, db, currentuser, useras, cobj):
#     permit(currentuser!=None, "must be logged in")
#     clause = (currentuser==useras, "User %s not authorized" % currentuser.nick)
#     clausesys = (db.isSystemUser(currentuser), "User %s not superuser" % currentuser.nick)
#     if cobj.__class__.__name__=='Group':
#         clause3=(db.isOwnerOfGroup(currentuser,cobj), "must be owner of group %s" % cobj.basic.fqin)
#     elif cobj.__class__.__name__=='App':
#         clause3=(db.isOwnerOfApp(currentuser,cobj), "must be owner of app %s" % cobj.basic.fqin)
#     elif cobj.__class__.__name__=='Library':
#         clause3=(db.isOwnerOfLibrary(currentuser,cobj), "must be owner of library %s" % cobj.basic.fqin)
#     permit2(authstart, [clausesys, clause3, clause])

# def authorize_context_member(authstart, db, currentuser, useras, cobj):
#     permit(currentuser!=None, "must be logged in")
#     clause = (currentuser==useras, "User %s not authorized" % currentuser.nick)
#     clausesys = (db.isSystemUser(currentuser), "User %s not superuser" % currentuser.nick)
#     if cobj.__class__.__name__=='Group':
#         clause3=(db.isMemberOfGroup(currentuser,cobj), "must be member of group %s" % cobj.basic.fqin)
#     elif cobj.__class__.__name__=='App':
#         clause3=(db.isMemberOfApp(currentuser,cobj), "must be member of app %s" % cobj.basic.fqin)
#     elif cobj.__class__.__name__=='Library':
#         clause3=(db.isMemberOfLibrary(currentuser,cobj), "must be member of group that owns library %s" % cobj.basic.fqin)
#     permit2(authstart, [clausesys, clause3, clause])


def classname(instance):
    #return type(instance).__name__
    return instance.classname

def classtype(instance):
    return type(instance)
#this needs to deal with both the target being a memberable as well as the target being a member of the memberable
#BUG thus currentuser=useras and maybe other need to fixed in both below
def authorize_membable_member(authstart, db, currentuser, memberable, cobj):
    #print "<<<",currentuser.basic.fqin, memberable.basic.fqin, cobj.basic.fqin
    #print currentuser.basic.fqin, memberable.basic.fqin, cobj.basic.fqin
    permit(currentuser.nick!='anonymouse', "must be logged in")
    #clause = (currentuser==useras, "User %s not authorized" % currentuser.nick)
    if classtype(memberable)==User:
        clause=(currentuser==memberable, "User %s not authorized" % currentuser.nick)
        clause=(True,'') #BUG: corrently allow these to be different
    elif classtype(memberable) in [Group, App]:
        #CHOICE:if you are testing membership, is it enough to be member? or should you be owner of memberable
        clause = (db.isMemberOfPostable(currentuser, currentuser, memberable), "%s must be member of postable %s %s" % (currentuser.adsid, classname(memberable), memberable.basic.fqin))
    else:
        clause=False
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
    elif classtype(memberable) in [Group, App]:#thie idea is to stop allowing this, for postable cobjs at
        clause = (db.isOwnerOfPostable(currentuser, currentuser, memberable), "%s must be owner of postable %s %s" % (currentuser.adsid, classname(memberable), memberable.basic.fqin))
    else:
        clause=False
    permit(*clause)
    clause3=(db.isOwnerOfOwnable(currentuser, memberable, cobj), "%s must be owner of ownable %s %s" % (currentuser.adsid, classname(cobj), cobj.basic.fqin))
    clausesys = (db.isSystemUser(currentuser), "User %s not superuser" % currentuser.nick)
    #print "clauses", clausesys[0], clause3[0], clause[0]
    if not clausesys[0]:
        permit(*clause3)

authorize_postable_owner=authorize_ownable_owner