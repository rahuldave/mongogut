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
        #print "ingetuser", [e.nick for e in User.objects]
        print "nick", nick
        try:
            user=User.objects(nick=nick).get()
        except:
            doabort('NOT_FND', "User %s not found" % nick)
        return user

    def getUserForAdsid(self, currentuser, adsid):
        "gets user for adsid"
        #print "ingetuser", [e.nick for e in User.objects]
        #print "nick", nick
        try:
            user=User.objects(adsid=adsid).get()
        except:
            print "JJJJ", sys.exc_info()
            doabort('NOT_FND', "User %s not found" % adsid)
        return user

    def getUserForCookieid(self, currentuser, cookieid):
        "gets user for adsid"
        #print "ingetuser", [e.nick for e in User.objects]
        #print "nick", nick
        try:
            user=User.objects(cookieid=cookieid).get()
        except:
            print "JJJJ", sys.exc_info()
            doabort('NOT_FND', "User %s not found" % cookieid)
        return user

    def getUserForFqin(self, currentuser, userfqin):
        "gets user for nick"
        try:
            user=User.objects(basic__fqin=userfqin).get()
        except:
            doabort('NOT_FND', "User %s not found" % userfqin)
        return user

    def getMemberableForFqin(self, currentuser, mtype, memberfqin):
        "gets user for nick"
        try:
            member=mtype.objects(basic__fqin=memberfqin).get()
        except:
            doabort('NOT_FND', "User %s not found" % memberfqin)
        return member

    #this one is PROTECTED
    def getUserInfo(self, currentuser, nick):
        "gets user for nick only if you are superuser or that user"
        user=self.getUserForNick(currentuser, nick)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, user)
        return user

    def getUserInfoFromAdsid(self, currentuser, adsid):
        "gets user for nick only if you are superuser or that user"
        user=self.getUserForAdsid(currentuser, adsid)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, user)
        return user


    #MEMBABLE AND POSTABLE interfaces. Postables are subsets of membables

    #generally, membable interface will only be internally used in postable functions
    #or for tagging. So I wont expose external functions to start with, and as we
    #go along, I will make sure to.

    def getMembable(self, currentuser, fqmn):
        "gets the membable corresponding to the fqpn"
        mtype=gettype(fqmn)
        try:
            membable=mtype.objects(basic__fqin=fqmn).get()
        except:
            doabort('NOT_FND', "%s %s not found" % (classname(mtype), fqmn))
        return membable

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
        print "AUTHING", currentuser.nick, memberable.nick
        authorize_postable_member(MEMBER_OF_POSTABLE, self, currentuser, memberable, postable)
        print "GOT HERE"
        owner = self.getUserForFqin(currentuser, postable.owner)
        creator = self.getUserForFqin(currentuser, postable.basic.creator)
        return postable, owner, creator

    #using MEMBERABLE interface. this one is unprotected
    #also returns true if a user is a member of a postable(say a group), which is a member
    #of this postable. Also works if the memberable is a postable itself, through the memberable.basic.fqin interface

    #BUG other membable things need to be added, as needed

    def isMemberOfMembable(self, currentuser, memberable, membable, memclass=MEMBABLES):
        "is the memberable a member of membable"
        #this is the slow way to do it. BUG.
        members=membable.get_member_fqins()
        if memberable.basic.fqin in members:
            return True
        for mem in members:
            ptype=gettype(mem)
            if  ptype in memclass:
                pos=self.getMembable(currentuser, mem)
                if memberable.basic.fqin in pos.get_member_fqins():
                    return True
        return False

    def isMemberOfPostable(self, currentuser, memberable, postable):
        "is the memberable a member of postable"
        return self.isMemberOfMembable(currentuser, memberable, postable, POSTABLES)

    #Also checks for membership!
    def canIPostToPostable(self, currentuser, memberable, postable, memclass=MEMBABLES):
        "is the memberable a member of postable"
        if self.isOwnerOfPostable(currentuser, memberable, postable):
            return True
        rws=postable.get_member_rws()
        print "P", postable.basic.fqin, "M", memberable.basic.fqin
        start=False
        if memberable.basic.fqin in rws.keys():
            print "here", rws.keys()
            start = start or rws[memberable.basic.fqin][1]
        print "there", rws.keys()
        #goes down membership list here
        for mem in rws.keys():
            ptype=gettype(mem)
            if  ptype in memclass:
                pos=self.getMembable(currentuser, mem)
                posmembers=pos.get_member_fqins()
                if memberable.basic.fqin in posmembers:
                    start = start or rws[mem][1]
        return start

    #using MEMBERABLE/OWNABLE:this can let a group be owner of the ownable, as long as its 'fqin' is in the owner field.
    #this one is unprotected
    def isOwnerOfOwnable(self, currentuser, memberable, ownable):
        "is memberable the owner of ownerable? ownerable is postable plus others"
        print "in IOOO", currentuser.basic.fqin, memberable.basic.fqin, ownable.basic.fqin, ownable.owner
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
        if memberable.basic.fqin in [m.fqmn for m in membable.inviteds]:
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
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables if e['ptype']==ptypestr]
        else:
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables]
        return postables

    #unprotected
    #BUG just for user currently. Dosent work for other memberables
    def postablesForUser(self, currentuser, useras, ptypestr=None):
        "return the postables the user is a member of"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesin
        if ptypestr:
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables if e['ptype']==ptypestr]
        else:
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables]
        return postables

    def postablesUserCanAccess(self, currentuser, useras, ptypestr=None):
        "return the postables the user is a member of"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        nlibpostables = useras.postablesnotlibrary()
        otherpostables = useras.postableslibrary()
        allpostables = nlibpostables + otherpostables
        if ptypestr:
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables if e['ptype']==ptypestr]
        else:
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables]
        return postables

    def postablesUserCanWriteTo(self, currentuser, useras, ptypestr=None):
        "return the postables the user is a member of"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        nlibpostables = useras.postablesnotlibrary()
        otherpostables = useras.postableslibrary()
        allpostables = nlibpostables + otherpostables
        if ptypestr:
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables if (e['ptype']==ptypestr and e['readwrite']==True)]
        else:
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables if e['readwrite']==True]
        return postables


    #unprotected
    #invitations only work for users for now.
    def postableInvitesForUser(self, currentuser, useras, ptypestr=None):
        "given a user, find their invitations to postables"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesinvitedto
        if ptypestr:
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables if e['ptype']==ptypestr]
        else:
            postables=[{'fqpn':e['fqpn'],'ptype':e['ptype']} for e in allpostables]
        return postables

    #unprotected
    #user/memberable may be member through another memberable
    #this will give just those memberables, and not their expansion: is that ok? i think so
    def membersOfPostable(self, currentuser, memberable, postable):
        "is user or memberable a member of the postable?"
        #i need to have access to this if i come in through being a member of a memberable which is a member
        #authorize_postable member takes care of this. That memberable is NOT the same memberable in the arguments here
        authorize_postable_member(False, self, currentuser, memberable, postable)
        print "CU", currentuser.nick, memberable.nick
        if self.isOwnerOfPostable(currentuser, memberable, postable):
            print "IS OWNER"
            perms=postable.get_member_rws()
        else:
            perms=postable.get_member_rws()
            for k in perms.keys():
                perms[k][1]=''
        return perms

    def membersOfPostableFromFqin(self, currentuser, memberable, fqpn):
        postable=self.getPostable(currentuser, fqpn)
        return self.membersOfPostable(currentuser, memberable, postable)

    #Needs owner or superuser access. currently useras must be a user
    def invitedsForPostable(self, currentuser, useras, postable):
        "is user or memberable a member of the postable?"
        #i need to have access to this if i come in through being a member of a memberable which is a member
        #authorize_postable member takes care of this. That memberable is NOT the same memberable in the arguments here
        authorize_postable_owner(False, self, currentuser, useras, postable)
        inviteds=postable.get_invited_rws()
        return inviteds

    def invitedsForPostableFromFqin(self, currentuser, memberable, fqpn):
        postable=self.getPostable(currentuser, fqpn)
        return self.invitedsForPostable(currentuser, memberable, postable)
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
        if not userspec['adsid']=='adsgut':
            authorize_systemuser(False, self, currentuser)
        try:
            userspec=augmentspec(userspec)
            newuser=User(**userspec)
            newuser.save(safe=True)
        except:
            print sys.exc_info()
            doabort('BAD_REQ', "Failed adding user %s" % userspec['adsid'])

        #BUG: more leakage here in bootstrap
        if userspec['adsid']=='adsgut':
            currentuser=newuser

        #Also add user to private default group and public group

        #currentuser adds this as newuser
        #print adding default personal group

        #BUG:CHANGED: is this ok?
        # self.addPostable(currentuser, newuser, "group", dict(name='default', creator=newuser.basic.fqin,
        #     personalgroup=True
        # ))
        self.addPostable(currentuser, newuser, "group", dict(name='default', creator=newuser.basic.fqin,
            personalgroup=True
        ))
        #currentuser adds this as root
        if not userspec['adsid']=='adsgut':
            self.addMemberableToPostable(currentuser, currentuser, 'adsgut/group:public', newuser.basic.fqin)
        #BUG:Bottom ought to be done via routing
        #self.addUserToApp(currentuser, 'ads@adslabs.org/app:publications', newuser, None)
        #should this be also done by routing?
        #This is also added as root
        if not userspec['adsid']=='adsgut':
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
            newpe=PostableEmbedded(ptype=ptypestr,fqpn=newpostable.basic.fqin, pname = newpostable.presentable_name(), readwrite=True, description=newpostable.basic.description)
            res=userq.update(safe_update=True, push__postablesowned=newpe)
            #print "result", res, currentuser.groupsowned, currentuser.to_json()
            
        except:
            doabort('BAD_REQ', "Failed adding postable %s %s" % (ptype.__name__, postablespec['basic'].fqin))
        #BUG changerw must be appropriate here!
        self.addMemberableToPostable(currentuser, useras, newpostable.basic.fqin, newpostable.basic.creator, changerw=False, ownermode=True)
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
    def addMemberableToPostable(self, currentuser, useras, fqpn, memberablefqin, changerw=False, ownermode=False):
        "add a user, group, or app to a postable=group, app, or library"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        print "types in AMTP", fqpn, ptype, memberablefqin,mtype
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
            print "Adding to POSTABLE ", memberable.basic.fqin, postable.basic.fqin, currentuser.basic.fqin, useras.basic.fqin
            #special case so any user can add themselves to public group
            #permit(self.isOwnerOfGroup(currentuser, grp) or self.isSystemUser(currentuser), "User %s must be owner of group %s or systemuser" % (currentuser.nick, grp.fqin))
            authorize_postable_owner(False, self, currentuser, useras, postable)
        try:
            if ownermode:
                rw=True
            else:
                if not changerw:
                    rw=RWDEFMAP[ptype]
                else:
                    rw= (not RWDEFMAP[ptype])
            pe=PostableEmbedded(ptype=ptype.classname,fqpn=postable.basic.fqin, pname = postable.presentable_name(), readwrite=rw, description=postable.basic.description)
            memberableq.update(safe_update=True, push__postablesin=pe)
            memb=MembableEmbedded(mtype=mtype.classname, fqmn=memberablefqin, readwrite=rw, pname = memberable.presentable_name())
            postableq.update(safe_update=True, push__members=memb)
        except:
            doabort('BAD_REQ', "Failed adding memberable %s %s to postable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        memberable.reload()
        return memberable, postableq.get()

    #because this is used along with other membership apply/decline funcs, we will go with memberable
    #as opposed to memberablefqin
    def toggleRWForMembership(self, currentuser, useras, fqpn, memberable):
        ptype=gettype(fqpn)
        memberablefqin=memberable.basic.fqin
        mtype=gettype(memberablefqin)
        print "types", fqpn, ptype, memberablefqin,mtype
        postableq=ptype.objects(basic__fqin=fqpn)
        #memberableq=mtype.objects(basic__fqin=memberablefqin)
        
        #BUG currently restricted admission. Later we will want groups and apps proxying for users.
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        try:
            postable=postableq.get()
            #memberable=memberableq.get()
        except:
            doabort('BAD_REQ', "No such unique memberable %s %s postable %s %s" %  (mtype.__name__, memberablefqin, ptype.__name__,fqpn))
        members=postable.members
        postables=memberable.postablesin
        #BUG make faster by using a mongo search
        #REAL BIG BUG: need to flip on both
        for me in members:
            if me.fqmn==memberablefqin:
                me.readwrite = (not me.readwrite)
        for p in postables:
            if p.fqpn==fqpn:
                p.readwrite = (not p.readwrite)
        #CHECK: does this make the change we want, or do we need explicit update?
        #postableq.update(safe_update=True)
        #memberableq.update(safe_update=True)
        postable.save(safe=True)
        memberable.save(safe=True)
        return memberable, postable

    def addUserToPostable(self, currentuser, fqpn, nick):
        user=self.getUserForNick(currentuser,nick)
        return self.addMemberableToPostable(currentuser, currentuser, fqpn, user.basic.fqin)

    #BUG: not really fleshed out as we need to handle refcounts and all that to see if objects ought to be removed.
    #Completely falls over. need appropriate readwrites.
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
            memberableq.update(safe_update=True, pull__postablesin__fqpn=postable.basic.fqin)
            #buf not sure how removing embedded doc works, if at all
            postableq.update(safe_update=True, pull__members__fqmn=memberablefqin)
        except:
            doabort('BAD_REQ', "Failed removing memberable %s %s from postable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        return OK

    #BUG: there is no restriction here of what can be added to what in memberables and postables
    #CHECK: why not use this generally? why separate for postables/ this seems to be used only for Tag. BUG: combine code is possible
    def addMemberableToMembable(self, currentuser, useras, fqpn, memberablefqin, changerw=False):
        "add a user, group, or app to a postable=group, app, or library"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        #BUG: need exception handling here, also want to make sure no strange fqins are accepted
        membableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(basic__fqin=memberablefqin)
        memberable = memberableq.get()
        try:
            if not changerw:
                rw=RWDEFMAP[ptype]
            else:
                rw= (not RWDEFMAP[ptype])
            memb=MembableEmbedded(mtype=mtype.classname, fqmn=memberablefqin, readwrite=rw, pname = memberable.presentable_name())
            membableq.update(safe_update=True, push__members=memb)
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
            membableq.update(safe_update=True, pull__members__fqmn=memberablefqin)
        except:
            doabort('BAD_REQ', "Failed removing memberable %s %s from postable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        return OK


    #do we want to use this for libraries? why not? Ca we invite other memberables?
    def inviteUserToPostable(self, currentuser, useras, fqpn, user, changerw=False):
        "invite a user to a postable."
        ptype=gettype(fqpn)
        postable=self.getPostable(currentuser, fqpn)
        usertobeaddedfqin=user.basic.fqin
        if usertobeaddedfqin==useras.basic.fqin:
            doabort('BAD_REQ', "Failed inviting user %s to postable %s as cant invite owner" % (usertobeaddedfqin, fqpn))
        # userq= User.objects(basic__fqin=usertobeaddedfqin)
        # try:
        #     user=userq.get()
        # except:
        #     doabort('BAD_REQ', "No such user %s" % usertobeaddedfqin)
        authorize_postable_owner(False, self, currentuser, useras, postable)
        try:
            if not changerw:
                rw=RWDEFMAP[ptype]
            else:
                rw= (not RWDEFMAP[ptype])
            pe=PostableEmbedded(ptype=ptype.classname,fqpn=postable.basic.fqin, pname = postable.presentable_name(), readwrite=rw, description=postable.basic.description)
            user.update(safe_update=True, push__postablesinvitedto=pe)
            memb=MembableEmbedded(mtype=User.classname, fqmn=usertobeaddedfqin, readwrite=rw, pname = user.presentable_name())
            #BUG: ok to use fqin here instead of getting from oblect?
            print "LLL", pe.to_json(), memb.to_json(), "+++++++++++++"
            print postable.to_json()
            postable.update(safe_update=True, push__inviteds=memb)
            #print "userq", userq.to_json()
        except:
            doabort('BAD_REQ', "Failed inviting user %s to postable %s" % (usertobeaddedfqin, fqpn))
        #print "IIIII", userq.get().groupsinvitedto
        postable.reload()
        user.reload()
        return user, postable

    def inviteUserToPostableUsingNick(self, currentuser, fqpn, nick, changerw=False):
        "invite a user to a postable."
        user=self.getUserForNick(currentuser,nick)
        return self.inviteUserToPostable(currentuser, currentuser, fqpn, user, changerw)

    def inviteUserToPostableUsingAdsid(self, currentuser, fqpn, adsid, changerw=False):
        "invite a user to a postable."
        user=self.getUserForAdsid(currentuser,adsid)
        return self.inviteUserToPostable(currentuser, currentuser, fqpn, user, changerw)

    #this cannot be masqueraded, must be explicitly approved by user
    #can we do without the mefqin?
    def acceptInviteToPostable(self, currentuser, fqpn, me):
        "do i accept the invite?"
        ptype=gettype(fqpn)
        postableq=ptype.objects(basic__fqin=fqpn)
        # userq= User.objects(basic__fqin=mefqin)
        # try:
        #     me=userq.get()
        # except:
        #     doabort('BAD_REQ', "No such user %s" % mefqin)
        mefqin=me.basic.fqin
        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" % (ptype.__name__,fqpn))
        authorize(False, self, currentuser, me)
        permit(self.isInvitedToPostable(currentuser, me, postable), "User %s must be invited to postable %s %s" % (mefqin, ptype.__name__,fqpn))
        try:
            inviteds=postable.inviteds
            memb=None
            for inv in inviteds:
                if inv.fqmn==mefqin:
                    memb=inv
            pe=None
            for uinv in me.postablesinvitedto:
                if uinv.fqpn==fqpn:
                    pe=uinv
            if memb==None or pe==None:
                doabort('BAD_REQ', "User %s was never invited to postable %s %s" % (mefqin, ptype.__name__, fqpn))
            me.update(safe_update=True, push__postablesin=pe, pull__postablesinvitedto__fqpn=pe.fqpn)
            postableq.update(safe_update=True, push__members=memb, pull__inviteds__fqmn=memb.fqmn)
        except:
            doabort('BAD_REQ', "Failed in user %s accepting invite to gpostable %s %s" % (mefqin, ptype.__name__, fqpn))
        me.reload()
        return me, postableq.get()

    def acceptInviteToPostableUsingNick(self, currentuser, fqpn, nick):
        "invite a user to a postable."
        user=self.getUserForNick(currentuser,nick)
        return self.acceptInviteToPostable(currentuser, fqpn, user)

    def acceptInviteToPostableUsingNiAdsid(self, currentuser, fqpn, adsid):
        "invite a user to a postable."
        user=self.getUserForNick(currentuser,adsid)
        return self.acceptInviteToPostable(currentuser, fqpn, user)

    #changes postable ownership to a 'ownerable'
    #USER must be owner! This CAN happen through membership in a member group.
    def changeOwnershipOfPostable(self, currentuser, owner, fqpn, newowner):
        "give ownership over to another user for g/a/l"
        ptype=gettype(fqpn)
        postableq=ptype.objects(basic__fqin=fqpn)
        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" % (ptype.__name__,fqpn))
        #Before anything else, make sure I own the stuff so can transfer it.
        #Bug this dosent work if useras is a group

        #useras must be member of postable
        authorize_postable_owner(False, self, currentuser, owner, postable)

        # try:
        #     newowner=self.getUserForFqin(currentuser, newownerfqin)
        # except:
        #     #make sure target exists.
        #     doabort('BAD_REQ', "No such newowner %s" % newownerfqin)
        newownerfqin=newowner.basic.fqin
        #Either as a user or a group, you must be member of group/app or app respectively to
        #transfer membership there. But what does it mean for a group to own a group. 
        #it makes sense for library and app, but not for group. Though currently let us have it
        #there. Then if a group owns a group, the person doing the changing must be owner.

        #newowner must be member of the postable (group cant own itself)
        permit(self.isMemberOfPostable(currentuser, newowner, postable), 
            " Possible new owner %s %s must be member of postable %s %s" % (newownertype.__name__, newownerfqin, ptype.__name__, fqpn))
        #BUG new orners rwmode must be  true!
        #we have removed the possibility of group ownership of postables. CHECK. I've removed the push right now as i assume new owner
        #must be a member of postable. How does this affect tag ownership if at all?
        try:
            oldownerfqpn=postable.owner
            members=postable.members
            memb=MembableEmbedded(mtype=User.classname, fqmn=newowner.basic.fqin, readwrite=True, pname = newowner.presentable_name())
            pe=PostableEmbedded(ptype=ptype.classname,fqpn=postable.basic.fqin, pname = postable.presentable_name(), readwrite=True, description=postable.basic.description)
            #find new owner as member, locate in postable his membership, update it with readwrite if needed, and make him owner
            #add embedded postable to his ownership and his membership
            postableq.filter(members__fqmn=newowner.basic.fqin).update_one(safe_update=True, set__owner = newowner.basic.fqin, set__members_S=memb)
            newownerq.filter(postablesin__fqpn==fqpn).update_one(safe_update=True, set__postablesin_S=pe)
            newowner.update(safe_update=True, push__postablesowned=pe)
            #for old owner we have removed ownership by changing owner, now remove ownership from him
            owner.update(safe_update=True, pull__postablesowned__fqpn=fqpn)
            #if newownertype != User:
            #
            #postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=memb)
            #else:
            #postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=newowner.basic.fqin, pull__members=oldownerfqpn)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for postable %s %s" % (oldownerfqpn, newowner.basic.fqin, ptype.__name__, fqpn))
        newowner.reload()
        postable.reload()
        owner.reload()
        return newowner, postable

    def changeDescriptionOfPostable(self, currentuser, owner, fqpn, description):
        "give ownership over to another user for g/a/l"
        ptype=gettype(fqpn)
        postableq=ptype.objects(basic__fqin=fqpn)
        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" % (ptype.__name__,fqpn))
        #Before anything else, make sure I own the stuff so can transfer it.
        #Bug this dosent work if useras is a group

        #useras must be member of postable
        authorize_postable_owner(False, self, currentuser, owner, postable)

        
        try:
            pe=PostableEmbedded(ptype=ptype.classname,fqpn=postable.basic.fqin, pname = postable.presentable_name(), readwrite=True, description=description)
            #find new owner as member, locate in postable his membership, update it with readwrite if needed, and make him owner
            #add embedded postable to his ownership and his membership
            postableq.update_one(safe_update=True, set__basic__description=description)
            owner.update(safe_update=True, pull__postablesowned__fqpn=fqpn)
            owner.update(safe_update=True, push__postablesowned=pe)

            #if newownertype != User:
            #
            #postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=memb)
            #else:
            #postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=newowner.basic.fqin, pull__members=oldownerfqpn)
        except:
            doabort('BAD_REQ', "Failed changing owner description for postable %s %s" % ( ptype.__name__, fqpn))
        owner.reload()
        postable.reload()
        return owner, postable

    #group should be replaced by anything that can be the owner
    #dont want to use this for postables, even though they are ownable.
    #This is where we deal with TAG's. Check. BUG: also combine with above for non repeated code.
    #tags are membables, we dont check that here. Ought it be done with postables?
    #and do we have use cases for tag ownership changes, as opposed to tagtypes and itemtypes?
    def changeOwnershipOfOwnable(self, currentuser, owner, fqon, newowner):
        "this is used for things like itentypes and tagtypes, not for g/a/l. Also for tags?"
        otype=gettype(fqon)
        oq=otype.objects(basic__fqin=fqon)
        try:
            ownable=oq.get()
        except:
            doabort('BAD_REQ', "No such ownable %s %s" % (otype.__name__,fqon))
        authorize_ownable_owner(False, self, currentuser, owner, ownable)

        # try:
        #     newowner=self.getUserForFqin(currentuser, newownerfqin)
        # except:
        #     #make sure target exists.
        #     doabort('BAD_REQ', "No such newowner %s" % newownerfqin)
        newownerfqin=newowner.basic.fqin
        permit(self.isMemberOfMembable(currentuser, newowner, ownable), 
            " Possible new owner %s %s must be member of ownable %s %s" % (newownertype.__name__, newownerfqin, ptype.__name__, fqpn))
        try:
            oldownerfqpn=ownable.owner
            memb=MembableEmbedded(mtype=User.classname, fqmn=newowner.basic.fqin, readwrite=True, pname = newowner.presentable_name())
            oq.filter(members__fqmn=newowner.basic.fqin).update_one(safe_update=True, set__owner = newowner.basic.fqin, set__members_S=memb)
            #ownable.update(safe_update=True, set__owner = newowner.basic.fqin)
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

    def getApp(self, currentuser, fqan):
        return self.getPostable(currentuser, fqan)

    def getLibrary(self, currentuser, fqln):
        return self.getPostable(currentuser, fqln)

def initialize_application(db_session):
    print Group
    currentuser=None
    whosdb=Database(db_session)
    adsgutuser=whosdb.addUser(currentuser, dict(nick='adsgut', adsid='adsgut'))
    currentuser=adsgutuser
    print "11111 Added Initial User, this should have added private group too"
    igspec=dict(personalgroup=False, name="public", description="Public Group")
    adsgutuser, publicgrp=whosdb.addGroup(adsgutuser, adsgutuser, igspec)
    print "22222 Added Initial Public group"
    adsgutuser, adsgutapp=whosdb.addApp(adsgutuser, adsgutuser, dict(name='adsgut', description="The MotherShip App"))
    print "33333 Added Mothership app"
    anonymouseuser=whosdb.addUser(adsgutuser, dict(nick='anonymouse', adsid='anonymouse'))
    adsuser=whosdb.addUser(adsgutuser, dict(nick='ads', adsid='ads'))
    print "44444 Added ADS user", adsuser.to_json()
    currentuser=adsuser
    adsuser, adspubsapp=whosdb.addApp(adsuser, adsuser, dict(name='publications', description="ADS's flagship publication app"))
    print "55555 ADS user added publications app"


def initialize_testing(db_session):
    print "INIT TEST"
    whosdb=Database(db_session)
    currentuser=None
    adsgutuser=whosdb.getUserForNick(currentuser, "adsgut")
    currentuser=adsgutuser
    adsuser=whosdb.getUserForNick(currentuser, "ads")

    rahuldave=whosdb.addUser(adsgutuser, dict(nick='rahuldave', adsid="rahuldave@gmail.com", cookieid='4df7ce0d06'))
    rahuldave, mlg=whosdb.addGroup(rahuldave, rahuldave, dict(name='ml', description="Machine Learning Group"))
    rahuldave, mll=whosdb.addLibrary(rahuldave, rahuldave, dict(name='mll', description="Machine Learning Library"))
    #why does currentuser below need to be adsgutuser?
    rahuldave, adspubapp=whosdb.addUserToPostable(adsuser, 'ads/app:publications', 'rahuldave')
    #rahuldave.applicationsin.append(adspubsapp)
    
    print "currentuser", currentuser.nick
    jayluker=whosdb.addUser(currentuser, dict(nick='jayluker', adsid="jayluker@gmail.com"))
    jayluker, adspubapp=whosdb.addUserToPostable(adsuser, 'ads/app:publications', 'jayluker')
    #jayluker.applicationsin.append(adspubsapp)
    print "GAGAGAGAGAGA", adspubapp.to_json()
    jayluker, mlg=whosdb.inviteUserToPostableUsingNick(rahuldave, 'rahuldave/group:ml', 'jayluker')
    print "invited", jayluker.to_json()

    jayluker, mlg = whosdb.acceptInviteToPostable(jayluker, 'rahuldave/group:ml', jayluker)
    jayluker, spg=whosdb.addGroup(jayluker, jayluker, dict(name='sp', description="Solr Programming Group"))
    jayluker, gpg=whosdb.addGroup(jayluker, jayluker, dict(name='gp', description="Gaussian Process Group"))
    jayluker, spl=whosdb.addLibrary(jayluker, jayluker, dict(name='spl', description="Solr Programming Library"))
    jayluker, mpl=whosdb.addLibrary(jayluker, jayluker, dict(name='mpl', description="Mongo Programming Library"))
    rahuldave, mpl=whosdb.inviteUserToPostableUsingNick(jayluker, 'jayluker/library:mpl', 'rahuldave')
    rahuldave, gpg=whosdb.inviteUserToPostableUsingNick(jayluker, 'jayluker/group:gp', 'rahuldave')
    rahuldave, spg=whosdb.addUserToPostable(jayluker, 'jayluker/group:sp', 'rahuldave')
    u, p =whosdb.addMemberableToPostable(jayluker, jayluker, 'jayluker/library:spl', 'rahuldave/group:ml', True)
    print "GEEEE", u, p
    import random
    for i in range(20):
        r=random.choice([1,2])
        userstring='user'+str(i)
        user=whosdb.addUser(adsgutuser, dict(adsid=userstring))
        user, adspubapp = whosdb.addUserToPostable(adsuser, 'ads/app:publications', user.nick)

        if r==1:
            user, mlg=whosdb.inviteUserToPostableUsingNick(rahuldave, 'rahuldave/group:ml', user.nick)
            print "==================================================================================================="
        else:
            user, spg=whosdb.inviteUserToPostableUsingNick(jayluker, 'jayluker/group:sp', user.nick)
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