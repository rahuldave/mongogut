from mongoclasses import *
import config
from perms import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser, authorize_membable_owner
from perms import authorize_ownable_owner, authorize_postable_member, authorize_postable_owner, authorize_membable_member
from exc import abort, doabort, ERRGUT
import types

import sys
from utilities import *
import copy

## we first start with some helper functions

#this looks for a postable like a library in the postablesin or postablesowned of a user
#or the postablesin of a group or app
def is_membable_embedded_in_memberable(pble, mblesub):
    fqpnhash = dict([(e.fqpn, e) for e in mblesub])
    if pble.basic.fqin in fqpnhash.keys():
        return fqpnhash[pble.basic.fqin]
    return False

#this gets the reverse, is a member as a user or a group among the membets of a library
#or if a user is among the members of an app or group
def is_memberable_embedded_in_membable(mble, pblesub):
    fqmnhash = dict([(e.fqmn, e) for e in pblesub])
    if mble.basic.fqin in fqmnhash.keys():
        return fqmnhash[mble.basic.fqin]
    return False

#this is an critical function which goes to a postable
#and changes a value on it. it then goes to the owner user and changes
#the value in postables owned. it then goes to all members of the postable,
#finds their postables in, and changes the value there. It allows for slightly
#different field names by having a different f and f_emb. This ridmarole is needed
#as our data model is fully flattened and thus we must handle the relational stuff
#ourself
def deep_changes_to_postable(postable, f,f_emb, fval, fembval=None):
    fdict={}
    fdict['set__'+f]=fval
    fqpn=postable.basic.fqin
    postable.update(safe_update=True,**fdict)
    owner=User.objects(basic__fqin=postable.owner).get()
    dazip=zip([e.fqpn for e in owner.postablesowned], owner.postablesowned)
    if fembval==None:
        fembval=fval
    for p,pe in dazip:
        if fqpn==p:
            emb=pe
            owner.update(safe_update=True, pull__postablesowned={'fqpn':fqpn})
            setattr(emb, f_emb, fembval)
            owner.update(safe_update=True, push__postablesowned=emb)
    for m in postable.members:
        mobj = MAPDICT[m.mtype].objects(basic__fqin=m.fqmn).get()
        #print "mobj is", mobj, m, m.fqmn
        dazip=zip([e.fqpn for e in mobj.postablesin], mobj.postablesin)
        for p,pe in dazip:
            if fqpn==p:
                emb=pe
                mobj.update(safe_update=True, pull__postablesin={'fqpn':fqpn})
                setattr(emb, f_emb, fembval)
                mobj.update(safe_update=True, push__postablesin=emb)
        if m.mtype=='user':
            dazip=zip([e.fqpn for e in mobj.postablesinvitedto], mobj.postablesinvitedto)
            for p,pe in dazip:
                if fqpn==p:
                    emb=pe
                    mobj.update(safe_update=True, pull__postablesinvitedto={'fqpn':fqpn})
                    setattr(emb, f_emb, fembval)
                    mobj.update(safe_update=True, push__postablesinvitedto=emb)


