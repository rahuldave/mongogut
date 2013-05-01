from classes import *
import config
from permissions import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser
from permissions import authorize_context_owner, authorize_context_member
from errors import abort, doabort, ERRGUT
import types

OK=200
LOGGEDIN_A_SUPERUSER_O_USERAS=False
MEMBER_OF_POSTABLE=False
POSTABLES=[Group, App, Library]

def augmentspec(specdict, spectype=User):
    basicdict={}
    print "INSPECDICT", specdict
    if spectype in POSTABLES:
        specdict['owner']=specdict['creator']
        basicdict['creator']=specdict['creator']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        basicdict['fqin']=specdict['creator']+"/"+spectype+":"+specdict['name']
    specdict['basic']=Basic(**basicdict)
    specdict['nick']=basicdict['fqin']
    del specdict['name']
    del specdict['creator']
    if specdict.has_key('description'):
        del specdict['description']
    return specdict

class Database():

    def __init__(self, db_session):
        self.session=db_session

    def isSystemUser(self, currentuser):
        if currentuser.nick=='adsgut':
            return True
        else:
            return False

    #this one is completely UNPROTECTED
    def getUserForNick(self, currentuser, nick):
        try:
            user=User.objects(nick=nick).get()
        except:
            doabort('NOT_FND', "User %s not found" % nick)
        return user

    def getUserInfo(self, currentuser, nick):
        user=self.getUserForNick(currentuser, nick)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, user)
        return user


    #POSTABLE interface

    def getPostable(self, currentuser, ptype, fqpn):
        try:
            postable=ptype.objects(basic__fqin=fqpn)
        except:
            doabort('NOT_FND', "%s %s not found" % (ptype.__name__, fqpn))
        return postable

    def getPostableInfo(self, currentuser, fqpn, ptype):
        postable=self.getPostable(currentuser, ptype, fqpn)
        authorize_postable_member(MEMBER_OF_POSTABLE, self, currentuser, None, postable)
        return postable

    #using ISMEMBER interface. what does currentuser do now?
    def isMemberOfPostable(self, currentuser, ismember, postable):
        if ismember.nick in postable.members:
            return True
        else:
            return False

    def isOwnerOfPostable(self, currentuser, ismember, postable):
        if ismember.nick==postable.owner:
            return True
        else:
            return False

    def isInvitedToPostable(self, currentuser, ismember, postable):
        if ismember.nick in postable.inviteds:
            return True
        else:
            return False

    def ownerOfPostables(self, currentuser, useras, ptype=None):
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesowned
        if ptype:
            postables=[e['fqpn'] for e in allpostables if e['ptype']==ptype]
        else:
            postables=allpostables
        return postables

    def postablesForUser(self, currentuser, useras, ptype=None):
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesin
        if ptype:
            postables=[e['fqpn'] for e in allpostables if e['ptype']==ptype]
        else:
            postables=allpostables
        return postables

    def postableInvitesForUser(self, currentuser, useras, ptype=None):
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allpostables=useras.postablesinvitedto
        if ptype:
            postables=[e['fqpn'] for e in allpostables if e['ptype']==ptype]
        else:
            postables=allpostables
        return postables

    
    def membersOfPostable(self, currentuser, useras, postable):
        #BUG: user may be member through another postable
        authorize_context_member(False, self, currentuser, useras, postable)
        members=postable.members
        return members

    #Add user to system, given a userspec from flask user object. commit needed
    #This should never be called from the web interface, but can be called on the fly when user
    #logs in in Giovanni's system. So will there be a cookie or not?
    #BUG: make sure this works on a pythonic API too. think about authorize in a
    #pythonic API setting
    #
    ##BUG: how should this be protected?
    def addUser(self, currentuser, userspec):
        try:
            newuser=User(**userspec)
            newuser.save(safe=True)
        except:
            doabort('BAD_REQ', "Failed adding user %s" % userspec['nick'])
        #Also add user to private default group and public group

        self.addPostable(newuser, Group, dict(name='default', creator=newuser.nick,
            personalgroup=True
        ))
        self.addUserToPostable(currentuser, Group, 'adsgut/group:public', newuser.nick)
        #self.addUserToApp(currentuser, 'ads@adslabs.org/app:publications', newuser, None)
        return newuser

    #BUG: we want to blacklist users and relist them
    #currently only allow users to be removed through scripts
    def removeUser(self, currentuser, usertoberemovednick):
        #Only sysuser can remove user. BUG: this is unfleshed
        authorize(False, self, currentuser, None)
        remuser=self.getUserForNick(currentuser, usertoberemovednick)
        #CONSIDER: remove user from users collection, but not his name elsewhere.
        remuser.delete(safe=True)
        return OK

    def addPostable(self, currentuser, ptype, postablespec):
        authorize(False, self, currentuser, currentuser)
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
        self.addUserToPostable(currentuser, ptype, newpostable.basic.fqin, newpostable.basic.creator)
        return newpostable

    def removePostable(self,currentuser, ptype, fqpn):
        rempostable=self.getPostable(currentuser, ptype, fqpn)
        authorize_context_owner(False, self, currentuser, None, rempostable)
        #BUG: group deletion is very fraught. Once someone else is in there
        #the semantics go crazy. Will have to work on refcounting here. And
        #then get refcounting to come in
        rempostable.delete(safe=True)
        return OK

    def addUserToPostable(elf, currentuser, ptype, fqpn, usertobeaddednick):
        pclass=PTYPEMAP[ptype]
        postableq=pclass.objects(basic__fqin=fqpn)
        userq= User.objects(nick=usertobeaddednick)

        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" %  (ptype.__name__,fqpn))

        if fqpn!='adsgut/group:public':
            #special case so any user can add themselves to public group
            #permit(self.isOwnerOfGroup(currentuser, grp) or self.isSystemUser(currentuser), "User %s must be owner of group %s or systemuser" % (currentuser.nick, grp.fqin))
            authorize_context_owner(False, self, currentuser, None, postable)
        try:
            pe=PostableEmbedded(ptype=ptype,fqpn=postable.basic.fqin)
            userq.update(safe_update=True, push__postablesin=pe)
            postableq.update(safe_update=True, push__members=usertobeaddednick)
        except:
            doabort('BAD_REQ', "Failed adding user %s to postable %s %s" % (usertobeaddednick, ptype.__name__, fqpn))
        return usertobeaddednick

    def removeUserFromPostable(self, currentuser, ptype, fqpn, usertoberemovednick):
        postableq=ptype.objects(basic__fqin=fqpn)
        userq= User.objects(nick=usertoberemovednick)

        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such group %s" % fqgn)
        authorize_context_owner(False, self, currentuser, None, postable)
        try:
            pe=PostableEmbedded(ptype=ptype,fqpn=postable.basic.fqin)
            userq.update(safe_update=True, pull_postablesin=pe)
            postableq.update(safe_update=True, pull__members=usertoberemovednick)
        except:
            doabort('BAD_REQ', "Failed removing user %s from postable %s %s" % (usertoberemovednick, ptype.__name__, fqpn))
        return OK

    def inviteUserToPostable(self, currentuser, ptype, fqpn, usertobeaddednick):
        postable=self.getPostable(currentuser, ptype, fqpn)
        userq= User.objects(nick=usertobeaddednick)
        authorize_context_owner(False, self, currentuser, None, postable)
        try:
            pe=PostableEmbedded(ptype=ptype,fqpn=postable.basic.fqin)
            userq.update(safe_update=True, push__postablesinvitedto=pe)
        except:
            doabort('BAD_REQ', "Failed inviting user %s to group %s" % (usertobeadded.nick, fqgn))
        #print "IIIII", userq.get().groupsinvitedto
        return usertobeaddednick

    def acceptInviteToPostable(self, currentuser, ptype, fqpn, menick):
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
    def changeOwnershipOfPostable(self, currentuser, ptype, fqpn, newownerptype, newownerfqpn):
        postableq=ptype.objects(basic__fqin=fqpn)
        try:
            newownerq=newownerptype.objects(nick=newownerfqpn)
            newowner=newownerq.get()
        except:
            #make sure target exists.
            doabort('BAD_REQ', "No such postable %s %s" % (newownerptype.__name, newowner))
        if newownerptype != User:
            authorize_context_member(False, self, currentuser, None, newowner)

        try:
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such postable %s %s" % (ptype.__name__,fqpn))
        authorize_context_owner(False, self, currentuser, None, postable)
        try:
            oldownernick=postable.owner
            if newownerptype != User:
                postable.update(safe_update=True, set__owner = newowner.nick, push__members=newowner.nick)
            else:
                postable.update(safe_update=True, set__owner = newowner.nick, push__members=newowner.nick, pull__members=oldownernick)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for postable %s %s" % (oldownernick, newowner.nick, ptype.__name__, fqln))
        return newowner

    #group should be replaced by anything that can be the owner

    def changeOwnershipOfOwnableType(self, currentuser, fqtypen, typetype, newowner, groupmode=False):
        if typetype=="itemtype":
            typeo=ItemType
        elif typrtype=="tagtype":
            typeo=TagType
        typq=typeo.objects(basic__fqin=fqtypen)
        if groupmode:
            try:
                groupq=Group.objects(basic__fqin=newowner)
                group=groupq.get()
                newowner=group.basic.fqin
            except:
                #make sure target exists.
                doabort('BAD_REQ', "No such group %s" % newowner)
            authorize_context_member(False, self, currentuser, None, group)
        else:
            try:
                userq= User.objects(nick=newowner)
                newowner=userq.get().nick
            except:
                #make sure target exists.
                doabort('BAD_REQ', "No such user %s" % newowner)
        try:
            typ=typq.get()
        except:
            doabort('BAD_REQ', "No such group %s" % fqtypen)
        authorize_context_owner(False, self, currentuser, None, typ)
        try:
            oldownernick=typ.owner
            if groupmode:
                typ.update(safe_update=True, set__owner = newowner)
            else:
                typ.update(safe_update=True, set__owner = newowner)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for type %s" % (oldownernick, newowner, fqtypen))
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
        return self.getPostable(currentuser, Group, fqgn)

    def getGroup(self, currentuser, fqan):
        return self.getPostable(currentuser, App, fqan)

    def getGroup(self, currentuser, fqln):
        return self.getPostable(currentuser, Library, fqln)