from mongoclasses import *
import config
from perms import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser, authorize_membable_owner
from perms import authorize_ownable_owner, authorize_postable_member, authorize_postable_owner, authorize_membable_member
from exc import abort, doabort, ERRGUT
import types

import sys
from utilities import *
import copy

def is_membable_embedded_in_memberable(pble, mblesub):
    fqpnhash = dict([(e.fqpn, e) for e in mblesub])
    if pble.basic.fqin in fqpnhash.keys():
        return fqpnhash[pble.basic.fqin]
    return False

def is_memberable_embedded_in_membable(mble, pblesub):
    fqmnhash = dict([(e.fqmn, e) for e in pblesub])
    if mble.basic.fqin in fqmnhash.keys():
        return fqmnhash[mble.basic.fqin]
    return False

class Database():

    def __init__(self, db_session):
        "initialize the database"
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
        "gets user for adsid"
        ##print "ingetuser", [e.nick for e in User.objects]
        ##print "nick", nick
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
    #BUG make sure ptype is in MEMBABLES.
    def _getMembable(self, currentuser, fqpn):
        "gets the postable corresponding to the fqpn"
        return self._getEntity(currentuser, fqpn)

    #this one is protected
    def getMembableInfo(self, currentuser, memberable, fqpn):
        "gets membable only if you are member of the membable"
        membable=self._getMembable(currentuser, fqpn)
        #BUG:this should work for a user member of postable as well as a memberable member of postable
        #print "AUTHING", currentuser.nick, memberable.nick
        authorize_membable_member(MEMBER_OF_MEMBABLE, self, currentuser, memberable, membable)
        #print "GOT HERE"
        owner = self._getUserForFqin(currentuser, membable.owner)
        creator = self._getUserForFqin(currentuser, membable.basic.creator)
        return membable, owner, creator



    def isMemberOfMembable(self, currentuser, memberable, membable, memclass=MEMBERABLES_NOT_USER):
        "is the memberable a member of membable"
        #this is the slow way to do it.
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

    #Also checks for membership!
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
        #print "MEMBERABLE", memberable.to_json(), "MEMBABLE", membable.to_json()
        if useras.basic.fqin in [m.fqmn for m in membable.inviteds]:
            return True
        else:
            return False

    def isInvitedToPostable(self, currentuser, memberable, postable):
        "is the user invited to the postable?"
        return self.isInvitedToMembable(currentuser, memberable, postable)

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
    #BUG just for user currently. Dosent work for other memberables
    def membablesForUser(self, currentuser, useras, ptypestr=None):
        "return the membables the user is DIRECTLY a member of"
        #authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        allmembables=useras.postablesin
        if ptypestr:
            membables=[e for e in allmembables if e['ptype']==ptypestr]
        else:
            membables=allmembables
        return membables

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

    def membablesUserCanWriteTo(self, currentuser, useras, ptypestr=None):
        """return the membables the user can access, directly or
        indirectly(for libraries), which user can write to"""
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

    #why auth here?
    #user/memberable may be member through another memberable
    #this will give just those memberables, and not their expansion: is that ok? i think so
    def membersOfMembable(self, currentuser, memberable, membable):
        "who are the members of the membable?"
        #i need to have access to this if i come in through being a member of a memberable which is a member
        #authorize_postable member takes care of this. That memberable is NOT the same memberable in the arguments here
        authorize_membable_member(False, self, currentuser, memberable, membable)
        #print "CU", currentuser.nick, memberable.nick
        if self.isOwnerOfMembable(currentuser, memberable, membable):
            #print "IS OWNER"
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
        #i need to have access to this if i come in through being a member of a memberable which is a member
        #authorize_postable member takes care of this. That memberable is NOT the same memberable in the arguments here
        authorize_membable_owner(False, self, currentuser, useras, membable)
        inviteds=membable.get_invited_rws()
        return inviteds

    def invitedsForMembableFromFqin(self, currentuser, memberable, fqpn):
        membable=self._getMembable(currentuser, fqpn)
        return self.invitedsForMembable(currentuser, memberable, membable)
    ################################################################################

    #Add user to system, given a userspec from flask user object. commit needed
    #This should never be called from the web interface, but can be called on the fly when user
    #logs in in Giovanni's system. So will there be a cookie or not?
    #BUG: make sure this works on a pythonic API too. think about authorize in a
    #pythonic API setting
    #
    #ought to be initialized on signup or in batch for existing users.
    #adduser must be called with the adsgut user as currentuser
    def addUser(self, currentuser, userspec):
        "add a user to the system. currently only sysadmin can do this"
        #if we are not trying to add adsgut:
        #BUG: any user can add adsuser. Thus this function should never be exposed via web service
        if not userspec['adsid']=='adsgut':
            authorize_systemuser(False, self, currentuser)#I MUST BE SYSTEMUSER
        try:
            userspec=augmentspec(userspec)
            newuser=User(**userspec)
            newuser.save(safe=True)
        except:
            import sys
            print sys.exc_info()
            doabort('BAD_REQ', "Failed adding user %s" % userspec['adsid'])

        #A this point, if adding adsgut, set the currentuser to adsgut
        if userspec['adsid']=='adsgut':
            currentuser=newuser
        #make who is doing this all explicit.
        adsgutuser=currentuser
        #Also add user to private default group and public group

        #currentuser adds this as newuser
        ##print adding default personal group

        #self.addGroup(currentuser, newuser, dict(name='default', creator=newuser.basic.fqin,
        #    personalgroup=True
        #))

        #add youre default library as yourself
        self.addLibrary(adsgutuser, newuser, dict(name='default', creator=newuser.basic.fqin, librarykind='udl'))
        #perhaps this kind of dual addition should later be done via routing?

        #if we are not trying to add adsgut
        if not userspec['adsid']=='adsgut':
            if newuser.basic.fqin!=ANONYMOUSE:
                self.addUserToGroup(adsgutuser, adsgutuser, PUBLICGROUP, newuser.basic.fqin)
                #SHOULD BE AUTOself.addUserToLibrary(adsgutuser, adsgutuser, PUBLICLIBRARY, newuser.basic.fqin)
                #adding to publications app done on importing from giovanni or getting into giovanni, by adsuser
                self.addUserToApp(adsgutuser, adsgutuser, MOTHERSHIPAPP, newuser.basic.fqin)
        newuser.reload()
        return newuser

    #TODO: we want to blacklist users and relist them. add a dormant to user object
    #TODO: what about removal of the user from tags: later we will hook this up to
    #tags a user is a member of, but its not urgent
    #TODO: THINK:What if they have create tagtypes? Then these may still be used but no-one can remove them.
    #this should only be a systemuser thing.
    #Generally we will never do this.
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

    def addMembable(self, currentuser, useras, ptypestr, membablespec_in, appmode=False):
        "the useras adds a postable. currently either currentuser=superuser or useras"
        #authorize(False, self, currentuser, currentuser)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        membablespec_in['creator']=useras.basic.fqin
        membablespec=copy.deepcopy(membablespec_in)
        membablespec=augmentspec(membablespec, ptypestr)
        a = membablespec['basic'].name.find(':')
        b = membablespec['basic'].name.find('/')
        if a!=-1 or b!=-1:
            doabort('BAD_REQ', "Failed adding membable due to presence of : or /  %s" % (membablespec['basic'].name))
        ptype=gettype(membablespec['basic'].fqin)
        try:
            #print "do we exist",membablespec['basic'].fqin
            p=ptype.objects.get(basic__fqin=membablespec['basic'].fqin)
            #print "postable exists", p.basic.fqin
            return useras, p
        except:
            #print "In addPostable", ptypestr, ptype
            try:
                newmembable=ptype(**membablespec)
                newmembable.save(safe=True)
                #how to save it together?
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
                ##print "result", res, currentuser.groupsowned, currentuser.to_json()

            except:
                doabort('BAD_REQ', "Failed adding membable %s %s" % (ptype.__name__, membablespec['basic'].fqin))
            #BUG changerw must be appropriate here!
            #owner must be a user WHY DO WE USE CREATOR?
            self.addMemberableToMembable(currentuser, useras, newmembable.basic.fqin, newmembable.basic.creator, changerw=False, ownermode=True)
            #now if this was a group or an app, add the corresponding library
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
            ##print "autoRELOAD?", userq.get().to_json()
            newmembable.reload()
            return user, newmembable

    def addGroup(self, currentuser, useras, groupspec):
        return self.addMembable(currentuser, useras, "group", groupspec)

    def addApp(self, currentuser, useras, appspec, appmode=False):
        return self.addMembable(currentuser, useras, "app", appspec, appmode)

    def addLibrary(self, currentuser, useras, libraryspec):
        return self.addMembable(currentuser, useras, "library", libraryspec)

    def removeMembable(self,currentuser, useras, fqpn):
        "currentuser removes a postable"
        membable=self._getMembable(currentuser, fqpn)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        authorize_membable_owner(False, self, currentuser, useras, membable)
        #ok, so must find all memberables, and for each memberable, delete this membable for it.
        memberfqins=[m.fqmn for m in membable.members]
        invitedfqins=[m.fqmn for m in membable.inviteds]
        for fqin in memberfqins:
            mtype=gettype(memberablefqin)
            member=self._getMemberableForFqin(currentuser, mtype, fqin)
            member.update(safe_update=True, pull__postablesin={'fqpn':fqpn})
        for fqin in invitedfqins:
            mtype=gettype(memberablefqin)
            if mtype==User:
                member=self._getMemberableForFqin(currentuser, mtype, fqin)
                member.update(safe_update=True, pull__postablesinvitedto={'fqpn':fqpn})
        useras.update(safe_update=True, pull_postablesowned={'fqpn':fqpn})

        #TODO:then every item/tag/postingdoc/taggingdoc which has this membable, remove the membable from it
        #we will do this later. we might use routing. Until then the items will show this group there. perhaps
        #as we check which membables a user can access, and now this membable wont be there,
        #so we may effectively never show it. We might have to deal with tag membership tho. This will be done later
        membable.delete(safe=True)
        return OK

    def removeGroup(self, currentuser, useras, fqpn):
        self.removeMembable(currentuser, useras, fqpn)

    def removeApp(self, currentuser, useras, fqpn):
        self.removeMembable(currentuser, useras, fqpn)

    def removeLibrary(self, currentuser, useras, fqpn):
        self.removeMembable(currentuser, useras, fqpn)

    #BUG: there is no restriction here of what can be added to what in memberables and postables
    #BUG: when do we use get and when not. And what makes sure the fqins are kosher?
    def addMemberableToMembable(self, currentuser, useras, fqpn, memberablefqin, changerw=False, ownermode=False):
        "add a user, group, or app to a postable=group, app, or library"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        membableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(basic__fqin=memberablefqin)
        #BUG currently restricted admission. Later we will want groups and apps proxying for users.
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
            #print "Adding to POSTABLE ", memberable.basic.fqin, postable.basic.fqin, currentuser.basic.fqin, useras.basic.fqin
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
                #print "restriction is", restriction
                if restriction[0]!=None:
                    if restriction[1]==None and ownermode==False:
                        doabort('BAD_REQ', "Only owner is allowed to be a member of %s" %  membable.librarykind)
                    if ownermode==False:#ownly the group/app/pub group entity is allowed to be a member of this library
                        if mtype!=restriction[0]:
                            doabort('BAD_REQ', "Memberable %s not allowed as member of %s library" %  (mtype.__name__,membable.librarykind))
                        if restriction[1]==True:
                            if membable.basic.name!=memberable.basic.name and membable.owner!=memberable.owner:
                                doabort('BAD_REQ', "Memberable %s not allowed as member of %s library" %  (memberable.basic.fqin,membable.basic.fqin))

            #if all of this passes, we are now ok to add

            pe = is_membable_embedded_in_memberable(membable, memberable.postablesin)
            #memb = is_memberable_embedded_in_membable(memberable, postable.members)
            #this would be added a second time but we are protected by this line above!
            if pe == False:
                if ptype==Library:
                    librarykind=membable.librarykind
                    islibrarypublic=membable.islibrarypublic
                else:
                    librarykind=""
                    islibrarypublic=False
                pe=MembableEmbedded(ptype=ptype.classname,fqpn=membable.basic.fqin, owner=useras.adsid, pname = membable.presentable_name(), readwrite=rw, description=membable.basic.description, librarykind=librarykind, islibrarypublic=islibrarypublic)
            memberableq.update(safe_update=True, push__postablesin=pe)
            member = is_memberable_embedded_in_membable(memberable, membable.members)
            if member == False:
                member=MemberableEmbedded(mtype=mtype.classname, fqmn=memberablefqin, readwrite=rw, pname = memberable.presentable_name())
                #if we are already there this happened and do nothing.clearly we need to be careful
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

    #because this is used along with other membership apply/decline funcs, we will go with memberable
    #as opposed to memberablefqin
    #WORKS ONLY FOR POSTABLE=LIBRARY
    def toggleRWForMembership(self, currentuser, useras, fqpn, memberable):
        ptype=gettype(fqpn)
        memberablefqin=memberable.basic.fqin
        mtype=gettype(memberablefqin)
        #print "types", fqpn, ptype, memberablefqin,mtype
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
        if memberablefqin=="adsgut/user:anonymouse":
            #you are guaranteed (sort of) that public group is also member.
            memberable2 = Group.objects(basic__fqin="adsgut/group:public").get()
            memberablefqin = memberable2.basic.fqin
            postables = memberable2.postablesin
        if memberablefqin=="adsgut/group:public":
            memberable2=memberable
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
        if memberablefqin=="adsgut/group:public":
            memberable2.save(safe=True)
        return memberable, postable


    #This should work for tags as well. you must be systemuser or tag owner to remove someone from tags
    def removeMemberableFromMembable(self, currentuser, useras, fqpn, memberablefqin):
        "remove a u/g/a from a g/a/l"
        ptype=gettype(fqpn)
        mtype=gettype(memberablefqin)
        membableq=ptype.objects(basic__fqin=fqpn)
        memberableq= mtype.objects(basic__fqin=memberablefqin)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self, currentuser, useras)
        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s" % fqpn)
        try:
            memberable=memberableq.get()
        except:
            doabort('BAD_REQ', "No such memberable %s" % memberablefqin)

        if useras.basic.fqin==memberablefqin:
            #if the user is removing herself, first make sure she is a member
            authorize_membable_member(False, self, currentuser, useras, membable)
            #now make sure she is not the owner
            if self.isOwnerOfMembable(currentuser, useras, membable):
                doabort('BAD_REQ', "Cannot remove owner %s of %s" % (useras.basic.fqin,fqpn))
        else:
            #otherwise you must be the owner of the membable or systemuser. this is independent
            #of whether the memberable is a user or a group/app in a library
            #or a user in a group/app
            #system user will be allowed by below so we are good
            authorize_membable_owner(False, self, currentuser, useras, membable)
        try:
            memberableq.update(safe_update=True, pull__postablesin__fqpn=membable.basic.fqin)
            #buf not sure how removing embedded doc works, if at all
            membableq.update(safe_update=True, pull__members__fqmn=memberablefqin)
        except:
            doabort('BAD_REQ', "Failed removing memberable %s %s from membable %s %s" % (mtype.__name__, memberablefqin, ptype.__name__, fqpn))
        return OK


    #do we want to use this for libraries? why not? Ca we invite other memberables?
    def inviteUserToMembable(self, currentuser, useras, fqpn, user, changerw=False):
        "invite a user to a postable."
        ptype=gettype(fqpn)
        membable=self._getMembable(currentuser, fqpn)
        usertobeaddedfqin=user.basic.fqin
        rw=False
        if usertobeaddedfqin==useras.basic.fqin:
            doabort('BAD_REQ', "Failed inviting user %s to postable %s as cant invite owner" % (usertobeaddedfqin, fqpn))
        # userq= User.objects(basic__fqin=usertobeaddedfqin)
        # try:
        #     user=userq.get()
        # except:
        #     doabort('BAD_REQ', "No such user %s" % usertobeaddedfqin)
        #print ">>>", membable.owner, useras.basic.fqin, currentuser.basic.fqin, user.basic.fqin
        authorize_membable_owner(False, self, currentuser, useras, membable)
        try:
            if ptype==Library:
                if not changerw:
                    rw=RWDEF[membable.librarykind]
                else:
                    rw= (not RWDEF[membable.librarykind])

            pe = is_membable_embedded_in_memberable(membable, user.postablesinvitedto)
            #memb = is_memberable_embedded_in_membable(memberable, postable.members)
            if pe == False:
                if ptype==Library:
                    librarykind=membable.librarykind
                    islibrarypublic=membable.islibrarypublic
                else:
                    librarykind=""
                    islibrarypublic=False
                pe=MembableEmbedded(ptype=ptype.classname,fqpn=membable.basic.fqin, owner=useras.adsid, pname = membable.presentable_name(), readwrite=rw, description=membable.basic.description, librarykind=librarykind, islibrarypublic=islibrarypublic)
                user.update(safe_update=True, push__postablesinvitedto=pe)

            memb = is_memberable_embedded_in_membable(user, membable.inviteds)
            if memb==False:
                memb=MemberableEmbedded(mtype=User.classname, fqmn=usertobeaddedfqin, readwrite=rw, pname = user.presentable_name())
                #BUG: ok to use fqin here instead of getting from oblect?
                #print "LLL", pe.to_json(), memb.to_json(), "+++++++++++++"
                #print postable.to_json()
                membable.update(safe_update=True, push__inviteds=memb)
            ##print "userq", userq.to_json()
        except:
            doabort('BAD_REQ', "Failed inviting user %s to postable %s" % (usertobeaddedfqin, fqpn))
        ##print "IIIII", userq.get().groupsinvitedto
        membable.reload()
        user.reload()
        return user, membable

    def inviteUserToMembableUsingNick(self, currentuser, fqpn, nick, changerw=False):
        "invite a user to a postable."
        user=self._getUserForNick(currentuser,nick)
        return self.inviteUserToMembable(currentuser, currentuser, fqpn, user, changerw)

    def inviteUserToMembableUsingAdsid(self, currentuser, fqpn, adsid, changerw=False):
        "invite a user to a postable."
        user=self._getUserForAdsid(currentuser,adsid)
        return self.inviteUserToMembable(currentuser, currentuser, fqpn, user, changerw)

    #this cannot be masqueraded, must be explicitly approved by user
    #can we do without the mefqin?
    def acceptInviteToMembable(self, currentuser, fqpn, me):
        "do i accept the invite?"
        ptype=gettype(fqpn)
        membableq=ptype.objects(basic__fqin=fqpn)
        # userq= User.objects(basic__fqin=mefqin)
        # try:
        #     me=userq.get()
        # except:
        #     doabort('BAD_REQ', "No such user %s" % mefqin)
        mefqin=me.basic.fqin
        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s %s" % (ptype.__name__,fqpn))
        authorize(False, self, currentuser, me)
        permit(self.isInvitedToMembable(currentuser, me, membable), "User %s must be invited to membable %s %s" % (mefqin, ptype.__name__,fqpn))
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
            me.update(safe_update=True, push__postablesin=pe, pull__postablesinvitedto__fqpn=pe.fqpn)
            membableq.update(safe_update=True, push__members=memb, pull__inviteds__fqmn=memb.fqmn)
        except:
            doabort('BAD_REQ', "Failed in user %s accepting invite to postable %s %s" % (mefqin, ptype.__name__, fqpn))
        me.reload()
        return me, membableq.get()

    def acceptInviteToMembableUsingNick(self, currentuser, fqpn, nick):
        "invite a user to a postable."
        user=self._getUserForNick(currentuser,nick)
        return self.acceptInviteToMembable(currentuser, fqpn, user)

    def acceptInviteToMembableUsingAdsid(self, currentuser, fqpn, adsid):
        "invite a user to a postable."
        user=self._getUserForNick(currentuser,adsid)
        return self.acceptInviteToMembable(currentuser, fqpn, user)

    #changes postable ownership to a 'ownerable'
    #USER must be owner! This CAN happen through membership in a member group.
    def changeOwnershipOfMembable(self, currentuser, owner, fqpn, newowner):
        "give ownership over to another user for g/a/l"
        ptype=gettype(fqpn)
        membableq=ptype.objects(basic__fqin=fqpn)
        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s %s" % (ptype.__name__,fqpn))
        #Before anything else, make sure I own the stuff so can transfer it.
        #Bug this dosent work if useras is a group

        #useras must be member of postable
        authorize_membable_owner(False, self, currentuser, owner, membable)

        # try:
        #     newowner=self._getUserForFqin(currentuser, newownerfqin)
        # except:
        #     #make sure target exists.
        #     doabort('BAD_REQ', "No such newowner %s" % newownerfqin)
        newownerfqin=newowner.basic.fqin
        #Either as a user or a group, you must be member of group/app or app respectively to
        #transfer membership there. But what does it mean for a group to own a group.
        #it makes sense for library and app, but not for group. Though currently let us have it
        #there. Then if a group owns a group, the person doing the changing must be owner.

        #newowner must be member of the postable (group cant own itself)
        permit(self.isMemberOfMembable(currentuser, newowner, membable),
            " Possible new owner %s must be member of membable %s %s" % ( newownerfqin, ptype.__name__, fqpn))
        #BUG new orners rwmode must be  true!
        #we have removed the possibility of group ownership of postables. CHECK. I've removed the push right now as i assume new owner
        #must be a member of postable. How does this affect tag ownership if at all?
        try:
            #we dont need to be that protective here as we have checked for ownership
            #and only owners can do this
            oldownerfqpn=membable.owner
            members=membable.members
            #get new user me
            #memb=MemberableEmbedded(mtype=User.classname, fqmn=newowner.basic.fqin, readwrite=True, pname = newowner.presentable_name())
            memb = is_memberable_embedded_in_membable(newowner, membable.members)
            #get postable pe
            #If owner the pe must already be there.
            pe = is_membable_embedded_in_memberable(membable, owner.postablesowned)
            #pe=MembableEmbedded(ptype=ptype.classname,fqpn=postable.basic.fqin, owner=newowner.adsid, pname = postable.presentable_name(), readwrite=True, description=postable.basic.description)
            #find new owner as member, locate in postable his membership, update it with readwrite if needed, and make him owner
            #add embedded postable to his ownership and his membership
            membable.update(safe_update=True, set__owner = newowner.basic.fqin)
            newowner.update(safe_update=True, push__postablesowned=pe)
            #for old owner we have removed ownership by changing owner, now remove ownership from him
            owner.update(safe_update=True, pull__postablesowned__fqpn=fqpn)

            #also change library's owner
            if ptype==Group or ptype==App:
                fqnn=getLibForMembable(fqpn)
                lowner, lib=self.changeOwnershipOfMembable(currentuser, owner, fqnn, newowner)
            #if newownertype != User:
            #
            #postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=memb)
            #else:
            #postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=newowner.basic.fqin, pull__members=oldownerfqpn)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for membable %s %s" % (oldownerfqpn, newowner.basic.fqin, ptype.__name__, fqpn))
        newowner.reload()
        membable.reload()
        owner.reload()
        return newowner, membable

    #Instead of changing ownership of a group or app library here we must do it separately
    def changeDescriptionOfMembable(self, currentuser, owner, fqpn, description):
        "give ownership over to another user for g/a/l"
        ptype=gettype(fqpn)
        membableq=ptype.objects(basic__fqin=fqpn)
        try:
            membable=membableq.get()
        except:
            doabort('BAD_REQ', "No such membable %s %s" % (ptype.__name__,fqpn))
        #Before anything else, make sure I own the stuff so can transfer it.
        #Bug this dosent work if useras is a group

        #useras must be member of postable
        authorize_membable_owner(False, self, currentuser, owner, membable)


        try:
            if ptype==Library:
                librarykind=membable.librarykind
                islibrarypublic=membable.islibrarypublic
            else:
                librarykind=""
                islibrarypublic=False
            pe=MembableEmbedded(ptype=ptype.classname,fqpn=membable.basic.fqin, owner=owner.adsid, pname = membable.presentable_name(), readwrite=True, description=description, librarykind=librarykind, islibrarypublic=islibrarypublic)
            #find new owner as member, locate in postable his membership, update it with readwrite if needed, and make him owner
            #add embedded postable to his ownership and his membership
            membableq.update_one(safe_update=True, set__basic__description=description)
            owner.update(safe_update=True, pull__postablesowned__fqpn=fqpn)
            owner.update(safe_update=True, push__postablesowned=pe)

            #if newownertype != User:
            #
            #postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=memb)
            #else:
            #postable.update(safe_update=True, set__owner = newowner.basic.fqin, push__members=newowner.basic.fqin, pull__members=oldownerfqpn)
        except:
            doabort('BAD_REQ', "Failed changing owner description for membable %s %s" % ( ptype.__name__, fqpn))
        owner.reload()
        membable.reload()
        return owner, membable

    #group should be replaced by anything that can be the owner
    #dont want to use this for postables, even though they are ownable.
    #This is where we deal with TAG's. Check. BUG: also combine with above for non repeated code.
    #tags are membables, we dont check that here. Ought it be done with postables?
    #and do we have use cases for tag ownership changes, as opposed to tagtypes and itemtypes?
    #TODO:THINK:this is not explicitly for tags
    def changeOwnershipOfOwnable(self, currentuser, owner, fqon, newowner):
        "this is used for things like itentypes and tagtypes, not for g/a/l."
        otype=gettype(fqon)
        oq=otype.objects(basic__fqin=fqon)
        try:
            ownable=oq.get()
        except:
            doabort('BAD_REQ', "No such ownable %s %s" % (otype.__name__,fqon))
        authorize_ownable_owner(False, self, currentuser, owner, ownable)

        # try:
        #     newowner=self._getUserForFqin(currentuser, newownerfqin)
        # except:
        #     #make sure target exists.
        #     doabort('BAD_REQ', "No such newowner %s" % newownerfqin)
        newownerfqin=newowner.basic.fqin
        permit(self.isMemberOfMembable(currentuser, newowner, ownable),
            " Possible new owner %s must be member of ownable %s %s" % (newownerfqin, ptype.__name__, fqpn))
        try:
            oldownerfqpn=ownable.owner
            #memb=MemberableEmbedded(mtype=User.classname, fqmn=newowner.basic.fqin, readwrite=True, pname = newowner.presentable_name())
            memb = is_memberable_embedded_in_membable(newowner, ownable.members)
            #oq.filter(members__fqmn=newowner.basic.fqin).update_one(safe_update=True, set__owner = newowner.basic.fqin, set__members_S=memb)
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

