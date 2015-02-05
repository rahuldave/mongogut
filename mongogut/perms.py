from exc import abort, doabort
from mongoclasses import *
from utilities import *

#permit is the basis on which the entire permissions system is constructed
#if the clause is False, you get a http not-authorized error
def permit(clause, reason):
    if clause==False:
        doabort('NOT_AUT', reason)

#ands the clauses in clausetuples with the authstart
def permit_and(authstart, clausetuples):
    start=authstart
    reasons=[]
    for tup in clausetuples:
        start = start and tup[0]
        reasons.append(tup[1])
    if start==False:
        doabort('NOT_AUT', ' or '.join(reasons))

permit2=permit_and

#ors the clauses instead
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
    #make sure a real logged in user
    permit(currentuser.nick!='anonymouse', "must be logged in")
    #current user must be useras
    clause = (currentuser==useras, "User %s not authorized" % currentuser.nick)
    #or user must be system user
    clausesys = (db.isSystemUser(currentuser), "User %s not superuser" % currentuser.nick)
    #now do the or
    permit_or(authstart, [clausesys, clause])

#will only be true if we are system user (adsgut)
def authorize_systemuser(authstart, db, currentuser):
    return authorize(authstart, db, currentuser, None)

#currentuser=useras
def authorize_loggedin_or_systemuser(authstart, db, currentuser):
    return authorize(authstart, db, currentuser, currentuser)


#make sure you are a member of something
#the membable is cobj
#you are memberable. in this case 'you' can be a user, app, or group
def authorize_membable_member(authstart, db, currentuser, memberable, cobj):
    #if user u should be logged in
    if classtype(memberable)==User:
        # if not db.isSystemUser(currentuser) or not db.isOwnerOfOwnable(currentuser, currentuser, cobj):#currently leave out the possibility of a groupowner nasquerading as user
        #     clause=(currentuser==memberable, "User %s not authorized" % currentuser.nick)
        # else:
        clause=(True,'')
    elif classtype(memberable) in [Group, App]:#the memberable a membable, then u must be in memberable
        clause = (db.isMemberOfMembable(currentuser, currentuser, memberable), "%s must be member of membable %s %s" % (currentuser.adsid, classname(memberable), memberable.basic.fqin))
    else:
        clause=(False,"")
    permit(*clause)
    #after initial barrier make sure memberable is member of membable
    clause3=(db.isMemberOfMembable(currentuser, memberable, cobj), "%s must be member of membable %s %s" % (memberable.basic.fqin, classname(cobj), cobj.basic.fqin))
    clausesys = (db.isSystemUser(currentuser), "User %s not superuser" % currentuser.nick)
    #being a systemuser overrides all. but if not, make sure u member
    if not clausesys[0]:
        permit(*clause3)

#use this one specifically for libraries
authorize_postable_member=authorize_membable_member

#test for the ownership of a itemtype, or group, or library. again the object
#in question is cobj
def authorize_ownable_owner(authstart, db, currentuser, memberable, cobj):
    permit(currentuser.adsid!='anonymouse', "must be logged in")
    if classtype(memberable)==User:
        # if not db.isSystemUser(currentuser) or not db.isOwnerOfOwnable(currentuser, currentuser, cobj):#currently leave out the possibility of a groupowner nasquerading as user
        #     clause=(currentuser==memberable, "User %s not authorized" % currentuser.nick)
        # else:
        clause=(True,'')
    elif classtype(memberable) in [Group, App]:#this should NEVER BE True, owners must be User
        clause=(False,"")
    else:
        clause=(False,"")
    permit(*clause)
    #after initial barrier make sure memberable is owner of cobj like a membable
    clause3=(db.isOwnerOfOwnable(currentuser, memberable, cobj), "%s must be owner of ownable %s %s" % (currentuser.adsid, classname(cobj), cobj.basic.fqin))
    clausesys = (db.isSystemUser(currentuser), "User %s not superuser" % currentuser.nick)
    if not clausesys[0]:
        permit(*clause3)

#add special ones for groups/apps, and then libraries
authorize_membable_owner=authorize_ownable_owner
authorize_postable_owner=authorize_ownable_owner