#The social part of the database. This database becomes a part of the items-and-tags database
#and carries info about users/libraries/groups and apps in the Database class
class Database():

    def __init__(self, db_session):
        "initialize the database with mongoengine db_session"
        self.session=db_session

    #UNPROTECTED
    def isSystemUser(self, currentuser):
        "is the current user the superuser?"
        if currentuser.nick=='adsgut':
            return True
        else:
            return False

    #UNPROTECTED
    def _getUserForNick(self, currentuser, nick):
        "gets user for nick"
        try:
            user=User.objects(nick=nick).get()
        except:
            doabort('NOT_FND', "User %s not found" % nick)
        return user

    #UNPROTECTED
    def _getUserForAdsid(self, currentuser, adsid):
        "gets user for adsid"
        try:
            user=User.objects(adsid=adsid).get()
        except:
            doabort('NOT_FND', "User %s not found" % adsid)
        return user

    def _getUserForCookieid(self, currentuser, cookieid):
        "gets user for cookieid, the ads cookie"
        try:
            user=User.objects(cookieid=cookieid).get()
        except:
            #print "JJJJ", sys.exc_info()
            doabort('NOT_FND', "User %s not found" % cookieid)
        return user

    def _getUserForFqin(self, currentuser, userfqin):
        "gets user for the user's fully qualified name"
        try:
            user=User.objects(basic__fqin=userfqin).get()
        except:
            doabort('NOT_FND', "User %s not found" % userfqin)
        return user

    #get a user group or app from fqin
    def _getMemberableForFqin(self, currentuser, mtype, memberfqin):
        "gets a memberable from its fully qualified name"
        try:
            member=mtype.objects(basic__fqin=memberfqin).get()
        except:
            doabort('NOT_FND', "User %s not found" % memberfqin)
        return member

    #this one is PROTECTED
    def getUserInfo(self, currentuser, nick):
        "gets user for nick only if you are superuser or that user"
        user=self._getUserForNick(currentuser, nick)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, user)
        return user

    #this one is PROTECTED
    def getUserInfoFromAdsid(self, currentuser, adsid):
        "gets user for nick only if you are superuser or that user"
        user=self._getUserForAdsid(currentuser, adsid)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, user)
        return user


    def _getEntity(self, currentuser, fqmn):
        "gets the entity corresponding to the fqmn"
        mtype=gettype(fqmn)
        try:
            entity=mtype.objects(basic__fqin=fqmn).get()
        except:
            doabort('NOT_FND', "%s %s not found" % (classname(mtype), fqmn))
        return entity

    #this one is unprotected
    #TODO make sure ptype is in MEMBABLES.
    def _getMembable(self, currentuser, fqpn):
        "gets the postable corresponding to the fqpn"
        return self._getEntity(currentuser, fqpn)

    #this one is protected
    def getMembableInfo(self, currentuser, memberable, fqpn):
        "gets membable only if you are member of the membable"
        membable=self._getMembable(currentuser, fqpn)
        authorize_membable_member(MEMBER_OF_MEMBABLE, self, currentuser, memberable, membable)
        owner = self._getUserForFqin(currentuser, membable.owner)
        creator = self._getUserForFqin(currentuser, membable.basic.creator)
        return membable, owner, creator


    def isMemberOfMembable(self, currentuser, memberable, membable, memclass=MEMBERABLES_NOT_USER):
        "is the memberable(user/group/app) a member of membable(group/app/lib)"
        #First get the members, if our memberable is directly there, return true (direct user membership)
        memberfqins=membable.get_member_fqins()
        if memberable.basic.fqin in memberfqins:
            return True
        #Otherwise go through the members, one by one. If they are
        #of a class that has members, go through the members of that class and see if we are there.
        for memfqin in memberfqins:
            memberabletype=gettype(memfqin)
            if  memberabletype in memclass:#by restricting to memclass we get no users
                loopmemberable=self._getEntity(currentuser, memfqin)
                if memberable.basic.fqin in loopmemberable.get_member_fqins():
                    return True
        return False

    def isMemberOfPostable(self, currentuser, memberable, postable):
        "is the memberable a member of postable"
        return self.isMemberOfMembable(currentuser, memberable, postable)

    #this one checks direct membership of library, but then also checks for membership of grps/apps in lib!
    def canIPostToPostable(self, currentuser, memberable, library, memclass=MEMBERABLES_NOT_USER):
        "am i allowed to post to a library, either through user or through a memberable"
        #if i own the library let me post.
        if self.isOwnerOfPostable(currentuser, memberable, library):
            return True
        #otherwise get member read-write ability
        rws=library.get_member_rws()
        #if not returned already start with false
        start=False
        #now check iam a member AND have the ability to write
        if memberable.basic.fqin in rws.keys():
            start = start or rws[memberable.basic.fqin][1]
        #if i am not a user, i will be in some memclass
        #goes down membership list here
        for memfqin in rws.keys():
            memberabletype=gettype(memfqin)
            if  memberabletype in memclass:
                loopmemberable=self._getEntity(currentuser, memfqin)
                if memberable.basic.fqin in loopmemberable.get_member_fqins():
                    start = start or rws[memfqin][1]
        return start

    #OWNABLES=[Group, App, Library, ItemType, TagType, Tag]
    #Note that the owner is set to the fqin, not the nick
    def isOwnerOfOwnable(self, currentuser, useras, ownable):
        "is user the owner of ownable?"
        if useras.basic.fqin==ownable.owner:
            return True
        else:
            return False

    #defined this just for completion, and in code, it will be easier to read, unprotected
    def isOwnerOfPostable(self, currentuser, useras, postable):
        return self.isOwnerOfOwnable(currentuser, useras, postable)

    def isOwnerOfMembable(self, currentuser, useras, membable):
        return self.isOwnerOfOwnable(currentuser, useras, membable)

    #invitations for users. invitation to a tag is undefined, as yet. unprotected
    def isInvitedToMembable(self, currentuser, useras, membable):
        if useras.basic.fqin in [m.fqmn for m in membable.inviteds]:
            return True
        else:
            return False

    def isInvitedToPostable(self, currentuser, memberable, postable):
        "is the user invited to the postable?"
        return self.isInvitedToMembable(currentuser, memberable, postable)

    #unprotected.
    def ownerOfMembables(self, currentuser, useras, ptypestr=None):
        "return the membables the user is an owner of"
        #TODO:currently suppressiong protection. revisit.
        #authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allmembables=useras.postablesowned
        if ptypestr:
            membables=[e for e in allmembables if e['ptype']==ptypestr]
        else:
            membables=allmembables
        return membables

    #unprotected
    def membablesForUser(self, currentuser, useras, ptypestr=None):
        "return the membables the user is DIRECTLY a member of"
        #TODO: revisit whether this should be protected later
        #authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allmembables=useras.postablesin
        if ptypestr:
            membables=[e for e in allmembables if e['ptype']==ptypestr]
        else:
            membables=allmembables
        return membables

    #unprotected
    def membablesUserCanAccess(self, currentuser, useras, ptypestr=None):
        "return the membables the user can access, directly or indirectly(for libraries)"
        #authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        nlibmembables = useras.membablesnotlibrary()
        othermembables = useras.membableslibrary()
        allmembables = nlibmembables + othermembables
        if ptypestr:
            membables=[e for e in allmembables if e['ptype']==ptypestr]
        else:
            membables=allmembables
        return membables

    #unprotected
    def membablesUserCanWriteTo(self, currentuser, useras, ptypestr=None):
        """return the membables the user can access, directly or
        indirectly(for libraries), which user can write to (using readwrite)"""
        #authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        nlibmembables = useras.membablesnotlibrary()
        othermembables = useras.membableslibrary()
        allmembables = nlibmembables + othermembables
        if ptypestr:
            membables=[e for e in allmembables if (e['ptype']==ptypestr and e['readwrite']==True)]
        else:
            membables=[e for e in allmembables if e['readwrite']==True]
        return membables


    #why auth here?
    #invitations only work for users for now.
    def membableInvitesForUser(self, currentuser, useras, ptypestr=None):
        "given a user, find their invitations to postables"
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allmembables=useras.postablesinvitedto
        if ptypestr:
            membables=[e for e in allmembables if e['ptype']==ptypestr]
        else:
            membables=allmembables
        return membables

    #gives  members only along with their permissions. used to get perms for users and groups
    #in libs or users in libs
    def membersOfMembable(self, currentuser, memberable, membable):
        "who are the members of the membable?"
        #i need to have access to this if i come in through being a member of a memberable which is a member
        #authorize_membable_member takes care of this.
        authorize_membable_member(False, self, currentuser, memberable, membable)
        #print "CU", currentuser.nick, memberable.nick, membable.basic.fqin
        if self.isOwnerOfMembable(currentuser, memberable, membable):
            perms=membable.get_member_rws()
        else:
            perms=membable.get_member_rws()
            for k in perms.keys():
                perms[k][1]=''
        return perms

    def membersOfMembableFromFqin(self, currentuser, memberable, fqpn):
        membable=self._getMembable(currentuser, fqpn)
        return self.membersOfMembable(currentuser, memberable, membable)

    #Needs owner or superuser access. currently useras must be a user
    def invitedsForMembable(self, currentuser, useras, membable):
        "who are invited to the membable?"
        #you must be an owner to get all the inviteds
        authorize_membable_owner(False, self, currentuser, useras, membable)
        inviteds=membable.get_invited_rws()
        return inviteds

    def invitedsForMembableFromFqin(self, currentuser, memberable, fqpn):
        membable=self._getMembable(currentuser, fqpn)
        return self.invitedsForMembable(currentuser, memberable, membable)
    ################################################################################

    #Add user to system, given a userspec which can be your own, or from flask user object.
    #This should never be called from the web services, but can be called on the fly when user
    #logs in in Giovanni's system.
    #
    #adduser MUST be called with the adsgut user as currentuser
    def addUser(self, currentuser, userspec):
        "add a user to the system. currently only sysadmin can do this"
        #NOTE: any user can add adsuser, but only adsgut should. Thus this function should never be exposed via web service

        #if we are not trying to add adsgut:
        if not userspec['adsid']=='adsgut':
            authorize_systemuser(False, self, currentuser)#I MUST BE SYSTEMUSER
        try:
            userspec=augmentspec(userspec)
            newuser=User(**userspec)
            newuser.save(safe=True)
        except:
            doabort('BAD_REQ', "Failed adding user %s" % userspec['adsid'])

        #A this point, if adding adsgut, set the currentuser to adsgut
        if userspec['adsid']=='adsgut':
            currentuser=newuser
        #make who is doing this all explicit.
        adsgutuser=currentuser

        #adding the default library in
        self.addLibrary(adsgutuser, newuser, dict(name='default', creator=newuser.basic.fqin, librarykind='udl'))

        #if we are not trying to add adsgut, or anonymouse, add user to public group and adsgut main app
        if not userspec['adsid']=='adsgut':
            if newuser.basic.fqin!=ANONYMOUSE:
                self.addUserToGroup(adsgutuser, adsgutuser, PUBLICGROUP, newuser.basic.fqin)
                #this will automatically add to the public library as well
                self.addUserToApp(adsgutuser, adsgutuser, MOTHERSHIPAPP, newuser.basic.fqin)
        newuser.reload()
        return newuser

    #TODO: we want to blacklist users and relist them. add a method for this using the dormant field

    #Generally we will never do this. There is nothing in the UI for it.
    #TODO: let us hook up a script for this
    def removeUser(self, currentuser, usertoberemovednick):
        "remove a user. only systemuser can do this"
        #Only sysuser can remove user.
        #BUG: this is unfleshed. routing and reference counting ought to be used to handle this
        authorize_systemuser(False, self, currentuser)
        remuser=self._getUserForNick(currentuser, usertoberemovednick)
        #CONSIDER: remove user from users collection, but not his name elsewhere.
        #remove user from all ownables/membables that user is a member of
        #BUG: what about tags
        membablesin=[m.fqpn for m in remuser.postablesin]
        for fqpn in membablesin:
            self.removeMemberableFromMembable(currentuser, useras, fqpn, remuser.basic.fqin)
        remuser.delete(safe=True)
        return OK

    #this method has a user adding a group, library, or application
    def addMembable(self, currentuser, useras, ptypestr, membablespec_in, appmode=False):
        "the useras adds a postable. currently either currentuser=superuser or useras"
        #first make sure that user is either logged in or isa superuser
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        #set the creator
        membablespec_in['creator']=useras.basic.fqin
        membablespec=copy.deepcopy(membablespec_in)
        membablespec=augmentspec(membablespec, ptypestr)
        #make sure we dont have a colon(:) or a / in the name of the membable.
        a = membablespec['basic'].name.find(':')
        b = membablespec['basic'].name.find('/')
        if a!=-1 or b!=-1:
            doabort('BAD_REQ', "Failed adding membable due to presence of : or /  %s" % (membablespec['basic'].name))
        ptype=gettype(membablespec['basic'].fqin)
        #idempotency: if this membable already exists, return it and the user
        try:
            p=ptype.objects.get(basic__fqin=membablespec['basic'].fqin)
            return useras, p
        except:
            #if not, try creating the membable
            try:
                newmembable=ptype(**membablespec)
                newmembable.save(safe=True)
                #also get the user to save into postablesowned
                userq= User.objects(basic__fqin=newmembable.owner)
                user=userq.get()
                newpe = is_membable_embedded_in_memberable(newmembable, user.postablesowned)
                #memb = is_memberable_embedded_in_membable(memberable, postable.members)
                #this would be added a second time but we are protected by this line above!
                if membablespec.has_key('librarykind'):
                    librarykind=membablespec['librarykind']
                else:
                    librarykind=""#islibrarypublic will be set by default to False
                if newpe == False:
                    newpe=MembableEmbedded(ptype=ptypestr,fqpn=newmembable.basic.fqin, owner=user.adsid, pname = newmembable.presentable_name(), readwrite=True, description=newmembable.basic.description, librarykind=librarykind)
                    res=userq.update(safe_update=True, push__postablesowned=newpe)
            except:
                doabort('BAD_REQ', "Failed adding membable %s %s" % (ptype.__name__, membablespec['basic'].fqin))
            #This will add the creator to postablesin, with changerw false
            self.addMemberableToMembable(currentuser, useras, newmembable.basic.fqin, newmembable.basic.creator, changerw=False, ownermode=True)
            #now if this was a group or an app, add the corresponding library
            #if appmode is true we are also adding the app into the library
            if appmode:
                ptypelist=['group', 'app']
            else:
                ptypelist=['group']
            if ptypestr in ptypelist:
                membablespeclib_in=copy.deepcopy(membablespec_in)
                if not membablespeclib_in.has_key('librarykind'):
                    membablespeclib_in['librarykind']=ptypestr
                luser, mlib=self.addMembable(currentuser, useras, 'library', membablespeclib_in)
                #now make sure group or app is in that library
                self.addMemberableToMembable(currentuser, useras, mlib.basic.fqin, newmembable.basic.fqin, changerw=False, ownermode=False)
            newmembable.reload()
            return user, newmembable

    def addGroup(self, currentuser, useras, groupspec):
        return self.addMembable(currentuser, useras, "group", groupspec)

    def addApp(self, currentuser, useras, appspec, appmode=False):
        return self.addMembable(currentuser, useras, "app", appspec, appmode)

    def addLibrary(self, currentuser, useras, libraryspec):
        return self.addMembable(currentuser, useras, "library", libraryspec)


    #add a memberable to a membable, such as a user to group or library, or a group/app to a library
    def addMemberableToMembable(self, currentuser, useras, fqpn, memberablefqin, changerw=False, ownermode=False):
        "add a user, group, or app to a postable=group, app, or library"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        membableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(basic__fqin=memberablefqin)
        #currently restricted admission. Later we will want groups and apps proxying for users.
        #make sure its a logged in user or superuser
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        rw=False#makes no sense unless you are in a library
        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s %s" %  (ptype.__name__,fqpn))
        try:
            memberable=memberableq.get()
        except:
            doabort('BAD_REQ', "No such memberable %s %s" %  (mtype.__name__,memberablefqin))

        if fqpn!='adsgut/group:public':
            #make sure only the owner of the membable can do things
            #special case so any user can add themselves to public group
            authorize_membable_owner(False, self, currentuser, useras, membable)
        try:
            if ptype==Library:
                if ownermode:
                    rw=True
                else:#RWDEF only used when not in ownermode
                    if not changerw:
                        rw=RWDEF[membable.librarykind]
                    else:
                        rw= (not RWDEF[membable.librarykind])
                restriction=RESTR[membable.librarykind]
                #RESTR is used in libraries to set what is allowed in
                if restriction[0]!=None:#only in case of 'udl'
                    if restriction[1]==None and ownermode==False:
                        doabort('BAD_REQ', "Only owner is allowed to be a member of %s" %  membable.librarykind)
                    #TODO: remove as none of this ought to kick in. If we decide to make things more useful
                    #this could be used to kick in the right permissions
                    if ownermode==False:#ownly the group/app/pub group entity is allowed to be a member of this library
                        if mtype!=restriction[0]:
                            doabort('BAD_REQ', "Memberable %s not allowed as member of %s library" %  (mtype.__name__,membable.librarykind))
                        if restriction[1]==True:#this used to be the case when we wanted a one group lib but
                            #thats not the case any more.
                            if membable.basic.name!=memberable.basic.name and membable.owner!=memberable.owner:
                                doabort('BAD_REQ', "Memberable %s not allowed as member of %s library" %  (memberable.basic.fqin,membable.basic.fqin))

            #if all of this passes, we are now ok to add
            #do we have a membable-embedded already for some reason? just use it (idempotency)
            pe = is_membable_embedded_in_memberable(membable, memberable.postablesin)

            if pe == False:
                if ptype==Library:
                    librarykind=membable.librarykind
                    #adding anonymouse to any library but her own
                    if memberable.basic.fqin=="adsgut/user:anonymouse" and membable.basic.fqin!="anonymous/library:default":
                        islibrarypublic=True
                        rw=False#we artificially make anonymouse read-only, always
                        deep_changes_to_postable(membable, "islibrarypublic", "islibrarypublic", islibrarypublic)
                        membable.reload()
                    islibrarypublic=membable.islibrarypublic
                else:
                    librarykind=""
                    islibrarypublic=False
                #now create a membable embedded to add to memberable
                pe=MembableEmbedded(ptype=ptype.classname,fqpn=membable.basic.fqin, owner=useras.adsid, pname = membable.presentable_name(), readwrite=rw, description=membable.basic.description, librarykind=librarykind, islibrarypublic=islibrarypublic)
            #update memberable with membable
            memberableq.update(safe_update=True, push__postablesin=pe)
            #again, for idempotency, see if we have a memberable embedded
            member = is_memberable_embedded_in_membable(memberable, membable.members)
            if member == False:
                member=MemberableEmbedded(mtype=mtype.classname, fqmn=memberablefqin, readwrite=rw, pname = memberable.presentable_name())
                #update membable with member
                membableq.update(safe_update=True, push__members=member)
        except:
            doabort('BAD_REQ', "Failed adding memberable %s %s to postable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        memberable.reload()
        return memberable, membableq.get()

    def addUserToGroup(self, currentuser, useras, fqpn, memberablefqin, changerw=False, ownermode=False):
        self.addMemberableToMembable(currentuser, useras, fqpn, memberablefqin, changerw, ownermode)

    def addUserToApp(self, currentuser, useras, fqpn, memberablefqin, changerw=False, ownermode=False):
        self.addMemberableToMembable(currentuser, useras, fqpn, memberablefqin, changerw, ownermode)

    def addUserToLibrary(self, currentuser, useras, fqpn, memberablefqin, changerw=False, ownermode=False):
        self.addMemberableToMembable(currentuser, useras, fqpn, memberablefqin, changerw, ownermode)

    def addGroupToLibrary(self, currentuser, useras, fqpn, memberablefqin, changerw=False, ownermode=False):
        self.addMemberableToMembable(currentuser, useras, fqpn, memberablefqin, changerw, ownermode)

    def addUserToMembable(self, currentuser, fqpn, nick, changerw=False, ownermode=False):
        user=self._getUserForNick(currentuser, nick)
        return self.addMemberableToMembable(currentuser, currentuser, fqpn, user.basic.fqin, changerw, ownermode)

    #this methods lets us toggle the read-only vs read-write status for a member of a library
    #WORKS ONLY FOR POSTABLE=LIBRARY. The notion of posting dosent make sense for any other membership.
    def toggleRWForMembership(self, currentuser, useras, fqpn, memberable):
        ptype=gettype(fqpn)
        memberablefqin=memberable.basic.fqin
        mtype=gettype(memberablefqin)
        postableq=ptype.objects(basic__fqin=fqpn)

        #TODO currently restricted admission. Later we will want groups and apps proxying for users.
        #currently must be superuser or logged in user
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        try:#get the library
            postable=postableq.get()
        except:
            doabort('BAD_REQ', "No such unique memberable %s %s postable %s %s" %  (mtype.__name__, memberablefqin, ptype.__name__,fqpn))
        #make sure that the user making changes actually owns the library
        authorize_postable_owner(False, self, currentuser, useras, postable)
        members=postable.members
        postables=memberable.postablesin
        #toggling on anonymouse is not allowed. anonymouse may only read
        if memberablefqin=="adsgut/user:anonymouse":
            doabort('BAD_REQ', "Cant give write priviledges to non logged-in users")
        #prevent owner from toggling herself
        if memberablefqin==useras.basic.fqin:
            doabort('BAD_REQ', "owner cannot toggle their own read-write status")
        #make the toggle change both in members and postablesin
        #(need not worry about postablesowned as you are not allowed to toggle that)

        for me in members:
            if me.fqmn==memberablefqin:
                me.readwrite = (not me.readwrite)
        for p in postables:
            if p.fqpn==fqpn:
                p.readwrite = (not p.readwrite)

        postable.save(safe=True)
        memberable.save(safe=True)
        #note how we are using save instead of update. this technique could potentially simplify
        #codeelsewhere
        return memberable, postable


    #THINK: This should perhaps work for tags as well. 
    #you must be systemuser or tag owner to remove someone from tags

    #remove a user from a group/app, or u/g/a from a library.
    def removeMemberableFromMembable(self, currentuser, useras, fqpn, memberablefqin):
        "remove a u/g/a from a g/a/l"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        membableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(basic__fqin=memberablefqin)
        #make sure you are superuser or logged in
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        #get the membable
        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s" % fqpn)
        #get the memberable
        try:
            memberable=memberableq.get()
        except:
            doabort('BAD_REQ', "No such memberable %s" % memberablefqin)
        #If you are the memberable, that is, you are removing yourself:
        if useras.basic.fqin==memberablefqin:
            #if the user is removing herself, first make sure she is a member
            authorize_membable_member(False, self, currentuser, useras, membable)
            #now make sure she is not the owner (that would be harakiri)
            if self.isOwnerOfMembable(currentuser, useras, membable):
                doabort('BAD_REQ', "Cannot remove owner %s of %s" % (useras.basic.fqin,fqpn))
        else:
            #otherwise you must be the owner of the membable or systemuser. this is independent
            #of whether the memberable is a user or a group/app in a library
            #or a user in a group/app
            #system user will be allowed by below
            authorize_membable_owner(False, self, currentuser, useras, membable)
        #pull from postablesin and members
        try:
            memberableq.update(safe_update=True, pull__postablesin__fqpn=membable.basic.fqin)
            membableq.update(safe_update=True, pull__members__fqmn=memberablefqin)
            #if you are removing anonymouse, you need to flip the "is library public"
            if memberablefqin=='adsgut/user:anonymouse':
                deep_changes_to_postable(membable, "islibrarypublic", "islibrarypublic", False)
        except:
            doabort('BAD_REQ', "Failed removing memberable %s %s from membable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        return OK


    #invite user to a group, app, or library (currently we dont invite to apps)
    def inviteUserToMembable(self, currentuser, useras, fqpn, user, changerw=False):
        "invite a user to a membable."
        ptype=gettype(fqpn)
        membable=self._getMembable(currentuser, fqpn)
        usertobeaddedfqin=user.basic.fqin
        rw=False
        #cant invite owner!
        if usertobeaddedfqin==useras.basic.fqin:
            doabort('BAD_REQ', "Failed inviting user %s to postable %s as cant invite owner" % (usertobeaddedfqin, fqpn))
        #to invite, you must be the owner of the membable
        authorize_membable_owner(False, self, currentuser, useras, membable)
        #if library, deal with the read-write invitation mode
        try:
            if ptype==Library:
                if not changerw:
                    rw=RWDEF[membable.librarykind]
                else:
                    rw= (not RWDEF[membable.librarykind])
            #if invitation has already been made, fetch it
            pe = is_membable_embedded_in_memberable(membable, user.postablesinvitedto)
            #if not, create the membable-embedded for the invitation and update user with it
            if pe == False:
                if ptype==Library:
                    librarykind=membable.librarykind
                    islibrarypublic=membable.islibrarypublic
                else:
                    librarykind=""
                    islibrarypublic=False
                pe=MembableEmbedded(ptype=ptype.classname,fqpn=membable.basic.fqin, owner=useras.adsid, pname = membable.presentable_name(), readwrite=rw, description=membable.basic.description, librarykind=librarykind, islibrarypublic=islibrarypublic)
                user.update(safe_update=True, push__postablesinvitedto=pe)
            #also, go for the memberable-embedded and put it in the inviteds for the membable/postable
            memb = is_memberable_embedded_in_membable(user, membable.inviteds)
            #if not already there, create it!
            if memb==False:
                memb=MemberableEmbedded(mtype=User.classname, fqmn=usertobeaddedfqin, readwrite=rw, pname = user.presentable_name())
                membable.update(safe_update=True, push__inviteds=memb)
        except:
            doabort('BAD_REQ', "Failed inviting user %s to postable %s" % (usertobeaddedfqin, fqpn))
        membable.reload()
        user.reload()
        return user, membable

    #use the nickname(uuid)
    def inviteUserToMembableUsingNick(self, currentuser, fqpn, nick, changerw=False):
        "invite a user to a postable."
        user=self._getUserForNick(currentuser,nick)
        return self.inviteUserToMembable(currentuser, currentuser, fqpn, user, changerw)

    #use the adsid to invite(email). this is the workhorse
    def inviteUserToMembableUsingAdsid(self, currentuser, fqpn, adsid, changerw=False):
        "invite a user to a postable."
        user=self._getUserForAdsid(currentuser,adsid)
        return self.inviteUserToMembable(currentuser, currentuser, fqpn, user, changerw)

    #accept invitation to group or library. 
    #this cannot be masqueraded, must be explicitly approved by user
    def acceptInviteToMembable(self, currentuser, fqpn, me):
        "do i accept the invite?"
        ptype=gettype(fqpn)
        membableq=ptype.objects(basic__fqin=fqpn)
        mefqin=me.basic.fqin
        #get the membable the invitation is to
        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s %s" % (ptype.__name__,fqpn))
        #make sure it is I who am logge on, and no-one else
        authorize(False, self, currentuser, me)
        #make sure i have actually been invited
        permit(self.isInvitedToMembable(currentuser, me, membable), "User %s must be invited to membable %s %s" % (mefqin, ptype.__name__,fqpn))
        #obtain the membable-embedded and memberable embedded with the aim of pulling from invitations
        #and updating the membership
        try:
            inviteds=membable.inviteds
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
            #now that we got these, pull gtom inviteds and add to ins
            me.update(safe_update=True, push__postablesin=pe, pull__postablesinvitedto__fqpn=pe.fqpn)
            membableq.update(safe_update=True, push__members=memb, pull__inviteds__fqmn=memb.fqmn)
        except:
            doabort('BAD_REQ', "Failed in user %s accepting invite to postable %s %s" % (mefqin, ptype.__name__, fqpn))
        me.reload()
        return me, membableq.get()

    #use nicks to accept invitations
    def acceptInviteToMembableUsingNick(self, currentuser, fqpn, nick):
        "invite a user to a postable."
        user=self._getUserForNick(currentuser,nick)
        return self.acceptInviteToMembable(currentuser, fqpn, user)

    #use adsids to accept invitations
    def acceptInviteToMembableUsingAdsid(self, currentuser, fqpn, adsid):
        "invite a user to a postable."
        user=self._getUserForNick(currentuser,adsid)
        return self.acceptInviteToMembable(currentuser, fqpn, user)

    #changes membable ownership to another user
    #USER must be owner! This CAN happen through membership in a member group.
    def changeOwnershipOfMembable(self, currentuser, owner, fqpn, newowner):
        "give ownership over to another user for g/a/l"
        ptype=gettype(fqpn)
        membableq=ptype.objects(basic__fqin=fqpn)
        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s %s" % (ptype.__name__,fqpn))

        #useras must be owner of membable
        authorize_membable_owner(False, self, currentuser, owner, membable)

        #set the newowner-fqin
        newownerfqin=newowner.basic.fqin

        #newowner must be member of the membable who's ownership is being changed
        permit(self.isMemberOfMembable(currentuser, newowner, membable),
            " Possible new owner %s must be member of membable %s %s" % ( newownerfqin, ptype.__name__, fqpn))
        #TODO new owners rwmode must be  true! BUG: needs to be explicitly set
        try:
            #we dont need to be that protective here as we have checked for ownership
            #and only owners can do this
            oldownerfqpn=membable.owner
            members=membable.members
            #get new user memberable embedded. member must be there
            memb = is_memberable_embedded_in_membable(newowner, membable.members)
            #get membable-embedded
            #If owner the pe must already be there.
            pe = is_membable_embedded_in_memberable(membable, owner.postablesowned)
 
            newowner.update(safe_update=True, push__postablesowned=pe)
            #for old owner we have removed ownership by changing owner, now remove ownership from him
            owner.update(safe_update=True, pull__postablesowned__fqpn=fqpn)
            deep_changes_to_postable(membable, "owner", "owner", newowner.basic.fqin, newowner.adsid)
            #WRITE CODE HERE TO CHANGE LIBRARY RW
            #if group or app change library membership as well
            if ptype==Group or ptype==App:
                fqnn=getLibForMembable(fqpn)
                lowner, lib=self.changeOwnershipOfMembable(currentuser, owner, fqnn, newowner)

        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for membable %s %s" % (oldownerfqpn, newowner.basic.fqin, ptype.__name__, fqpn))
        newowner.reload()
        membable.reload()
        owner.reload()
        return newowner, membable

    #this is used tointeractively change description of a group/library
    def changeDescriptionOfMembable(self, currentuser, owner, fqpn, description):
        "change description for g/a/l"
        ptype=gettype(fqpn)
        membableq=ptype.objects(basic__fqin=fqpn)
        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s %s" % (ptype.__name__,fqpn))

        authorize_membable_owner(False, self, currentuser, owner, membable)


        try:
            deep_changes_to_postable(membable, "basic__description", "description", description)
        except:
            doabort('BAD_REQ', "Failed changing owner description for membable %s %s" % ( ptype.__name__, fqpn))
        owner.reload()
        membable.reload()
        return owner, membable

    #UNUSED currently. This was created to change ownership of itemtypes/tagtypes
    #and possibly for tags. But we dont use this currently
    def changeOwnershipOfOwnable(self, currentuser, owner, fqon, newowner):
        "this is used for things like itentypes and tagtypes, not for g/a/l."
        otype=gettype(fqon)
        oq=otype.objects(basic__fqin=fqon)
        try:
            ownable=oq.get()
        except:
            doabort('BAD_REQ', "No such ownable %s %s" % (otype.__name__,fqon))
        authorize_ownable_owner(False, self, currentuser, owner, ownable)

        newownerfqin=newowner.basic.fqin
        permit(self.isMemberOfMembable(currentuser, newowner, ownable),
            " Possible new owner %s must be member of ownable %s %s" % (newownerfqin, ptype.__name__, fqpn))
        try:
            oldownerfqpn=ownable.owner
            memb = is_memberable_embedded_in_membable(newowner, ownable.members)
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
        return self._getMembable(currentuser, fqgn)

    def getApp(self, currentuser, fqan):
        return self._getMembable(currentuser, fqan)

    def getLibrary(self, currentuser, fqln):
        return self._getMembable(currentuser, fqln)


#this critical function sets up the initialization of the database
def initialize_application(db_session):
    currentuser=None
    #make the connection
    whosdb=Database(db_session)
    #add the superuser, or adsgut
    adsgutuser=whosdb.addUser(currentuser, dict(nick='adsgut', adsid='adsgut'))
    #set current user to superuser
    currentuser=adsgutuser
    igspec=dict(personalgroup=False, name="public", description="Public Group", librarykind="public")
    #adsgut creates the public group
    adsgutuser, publicgrp=whosdb.addGroup(adsgutuser, adsgutuser, igspec)
    #adsgut adds the mothership adsgut app everyone is in
    adsgutuser, adsgutapp=whosdb.addApp(adsgutuser, adsgutuser, dict(name='adsgut', description="The MotherShip App"))
    #adsgut creates anonymouse to represent a not-loggedin user
    anonymouseuser=whosdb.addUser(adsgutuser, dict(nick='anonymouse', adsid='anonymouse'))
    #adsgut creates the ads user who runs the publications app
    adsuser=whosdb.addUser(adsgutuser, dict(nick='ads', adsid='ads'))
    # now set the current user to the ads user
    currentuser=adsuser
    #ads user adds the ads app.
    adsuser, adspubsapp=whosdb.addApp(adsuser, adsuser, dict(name='publications', description="ADS's flagship publication app"))
    #CHECK: does anonymouse user need to be in flagship app to see anything?
    #add anonymouse user to pubs app, or will not be able to access any itemtypes/tagtypes defined by adsuser
    anonymouseuser, adspubapp=whosdb.addUserToMembable(adsuser, FLAGSHIPAPP, 'anonymouse')


def initialize_testing(db_session):
    #print "INIT TEST"
    whosdb=Database(db_session)
    currentuser=None
    adsgutuser=whosdb._getUserForNick(currentuser, "adsgut")
    currentuser=adsgutuser
    adsuser=whosdb._getUserForNick(currentuser, "ads")

    rahuldave=whosdb.addUser(adsgutuser, dict(nick='rahuldave', adsid="rahuldave@gmail.com", cookieid='4df7ce0d06'))
    rahuldave, mlg=whosdb.addGroup(rahuldave, rahuldave, dict(name='ml', description="Machine Learning Group"))
    rahuldave, mll=whosdb.addLibrary(rahuldave, rahuldave, dict(name='mll', description="Machine Learning Library"))
    #must explicitly add in testing as this happens on before_request otherwise
    rahuldave, adspubapp=whosdb.addUserToMembable(adsuser, FLAGSHIPAPP, 'rahuldave')

    jayluker=whosdb.addUser(currentuser, dict(nick='jayluker', adsid="jayluker@gmail.com"))
    jayluker, adspubapp=whosdb.addUserToMembable(adsuser, FLAGSHIPAPP, 'jayluker')
    jayluker, mlg=whosdb.inviteUserToMembableUsingNick(rahuldave, 'rahuldave/group:ml', 'jayluker')

    jayluker, mlg = whosdb.acceptInviteToMembable(jayluker, 'rahuldave/group:ml', jayluker)
    jayluker, spg=whosdb.addGroup(jayluker, jayluker, dict(name='sp', description="Solr Programming Group"))
    jayluker, gpg=whosdb.addGroup(jayluker, jayluker, dict(name='gp', description="Gaussian Process Group"))
    jayluker, spl=whosdb.addLibrary(jayluker, jayluker, dict(name='spl', description="Solr Programming Library"))
    jayluker, mpl=whosdb.addLibrary(jayluker, jayluker, dict(name='mpl', description="Mongo Programming Library"))
    rahuldave, mpl=whosdb.inviteUserToMembableUsingNick(jayluker, 'jayluker/library:mpl', 'rahuldave')
    rahuldave, gpg=whosdb.inviteUserToMembableUsingNick(jayluker, 'jayluker/group:gp', 'rahuldave')
    rahuldave, spg=whosdb.addUserToMembable(jayluker, 'jayluker/group:sp', 'rahuldave')
    u, p =whosdb.addMemberableToMembable(jayluker, jayluker, 'jayluker/library:spl', 'rahuldave/group:ml', True)
    import random
    for i in range(20):
        r=random.choice([1,2])
        userstring='user'+str(i)
        user=whosdb.addUser(adsgutuser, dict(adsid=userstring))
        user, adspubapp = whosdb.addUserToMembable(adsuser, FLAGSHIPAPP, user.nick)

        if r==1:
            user, mlg=whosdb.inviteUserToMembableUsingNick(rahuldave, 'rahuldave/group:ml', user.nick)
        else:
            user, spg=whosdb.inviteUserToMembableUsingNick(jayluker, 'jayluker/group:sp', user.nick)

def _init(*args):

    print args
    if len(args)==1:
        db_session=connect(args[0])
    elif len(args)==2:
        db_session=connect("%s" % args[0], host=args[1])
    else:
        print "Not right number of arguments. Exiting"
        sys.exit(-1)
    initialize_application(db_session)
    #initialize_testing(db_session)

if __name__=="__main__":
    import sys
    _init(*sys.argv[1:])
