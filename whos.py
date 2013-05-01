#managing users, groups, and applications
from classes import *
import config
from permissions import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser
from permissions import authorize_context_owner, authorize_context_member
from errors import abort, doabort, ERRGUT
import types

OK=200
def is_stringtype(v):
    if type(v)==types.StringType or type(v)==types.UnicodeType:
        return True
    else:
        return False

def augmentspec(specdict, spectype="user"):
    basicdict={}
    print "INSPECDICT", specdict
    if spectype=='group' or spectype=='app':
        specdict['owner']=specdict['creator']
        basicdict['creator']=specdict['creator']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        basicdict['fqin']=specdict['creator']+"/"+spectype+":"+specdict['name']
    specdict['basic']=Basic(**basicdict)
    del specdict['name']
    del specdict['creator']
    if specdict.has_key('description'):
        del specdict['description']
    return specdict

#An interface to the user, groups, and apps database
class Whosdb():

    def __init__(self, db_session):
        self.session=db_session
    #Get user object for nickname nick
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
        authorize(False, self, currentuser, user)
        # permit(self.isOwnerOfGroup(currentuser, grp) or self.isSystemUser(currentuser), "User %s must be owner of group %s or systemuser" % (currentuser.nick, grp.fqin))
        # permit(self.isMemberOfGroup(usertobenewowner, grp) or self.isSystemUser(usertobenewowner), " User %s must be member of grp %s or systemuser" % (currentuser.nick, grp.fqin))
        return user
    #Get group object given fqgn, unprotected
    #Bug remove currentuser from here and the cascades. also change signature
    def getGroup(self, currentuser, fqgn):
        try:
            group=Group.objects(basic__fqin=fqgn).get()
        except:
            doabort('NOT_FND', "Group %s not found" % fqgn)
        return group

    #Get group info given fqgn
    def getGroupInfo(self, currentuser, fqgn):
        grp=self.getGroup(currentuser, fqgn)
        #set useras to something not needed in cases where we dont really have useras
        #we use None as it wont match and currentuser being None is already taken care of
        authorize_context_member(False, self, currentuser, None, grp)
        print "AUTH FOR", fqgn
        # permit(self.isOwnerOfGroup(currentuser, grp) or self.isSystemUser(currentuser), "User %s must be owner of group %s or systemuser" % (currentuser.nick, grp.fqin))
        # permit(self.isMemberOfGroup(usertobenewowner, grp) or self.isSystemUser(usertobenewowner), " User %s must be member of grp %s or systemuser" % (currentuser.nick, grp.fqin))
        return grp

    #Get app object fiven fqan, unprotected.
    def getApp(self, currentuser, fqan):
        try:
            app=App.objects(basic__fqin=fqan).get()
        except:
            doabort('NOT_FND', "App %s not found" % fqan)
        return app

    #Get app info given fqan
    def getAppInfo(self, currentuser, fqan):
        app=self.getApp(currentuser, fqan)
        authorize_context_member(False, self, currentuser, None, app)
        return app

    #Get app object fiven fqan, unprotected.
    def getLibrary(self, currentuser, fqln):
        try:
            library=App.objects(basic__fqin=fqln).get()
        except:
            doabort('NOT_FND', "Library %s not found" % fqln)
        return library

    #Get app info given fqan
    def getLibraryInfo(self, currentuser, fqln):
        library=self.getLibrary(currentuser, fqln)
        authorize_context_member(False, self, currentuser, None, library)
        return library

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
            import sys
            print sys.exc_info()
            doabort('BAD_REQ', "Failed adding user %s" % userspec['nick'])
        #Also add user to private default group and public group

        self.addGroup(newuser, dict(name='default', creator=newuser.nick,
            personalgroup=True
        ))
        self.addUserToGroup(currentuser, 'adsgut/group:public', newuser.nick)
        #Faking this for now
        #self.addUserToApp(currentuser, 'ads@adslabs.org/app:publications', newuser, None)
        #Returns user rather than nick here
        return newuser

    #BUG: we want to blacklist users and relist them
    #currently only allow users to be removed through scripts
    def removeUser(self, currentuser, usertoberemovednick):
        #permit(self.isSystemUser(currentuser), "Only System User can remove users")
        #any logged in user not system user will be failed by this.
        authorize(False, self, currentuser, None)
        remuser=self.getUserForNick(currentuser, usertoberemovednick)
        #CONSIDER: remove user from users collection, but not his name elsewhere.
        remuser.delete(safe=True)
        return OK

    def addGroup(self, currentuser, groupspec):
        authorize(False, self, currentuser, currentuser)
        groupspec=augmentspec(groupspec, "group")
        #print "GROUPSPEC", groupspec, groupspec['basic'].fqin
        try:
            newgroup=Group(**groupspec)
            newgroup.save(safe=True)
            #how to save it together?
            userq= User.objects(nick=newgroup.owner)
            res=userq.update(safe_update=True, push__groupsowned=newgroup.basic.fqin)
            #print "result", res, currentuser.groupsowned, currentuser.to_json()
        except:
            import sys
            print sys.exc_info()
            doabort('BAD_REQ', "Failed adding group %s" % groupspec['basic'].name)
        self.addUserToGroup(currentuser, newgroup.basic.fqin, newgroup.basic.creator)
        return newgroup

    def isOwnerOfGroup(self, currentuser, grp):
        if currentuser.nick==grp.owner:
            return True
        else:
            return False

    def isMemberOfGroup(self, currentuser, grp):
        if currentuser.nick in grp.members:
            return True
        else:
            return False

    def isInvitedToGroup(self, currentuser, fqgn):
        if fqgn in currentuser.groupsinvitedto:
            return True
        else:
            return False

    def isOwnerOfApp(self, currentuser, app):
        if currentuser.nick==app.owner:
            return True
        else:
            return False

    def isMemberOfApp(self, currentuser, app):
        if currentuser.nick in app.members:
            return True
        else:
            return False

    def isInvitedToApp(self, currentuser, app):
        if app in currentuser.appsinvitedto:
            return True
        else:
            return False

    def isOwnerOfLibrary(self, currentuser, library):
        if currentuser.nick==library.owner:
            return True
        else:
            return False

    #BUG: dont like this: should this not be getting from whether the library has a group
    #namespace or not?
    def isMemberOfLibrary(self, currentuser, library):
        if currentuser.nick in library.members:
            return True
        else:
            return False
    #The only person who can remove a group is the system user or the owner
    def removeGroup(self,currentuser, fqgn):
        remgrp=self.getGroup(currentuser, fqgn)
        authorize_context_owner(False, self, currentuser, None, remgrp)
        #BUG: group deletion is very fraught. Once someone else is in there
        #the semantics go crazy
        remgrp.delete(safe=True)
        return OK

    def addApp(self, currentuser, appspec):
        authorize(False, self, currentuser, currentuser)
        appspec=augmentspec(appspec, "app")
        print "APPSPEC", appspec
        try:
            newapp=App(**appspec)
            newapp.save(safe=True)
            userq= User.objects(nick=newapp.owner)
            userq.update(safe_update=True, push__appsowned=newapp.basic.fqin)

        except:
            import sys
            print sys.exc_info()
            doabort('BAD_REQ', "Failed adding app %s" % appspec['basic'].name)
        #self.commit()#needed due to full lookup in addUserToApp. fixthis
        self.addUserToApp(currentuser, newapp.basic.fqin, newapp.basic.creator)
        return newapp

    def removeApp(self,currentuser, fqan):
        remapp=self.getApp(currentuser, fqan)
        authorize_context_owner(False, self, currentuser, None, remapp)
        #BUG: app deletion, just like group deletion, is fraught.
        remapp.delete(safe=True)
        return OK


    #DERIVED

    #Adding users to a group is something to be done for public and
    #personal group. There is perhaps a use case in some subscription notion
    def addUserToGroup(self, currentuser, fqgn, usertobeaddednick):
        grpq=Group.objects(basic__fqin=fqgn)
        userq= User.objects(nick=usertobeaddednick)

        try:
            grp=grpq.get()
        except:
            doabort('BAD_REQ', "No such group %s" %  fqgn)

        if fqgn!='adsgut/group:public':
            #special case so any user can add themselves to public group
            #permit(self.isOwnerOfGroup(currentuser, grp) or self.isSystemUser(currentuser), "User %s must be owner of group %s or systemuser" % (currentuser.nick, grp.fqin))
            authorize_context_owner(False, self, currentuser, None, grp)
        try:
            userq.update(safe_update=True, push__groupsin=fqgn)
            grpq.update(safe_update=True, push__members=usertobeaddednick)
        except:
            doabort('BAD_REQ', "Failed adding user %s to group %s" % (usertobeaddednick, fqgn))
        return usertobeaddednick

        #EVEN MORE DERIVED
    #who runs this? is it run on acceptance of group to app? How to permit for that?
    #BUG: complication is with itemtypes app. Currently i have no invite, and the adsuser
    #never runs anything to invite users to the app. How do i manage this?
    def addUserToApp(self, currentuser, fqan, usertobeaddednick):
        appq=App.objects(basic__fqin=fqan)
        userq= User.objects(nick=usertobeaddednick)

        try:
            app=appq.get()
        except:
            doabort('BAD_REQ', "No such app %s" %  fqan)
        authorize_context_owner(False, self, currentuser, None, app)
        try:
            userq.update(safe_update=True, push__appsin=fqan)
            appq.update(safe_update=True, push__members=usertobeaddednick)
        except:
            doabort('BAD_REQ', "Failed adding user %s to app %s" % (usertobeaddednick, fqan))
        return usertobeaddednick

    def inviteUserToGroup(self, currentuser, fqgn, usertobeaddednick):
        grp=self.getGroup(currentuser, fqgn)
        userq= User.objects(nick=usertobeaddednick)
        authorize_context_owner(False, self, currentuser, None, grp)
        try:
            userq.update(safe_update=True, push__groupsinvitedto=fqgn)
        except:
            doabort('BAD_REQ', "Failed inviting user %s to group %s" % (usertobeadded.nick, fqgn))
        #print "IIIII", userq.get().groupsinvitedto
        return usertobeaddednick

    def inviteUserToApp(self, currentuser, fqan, usertobeaddednick):
        app=self.getApp(currentuser, fqan)
        userq= User.objects(nick=usertobeaddednick)
        authorize_context_owner(False, self, currentuser, None, app)
        try:
            userq.update(safe_update=True, push__appsinvitedto=fqan)
        except:
            doabort('BAD_REQ', "Failed inviting user %s to app %s" % (usertobeadded.nick, fqan))
        return usertobeaddednick

    def acceptInviteToGroup(self, currentuser, fqgn, menick):
        grpq=Group.objects(basic__fqin=fqgn)
        userq= User.objects(nick=menick)
        try:
            me=userq.get()
        except:
            doabort('BAD_REQ', "No such user %s" % menick)
        try:
            grp=grpq.get()
        except:
            doabort('BAD_REQ', "No such group %s" % fqgn)
        authorize(False, self, currentuser, me)
        print "JJJJJ", me.groupsinvitedto
        permit(self.isInvitedToGroup(me, grp.basic.fqin), "User %s must be invited to group %s" % (menick, fqgn))
        try:
            userq.update(safe_update=True, push__groupsin=fqgn, pull__groupsinvitedto=fqgn)
            grpq.update(safe_update=True, push__members=menick)
        except:
            doabort('BAD_REQ', "Failed in user %s accepting invite to group %s" % (menick, fqgn))
        return menick

    def acceptInviteToApp(self, currentuser, fqan, menick):
        appq=Group.objects(basic__fqin=fqan)
        userq= User.objects(nick=menick)
        try:
            me=userq.get()
        except:
            doabort('BAD_REQ', "No such user %s" % menick)
        try:
            app=appq.get()
        except:
            doabort('BAD_REQ', "No such app %s" % fqan)
        authorize(False, self, currentuser, me)
        permit(self.isInvitedToApp(me, app.basic.fqin), "User %s must be invited to app %s" % (menick, fqan))
        try:
            userq.update(safe_update=True, push__appsin=fqan, pull__appsinvitedto=fqan)
            appq.update(safe_update=True, push__members=menick)
        except:
            doabort('BAD_REQ', "Failed in user %s accepting invite to app %s" % (menick, fqan))
        return menick


    #Blithely do not worry about users items in a group.
    def removeUserFromGroup(self, currentuser, fqgn, usertoberemovednick):
        grpq=Group.objects(basic__fqin=fqgn)
        userq= User.objects(nick=usertoberemovednick)

        try:
            grp=grpq.get()
        except:
            doabort('BAD_REQ', "No such group %s" % fqgn)
        authorize_context_owner(False, self, currentuser, None, grp)
        try:
            userq.update(safe_update=True, pull_groupsin=fqgn)
            grpq.update(safe_update=True, pull__members=usertoberemovednick)
        except:
            doabort('BAD_REQ', "Failed removing user %s from group %s" % (usertoberemovednick, fqgn))
        return OK

    def removeUserFromApp(self, currentuser, fqan, usertoberemovednick):
        appq=App.objects(basic__fqin=fqan)
        userq= User.objects(nick=usertoberemovednick)

        try:
            app=appq.get()
        except:
            doabort('BAD_REQ', "No such app %s" % fqan)
        authorize_context_owner(False, self, currentuser, None, app)
        try:
            userq.update(safe_update=True, pull_groupsin=fqan)
            appq.update(safe_update=True, pull__members=usertoberemovednick)
        except:
            doabort('BAD_REQ', "Failed removing user %s from app %s" % (usertoberemovednick, fqan))
        return OK

    #BUG: shouldnt new owner have to accept this. Currently, no. We foist it. We'll perhaps never expose this.
    def changeOwnershipOfGroup(self, currentuser, fqgn, usertobenewownernick):
        grpq=Group.objects(basic__fqin=fqgn)
        userq= User.objects(nick=usertobenewownernick)
        try:
            usertobenewowner=userq.get()
        except:
            doabort('BAD_REQ', "No such user %s" % usertobenewownernick)
        try:
            grp=grpq.get()
        except:
            doabort('BAD_REQ', "No such group %s" % fqgn)
        authorize_context_owner(False, self, currentuser, None, grp)
        permit(self.isMemberOfGroup(usertobenewowner, grp), " User %s must be member of grp %s" % (currentuser.nick, fqgn))
        try:
            oldownernick=grp.owner
            grp.update(safe_update=True, set__owner = usertobenewownernick)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for group %s" % (oldownernick, usertobenewowner.nick, fqgn))
        return usertobenewownernick


    #once trnsferroed to a group, cannot be transfered back.
    #for now, u must me member of group to transfer ownership there
    #if you transfer to another person you lose rights
    #groups cant create tags for now, must transfer to group
    #BUG: should be transferable to any 'owner' entity
    #BUG: we want to be able to transfer itemtypes and tagtype
    #ownerships too. But this is different from (or is it?) ownership
    #of a group or app
    def changeOwnershipOfLibrary(self, currentuser, fqln, newowner, groupmode=False):
        libq=Library.objects(basic__fqin=fqln)
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
            lib=libq.get()
        except:
            doabort('BAD_REQ', "No such group %s" % fqtn)
        authorize_context_owner(False, self, currentuser, None, lib)
        try:
            oldownernick=lib.owner
            if groupmode:
                lib.update(safe_update=True, set__owner = newowner, push__members=newowner)
            else:
                lib.update(safe_update=True, set__owner = newowner, push__members=newowner, pull__members=oldownernick)
        except:
            doabort('BAD_REQ', "Failed changing owner from %s to %s for lib %s" % (oldownernick, newowner, fqln))
        return newowner

    #group should be replaced by anything that can be the owner

    def changeOwnershipOfType(self, currentuser, fqtypen, typetype, newowner, groupmode=False):
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


    def ownerOfGroups(self, currentuser, useras):
        authorize(False, self, currentuser, useras)
        groups=useras.groupsowned
        return groups

    def ownerOfApps(self, currentuser, useras):
        authorize(False, self, currentuser, useras)
        applications=useras.appsowned
        return applications

    # def ownerOfLibraries(self, currentuser, useras):
    #     authorize(False, self, currentuser, useras)
    #     applications=useras.librariesowned
    #     return applications


    def usersInGroup(self, currentuser, fqgn):
        grp=self.getGroup(currentuser, fqgn)
        #all members have access to member list as smaller context
        authorize_context_member(False, self, currentuser, None, grp)
        users=grp.members
        return users

    def groupsForUser(self, currentuser, useras):
        authorize(False, self, currentuser, useras)
        groups=useras.groupsin
        return groups

    def groupInvitationsForUser(self, currentuser, useras):
        authorize(False, self, currentuser, useras)
        groups=useras.groupsinvitedto
        return groups

    def usersInApp(self, currentuser, fqan):
        app=self.getApp(currentuser, fqan)
        #owner gets users here as its a bigger context
        authorize_context_owner(False, self, currentuser, None, app)
        users=app.members
        return users


    def appsForUser(self, currentuser, useras):
        authorize(False, self, currentuser, useras)
        apps=useras.appsin
        return apps

    def appInvitationsForUser(self, currentuser, useras):
        authorize(False, self, currentuser, useras)
        apps=useras.appsinvitedto
        return apps
