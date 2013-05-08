from classes import *
import config
from permissions import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser
from permissions import authorize_ownable_owner, authorize_postable_member
from errors import abort, doabort, ERRGUT
import types

OK=200
LOGGEDIN_A_SUPERUSER_O_USERAS=False
MEMBER_OF_POSTABLE=False
POSTABLES=[Group, App, Library]#things that can be posted to, and you can be a member of
MEMBERABLES=[Group, App, User]#things that can be members
#above all use nicks
OWNABLES=[Group, App, Library, ItemType, TagType]#things that can be owned
#OWNERABLES=[Group, App, User]#things that can be owners. Do we need a shadow owner?
#the above all have nicks
#TAGGISH=[Group, App, Library, Tag]: or should it be PostingDoc, TaggingDoc?
MAPDICT={
    'group':Group,
    'app':App,
    'user':User,
    'library':Library
}


def augmentspec(specdict, spectype='user'):
    basicdict={}
    print "INSPECDICT", specdict
    spectypestring = spectype.classname
    if spectype in POSTABLES:
        specdict['owner']=specdict['creator']
        basicdict['creator']=specdict['creator']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        basicdict['fqin']=specdict['creator']+"/"+spectypestring+":"+specdict['name']
        specdict['nick']=basicdict['fqin']
    elif spectype==User:
        basicdict['creator']="adsgut"
        basicdict['description']=specdict.get('description','')
        basicdict['fqin']=specdict['creator']+"/"+spectypestring+":"+specdict['nick']
    specdict['basic']=Basic(**basicdict)
    
    del specdict['name']
    del specdict['creator']
    if specdict.has_key('description'):
        del specdict['description']
    return specdict

def classname(instance):
    return type(instance).__name__

def classtype(instance):
    return type(instance)

def getNSTypeName(fqin):
    ns, val=fqin.split(':')
    nslist=ns.split('/')
    nstypename=nslist[-1]

