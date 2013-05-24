from classes import *
import config
from permissions import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser
from permissions import authorize_ownable_owner, authorize_postable_member, authorize_postable_owner, authorize_membable_member
from errors import abort, doabort, ERRGUT
import types

import sys
from commondefs import *


class Database():

    def __init__(self, db_session):
        "initialize the database"
        self.session=db_session


    def isSystemUser(self, currentuser):
        "is the current user the superuser?"
        if currentuser.nick=='adsgut':
            return True
        else:
            return False

    #this one is completely UNPROTECTED
    def getUserForNick(self, currentuser, nick):
        "gets user for nick"
        print "ingetuser", [e.nick for e in User.objects]
        print "nick", nick
        try:
            user=User.objects(nick=nick).get()
        except:
            doabort('NOT_FND', "User %s not found" % nick)
        return user

    def getUserForFqin(self, currentuser, userfqin):
        "gets user for nick"
        try:
            user=User.objects(basic__fqin=userfqin).get()
        except:
            doabort('NOT_FND', "User %s not found" % userfqin)
        return user

    #this one is PROTECTED
    def getUserInfo(self, currentuser, nick):
        "gets user for nick only if you are superuser or that user"
        user=self.getUserForNick(currentuser, nick)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, user)
        return user


    #MEMBABLE AND POSTABLE interfaces. Postables are subsets of membables

    #generally, membable interface will only be internally used in postable functions
    #or for tagging. So I wont expose external functions to start with, and as we
    #go along, I will make sure to.

    def getMembable(self, currentuser, fqpn):
        "gets the membable corresponding to the fqpn"
        ptype=gettype(fqpn)
        try:
            postable=ptype.objects(basic__fqin=fqpn).get()
        except:
            doabort('NOT_FND', "%s %s not found" % (classname(ptype), fqpn))
        return postable

    #this one is unprotected
    #BUG make sure ptype is in MEMBABLES.
    def getPostable(self, currentuser, fqpn):
        "gets the postable corresponding to the fqpn"
        return self.getMembable(currentuser, fqpn)

    #this one is protected
    def getPostableInfo(self, currentuser, memberable, fqpn):
        "gets postable only if you are member of the postable"
        postable=self.getPostable(currentuser, fqpn)
        #BUG:this should work for a user member of postable as well as a memberable member of postable
        authorize_postable_member(MEMBER_OF_POSTABLE, self, currentuser, memberable, postable)
        return postable

    #using MEMBERABLE interface. this one is unprotected
    #also returns true if a user is a member of a postable(say a group), which is a member
    #of this postable. Also works if the memberable is a postable itself, through the memberable.basic.fqin interface

    #BUG other membable things need to be added, as needed

    def isMemberOfMembable(self, currentuser, memberable, membable, memclass=MEMBABLES):
        "is the memberable a member of membable"
        if memberable.basic.fqin in membable.members:
            return True
        for mem in membable.members:
            ptype=gettype(mem)
            if  ptype in memclass:
                pos=self.getMembable(currentuser, mem)
                if memberable.basic.fqin in pos.members:
                    return True
        return False

    def isMemberOfPostable(self, currentuser, memberable, postable):
        "is the memberable a member of postable"
        return self.isMemberOfMembable(currentuser, memberable, postable, POSTABLES)


    #using MEMBERABLE/OWNABLE:this can let a group be owner of the ownable, as long as its 'fqin' is in the owner field.
    #this one is unprotected
    def isOwnerOfOwnable(self, currentuser, memberable, ownable):
        "is memberable the owner of ownerable? ownerable is postable plus others"
        if memberable.basic.fqin==ownable.owner:
            return True
        else:        
            return False

    #defined this just for completion, and in code, it will be easier to read, unprotected
    def isOwnerOfPostable(self, currentuser, memberable, postable):
        return self.isOwnerOfOwnable(currentuser, memberable, postable)

    #invitations only work for users for now, even tho we have a memberable. unprotected
    def isInvitedToMembable(self, currentuser, memberable, membable):
        print "MEMBERABLE", memberable.to_json(), "MEMBABLE", membable.to_json()
        if memberable.basic.fqin in membable.inviteds:
            return True
        else:
            return False

    def isInvitedToPostable(self, currentuser, memberable, postable):
        "is the user invited to the postable?"
        return self.isInvitedToMembable(currentuser, memberable, postable)

    #unprotected
    #BUG just for user currently. Dosent work for other memberables. Is not transitive
    #so that a postable is listed for the owner of the memberable
    def ownerOfPostables(self, currentuser, useras, ptypestr=None):
        "return the postables the user is an owner of"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesowned
        if ptypestr:
            postables=[e['fqpn'] for e in allpostables if e['ptype']==ptypestr]
        else:
            postables=allpostables
        return postables

    #unprotected
    #BUG just for user currently. Dosent work for other memberables
    def postablesForUser(self, currentuser, useras, ptypestr=None):
        "return the postables the user is a member of"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesin
        if ptypestr:
            postables=[e['fqpn'] for e in allpostables if e['ptype']==ptypstre]
        else:
            postables=allpostables
        return postables

    #unprotected
    #invitations only work for users for now.
    def postableInvitesForUser(self, currentuser, useras, ptypestr=None):
        "given a user, find their invitations to postables"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesinvitedto
        if ptypestr:
            postables=[e['fqpn'] for e in allpostables if e['ptype']==ptypestr]
        else:
            postables=allpostables
        return postables

    #unprotected
    #user/memberable may be member through another memberable
    #this will give just those memberables, and not their expansion: is that ok? i think so
    def membersOfPostable(self, currentuser, memberable, postable):
        "is user or memberable a member of the postable?"
        #i need to have access to this if i come in through being a member of a memberable which is a member
        #authorize_postable member takes care of this. That memberable is NOT the same memberable in the arguments here
        authorize_postable_member(False, self, currentuser, memberable, postable)
        members=postable.members
        return members

    ################################################################################

    #Add user to system, given a userspec from flask user object. commit needed
    #This should never be called from the web interface, but can be called on the fly when user
    #logs in in Giovanni's system. So will there be a cookie or not?
    #BUG: make sure this works on a pythonic API too. think about authorize in a
    #pythonic API setting
    #
    #ought to be initialized on signup or in batch for existing users.
    def addUser(self, currentuser, userspec):
        "add a user to the system. currently only sysadmin can do this"
        #BUG BUG BUG: big security hole opened here for testing. This should be added externally to mongo.
        if not userspec['nick']=='adsgut':
            authorize_systemuser(False, self, currentuser)
        try:
            userspec=augmentspec(userspec)
            newuser=User(**userspec)
            newuser.save(safe=True)
        except:
            print sys.exc_info()
            doabort('BAD_REQ', "Failed adding user %s" % userspec['nick'])

        #BUG: more leakage here in bootstrap
        if userspec['nick']=='adsgut':
            currentuser=newuser

        #Also add user to private default group and public group

        #currentuser adds this as newuser
        #print adding default personal group
        self.addPostable(currentuser, newuser, "group", dict(name='default', creator=newuser.basic.fqin,
            personalgroup=True
        ))
        #currentuser adds this as root
        if not userspec['nick']=='adsgut':
            self.addMemberableToPostable(currentuser, currentuser, 'adsgut/group:public', newuser.basic.fqin)
        #BUG:Bottom ought to be done via routing
        #self.addUserToApp(currentuser, 'ads@adslabs.org/app:publications', newuser, None)
        #should this be also done by routing?
        #This is also added as root
        if not userspec['nick']=='adsgut':
            self.addMemberableToPostable(currentuser, currentuser, 'adsgut/app:adsgut', newuser.basic.fqin)
        newuser.reload()
        return newuser

    #BUG: we want to blacklist users and relist them
    #currently only allow users to be removed through scripts
    def removeUser(self, currentuser, usertoberemovednick):
        "remove a user. only systemuser can do this"
        #Only sysuser can remove user. 
        #BUG: this is unfleshed. routing and reference counting ought to be used to handle this
        authorize_systemuser(False, self, currentuser)
        remuser=self.getUserForNick(currentuser, usertoberemovednick)
        #CONSIDER: remove user from users collection, but not his name elsewhere.
        remuser.delete(safe=True)
        return OK

    def addPostable(self, currentuser, useras, ptypestr, postablespec):
        "the useras adds a postable. currently either currentuser=superuser or useras"
        #authorize(False, self, currentuser, currentuser)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        postablespec['creator']=useras.basic.fqin
        postablespec=augmentspec(postablespec, ptypestr)
        ptype=gettype(postablespec['basic'].fqin)
        print "In addPostable", ptypestr, ptype
        try:
            newpostable=ptype(**postablespec)
            newpostable.save(safe=True)
            #how to save it together?
            userq= User.objects(basic__fqin=newpostable.owner)
            newpe=PostableEmbedded(ptype=ptypestr,fqpn=newpostable.basic.fqin)
            res=userq.update(safe_update=True, push__postablesowned=newpe)
            #print "result", res, currentuser.groupsowned, currentuser.to_json()
            
        except:
            doabort('BAD_REQ', "Failed adding postable %s %s" % (ptype.__name__, postablespec['basic'].fqin))
        self.addMemberableToPostable(currentuser, useras, newpostable.basic.fqin, newpostable.basic.creator)
        #print "autoRELOAD?", userq.get().to_json()
        newpostable.reload()
        return userq.get(), newpostable

    def addGroup(self, currentuser, useras, groupspec):
        return self.addPostable(currentuser, useras, "group", groupspec)

    def addApp(self, currentuser, useras, appspec):
        return self.addPostable(currentuser, useras, "app", appspec)

    def addLibrary(self, currentuser, useras, libraryspec):
        return self.addPostable(currentuser, useras, "library", libraryspec)

    #BUG: why is there no useras here? perhaps too dangerous to let a useras delete?
    def removePostable(self,currentuser, fqpn):
        "currentuser removes a postable"
        rempostable=self.getPostable(currentuser, fqpn)
        authorize_ownable_owner(False, self, currentuser, None, rempostable)
        #BUG: group deletion is very fraught. Once someone else is in there
        #the semantics go crazy. Will have to work on refcounting here. And
        #then get refcounting to come in
        rempostable.delete(safe=True)
        return OK

    #BUG: there is no restriction here of what can be added to what in memberables and postables
    #BUG: when do we use get and when not. And what makes sure the fqins are kosher?
    def addMemberableToPostable(self, currentuser, useras, fqpn, memberablefqin):
        "add a user, group, or app to a postable=group, app, or library"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        print "types", fqpn, ptype, memberablefqin,mtype
        postableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(basic__fqin=memberablefqin)
        #BUG currently restricted admission. Later we will want groups and apps proxying for users.
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" %  (ptype.__name__,fqpn))
        try:
            memberable=memberableq.get()
        except:
            doabort('BAD_REQ', "No such memberable %s %s" %  (mtype.__name__,memberablefqin))

        if fqpn!='adsgut/group:public':
            #special case so any user can add themselves to public group
            #permit(self.isOwnerOfGroup(currentuser, grp) or self.isSystemUser(currentuser), "User %s must be owner of group %s or systemuser" % (currentuser.nick, grp.fqin))
            authorize_ownable_owner(False, self, currentuser, memberable, postable)
        try:
            pe=PostableEmbedded(ptype=ptype.classname,fqpn=postable.basic.fqin)
            memberableq.update(safe_update=True, push__postablesin=pe)
            postableq.update(safe_update=True, push__members=memberablefqin)
        except:
            doabort('BAD_REQ', "Failed adding memberable %s %s to postable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        memberable.reload()
        return memberable, postableq.get()

    def addUserToPostable(self, currentuser, fqpn, nick):
        user=self.getUserForNick(currentuser,nick)
        return self.addMemberableToPostable(currentuser, currentuser, fqpn, user.basic.fqin)

    #BUG: not really fleshed out as we need to handle refcounts and all that to see if objects ought to be removed.
    def removeMemberableFromPostable(self, currentuser, fqpn, memberablefqin):
        "remove a u/g/a from a g/a/l"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        postableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(basic__fqin=memberablefqin)

        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such group %s" % fqgn)
        #Bug shouldnt this have memberable?
        authorize_ownable_owner(False, self, currentuser, None, postable)
        try:
            pe=PostableEmbedded(ptype=ptype.classname,fqpn=postable.basic.fqin)
            memberableq.update(safe_update=True, pull_postablesin=pe)
            postableq.update(safe_update=True, pull__members=memberablefqin)
        except:
            doabort('BAD_REQ', "Failed removing memberable %s %s from postable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        return OK

    #BUG: there is no restriction here of what can be added to what in memberables and postables
    def addMemberableToMembable(self, currentuser, useras, fqpn, memberablefqin):
        "add a user, group, or app to a postable=group, app, or library"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        #BUG: need exception handling here, also want to make sure no strange fqins are accepted
        membableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(basic__fqin=memberablefqin)
        try:
            membableq.update(safe_update=True, push__members=memberablefqin)
        except:
            doabort('BAD_REQ', "Failed adding memberable %s %s to membable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        return memberableq.get(), membableq.get()

    #BUG: not really fleshed out as we need to handle refcounts and all that to see if objects ought to be removed.
    def removeMemberableFromMembable(self, currentuser, fqpn, memberablefqin):
        "remove a u/g/a from a g/a/l"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        membableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(basic__fqin=memberablefqin)

        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s" % fqpn)
        #Bug: this is currentuser for now
        authorize_ownable_owner(False, self, currentuser, None, membable)
        try:
            membableq.update(safe_update=True, pull__members=memberablefqin)
        except:
            doabort('BAD_REQ', "Failed removing memberable %s %s from postable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        return OK


    #do we want to use this for libraries? why not? Ca we invite other memberables?
    def inviteUserToPostable(self, currentuser, useras, fqpn, usertobeaddedfqin):
        "invite a user to a postable."
        ptype=gettype(fqpn)
        postable=self.getPostable(currentuser, fqpn)
        userq= User.objects(basic__fqin=usertobeaddedfqin)
        authorize_ownable_owner(False, self, currentuser, useras, postable)
        try:
            pe=PostableEmbedded(ptype=ptype.classname,fqpn=postable.basic.fqin)
            userq.update(safe_update=True, push__postablesinvitedto=pe)
            #BUG: ok to use fqin here instead of getting from oblect?
            postable.update(safe_update=True, push__inviteds=usertobeaddedfqin)
            #print "userq", userq.to_json()
        except:
            doabort('BAD_REQ', "Failed inviting user %s to postable %s" % (usertobeaddedfqin, fqpn))
        #print "IIIII", userq.get().groupsinvitedto
        postable.reload()
        return userq.get(), postable

    def inviteUserToPostableUsingNick(self, currentuser, fqpn, nick):
        "invite a user to a postable."
        user=self.getUserForNick(currentuser,nick)
        return self.inviteUserToPostable(currentuser, currentuser, fqpn, user.basic.fqin)

    #this cannot be masqueraded, must be explicitly approved by user
    #can we do without the mefqin?
    def acceptInviteToPostable(self, currentuser, fqpn, mefqin):
        "do i accept the invite?"
        ptype=gettype(fqpn)
        postableq=ptype.objects(basic__fqin=fqpn)
        userq= User.objects(basic__fqin=mefqin)
        try:
            me=userq.get()
        except:
            doabort('BAD_REQ', "No such user %s" % mefqin)
        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" % (ptype.__name__,fqpn))
        authorize(False, self, currentuser, me)
        permit(self.isInvitedToPostable(currentuser, me, postable), "User %s must be invited to postable %s %s" % (mefqin, ptype.__name__,fqpn))
        try:
            pe=PostableEmbedded(ptype=ptype.classname,fqpn=postable.basic.fqin)
            userq.update(safe_update=True, push__postablesin=pe, pull__postablesinvitedto=pe)
            postableq.update(safe_update=True, push__members=mefqin, pull__inviteds=mefqin)
        except:
            doabort('BAD_REQ', "Failed in user %s accepting invite to gpostable %s %s" % (mefqin, ptype.__name__, fqpn))
        me.reload()
        return me, postableq.get()

    #changes postable ownership to a 'ownerable'
    def changeOwnershipOfPostable(self, currentuser, owner, fqpn, newownerfqpn):
        "give ownership over to another user/group etc for g/a/l"
        ptype=gettype(fqpn)
        newownerptype = gettype(newownerfqpn)
        postableq=ptype.objects(basic__fqin=fqpn)
        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" % (ptype.__name__,fqpn))
        #Before anything else, make sure I own the stuff so can transfer it.
        #Bug this dosent work if useras is a group

        #useras must be member of postable
        authorize_ownable_owner(False, self, currentuser, owner, postable)

        try:
            newownerq=newownerptype.objects(basic__fqin=newownerfqpn)
            newowner=newownerq.get()
        except:
            #make sure target exists.
            doabort('BAD_REQ', "No such newowner %s %s" % (newownerptype.__name__, newownerfqpn))
        #Either as a user or a group, you must be member of group/app or app respectively to
        #transfer membership there. But what does it mean for a group to own a group. 
        #it makes sense for library and app, but not for group. Though currently let us have it
        #there. Then if a group owns a group, the person doing the changing must be owner.

        #newowner must be member of the postable (group cant own itself)
        permit(self.isMemberOfPostable(currentuser, newowner, postable), 
            " Possible new owner %s %s must be member of postable %s %s" % (newownerptype.__name__, newownerfqpn, ptype.__name__, fqpn))

       
        try:
            oldownerfqpn=postable.owner
            #if newownerptype != User:
            postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=newowner.basic.fqin)
            #else:
            #postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=newowner.basic.fqin, pull__members=oldownerfqpn)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for postable %s %s" % (oldownerfqpn, newowner.basic.fqin, ptype.__name__, fqpn))
        newowner.reload()
        postable.reload()
        return newowner, postable

    #group should be replaced by anything that can be the owner
    #dont want to use this for postables, even though they are ownable.
    def changeOwnershipOfOwnable(self, currentuser, owner, fqon, newownerfqpn):
        "this is used for things like itentypes and tagtypes, not for g/a/l"
        otype=gettype(fqon)
        newownerptype = gettype(newownerfqpn)
        oq=otype.objects(basic__fqin=fqon)
        try:
            ownable=oq.get()
        except:
            doabort('BAD_REQ', "No such ownable %s %s" % (otype.__name__,fqon))
        authorize_ownable_owner(False, self, currentuser, owner, ownable)

        try:
            newownerq=newownerptype.objects(basic__fqin=newownerfqpn)
            newowner=newownerq.get()
        except:
            #make sure target exists.
            doabort('BAD_REQ', "No such newowner %s %s" % (newownerptype.__name__, newowner.basic.fqpn))
        
        #if transferring to a group/app I better be a member of it, else I can transfer to any user.
        if newownerptype != User:
            authorize_postable_member(False, self, currentuser, owner, newowner)
      
        try:
            oldownerfqpn=ownable.owner
            ownable.update(safe_update=True, set__owner = newowner.basic.fqin)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for ownable %s %s" % (oldownerfqpn, newowner.basic.fqin, otype.__name__, fqon))
        newowner.reload()
        ownable.reload()
        return newowner, ownable

    def allUsers(self, currentuser):
        authorize_systemuser(False, self, currentuser)
        users=User.objects.all()
        return users

    def allGroups(self, currentuser):
        authorize_systemuser(False, self, currentuser)
        groups=Group.objects(personalgroup=False).all()
        return groups

    def allApps(self, currentuser):
        authorize_systemuser(False, self, currentuser)
        apps=App.objects.all()
        return apps

    def allLibraries(self, currentuser):
        authorize_systemuser(False, self, currentuser)
        libs=Library.objects.all()
        return libs

    def getGroup(self, currentuser, fqgn):
        return self.getPostable(currentuser, fqgn)

    def getApplication(self, currentuser, fqan):
        return self.getPostable(currentuser, fqan)

    def getLibrary(self, currentuser, fqln):
        return self.getPostable(currentuser, fqln)

def initialize_application(db_session):
    print Group
    currentuser=None
    whosdb=Database(db_session)
    adsgutuser=whosdb.addUser(currentuser, dict(nick='adsgut', adsid='adsgut'))
    currentuser=adsgutuser
    print "Added Initial User, this should have added private group too"
    igspec=dict(personalgroup=False, name="public", description="Public Group")
    adsgutuser, publicgrp=whosdb.addGroup(currentuser, adsgutuser, igspec)
    print "Added Initial Public group"
    adsgutuser, adsgutapp=whosdb.addApp(currentuser, adsgutuser, dict(name='adsgut', description="The MotherShip App"))
    print "Added Mothership app"
    adsuser=whosdb.addUser(currentuser, dict(nick='ads', adsid='ads'))
    print "Added ADS user", adsuser.to_json()
    currentuser=adsuser
    adsuser, adspubsapp=whosdb.addApp(currentuser, adsuser, dict(name='publications', description="ADS's flagship publication app"))
    print "ADS user added publications app"

def initialize_testing(db_session):
    print "INIT TEST"
    whosdb=Database(db_session)
    currentuser=None
    adsgutuser=whosdb.getUserForNick(currentuser, "adsgut")
    currentuser=adsgutuser
    rahuldave=whosdb.addUser(currentuser, dict(nick='rahuldave', adsid="rahuldave"))
    rahuldave, mlg=whosdb.addGroup(rahuldave, rahuldave, dict(name='ml', description="Machine Learning Group"))
    rahuldave, adspubapp=whosdb.addUserToPostable(currentuser, 'ads/app:publications', 'rahuldave')
    #rahuldave.applicationsin.append(adspubsapp)
    adsuser=whosdb.getUserForNick(currentuser, "ads")
    print "currentuser", currentuser.nick
    jayluker=whosdb.addUser(currentuser, dict(nick='jayluker', adsid="jayluker"))
    jayluker, adspubapp=whosdb.addUserToPostable(adsuser, 'ads/app:publications', 'jayluker')
    #jayluker.applicationsin.append(adspubsapp)
    print "testing invite"
    jayluker, mlg=whosdb.inviteUserToPostableUsingNick(rahuldave, 'rahuldave/group:ml', 'jayluker')
    print "invited", jayluker.to_json()

    jayluker, mlg = whosdb.acceptInviteToPostable(jayluker, 'rahuldave/group:ml', jayluker.basic.fqin)
    jayluker, spg=whosdb.addGroup(jayluker, jayluker, dict(name='sp', description="Solr Programming Group"))
    import random
    for i in range(20):
        r=random.choice([1,2])
        userstring='user'+str(i)
        user=whosdb.addUser(adsgutuser, dict(nick=userstring, adsid=userstring))
        user, adspubapp = whosdb.addUserToPostable(adsuser, 'ads/app:publications', userstring)

        if r==1:
            user, mlg=whosdb.inviteUserToPostableUsingNick(rahuldave, 'rahuldave/group:ml', userstring)
        else:
            user, spg=whosdb.inviteUserToPostableUsingNick(jayluker, 'jayluker/group:sp', userstring)
    #whosdb.addGroupToApp(currentuser, 'ads@adslabs.org/app:publications', 'adsgut@adslabs.org/group:public', None )
    #public.applicationsin.append(adspubsapp)
    #rahuldavedefault.applicationsin.append(adspubsapp)

    print "ending init", whosdb.ownerOfPostables(rahuldave, rahuldave), whosdb.ownerOfPostables(rahuldave, rahuldave, "group")
    print "=============================="
    print rahuldave.to_json(), mlg.to_json()
    print "=============================="
    print adsuser.to_json()
    print "=============================="

if __name__=="__main__":
    db_session=connect("adsgut")
    initialize_application(db_session)
    initialize_testing(db_session)