def initialize_application(db_session):
    #print Group
    currentuser=None
    whosdb=Database(db_session)
    adsgutuser=whosdb.addUser(currentuser, dict(nick='adsgut', adsid='adsgut'))
    currentuser=adsgutuser
    #print "11111 Added Initial User, this should have added private group too"
    igspec=dict(personalgroup=False, name="public", description="Public Group", librarykind="public")
    adsgutuser, publicgrp=whosdb.addGroup(adsgutuser, adsgutuser, igspec)
    #this should automatically create the public library
    #ilspec=dict(name="public", description="Public Library")
    #adsgutuser, publiclib=whosdb.addLibrary(adsgutuser, adsgutuser, ilspec)
    #adsgutuser, publiclibrary=whosdb.addLibraryForGroup(adsgutuser, publicgrp, "public")
    #print "22222 Added Initial Public group"
    adsgutuser, adsgutapp=whosdb.addApp(adsgutuser, adsgutuser, dict(name='adsgut', description="The MotherShip App"))
    #will automatically add a library corresponding to this
    #print "33333 Added Mothership app"
    anonymouseuser=whosdb.addUser(adsgutuser, dict(nick='anonymouse', adsid='anonymouse'))
    adsuser=whosdb.addUser(adsgutuser, dict(nick='ads', adsid='ads'))
    #print "44444 Added ADS user", adsuser.to_json()
    currentuser=adsuser
    adsuser, adspubsapp=whosdb.addApp(adsuser, adsuser, dict(name='publications', description="ADS's flagship publication app"))
    #will automatically add a library corresponding to this
    #TODO: does anonymouse user need to be in flagship app to see anything?
    anonymouseuser, adspubapp=whosdb.addUserToMembable(adsuser, FLAGSHIPAPP, 'anonymouse')
    #print "55555 ADS user added publications app"


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
    #rahuldave.applicationsin.append(adspubsapp)

    #print "currentuser", currentuser.nick
    jayluker=whosdb.addUser(currentuser, dict(nick='jayluker', adsid="jayluker@gmail.com"))
    jayluker, adspubapp=whosdb.addUserToMembable(adsuser, FLAGSHIPAPP, 'jayluker')
    #jayluker.applicationsin.append(adspubsapp)
    #print "GAGAGAGAGAGA", adspubapp.to_json()
    jayluker, mlg=whosdb.inviteUserToMembableUsingNick(rahuldave, 'rahuldave/group:ml', 'jayluker')
    #print "invited", jayluker.to_json()

    jayluker, mlg = whosdb.acceptInviteToMembable(jayluker, 'rahuldave/group:ml', jayluker)
    jayluker, spg=whosdb.addGroup(jayluker, jayluker, dict(name='sp', description="Solr Programming Group"))
    jayluker, gpg=whosdb.addGroup(jayluker, jayluker, dict(name='gp', description="Gaussian Process Group"))
    jayluker, spl=whosdb.addLibrary(jayluker, jayluker, dict(name='spl', description="Solr Programming Library"))
    jayluker, mpl=whosdb.addLibrary(jayluker, jayluker, dict(name='mpl', description="Mongo Programming Library"))
    rahuldave, mpl=whosdb.inviteUserToMembableUsingNick(jayluker, 'jayluker/library:mpl', 'rahuldave')
    rahuldave, gpg=whosdb.inviteUserToMembableUsingNick(jayluker, 'jayluker/group:gp', 'rahuldave')
    rahuldave, spg=whosdb.addUserToMembable(jayluker, 'jayluker/group:sp', 'rahuldave')
    u, p =whosdb.addMemberableToMembable(jayluker, jayluker, 'jayluker/library:spl', 'rahuldave/group:ml', True)
    #print "GEEEE", u, p
    import random
    for i in range(20):
        r=random.choice([1,2])
        userstring='user'+str(i)
        user=whosdb.addUser(adsgutuser, dict(adsid=userstring))
        user, adspubapp = whosdb.addUserToMembable(adsuser, FLAGSHIPAPP, user.nick)

        if r==1:
            user, mlg=whosdb.inviteUserToMembableUsingNick(rahuldave, 'rahuldave/group:ml', user.nick)
            #print "==================================================================================================="
        else:
            user, spg=whosdb.inviteUserToMembableUsingNick(jayluker, 'jayluker/group:sp', user.nick)
    #whosdb.addGroupToApp(currentuser, 'ads@adslabs.org/app:publications', 'adsgut@adslabs.org/group:public', None )
    #public.applicationsin.append(adspubsapp)
    #rahuldavedefault.applicationsin.append(adspubsapp)

    #print "ending init", whosdb.ownerOfMembables(rahuldave, rahuldave), whosdb.ownerOfMembables(rahuldave, rahuldave, "group")
    #print "=============================="
    #print rahuldave.to_json(), mlg.to_json()
    #print "=============================="
    #print adsuser.to_json()
    #print "=============================="

if __name__=="__main__":
    import sys
    if len(sys.argv)==1:
        db_session=connect("adsgut2")
    elif len(sys.argv)==3:
        db_session=connect("adsgut2", host="mongodb://%s:%s@localhost/adsgut2" % (sys.argv[1], sys.argv[2]))
    else:
        print "Not right number of arguments. Exiting"
        sys.exit(-1)
    initialize_application(db_session)
    #initialize_testing(db_session)