#why cant arguments be specified via destructuring as in coffeescript

def initialize_application(db_session):
    currentuser=None
    whosdb=Whosdb(db_session)
    igspec=dict(personalgroup=False, name="public", description="Public Group", creator="adsgut")
    igspec=augmentspec(igspec, "group")
    #print "IGSPEC", igspec
    initgroup=Group(**igspec)
    initgroup.save(safe=True)
    adsgutuser=whosdb.addUser(currentuser, dict(nick='adsgut', adsid='adsgut'))
    currentuser=adsgutuser
    adsgutapp=whosdb.addApp(currentuser, dict(name='adsgut', description="The MotherShip App", creator=adsgutuser.nick))

    adsuser=whosdb.addUser(currentuser, dict(nick='ads', adsid='ads'))
    #adsuser=User(name='ads', email='ads@adslabs.org')
    currentuser=adsuser
    adspubsapp=whosdb.addApp(currentuser, dict(name='publications', description="ADS's flagship publication app", creator=adsuser.nick))


def initialize_testing(db_session):
    print "INIT TEST"
    whosdb=Whosdb(db_session)
    currentuser=None
    adsgutuser=whosdb.getUserForNick(currentuser, "adsgut")
    currentuser=adsgutuser
    rahuldave=whosdb.addUser(currentuser, dict(nick='rahuldave', adsid="rahuldave"))
    whosdb.addUserToApp(currentuser, 'ads/app:publications', 'rahuldave')
    #rahuldave.applicationsin.append(adspubsapp)

    mlg=whosdb.addGroup(currentuser, dict(name='ml', description="Machine Learning Group", creator="rahuldave"))
    jayluker=whosdb.addUser(currentuser, dict(nick='jayluker', adsid="jayluker"))
    whosdb.addUserToApp(currentuser, 'ads/app:publications', 'jayluker')
    #jayluker.applicationsin.append(adspubsapp)
    print "testing invite"
    currentuser=rahuldave
    whosdb.inviteUserToGroup(currentuser, 'rahuldave/group:ml', 'jayluker')
    print "invited", jayluker.to_json()
    currentuser=jayluker
    whosdb.acceptInviteToGroup(currentuser, 'rahuldave/group:ml', 'jayluker')
    spg=whosdb.addGroup(currentuser, dict(name='sp', description="Solr Programming Group", creator="jayluker"))
    import random
    for i in range(20):
        r=random.choice([1,2])
        user='user'+str(i)
        userst=whosdb.addUser(adsgutuser, dict(nick=user, adsid=user))
        whosdb.addUserToApp(adsgutuser, 'ads/app:publications', user)

        if r==1:
            whosdb.inviteUserToGroup(rahuldave, 'rahuldave/group:ml', user)
        else:
            whosdb.inviteUserToGroup(jayluker, 'jayluker/group:sp', user)
    #whosdb.addGroupToApp(currentuser, 'ads@adslabs.org/app:publications', 'adsgut@adslabs.org/group:public', None )
    #public.applicationsin.append(adspubsapp)
    #rahuldavedefault.applicationsin.append(adspubsapp)
    rahuldave.reload()

    print "ending init", whosdb.ownerOfGroups(rahuldave, rahuldave), rahuldave.to_json()


def makeconnect(dbase):
    dbs=connect(dbase)
    w=Whosdb(dbs)
    return w

if __name__=="__main__":
    db_session=connect("adsgut")
    initialize_application(db_session)
    initialize_testing(db_session)