def gettype(fqin):
    return classtype(MAPDICT[getNSTypeName(fqin)])


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
        try:
            user=User.objects(nick=nick).get()
        except:
            doabort('NOT_FND', "User %s not found" % nick)
        return user

    #this one is PROTECTED
    def getUserInfo(self, currentuser, nick):
        "gets user for nick only if you are superuser or that user"
        user=self.getUserForNick(currentuser, nick)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, user)
        return user


    #POSTABLE interface

    #this one is unprotected
    def getPostable(self, currentuser, fqpn):
        "gets the postable corresponding to the fqpn"
        ptype=gettype(fqpn)
        try:
            postable=ptype.objects(basic__fqin=fqpn)
        except:
            doabort('NOT_FND', "%s %s not found" % (classname(ptype), fqpn))
        return postable

    #this one is protected
    def getPostableInfo(self, currentuser, memberable, fqpn):
        "gets postable only if you are member of the postable"
        postable=self.getPostable(currentuser, fqpn)
        #BUG:this should work for a user member of postable as well as a memberable member of postable
        authorize_postable_member(MEMBER_OF_POSTABLE, self, currentuser, memberable, postable)
        return postable

    #using MEMBERABLE interface. this one is unprotected
    #also returns true if a user is a member of a postable(say a group), which is a member
    #of this postable. Also works if the memberable is a postable itself, through the nick interface
    def isMemberOfPostable(self, currentuser, memberable, postable):
        "is the memberable a member of postable"
        if memberable.nick in postable.members:
            return True
        for mem in postable.members:
            ptype=gettype(mem)
            if  ptype in POSTABLES:
                pos=self.getPostable(currentuser, mem)
                if memberable.nick in pos.members:
                    return True
        return False


    #using MEMBERABLE/OWNABLE:this can let a group be owner of the ownable, as long as its 'nick' is in the owner field.
    #this one is unprotected
    def isOwnerOfOwnable(self, currentuser, memberable, ownable):
        "is memberable the owner of ownerable? ownerable is postable plus others"
        if memberable.nick==ownable.owner:
            return True
        else:        
            return False

    #defined this just for completion, and in code, it will be easier to read, unprotected
    def isOwnerOfPostable(self, currentuser, memberable, postable):
        return self.isOwnerOfOwnable(currentuser, memberable, postable)

    #invitations only work for users for now, even tho we have a memberable. unprotected
    def isInvitedToPostable(self, currentuser, memberable, postable):
        "is the user invited to the postable?"
        if memberable.nick in postable.inviteds:
            return True
        else:
            return False

    #unprotected
    #BUG just for user currently. Dosent work for other memberables. Is not transitive
    #so that a postable is listed for the owner of the memberable
    def ownerOfPostables(self, currentuser, useras, ptype=None):
        "return the postables the user is an owner of"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesowned
        if ptype:
            postables=[e['fqpn'] for e in allpostables if e['ptype']==ptype]
        else:
            postables=allpostables
        return postables

    #unprotected
    #BUG just for user currently. Dosent work for other memberables
    def postablesForUser(self, currentuser, useras, ptype=None):
        "return the postables the user is a member of"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesin
        if ptype:
            postables=[e['fqpn'] for e in allpostables if e['ptype']==ptype]
        else:
            postables=allpostables
        return postables

    #unprotected
    #invitations only work for users for now.
    def postableInvitesForUser(self, currentuser, useras, ptype=None):
        "given a user, find their invitations to postables"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesinvitedto
        if ptype:
            postables=[e['fqpn'] for e in allpostables if e['ptype']==ptype]
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
        authorize_systemuser(False, self, currentuser)
        try:
            userspec=augmentspec(userspec)
            newuser=User(**userspec)
            newuser.save(safe=True)
        except:
            doabort('BAD_REQ', "Failed adding user %s" % userspec['nick'])
        #Also add user to private default group and public group
        self.addPostable(currentuser, newuser, Group, dict(name='default', creator=newuser.nick,
            personalgroup=True
        ))
        self.addMemberableToPostable(currentuser, currentuser, 'adsgut/group:public', newuser.nick)
        #BUG:Bottom ought to be done via routing
        #self.addUserToApp(currentuser, 'ads@adslabs.org/app:publications', newuser, None)
        #should this be also done by routing?
        self.addMemberableToPostable(currentuser, currentuser, App, 'adsgut/app:adsgut', User, newuser.nick)
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

    def addPostable(self, currentuser, useras, ptype, postablespec):
        "the useras adds a postable. currently either currentuser=superuser or useras"
        #authorize(False, self, currentuser, currentuser)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        postablespec=augmentspec(postablespec, ptype)
        try:
            newpostable=ptype(**groupspec)
            newpostable.save(safe=True)
            #how to save it together?
            userq= User.objects(nick=newpostable.owner)
            newpe=PostableEmbedded(ptype=ptype,fqpn=newpostable.basic.fqin)
            res=userq.update(safe_update=True, push__postablesowned=newpe)
            #print "result", res, currentuser.groupsowned, currentuser.to_json()
        except:
            doabort('BAD_REQ', "Failed adding postable %s %s" % (ptype.__name__, postablespec['basic'].fqin))
        self.addMemberableToPostable(currentuser, useras, newpostable.basic.fqin, newpostable.basic.creator)
        return newpostable

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
    def addMemberableToPostable(self, currentuser, useras, fqpn, memberablenick):
        "add a user, group, or app to a postable=group, app, or library"
        ptype=gettype(fqpn)
        mtype=gettype(memberablenick)
        postableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(nick=memberablenick)
        #BUG currently restricted admission. Later we will want groups and apps proxying for users.
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" %  (ptype.__name__,fqpn))

        if fqpn!='adsgut/group:public':
            #special case so any user can add themselves to public group
            #permit(self.isOwnerOfGroup(currentuser, grp) or self.isSystemUser(currentuser), "User %s must be owner of group %s or systemuser" % (currentuser.nick, grp.fqin))
            authorize_ownable_owner(False, self, currentuser, None, postable)
        try:
            pe=PostableEmbedded(ptype=ptype,fqpn=postable.basic.fqin)
            memberableq.update(safe_update=True, push__postablesin=pe)
            postableq.update(safe_update=True, push__members=memberablenick)
        except:
            doabort('BAD_REQ', "Failed adding memberable %s %s to postable %s %s" % (mtype.__name__, memberablenick, ptype.__name__, fqpn))
        return usertobeaddednick

    #BUG: not really fleshed out as we need to handle refcounts and all that to see if objects ought to be removed.
    def removeMemberableFromPostable(self, currentuser, fqpn, memberablenick):
        "remove a u/g/a from a g/a/l"
        ptype=gettype(fqpn)
        mtype=gettype(memberablenick)
        postableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(nick=usertoberemovednick)

        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such group %s" % fqgn)
        authorize_ownable_owner(False, self, currentuser, None, postable)
        try:
            pe=PostableEmbedded(ptype=ptype,fqpn=postable.basic.fqin)
            memberableq.update(safe_update=True, pull_postablesin=pe)
            postableq.update(safe_update=True, pull__members=memberablenick)
        except:
            doabort('BAD_REQ', "Failed removing memberable %s %s from postable %s %s" % (mtype.__name__, memberablenick, ptype.__name__, fqpn))
        return OK


    #do we want to use this for libraries? why not? Ca we invite other memberables?
    def inviteUserToPostable(self, currentuser, useras, fqpn, usertobeaddednick):
        "invite a user to a postable."
        ptype=gettype(fqpn)
        postable=self.getPostable(currentuser, fqpn)
        userq= User.objects(nick=usertobeaddednick)
        authorize_ownable_owner(False, self, currentuser, useras, postable)
        try:
            pe=PostableEmbedded(ptype=ptype,fqpn=postable.basic.fqin)
            userq.update(safe_update=True, push__postablesinvitedto=pe)
        except:
            doabort('BAD_REQ', "Failed inviting user %s to group %s" % (usertobeadded.nick, fqgn))
        #print "IIIII", userq.get().groupsinvitedto
        return usertobeaddednick

    #this cannot be masqueraded, must be explicitly approved by user
    #can we do without the menick?
    def acceptInviteToPostable(self, currentuser, fqpn, menick):
        "do i accept the invite?"
        ptype=gettype(fqpn)
        postableq=ptype.objects(basic__fqin=fqpn)
        userq= User.objects(nick=menick)
        try:
            me=userq.get()
        except:
            doabort('BAD_REQ', "No such user %s" % menick)
        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" % (ptype.__name__,fqpn))
        authorize(False, self, currentuser, me)
        permit(self.isInvitedToPostable(currentuser, me, postable.basic.fqin), "User %s must be invited to postable %s %s" % (menick, ptype.__name__,fqpn))
        try:
            pe=PostableEmbedded(ptype=ptype,fqpn=postable.basic.fqin)
            userq.update(safe_update=True, push__postablesin=pe, pull__postablesinvitedto=pe)
            postableq.update(safe_update=True, push__members=menick)
        except:
            doabort('BAD_REQ', "Failed in user %s accepting invite to gpostable %s %s" % (menick, ptype.__name__, fqpn))
        return menick

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
            newownerq=newownerptype.objects(nick=newownerfqpn)
            newowner=newownerq.get()
        except:
            #make sure target exists.
            doabort('BAD_REQ', "No such newowner %s %s" % (newownerptype.__name__, newowner.nick))
        #Either as a user or a group, you must be member of group/app or app respectively to
        #transfer membership there. But what does it mean for a group to own a group. 
        #it makes sense for library and app, but not for group. Though currently let us have it
        #there. Then if a group owns a group, the person doing the changing must be owner.

        #newowner must be member of the postable (group cant own itself)
        permit(self.isMemberOfPostable(currentuser, newowner, postable), 
            " Possible new owner %s %s must be member of postable %s %s" % (newownerptype.__name__, newowner.nick, ptype.__name__, fqpn))

       
        try:
            oldownernick=postable.owner
            #if newownerptype != User:
            postable.update(safe_update=True, set__owner = newowner.nick, push__members=newowner.nick)
            #else:
            #postable.update(safe_update=True, set__owner = newowner.nick, push__members=newowner.nick, pull__members=oldownernick)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for postable %s %s" % (oldownernick, newowner.nick, ptype.__name__, fqpn))
        return newowner

    #group should be replaced by anything that can be the owner
    #dont want to use this for postables, even though they are ownable.
    def changeOwnershipOfOwnableType(self, currentuser, owner, fqtypen, newownerfqpn):
        "this is used for things like itentypes and tagtypes, not for g/a/l"
        typetype=gettype(fqtypen)
        newownerptype = gettype(newownerfqpn)
        typq=typetype.objects(basic__fqin=fqtypen)
        try:
            ownable=typq.get()
        except:
            doabort('BAD_REQ', "No such ownable %s %s" % (typetype.__name__,fqtypen))
        authorize_ownable_owner(False, self, currentuser, owner, ownable)

        try:
            newownerq=newownerptype.objects(nick=newownerfqpn)
            newowner=newownerq.get()
        except:
            #make sure target exists.
            doabort('BAD_REQ', "No such newowner %s %s" % (newownerptype.__name__, newowner))
        
        #if transferring to a group/app I better be a member of it, else I can transfer to any user.
        if newownerptype != User:
            authorize_postable_member(False, self, currentuser, owner, newowner)
      
        try:
            oldownernick=ownable.owner
            ownable.update(safe_update=True, set__owner = newowner.nick)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for ownable %s %s" % (oldownernick, newowner.nick, typetype.__name__, fqtypen))
        return newowner

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