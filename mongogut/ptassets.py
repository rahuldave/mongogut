from mongoclasses import *
import uuid
import sys
import config
from perms import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser, authorize_membable_owner
from perms import authorize_ownable_owner, authorize_postable_member, authorize_postable_owner, authorize_membable_member
from exc import abort, doabort, ERRGUT
import types

from utilities import *
from collections import defaultdict

from social import Database

from blinker import signal

import operator

#this function is used to connect a sender to a function to be called when a signal is activated
#(blinker signal)
def receiver(f):
    def realreceiver(sender, **data):
        otherargs={}
        for e in data.keys():
            if e not in ['obj', 'currentuser', 'useras']:
                otherargs[e]=data[e]
        obj=data['obj']
        currentuser=data['currentuser']
        useras=data['useras']
        val=f(currentuser, useras, **otherargs)
        return val
    return realreceiver


#this function is used to set up a filter on embedded documents in mongo-engine style. It takes
#an existing query set, and a set of clauses, with a prefix to search under
def embeddedmatch(inqset, ed, **clauseargs):
    propclause={}
    for ele in clauseargs.keys():
        propclause[ed+'__'+ele]=clauseargs[ele]
    of=inqset.filter(**propclause)
    return of

#a matcher for our own little filter language
def element_matcher(ed, clauseargs):
    f={}
    f[ed]={}
    clauselist=[]
    #split the search and set op to =
    for k in clauseargs.keys():
        klst=k.split('__')
        field=klst[0]
        op="eq"
        if len(klst) ==2:
            op=klst[1]
        clauselist.append((field, op, clauseargs[k]))
    #if we want all, explicitly construct a list of all clauses
    for ele in clauselist:
        if ele[1]=='all':
            thedicts=[{ele[0]:x} for x in ele[2]]
    d={}
    #for those not 'all' in the clause 
    for ele in clauselist:
        if ele[1]!='all':
            if ele[1] != 'eq':#get op ifnot eq
                d[ele[0]]={'$'+ele[1]: ele[2]}
            elif ele[1] == 'eq':#got a list
                d[ele[0]]=ele[2]
    #now add in the dicts from the all clause
    for e in thedicts:
        e.update(d)
    mq=[{'$elemMatch': e} for e in thedicts]
    #finally combine under the $all operator
    f[ed]["$all"]=mq
    return f

#This is the database for items and tags and the like. Its done as a separate class to simply keep
#it different from the social aspects, but this is an arbitrary construction. The social database
#is kept under self.whosdb

class Postdb():

    def __init__(self, db_session):
        self.session=db_session
        self.whosdb=Database(db_session)
        #let some methods of the social database be made available here. This simplifies
        #permission checking TODO: not sure the simplicity is worth additional namespace pollution
        self.isOwnerOfOwnable=self.whosdb.isOwnerOfOwnable
        self.isOwnerOfPostable=self.whosdb.isOwnerOfPostable
        self.isMemberOfPostable=self.whosdb.isMemberOfPostable
        self.canIPostToPostable=self.whosdb.canIPostToPostable
        self.isMemberOfMembable=self.whosdb.isMemberOfMembable
        self.isOwnerOfMembable=self.whosdb.isOwnerOfMembable
        self.isSystemUser=self.whosdb.isSystemUser

        #set up a dictionary for signals
        self.signals={}
        
        #set up a dictionary with keys the signals and values the functions that will be called
        #when the signal is fired.
        #            "added-to-app":[receiver(self.recv_spreadOwnedTaggingIntoPostable)],
        SIGNALS={
            "saved-item":[receiver(self.recv_postItemIntoPersonal)],
            "save-to-personal-group-if-not":[receiver(self.recv_postItemIntoPersonal)],
            "tagged-item":[
                        receiver(self.recv_spreadTaggingToAppropriatePostables), receiver(self.recv_postTaggingIntoPersonal)
                    ],
            "tagmode-changed":[receiver(self.recv_spreadTaggingToAppropriatePostables)],
            "added-to-library":[receiver(self.recv_spreadOwnedTaggingIntoPostable)],
        }
        for ele in SIGNALS:
            #set up blinker signal
            self.signals[ele]=signal(ele)
            for r in SIGNALS[ele]:
                self.signals[ele].connect(r, sender=self, weak=False)

    #a set of unprotected functions, to be used internaly to get
    #itemtypes, tagtypes, items, and tags
    def _getItemType(self, currentuser, fullyQualifiedItemType):
        try:
            itemtype=ItemType.objects(basic__fqin=fullyQualifiedItemType).get()
        except:
            doabort('NOT_FND', "ItemType %s not found" % fullyQualifiedItemType)
        return itemtype

    def _getTagType(self, currentuser, fullyQualifiedTagType):
        try:
            tagtype=TagType.objects(basic__fqin=fullyQualifiedTagType).get()
        except:
            doabort('NOT_FND', "TagType %s not found" % fullyQualifiedTagType)
        return tagtype

    def _getItem(self, currentuser, fullyQualifiedItemName):
        try:
            item=Item.objects(basic__fqin=fullyQualifiedItemName).get()
        except:
            doabort('NOT_FND', "Item %s not found" % fullyQualifiedItemName)
        return item

    def _getTag(self, currentuser, fullyQualifiedTagName):
        try:
            tag=Tag.objects(basic__fqin=fullyQualifiedTagName).get()
        except:
            doabort('NOT_FND', "Tag %s not found" % fullyQualifiedTagName)
        return tag


    #add an item type. note masquerading is not allowed in here as this is a system
    #changing function.
    def addItemType(self, currentuser, typespec):
        "add an itemtype. only owners of apps can do this for now"
        typespec['creator']=currentuser.basic.fqin
        typespec=augmenttypespec(typespec)
        useras=currentuser
        authorize(False, self, currentuser, useras)
        #do it in the context of a membable so that it can be used by all members
        membable=self.whosdb._getMembable(currentuser, typespec['membable'])
        #To add a new itemtype you must be owner of the membable!
        authorize_membable_owner(False, self, currentuser, useras, membable)
        try:
            itemtype=ItemType(**typespec)
            itemtype.save(safe=True)
            itemtype.reload()
        except:
            doabort('BAD_REQ', "Failed adding itemtype %s" % typespec['basic'].name)
        return itemtype



    #remove an itemtype. This should not be called in system contexts,
    #but a user might want to do it in their group/app
    def removeItemType(self, currentuser, fullyQualifiedItemType):
        itemtype=self._getItemType(currentuser, fullyQualifiedItemType)
        authorize(False, self, currentuser, currentuser)#any logged in user
        permit(currentuser.nick==itemtype.creator, "User %s not authorized." % currentuser.nick)
        itemtype.delete(safe=True)
        return OK

    #add a tagtype in the context of a membable
    def addTagType(self, currentuser, typespec):
        "add a tagtype in the context of an app"
        typespec['creator']=currentuser.basic.fqin
        typespec=augmenttypespec(typespec, "tagtype")
        useras=currentuser
        authorize(False, self, currentuser, useras)
        membable=self.whosdb._getMembable(currentuser, typespec['membable'])
        #can you post a tag to a group if the tagtype is not in that groups scope?
        authorize_membable_member(False, self, currentuser, useras, membable)
        try:
            tagtype=TagType(**typespec)
            tagtype.save(safe=True)
            tagtype.reload()
        except:
            doabort('BAD_REQ', "Failed adding tagtype %s" % typespec['basic'].name)
        return tagtype

    #remove a tag type. should not be used in system contexts.
    def removeTagType(self, currentuser, fullyQualifiedTagType):
        tagtype=self._getTagType(currentuser, fullyQualifiedTagType)
        authorize(False, self, currentuser, currentuser)#any logged in user
        permit(currentuser.nick==tagtype.creator, "User %s not authorized" % currentuser.nick)
        tagtype.delete(safe=True)
        return OK

    #change ownership of item and tag types. unused for now
    def changeOwnershipOfItemType(self, currentuser, owner, fqitype, fqno):
        newowner=self.changeOwnershipOfOwnable(currentuser, owner, fqitype, fqno)
        return newowner

    def changeOwnershipOfTagType(self, currentuser, owner, fqttype, fqno):
        newowner=self.changeOwnershipOfOwnable(currentuser, owner, fqttype, fqno)
        return newowner

    #the workhorse function. post an item into a library
    def postItemIntoPostable(self, currentuser, useras, fqpn, item):
        #get the library instance
        ptype=gettype(fqpn)
        postable=self.whosdb._getMembable(currentuser, fqpn)
        #make sure you are (a) a member and (b) can write
        authorize_postable_member(False, self, currentuser, useras, postable)
        permit(self.canIPostToPostable(currentuser, useras, postable),
            "No perms to post into library %s" % postable.basic.fqin)
        #where is this item already posted?
        postablefqpns=[ele.postfqin for ele in item.pinpostables]
        #if it is already posted by myself (IDEMPOTENCY), return
        for p in item.pinpostables:
            if p.postfqin==fqpn and p.postedby==useras.adsid:
                return item, p

        #ok now its been posted by another user, or unposted
        now=datetime.datetime.now()

        try:
            #ok is it posted by another user?
            postingdoc=self._getPostingDoc(currentuser, item.basic.fqin, fqpn)
            postingdoc.posting.whenposted=now
            postingdoc.posting.postedby=useras.adsid
            #if so update the posting time (this will bring to top of list)
            #and also update the posting by
            postingdoc.save(safe=True)
            postingdoc.reload()
            newposting=postingdoc.posting
        except:
            #if not, we must make a new posting
            try:
                newposting=Post(postfqin=postable.basic.fqin, posttype=getNSTypeName(fqpn),
                    postedby=useras.adsid, thingtopostfqin=item.basic.fqin, thingtopostname=item.basic.name,
                    thingtopostdescription=item.basic.description, thingtoposttype=item.itemtype, whenposted=now)
                postingdoc=PostingDocument(posting=newposting)
                postingdoc.save(safe=True)
            except:
                doabort('BAD_REQ', "Failed adding newposting of item %s into %s %s." % (item.basic.fqin, typename, postable.basic.fqin))

        #in either case update the item with the new posting
        item.update(safe_update=True, push__pinpostables=newposting)
        #also update the history in the posting doc (remember pd is i,lib uniq)
        newhist=TPHist(postedby=useras.adsid,whenposted=now)
        postingdoc.update(safe_update=True, push__hist=newhist)
        postingdoc.reload()
        #routing. 
        #TODO: ought we be adding to the datatypes app? could be useful for future functionality
        personalfqln=useras.nick+"/library:default"
        #make sure we dont send infinite signals on the signal being fired to add to peronal lib
        if postable.basic.fqin!=personalfqln:
            self.signals['added-to-library'].send(self, obj=self, currentuser=currentuser, useras=useras, item=item, fqpn=fqpn)
        item.reload()
        return item, newposting

    #specifically post to a group library
    def postItemIntoGroupLibrary(self, currentuser, useras, fqgn, item):
        fqnn=getLibForMembable(fqgn)
        item=self.postItemIntoPostable(currentuser, useras, fqnn, item)
        return item
  
    #specifically post to an app library
    def postItemIntoAppLibrary(self, currentuser, useras, fqan, item):
        fqnn=getLibForMembable(fqan)
        item=self.postItemIntoPostable(currentuser, useras, fqnn, item)
        return item

    #stupid wrapper which made more sense whrn u could post into groups
    #TODO rationalize by reducing some of these functions
    def postItemIntoLibrary(self, currentuser, useras, fqln, item):
        item=self.postItemIntoPostable(currentuser, useras, fqln, item)
        return item

    #a reciever that will post an item into a personal library
    #recievers start with recv_
    def recv_postItemIntoPersonal(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['item'])
        item=kwargs['item']
        personalfqln=useras.nick+"/library:default"
        if personalfqln not in [ptt.postfqin for ptt in item.pinpostables]:
            self.postItemIntoLibrary(currentuser, useras, personalfqln, item)

    #remove an item from a postable. This is triggered by the little red buttons
    def removeItemFromPostable(self, currentuser, useras, fqpn, itemfqin):
        ptype=gettype(fqpn)
        postable=self.whosdb._getMembable(currentuser, fqpn)
        item=self._getItem(currentuser, itemfqin)
        cantremove=0
        #if you are an owner of library u can remove it wholesale
        if self.isOwnerOfPostable(currentuser, useras, postable):
            #print "I AM OWNER"
            item.update(safe_update=True, pull__pinpostables={'postfqin':postable.basic.fqin})
            postingdoc=self._getPostingDoc(currentuser, itemfqin, fqpn)
            postingdoc.delete(safe=True)
            return {'status':'OK', 'histset':0}
        #if u are a member, you can remove your own posting of the item, updating history
        if self.isMemberOfPostable(currentuser, useras, postable):
            item.update(safe_update=True, pull__pinpostables={'postfqin':postable.basic.fqin, 'postedby':useras.adsid})
            postingdoc=self._getPostingDoc(currentuser, itemfqin, fqpn)
            postingdoc.update(safe_update=True, pull__hist={'postedby':useras.adsid})
            #reload
            postingdoc.reload()
            hists=postingdoc.hist
            #set the postingdoc to reflect the next-latest post from the hists
            if len(hists) > 0:
                maxdict=max(hists, key=lambda x:x['whenposted'])
                postingdoc.posting.whenposted=maxdict['whenposted']
                postingdoc.posting.postedby=maxdict['postedby']
                postingdoc.save(safe=True)
                postingdoc.reload()
                histset=1
            else:#if this was the only posting you can remove the posting doc!
                postingdoc.delete(safe=True)
                histset=0
        else:
            doabort('BAD_REQ', "Only member of postable %s who posted this item, or owner of postable can remove it" % postable.basic.fqin)
        return {'status':'OK', 'histset':histset}

    #remove item from library
    def removeItemFromLibrary(self, currentuser, useras, fqln, itemfqin):
        removeItemFromPostable(self, currentuser, useras, fqln, itemfqin)

    #a signal reciever for posting into an itemtypes app. we do not use this
    #currently, relying instead on access to itemtype by user being in app
    #but for a website that intends to replicate whats in the ADS, this is the
    #ticket
    def recv_postItemIntoItemtypesApp(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['item'])
        item=kwargs['item']
        fqan=self._getItemType(currentuser, item.itemtype).postable
        self.postItemIntoAppLibrary(currentuser, useras, fqan, item)

    #this is workhorse number two. It ensures that the item is saved in items table, and
    #in the user's default library.
    def saveItem(self, currentuser, useras, itemspec):
        authorize(False, self, currentuser, useras)#sysadmin or any logged in user where but cu and ua must be same
        itemspec['creator']=useras.basic.fqin
        itemspec=augmentitspec(itemspec)
        #try and see if the item already exists in the items table
        try:
            #this does idempotency for us.
            newitem=self._getItem(currentuser, itemspec['basic'].fqin)
        except:
            #the item was not found. Create it
            try:
                newitem=Item(**itemspec)
                newitem.save(safe=True)
                newitem.reload()
            except:
                doabort('BAD_REQ', "Failed adding item %s" % itemspec['basic'].fqin)

        #set up a signal so that item goes into default library
        self.signals['saved-item'].send(self, obj=self, currentuser=currentuser, useras=useras, item=newitem)
        return newitem

    ######now we start with a bunch of tag related methods ########

    #is the useras a member of tag? Note this takes care of indirect membership!!!
    def isMemberOfTag(self, currentuser, useras, tagfqin):
        tag=self._getTag(currentuser, tagfqin)
        ismember=self.whosdb.isMemberOfMembable(currentuser, useras, tag, MEMBERABLES_FOR_TAG_NOT_USER)
        return ismember

    #is the user the owner of the tag(remember owners are always user's)
    #you own a tag by creating it.
    def isOwnerOfTag(self, currentuser, useras, tag):
        if useras.basic.fqin==tag.owner:
            return True
        else:
            return False

    #can you access this itemtype or tagtype?
    def canAccessThisType(self, currentuser, useras, thetype, isitemtype=True):
        if isitemtype:
            typeobj=self._getItemType(currentuser, thetype)
        else:
            typeobj=self._getTagType(currentuser, thetype)
        #this is the critical line: get the membable for the type object
        #for example pub app for pubs: if you are member there you can access pubs
        #this is needed for u to tag and post items
        membable=self.whosdb._getMembable(currentuser, typeobj.membable)
        if self.isMemberOfMembable(currentuser, useras, membable):
                return True
        return False

    #if the tagtypes membable is one we are a member of, we could have created this tag
    def canCreateThisTag(self, currentuser, useras, tagtype):
        "return true if this user can use this tag from access to tagtype, namespace, etc"
        return self.canAccessThisType(currentuser, useras, tagtype, False)

    #another WORKHORSE. can you use a tag. there are various situations in which you can
    #follow along to see what these are.
    def canUseThisTag(self, currentuser, useras, tag):
        "return true is this user can use this tag from access to tagtype, namespace, etc"
        #If you OWN this tag, you can use it
        if self.isOwnerOfTag(currentuser, useras, tag):
            return True
        #if you could not have created this tag, you cant use it
        if not self.canCreateThisTag(currentuser, useras, tag.tagtype):
            return False
        #if you are a member of this tag (directly or indirectly), you can use it
        if self.isMemberOfTag(currentuser, useras, tag.basic.fqin):
            return True
        return False

    def canUseThisFqtn(self, currentuser, useras, fqtn):
        tag=self._getTag(currentuser, fqtn)
        return self.canUseThisTag(currentuser, useras, tag)


    #this is done for making a standalone tag, without tagging anything with it
    def makeTag(self, currentuser, useras, tagspec):
        authorize(False, self, currentuser, useras)#make sure we are logged in
        #first check to see if the tag exists
        try:
            tag=self._getTag(currentuser, tagspec['basic'].fqin)
        except:
            #it wasnt, make it
            try:
                #we must be able to 'create' this tag by being in app/group which the tagtype
                #is affiliated with
                if not self.canCreateThisTag(currentuser, useras, tagspec['tagtype']):
                    doabort('NOT_AUT', "Not authorized for tag %s" % tagspec['basic'].fqin)
                #ok, so now create the tag and add us as a member
                tag=Tag(**tagspec)
                tag.save(safe=True)
                memb=MemberableEmbedded(mtype=User.classname, fqmn=useras.basic.fqin, readwrite=True, pname=useras.presentable_name())
                tag.update(safe_update=True, push__members=memb)
                tag.reload()
                #can obviously use tag if i created it
            except:
                doabort('BAD_REQ', "Failed making tag %s" % tagspec['basic'].fqin)
        #throw error if i cant use tag. if we created it this will not throw error
        if not self.canUseThisTag(currentuser, useras, tag):
            doabort('NOT_AUT', "Not authorized for tag %s" % tagspec['basic'].fqin)
        return tag

    #WORKHORSE: actually tag an item
    #The tagspec here needs to have name and tagtype, this gives, given the useras, the fqtn and allows
    #us to create a new tag or tag an item with an existing tag. If you want to use someone elses tag,
    #on the assumption u are allowed to, add a creator into the tagspec
    def tagItem(self, currentuser, useras, item, tagspec):
        tagspec=musthavekeys(tagspec, ['tagtype'])
        tagtypeobj=self._getTagType(currentuser, tagspec['tagtype'])
        #singletonmode is used for notes. it means each tag is uniqie (each note gets uuid)
        if not tagspec.has_key('singletonmode'):
            tagspec['singletonmode']=tagtypeobj.singletonmode
        if not tagspec.has_key('creator'):
            tagspec['creator']=useras.basic.fqin
        #a note must hasve a tagspec key content. This then becomes the note text
        #which is added to the description, and a unique uuid is assigned as the name
        if tagspec.has_key('content') and tagspec['singletonmode']:
            tagspec['name']=str(uuid.uuid4())
            tagspec['description']=tagspec['content']
            del tagspec['content']
        tagspec=augmentitspec(tagspec, spectype='tag')
        #make sure you are logged in
        authorize(False, self, currentuser, useras)
        itemtobetagged=item
        #the tagmode tells us the privacy of the tag. use if given, else use the
        #tagtype's tagmode. this lets us things like have default note's tagmode as private
        #but add fqpn instead by clicking the checkbox
        if tagspec.has_key('tagmode'):
            tagmode = tagspec['tagmode']
            del tagspec['tagmode']
        else:
            tagmode=tagtypeobj.tagmode

        #makeTag handles idempotency
        tag = self.makeTag(currentuser, useras, tagspec)
        singletonmode=tag.singletonmode
        #Now that we have a tag item, we need to create a tagging
        now=datetime.datetime.now()
        try:
            #because we do this we can never have more than one taggingdoc for item/tag/user
            #so if *we* already tagged item with that tag, just getch the tagging doc
            taggingdoc=self._getTaggingDoc(currentuser, itemtobetagged.basic.fqin, tag.basic.fqin, useras.adsid)
            itemtag=taggingdoc.posting
            #if tagmode for this tag changed, change it (we update it) [no ui for this as yet]
            if tagspec.has_key('tagmode') and itemtag.tagmode!=tagmode:#tagmode has updated value
                taggingdoc.posting.tagmode = tagmode
            taggingdoc.posting.whenposted=now#bump time is only change to idempotency
            taggingdoc.save(safe=True)
            taggingdoc.reload()
        except:
            #ok create a tagging document since it does not exist.
            tagtype=self._getTagType(currentuser, tag.tagtype)
            #if singletonmode pluck the description from the tag else set to empty string
            #todo: we should perhaps get this from a tagtype like thing later?
            if tagtype.singletonmode:
                tagdescript=tag.basic.description
            else:
                tagdescript=""
            #create the tagging
            try:
                itemtag=Tagging(postfqin=tag.basic.fqin,
                                posttype=tag.tagtype,
                                tagname=tag.basic.name,
                                tagmode=tagmode,
                                singletonmode=singletonmode,
                                tagdescription=tagdescript,
                                postedby=useras.adsid,
                                whenposted=now,
                                thingtopostfqin=itemtobetagged.basic.fqin,
                                thingtoposttype=itemtobetagged.itemtype,
                                thingtopostname=itemtobetagged.basic.name,
                                thingtopostdescription=itemtobetagged.basic.description
                )
                #save the taggingdoc
                taggingdoc=TaggingDocument(posting=itemtag)
                taggingdoc.save(safe=True)
                taggingdoc.reload()
                #if its not a singletonmode update the stags on the item
                if not singletonmode:
                    itemtobetagged.update(safe_update=True, push__stags=itemtag)
            except:
                doabort('BAD_REQ', "Failed adding newtagging on item %s with tag %s" % (itemtobetagged.basic.fqin, tag.basic.fqin))
            #signal to save to personal library
            self.signals['save-to-personal-group-if-not'].send(self, obj=self, currentuser=currentuser, useras=useras,
                item=itemtobetagged)
        #in either case, even if retagging, signal tagged item. This will ensure the tagging
        #is spread to appropriate libraries item is in (when tagged in saved items mode, for eg)    
        self.signals['tagged-item'].send(self, obj=self, currentuser=currentuser, useras=useras,
            taggingdoc=taggingdoc, tagmode=tagmode, item=itemtobetagged)
        itemtobetagged.reload()
        return itemtobetagged, tag, itemtag, taggingdoc

    #this is the removal of the tagging doc associated with the useras
    #only that taggingdoc will be removed.
    def untagItem(self, currentuser, useras, fullyQualifiedTagName, fullyQualifiedItemName):
        #make sure user is logged in
        authorize(False, self, currentuser, useras)
        tag=self._getTag(currentuser, fullyQualifiedTagName)
        item=self._getItem(currentuser, fullyQualifiedItemName)
        #make sure user can use this tag
        if not self.canUseThisTag(currentuser, useras, tag):
            doabort('NOT_AUT', "Not authorized for tag %s" % tag.basic.fqin)
        #now get the tagging doc
        taggingdoc=self._getTaggingDoc(currentuser, item.basic.fqin, tag.basic.fqin, useras.adsid)
        #removing the taggingdoc will remove pinpostables will thus
        #remove it from all the places the tagging was spread too
        #get the places to which this taggingdoc went that were posted by you! (this should be all tho
        #as taggingdoc (as oppoed to tag) is specific to u)
        postablefqpns=[e.postfqin for e in taggingdoc.pinpostables if taggingdoc.posting.postedby==useras.adsid]
        for fqpn in postablefqpns:
            #get library, and checking that we are indeed a member, remove tagging from library
            postable=self.whosdb._getMembable(currentuser, fqpn)
            if self.isMemberOfMembable(currentuser, useras, postable):
                self.removeTaggingFromPostable(currentuser, useras, fqpn, fullyQualifiedItemName, fullyQualifiedTagName)
        #if we cerated a note we can remove this note without reservation
        if tag.singletonmode==True:
            #only delete tag if its a note: ie we are in singletonmode
            if not self.isOwnerOfTag(currentuser, useras, tag):
                doabort('NOT_AUT', "Not authorized for tag %s" % tag.basic.fqin)
            tag.delete(safe=True)
        else:#if not note, then remove this tagging from the item
            item.update(safe_update=True, pull__stags={'postfqin':tag.basic.fqin, 'postedby':useras.adsid})
        #now deleting the taggingdoc will also delete all postings for this tag: nice, no?
        taggingdoc.delete(safe=True)
        #we never delete tags from the system unless they are singletonmodes, as we might want to
        #use these tags later
        return OK

    #get the taggingdoc given the u/i/t triad
    def _getTaggingDoc(self, currentuser, fqin, fqtn, adsid):
        try:
          taggingdoc=embeddedmatch(TaggingDocument.objects, "posting", thingtopostfqin=fqin, postfqin=fqtn, postedby=adsid).get()
        except:
          doabort('NOT_FND', "Taggingdoc for tag %s not found" % fqtn)
        return taggingdoc

    #expose this one outside. currently just a simple authorize currentuser to useras.
    #does not make more checks as if u didnt create it, we'll doabort
    def getTaggingDoc(self, currentuser, useras, fqin, fqtn):
        authorize(False, self, currentuser, useras)
        taggingdoc=self._getTaggingDoc(currentuser, fqin, fqtn, useras.adsid)
        return taggingdoc

    #change to make an existing tagging to another mode. dont believe this is exposed as yet
    def changeTagmodeOfTagging(self, currentuser, useras, fqin, fqtn, tomode='0'):
        #below makes sure user owned that tagging doc
        taggingdoc=self.getTaggingDoc(currentuser, useras, fqin, fqtn)
        taggingdoc.update(safe_update=True, set__posting__tagmode=tomode)
        taggingdoc.reload()
        #if tagmode changes send a signal so that reciever will add/take from appropriate libraries
        itemtobetagged=self._getItem(currentuser, fqin)
        self.signals['tagmode-changed'].send(self, obj=self, currentuser=currentuser, useras=useras,
                taggingdoc=taggingdoc, tagmode=tomode, item=itemtobetagged)
        return taggingdoc

    # postingdoc is unique to item and library. get it.
    def _getPostingDoc(self, currentuser, fqin, fqpn):
        postingdoc=embeddedmatch(PostingDocument.objects, "posting", thingtopostfqin=fqin, postfqin=fqpn).get()
        return postingdoc


    #UNUSED FOR NOW: post something into the itemtypes app
    #may be useful for third party apps.
    def recv_postTaggingIntoItemtypesApp(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['item', 'taggingdoc', 'tagmode'])
        item=kwargs['item']
        taggingdoc=kwargs['taggingdoc']
        tagmode=kwargs['tagmode']
        if tagmode=='0':#this works in promiscuous mode only
            fqan=self._getItemType(currentuser, item.itemtype).postable
            self.postTaggingIntoAppLibrary(currentuser, useras, fqan, taggingdoc)

    #WORKHORSE signal reciever.
    #Iit will automatically post YOUR tags to libraries you are a member of
    #if tagmode allows it
    def recv_spreadTaggingToAppropriatePostables(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['tagmode', 'item', 'taggingdoc'])
        item=kwargs['item']
        taggingdoc=kwargs['taggingdoc']
        tagmode=kwargs['tagmode']
        personalfqln=useras.nick+"/library:default"
        #if we are in promiscuous mode
        if tagmode=='0':
            postablesin=[]
            for ptt in item.pinpostables:
                pttfqin=ptt.postfqin
                postable=self.whosdb._getMembable(currentuser, pttfqin)
                #add those non-personal libs u can write to:
                if pttfqin!=personalfqln and self.isMemberOfPostable(currentuser, useras, postable) and self.canIPostToPostable(currentuser, useras, postable):
                    postablesin.append(postable)
            #now post the tagging to the postable
            for postable in postablesin:
                self.postTaggingIntoPostable(currentuser, useras, postable.basic.fqin, taggingdoc)
        #if item posted to an individual library, make sure the tagging is posted there
        #as long as its not the personal library
        if tagmode not in ['0','1']:
            fqpn=tagmode
            postable=self.whosdb._getMembable(currentuser, fqpn)
            if fqpn!=personalfqln and self.isMemberOfPostable(currentuser, useras, postable) and self.canIPostToPostable(currentuser, useras, postable):
                self.postTaggingIntoPostable(currentuser, useras, postable.basic.fqin, taggingdoc)
    
    #this one reacts to the posted-to-postable kind of signal. It takes the taggings on the item that I made and
    #makes sure that these existing taggings are posted into this postable(their mode allowing)
    def recv_spreadOwnedTaggingIntoPostable(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['item', 'fqpn'])
        item=kwargs['item']
        fqpn=kwargs['fqpn']
        for tagging in item.stags:
            if tagging.postedby==useras.basic.fqin:#you did this tagging
                taggingstopost.append(tagging)
        for tagging in taggingstopost:
            #get tagging doc by u/i/t
            taggingdoc=embeddedmatch(TaggingDocument.objects, "posting", postfqin=tagging.postfqin,
                    thingtopostfqin=tagging.thingtopostfqin,
                    postedby=tagging.postedby).get()
            #if tagmode allows us to post it, then we post it. 
            if taggingdoc.posting.tagmode=='0':
                self.postTaggingIntoPostable(currentuser, useras, fqpn, taggingdoc)

    #WORKHORSE: function that posts tagging into a postable. This is either used directly
    #in the items UI or in recievers.
    def postTaggingIntoPostable(self, currentuser, useras, fqpn, taggingdoc):
        itemtag=taggingdoc.posting
        postable=self.whosdb._getMembable(currentuser, fqpn)
        ptype=classtype(postable)
        #TODO:we dont need both of these, i think
        authorize_postable_member(False, self, currentuser, useras, postable)
        permit(self.canIPostToPostable(currentuser, useras, postable),
            "No perms to post into postable %s %s" % (ptype, postable.basic.fqin))
        #get the tag and item and where the item is posted, aborting if u r trying to post
        #tagging to a place where the item has not been posted
        tag=self._getTag(currentuser, itemtag.postfqin)
        item=self._getItem(currentuser, itemtag.thingtopostfqin)
        itemsfqpns =[ele.postfqin for ele in item.pinpostables]
        if not fqpn in itemsfqpns:
            doabort('NOT_AUT', "Cant post tag %s in postable %s if item %s is not there" % (tag.basic.fqin, fqpn, item.basic.fqin))

        #if you cant use the tag, you cant post it into a postable: this is to make sure
        #that some web service is not posting someone elses tag into a postable unless the
        #user can use that tag
        if not self.canUseThisTag(currentuser, useras, tag):
            doabort('NOT_AUT', "Not authorized for tag %s" % tag.basic.fqin)
        #get the posting doc for item and fqpn
        pd=self._getPostingDoc(currentuser, item.basic.fqin, fqpn)
        now=datetime.datetime.now()
        try:
            #first update the taggingdoc with a new posting
            newposting=Post(postfqin=postable.basic.fqin, posttype=getNSTypeNameFromInstance(postable),
                thingtopostname=itemtag.tagname, thingtopostdescription=itemtag.tagdescription,
                postedby=useras.adsid, whenposted=now,
                thingtopostfqin=itemtag.postfqin, thingtoposttype=itemtag.posttype)
            taggingdoc.update(safe_update=True, push__pinpostables=newposting)

            #TODO:postables will be pushed multiple times here. How to unique? i think we ought to have this
            #happen at mongoengine/mongodb level. butwe do uniq on queries so this should be ok
            #still fix at some point. FIXSOON

            #get the rw mode
            if postable.basic.fqin==useras.nick+"/library:default":
                rw=True
            else:
                rw=RWDEF[postable.librarykind]
            #add this postable as a member of the tag if not already there.
            if postable.basic.fqin not in [p.fqmn for p in tag.members]:
                memb=MemberableEmbedded(mtype=postable.classname, fqmn=postable.basic.fqin, readwrite=rw, pname=postable.presentable_name())
                #tag.update(safe_update=True, push__members=postable.basic.fqin)

                tag.update(safe_update=True, push__members=memb)
                tag.reload()
            taggingdoc.reload()
            #update the posting doc in question with this tag
            #Think:will there be one itemtag per item/tag/user combo in this list?
            if not tag.singletonmode:
                pd.update(safe_update=True, push__stags=itemtag)
        except:
            doabort('BAD_REQ', "Failed adding newtagging on item %s with tag %s in postable %s" % (itemtag.thingtopostfqin, itemtag.postfqin, postable.basic.fqin))

        return item, tag, taggingdoc.posting, newposting

    #remove tagging from a library. you may not have permissions to nuke a tag,
    #but you might have permissions to remove it from a library u posted it to
    def removeTaggingFromPostable(self, currentuser, useras, fqpn, fqin, fqtn):
        ptype=gettype(fqpn)
        postable=self.whosdb._getMembable(currentuser, fqpn)
        if postable.basic.fqin==useras.nick+"/library:default":
            rw=True
        else:
            rw=RWDEF[postable.librarykind]
        item=self._getItem(currentuser, fqin)
        tag=self._getTag(currentuser, fqtn)
        #firstly i must be a member of the postable
        authorize_postable_member(False, self, currentuser, useras, postable)
        #need to make sure if i am not the creator of this tag, i am owner of the
        #postable from which tag is being removed.
        owneroftag=useras
        #if i am not the owner of the tag, i better be the owner of the postable.
        if tag.owner!=useras.basic.fqin:
            authorize_postable_owner(False, self, currentuser, useras, postable)
            owneroftag=self.whosdb._getUserForFqin(currentuser, tag.owner)
        #just in case, we'll throw an error here if this user did not post it.
        try:
          taggingdoc=self._getTaggingDoc(currentuser, item.basic.fqin, tag.basic.fqin, owneroftag.adsid)
        except:
          doabort('BAD_REQ', "Wasnt a tagging on item %s with tag %s in postable %s for user %s" % (item.basic.fqin, tag.basic.fqin, postable.basic.fqin, owneroftag.adsid))
        #remove the taggingdoc's pinpostable
        taggingdoc.update(safe_update=True, pull__pinpostables={'postfqin':postable.basic.fqin, 'postedby':owneroftag.adsid})
        #NOTE: even if we remove this tagging, we continue to let the tag have this postable as a member. So there
        #is no deletion of postable membership of tag. This allows the tag to be continued to be used in this library
        if tag.singletonmode:
            return OK
        #only get here for stags (ie not singletonmodes): also update postingdoc by pulling stag
        #from postingdoc
        try:
          postingdoc=self._getPostingDoc(currentuser, item.basic.fqin, fqpn)
        except:
          doabort('BAD_REQ', "Wasnt a postingon item %s in postable %s" % (item.basic.fqin, fqpn))
        #this removes the stag from the postingdoc
        postingdoc.update(safe_update=True, pull__stags={'postfqin':taggingdoc.posting.postfqin, 'thingtopostfqin':item.basic.fqin, 'postedby':owneroftag.adsid})
        return OK

    #just a more specific function for us to use.
    def postTaggingIntoGroupLibrary(self, currentuser, useras, fqgn, taggingdoc):
        fqnn=getLibForMembable(fqgn)
        itemtag=self.postTaggingIntoPostable(currentuser, useras, fqnn, taggingdoc)
        return itemtag

    #a signal called to post tagging into personal lib
    def recv_postTaggingIntoPersonal(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['taggingdoc'])
        taggingdoc=kwargs['taggingdoc']
        personalfqln=useras.nick+"/library:default"
        if personalfqln not in [ptt.postfqin for ptt in taggingdoc.pinpostables]:
            self.postTaggingIntoLibrary(currentuser, useras, personalfqln, taggingdoc)

    def postTaggingIntoAppLibrary(self, currentuser, useras, fqan, taggingdoc):
        fqnn=getLibForMembable(fqan)
        itemtag=self.postTaggingIntoPostable(currentuser, useras, fqnn, taggingdoc)
        return itemtag

    def postTaggingIntoLibrary(self, currentuser, useras, fqln, taggingdoc):
        itemtag=self.postTaggingIntoPostable(currentuser, useras, fqln, taggingdoc)
        return itemtag

    #WORKHORSE: delete a library, group, or app
    #WE MOVED THIS HERE AS WE NEED TO NUKE items/tags/pds/tds, etc associated with
    #a deleted library
    def removeMembable(self,currentuser, useras, fqpn):
        "currentuser removes a postable"
        ptype=gettype(fqpn)
        membable=self.whosdb._getMembable(currentuser, fqpn)
        authorize(LOGGEDIN_A_SUPERUSER_O_USERAS, self.whosdb, currentuser, useras)
        authorize_membable_owner(False, self.whosdb, currentuser, useras, membable)
        #ok, so must find all memberables, and for each memberable, delete this membable for it.
        memberfqins=[m.fqmn for m in membable.members]
        invitedfqins=[m.fqmn for m in membable.inviteds]
        #do it for members, including groups
        for fqin in memberfqins:
            mtype=gettype(fqin)
            member=self.whosdb._getMemberableForFqin(currentuser, mtype, fqin)
            member.update(safe_update=True, pull__postablesin={'fqpn':fqpn})
        #do it for invited users
        for fqin in invitedfqins:
            mtype=gettype(memberablefqin)
            if mtype==User:
                member=self.whosdb._getMemberableForFqin(currentuser, mtype, fqin)
                member.update(safe_update=True, pull__postablesinvitedto={'fqpn':fqpn})
        #remove this library from postables owned by the user
        useras.update(safe_update=True, pull__postablesowned={'fqpn':fqpn})

        #Every item/tag/postingdoc/taggingdoc which has this membable, remove the membable from it
        if ptype==Library:
            items=Item.objects(pinpostables__postfqin=fqpn)
            for i in items:
                i.update(safe_update=True, pull__pinpostables={'postfqin':fqpn})
            pds=PostingDocument.objects(posting__postfqin=fqpn)
            for pd in pds:
                pd.delete(safe=True)
            tds=TaggingDocument.objects(pinpostables__postfqin=fqpn)
            for td in tds:
                td.update(safe_update=True, pull__pinpostables={'postfqin':fqpn})
            tags=Tag.objects(members__fqmn=fqpn)
            for t in tags:
                t.update(safe_update=True, pull__members={'fqmn':fqpn})
        #what if this was a group or an app, then remove it from the libraries it was in
        if ptype in MEMBERABLES_NOT_USER:
            infqpns=[e.fqpn for e in membable.postablesin]
            for f in infqpns:
                postable = self.whosdb._getMembable(currentuser, f)
                postable.update(safe_update=True, pull__members={'fqmn':fqpn})

        #Also, what about public memberships? since anonymouse and group:public
        #would be members, i believe this is taken care off

        #now nuke
        membable.delete(safe=True)
        return OK

    #specific removals
    def removeGroup(self, currentuser, useras, fqpn):
        self.removeMembable(currentuser, useras, fqpn)

    def removeApp(self, currentuser, useras, fqpn):
        self.removeMembable(currentuser, useras, fqpn)

    def removeLibrary(self, currentuser, useras, fqpn):
        self.removeMembable(currentuser, useras, fqpn)

    #################################moving onto searches ###########################
    ######## NOT DOCUMENTED YET #####################################################

    # SO HERE WE LIST THE SEARCHES
    #
    #Use cases
    #(0) get tags, as in get libraries, for a group/user/app/type.
    #(1) get items by tags, and tags intersections, tagspec/itemspec in general
    #(2) get tags for item, and tags for item compatible with user
    #(3) get items for group and app, and filter them further: the postablecontext filter
    #(4) to filter further down by user, the userthere filter.
    #(5) ordering is important. Set up default orders and allow for sorting

    #searchspec has :
    #   should searchspec have libraries?
    #   postablecontext={user:True|False, type:None|group|app, value:None|specificvalue}/None
    #   sort={by:field, ascending:True}/None #currently
    #   criteria=[{field:fieldname, op:operator, value:val}...]
    #   CURRENTLY we use AND outside. To do OR use an op:in query
    #   Finally we need to handle pagination/offsets
    #CRITTERS [{'field': 'owner', 'value': u'adsgut/user:rahuldave', 'op': 'eq'},
    #{'field': 'singleton', 'value': False, 'op': 'eq'}]
    #PREK field owner {'field': 'owner', 'value': u'adsgut/user:rahuldave', 'op': 'eq'
    def _makeQuery(self, klass, currentuser, useras, criteria, postablecontext=None, sort=None, shownfields=None, pagtuple=None):
        DEFPAGOFFSET=0
        DEFPAGSIZE=10
        kwdict={}
        qterms=[]
        #make sure we are atleast logged in and useras or superuser

        #authorize(False, self, currentuser, useras)
        #CHECK we merge RAW criteria so this is always an AND. I believe this is ok.
        dcriteria={}
        numdict=0
        #print '======================================================================='
        #print "CRITTERS", criteria
        for l in criteria:
            if type(l)==types.ListType:
                kwdict={}
                for d in l:
                    if d['op']=='eq':
                        kwdict[d['field']]=d['value']
                    else:
                        kwdict[d['field']+'__'+d['op']]=d['value']
                qterms.append(Q(**kwdict))
            elif type(l)==types.DictType:
                numdict=numdict+1
                precursor=l.keys()[0]
                kwdict={}
                #print "PREK", precursor, l[precursor], l
                for d in l[precursor]:
                    kwdict[d['field']+'__'+d['op']]=d['value']
                f=element_matcher(precursor, kwdict)
                dcriteria.update(f)
                #print "in zees", Q
        if numdict > 0:
            qterms.append(Q(__raw__=dcriteria))
        #print "qterms are", qterms



        if len(qterms) == 0:
            #print "NO CRITERIA"
            itemqset=klass.objects
        elif len(qterms) == 1:
            qclause=qterms[0]
            itemqset=klass.objects.filter(qclause)
        else:
            qclause = reduce(lambda q1, q2: q1.__and__(q2), qterms)
            itemqset=klass.objects.filter(qclause)

        #print "EXPLAIN", itemqset.explain()
        #BUG: if criteria are of type pinpostables, we need to merge criteria and context, otherwise
        #we land up doing an or. The simplest way to do this would be to use context to only filter
        #by user: even user default group goes into criteria (with external wrapper), and
        #merge that onto pinpostable criteria, is any. might have to combing raw with $all.
        userthere=False
        #CONTEXTS ONLY MAKE SENSE WHEN WE DONT USE pinpostables in the criteria.

        #BUG: THIS STUFF DOSENT SEEM TO BE cALLED ANY MORE. SO REMOVE, MAYBE
        # if postablecontext:
        #     if postablecontext=='default':
        #         postablecontext={'user':True, 'type':'group', 'value':useras.nick+"/group:default"}
        #     #BUG validate the values this can take. for eg: type must be a postable. none of then can be None
        #     #print "POSTABLECONTEXT", postablecontext
        #     userthere=postablecontext['user']
        #     ctype=postablecontext['type']
        #     ctarget=postablecontext['value']#a userfqin when needed
        #     postable=self.whosdb._getMembable(currentuser, ctarget)
        #     #BUG cant have dups here in context That would require an anding with context?
        #     #BUG: None of this is currently protected it seems. Add protection here
        #     if userthere:
        #         #print "USERTHERE", useras.basic.fqin, ctarget, ctype
        #         if ctype=="user":
        #             itemqset=itemqset.filter(pinpostables__postedby=ctarget)
        #         elif ctype in Postables:
        #             itemqset=elematch(itemqset, "pinpostables", postfqin=ctarget, postedby=useras.basic.fqin)
        #         #itemqset=itemqset.filter(pinpostables__postfqin=ctarget, pinpostables__postedby=useras.basic.fqin)
        #         #print "count", itemqset.count()
        #     else:
        #         #print "USERNOTTHERE", ctarget
        #         if ctype in Postables:
        #             itemqset=itemqset.filter(pinpostables__postfqin=ctarget)
        #     #BUG: need to set up proper aborts here.
        if sort:
            prefix=""
            if not sort['ascending']:
                prefix='-'
            sorter=prefix+sort['field']
            itemqset=itemqset.order_by(sorter)
        #else:
        #print "NO SORT"
        if shownfields:
            itemqset=itemqset.only(*shownfields)
        count=itemqset.count()
        #notice we get the count earlier, bcoz we want the count without the pagination
        #with pagination there is nothing to count.
        if pagtuple:
            pagoffset=pagtuple[0]
            pagsize=pagtuple[1]
            if pagsize==-1:
                pagsize=DEFPAGSIZE
            if pagoffset==-1:
                pagoffset=DEFPAGOFFSET
            pagend=pagoffset+pagsize
            retset=itemqset[pagoffset:pagend]
        else:
            retset=itemqset

        return count, retset


    def getTypesForQuery(self, currentuser, useras, criteria=False, usernick=False, isitemtype=True):
        SHOWNFIELDS=['postable', 'postabletype', 'basic.fqin', 'basic.description', 'basic.name', 'basic.uri', 'basic.creator', 'owner']
        if not criteria:
            criteria=[]
        if isitemtype:
            klass=ItemType
        else:
            klass=TagType
        if usernick:
            criteria.append([{'field':'owner', 'op':'eq', 'value':useras.basic.fqin}])
        count, result=self._makeQuery(klass, currentuser, useras, criteria, None, None, SHOWNFIELDS, None)
        thetypes=[t for t in result if self.canAccessThisType(currentuser, useras, t.basic.fqin, isitemtype)]
        return len(thetypes), thetypes

    #This can be used to somply get tags in a particular context
    def getTagsForTagspec(self, currentuser, useras, criteria, sort=None):
        SHOWNFIELDS=['tagtype', 'singletonmode', 'basic.fqin', 'basic.description', 'basic.name', 'basic.uri', 'basic.creator', 'owner']
        klass=Tag
        result=self._makeQuery(klass, currentuser, useras, criteria, None, sort, SHOWNFIELDS, None)
        return result


    #the next two are for autocomplete and stuff. They are NOT the tags consistent with the current search.(left hand tags)
    #indeed i am not sure if context works there at all!!!
    #get tags by owner and tagtype. remember this does not do libraries for us anymore.
    #we assume that tagtype based restrictions were taken care of at tag addition time
    #REMEMBER these are searches on tag fields, not on taggings, so postables dont matter a whit
    #except by membership. So either these give global answers, or we need to vary how we use context.

    #AUTOCOMPLETION AUTOCOMPLETION AUTOCOMPLETION
    #BUG: should these be wrapped in canUseThisTag or have we got it implicitly right?
    #I need functions which give me all tags I may use anywhere for AUTOCOMPLETION
    #They are the next two!
    def getTagsAsOwnerOnly(self, currentuser, useras, tagtype=None, singletonmode=False):
        criteria=[
            {'field':'owner', 'op':'eq', 'value':useras.basic.fqin},
            {'field':'singletonmode', 'op':'eq', 'value':singletonmode}
        ]
        #BUG: later add in support for tagtype being a list of tagtypes, currently only one
        if tagtype:
            criteria.append({'field':'tagtype', 'op':'eq', 'value':tagtype})
        result=self.getTagsForTagspec(currentuser, useras, [criteria])
        #print "RESO", [e.basic.name for e in list(result[1])]
        return result

    #You also have access to tags through group ownership of tags
    #no singletonmodes are usually transferred to group ownership
    #this will give me all
    def getTagsAsMemberOnly(self, currentuser, useras, tagtype=None, singletonmode=False, fqpn=None):
        #the postables for which user is a member
        #this is only for group so ok to use postablesForUser
        #why not libs? we should back out the libs tho
        if fqpn:
            postablesforuser=[fqpn]#TODO: make sure user has access somehow
        else:
            postablesforuser=[e['fqpn'] for e in self.whosdb.membablesForUser(currentuser, useras, "library")]
            #postablesforuser=[]
        #print "gtamo", postablesforuser
        #notice in op does OR not AND
        criteria=[
            {'field':'owner', 'op':'ne', 'value':useras.basic.fqin},
            {'field':'members__fqmn', 'op':'in', 'value':postablesforuser},
            {'field':'singletonmode', 'op':'eq', 'value':singletonmode}
        ]
        if tagtype:
            criteria.append({'field':'tagtype', 'op':'eq', 'value':tagtype})
        result=self.getTagsForTagspec(currentuser, useras, [criteria])
        #print "RESM", [e.basic.name for e in list(result[1])]
        return result

    def getAllTagsForUser(self, currentuser, useras, tagtype=None, singletonmode=False, fqpn=None):
        a=self.getTagsAsOwnerOnly(currentuser, useras, tagtype, singletonmode)
        b=self.getTagsAsMemberOnly(currentuser, useras, tagtype, singletonmode, fqpn)
        return (a[0]+b[0], list(a[1])+list(b[1]))


    #if there are no postables, this wont do any checking.
    def _qproc(self, currentuser, useras, query, usernick, specmode=False, default="udg"):
        tagquery=False
        postablequery=False
        tagquerytype=None
        ##print "QUERY=", query
        if query.has_key('stags'):
            tagquery=query.get("stags",[])
            tagquerytype="postfqin"
        elif query.has_key('tagname'):
            tagquery=query.get("tagname",{})
            tagquerytype="tagname"

        postablequery=query.get("postables",[])
        #if postablequey is empty, then default is used
        #BYPASS THIS BY SETTING POSTABLEQUERY FOR SPEC FUNCS
        if not specmode:
            if not postablequery:
                if default=="udg":
                    postablequery=[useras.nick+"/library:default"]
                elif default=="uag":
                    #BUG: should this have all libraries too?
                    #if its a group postablesForUSer is just fine, as there are no wierd access issues
                    postablegroupsforuser=[e['fqpn'] for e in self.whosdb.membablesForUser(currentuser, useras, "group")]
                    ##print "pgfu", postablegroupsforuser
                    postablesforuser = postablegroupsforuser
                    #postablesforuser = postablegroupsforuser + postablelibrariesforuser
                    postablequery=[p.basic.fqin for p in postablesforuser]
        for ele in postablequery:
            postable=self.whosdb._getMembable(currentuser, ele)
            #you must be a member of the library or the group
            authorize_postable_member(False, self, currentuser, useras, postable)
            #if you ask for atuff in apps, you better be an owner
            if getNSTypeName(ele)=="app":
                authorize_postable_owner(False, self, currentuser, useras, postable)
        # if tagquerytype=="postfqin":
        #     for ele in tagquery:
        #         tag=self._getTag(currentuser, ele)
        #         self.canUseThisTag(currentuser, useras, tag)
        userfqin=usernick
        if usernick:
            userfqin='adsgut/user:'+usernick
            userfqin=useras.adsid
        #print "HERE", userfqin
        return tagquery, tagquerytype, postablequery, userfqin


    #notice that items use ALL while postingdocuments use IN. That makes sense as a posting document is intimately
    #tied to a library. items queries may be used to get items in multiple libraries through pinpostables.
    #that information is simply not available in posting documents. I dont have a usecase for items as yet
    #though we do have the uag in qproc

    def _getItemsForQuery(self, shownfields, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None):
        #tagquery is currently assumed to be a list of stags=[tagfqin] or tagnames={tagtype, [names]}
        #or postables=[postfqin]
        klass=Item
        tagquery, tagquerytype, postablequery, userfqin = self._qproc(currentuser, useras, query, usernick)

        if not criteria:
            criteria=[]
        #CHECK:should we separate out the n=1 case as eq not all?
        #Do we need a any instead of all for tagging documents?
        if tagquery and tagquerytype=="postfqin":
            criteria.append(
                    [{'field':'stags__postfqin', 'op':'all', 'value':tagquery}]
            )
        if tagquery and tagquerytype=="tagname":
            criteria.append(
                    {'stags':[{'field':'tagname', 'op':'all', 'value':tagquery},
                                        {'field':'posttype', 'op':'eq', 'value':query['tagtype'][0]}
                    ]}
            )
        if postablequery and not userfqin:
            ##print "NO USER", userfqin
            criteria.append(
                    [{'field':'pinpostables__postfqin', 'op':'all', 'value':postablequery}]
            )

        if postablequery and userfqin:
            ##print "USER", userfqin
            criteria.append(
                    {'pinpostables':[{'field':'postfqin', 'op':'all', 'value':postablequery},
                                        {'field':'postedby', 'op':'eq', 'value':userfqin}
                    ]}
            )
        #print "?OUTCRITERIA",criteria,  sort, pagtuple
        result=self._makeQuery(klass, currentuser, useras, criteria, None, sort, shownfields, pagtuple)
        return result

    def getItemsForQueryOld(self, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None):
        SHOWNFIELDS=['itemtype', 'basic.fqin', 'basic.description', 'basic.name', 'basic.uri']
        #print "USERNICK", usernick
        result=self._getItemsForQuery(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, sort, pagtuple)
        return result

    def _getItemsForQueryFromPostingDocs(self, shownfields, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None, tags=False):
        #tagquery is currently assumed to be a list of stags=[tagfqin] or tagnames={tagtype, [names]}
        #or postables=[postfqin]
        klass=PostingDocument
        tagquery, tagquerytype, postablequery, userfqin = self._qproc(currentuser, useras, query, usernick)

        if not criteria:
            criteria=[]
        #CHECK:should we separate out the n=1 case as eq not all?
        #Do we need a any instead of all for tagging documents?
        if tagquery and tagquerytype=="postfqin":
            criteria.append(
                    [{'field':'stags__postfqin', 'op':'all', 'value':tagquery}]
            )
        if tagquery and tagquerytype=="tagname":
            criteria.append(
                    {'stags':[{'field':'tagname', 'op':'all', 'value':tagquery},
                                        {'field':'posttype', 'op':'eq', 'value':query['tagtype'][0]}
                    ]}
            )
        if postablequery and not userfqin:
            ##print "NO USER", userfqin
            criteria.append(
                    [{'field':'posting__postfqin', 'op':'in', 'value':postablequery}]
            )

        if postablequery and userfqin:
            ##print "USER", userfqin
            criteria.append(
                [{'field':'posting__postfqin', 'op':'in', 'value':postablequery},
                                    {'field':'hist__postedby', 'op':'eq', 'value':userfqin}]
            )
        #print "?OUTCRITERIA",criteria,  sort, pagtuple
        count, result=self._makeQuery(klass, currentuser, useras, criteria, None, sort, shownfields, pagtuple)
        tresult=[]
        for pd in result:
            hists=[e.postedby for e in pd.hist]
            item={'basic':{'fqin':pd.posting.thingtopostfqin,'name':pd.posting.thingtopostname,
                    'description':pd.posting.thingtopostdescription},
                'itemtype':pd.posting.thingtoposttype, 'whenposted':pd.posting.whenposted, 'postedby':pd.posting.postedby, 'hist':hists}
            if tags:
                item['tags']=list(set([e.tagname for e in pd.stags if e.posttype=="ads/tagtype:tag"]))
            tresult.append(item)
        #TODO:does postingby above leak?
        return count, tresult

    def getItemsForQuery(self, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None):
        SHOWNFIELDS=[   'posting.postfqin',
                        'posting.posttype',
                        'posting.thingtopostfqin',
                        'posting.thingtoposttype',
                        'posting.thingtopostname',
                        'posting.whenposted',
                        'posting.postedby',
                        'hist']
        #print "USERNICK", usernick
        result=self._getItemsForQueryFromPostingDocs(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, sort, pagtuple)
        return result

    def getItemsForQueryWithTags(self, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None):
        SHOWNFIELDS=[   'posting.postfqin',
                        'posting.posttype',
                        'posting.thingtopostfqin',
                        'posting.thingtoposttype',
                        'posting.thingtopostname',
                        'posting.whenposted',
                        'posting.postedby',
                        'stags']
        #print "USERNICK", usernick
        result=self._getItemsForQueryFromPostingDocs(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, sort, pagtuple, True)
        return result

    def _getPostingdocsForQuery(self, shownfields, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None, specmode=False):
        #tagquery is currently assumed to be a list of stags=[tagfqin] or tagnames={tagtype, [names]}
        #or postables=[postfqin]
        klass=PostingDocument
        #NO TAG QUERY IN THIS CASE
        tagquery, tagquerytype, postablequery, userfqin = self._qproc(currentuser, useras, query, usernick, specmode)
        if not criteria:
            criteria=[]
        #CHECK:should we separate out the n=1 case as eq not all?
        #Do we need a any instead of all for tagging documents?
        if postablequery and not userfqin:
            #Is the way to look at an embedded list correct here?
            criteria.append(
                    [{'field':'posting__postfqin', 'op':'in', 'value':postablequery}]
            )

        if postablequery and userfqin:
            criteria.append(
                    [{'field':'posting__postfqin', 'op':'in', 'value':postablequery},
                     {'field':'hist__postedby', 'op':'eq', 'value':userfqin}
                    ]
            )
        result=self._makeQuery(klass, currentuser, useras, criteria, None, sort, shownfields, pagtuple)
        return result

    def getPostingsForSpec(self, currentuser, useras, itemfqinlist,sort=None):
        result={}
        query={}
        postablesforuser=[e['fqpn'] for e in self.whosdb.membablesUserCanAccess(currentuser, useras, "library")]
        #print "gps", postablesforuser
        SHOWNFIELDS=[   'posting.postfqin',
                        'posting.posttype',
                        'posting.thingtopostfqin',
                        'posting.thingtoposttype',
                        'posting.thingtopostname',
                        'posting.whenposted',
                        'posting.postedby',
                        'hist']
        #you dont want this as it leaks who posted it in the other library: 'posting.postedby']
        #TODO: not sure of above. seems we need it, and if we are only in one fqpn we be ok as we get postingdocs for one fqpn only

        klass=PostingDocument
        criteria=[]
        criteria.append([
            {'field':'posting__postfqin', 'op':'in', 'value':postablesforuser},
            {'field':'posting__thingtopostfqin', 'op':'in', 'value':itemfqinlist}
        ])
        #query is empty so no additional postables will be added
        result1=self._getPostingdocsForQuery(SHOWNFIELDS, currentuser, useras, query, False, criteria, sort, None, True)
        result2={}
        for i in itemfqinlist:
            result2[i]=[]
        for pd in result1[1]:
            ifqin = pd.posting.thingtopostfqin
            result2[ifqin].append(pd)
        for k in result2.keys():
            result[k] = (len(result2[k]),result2[k])
        return result

    #This should be whittled down further
    def getPostingsConsistentWithUserAndItems(self, currentuser, useras, itemfqinlist, sort=None):
        result=self.getPostingsForSpec(currentuser, useras, itemfqinlist,  sort)
        return result

    def _getTaggingdocsForQuery(self, shownfields, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None, specmode=False):
        #tagquery is currently assumed to be a list of stags=[tagfqin] or tagnames={tagtype, [names]}
        #or postables=[postfqin]
        klass=TaggingDocument

        tagquery, tagquerytype, postablequery, userfqin = self._qproc(currentuser, useras, query, usernick, specmode)
        if not criteria:
            criteria=[]
        #CHECK:should we separate out the n=1 case as eq not all?
        #Do we need a any instead of all for tagging documents?
        if tagquery and tagquerytype=="postfqin":
            criteria.append(
                    [{'field':'posting__postfqin', 'op':'in', 'value':tagquery}]
            )
        # if tagquery and tagquerytype=="tagname":
        #     criteria.append(
        #             {'posting':[{'field':'tagname', 'op':'in', 'value':tagquery['names']},
        #                                 {'field':'tagtype', 'op':'eq', 'value':tagquery['tagtype']}
        #             ]}
        #     )
        if tagquery and tagquerytype=="tagname":
            criteria.append(
                    [{'field':'posting__tagname', 'op':'in', 'value':tagquery},
                                        {'field':'posting__posttype', 'op':'eq', 'value':query['tagtype'][0]}
                    ]
            )

        #notice that this hits the taggings pinpostables rather than the items. in practice, the tagging
        #can only be wgere the item is so this should be equivalent. But think about it TODO
        if postablequery and not userfqin:
            #print "NO USER", userfqin
            criteria.append(
                    [{'field':'pinpostables__postfqin', 'op':'all', 'value':postablequery}]
            )

        if postablequery and userfqin:
            #print "USER", userfqin
            criteria.append(
                    {'pinpostables':[{'field':'postfqin', 'op':'all', 'value':postablequery},
                                        {'field':'postedby', 'op':'eq', 'value':userfqin}
                    ]}
            )
        #print "?OUTCRITERIAtdocs",criteria,  sort, pagtuple
        result=self._makeQuery(klass, currentuser, useras, criteria, None, sort, shownfields, pagtuple)
        return result

    def _getTaggingsFromItems(self, shownfields, currentuser, useras, query, usernick=False, criteria=False, specmode=False):
        #tagquery is currently assumed to be a list of stags=[tagfqin] or tagnames={tagtype, [names]}
        #or postables=[postfqin]
        klass=Item
        tagquery, tagquerytype, postablequery, userfqin = self._qproc(currentuser, useras, query, usernick, specmode)

        if not criteria:
            criteria=[]
        #CHECK:should we separate out the n=1 case as eq not all?
        #Do we need a any instead of all for tagging documents?
        #print "TAGQ", tagquery, tagquerytype
        if tagquery and tagquerytype=="postfqin":
            criteria.append(
                    [{'field':'stags__postfqin', 'op':'all', 'value':tagquery}]
            )
        if tagquery and tagquerytype=="tagname":

            criteria.append(
                    {'stags':[{'field':'tagname', 'op':'all', 'value':tagquery},
                                        {'field':'posttype', 'op':'eq', 'value':query['tagtype'][0]}
                    ]}
            )
        if postablequery and not userfqin:
            #print "NO USER", userfqin
            criteria.append(
                    [{'field':'pinpostables__postfqin', 'op':'all', 'value':postablequery}]
            )

        if postablequery and userfqin:
            #print "USER", userfqin
            criteria.append(
                    {'pinpostables':[{'field':'postfqin', 'op':'all', 'value':postablequery},
                                        {'field':'postedby', 'op':'eq', 'value':userfqin}
                    ]}
            )
        #print "?OUTCRITERIA2222",criteria
        result=self._makeQuery(klass, currentuser, useras, criteria, None, None, shownfields, None)
        return result

    def _getTaggingsFromPostingDocs(self, shownfields, currentuser, useras, query, usernick=False, criteria=False, specmode=False):
        #tagquery is currently assumed to be a list of stags=[tagfqin] or tagnames={tagtype, [names]}
        #or postables=[postfqin]
        klass=PostingDocument
        tagquery, tagquerytype, postablequery, userfqin = self._qproc(currentuser, useras, query, usernick, specmode)

        if not criteria:
            criteria=[]
        #CHECK:should we separate out the n=1 case as eq not all?
        #Do we need a any instead of all for tagging documents?
        #print "TAGQ", tagquery, tagquerytype
        if tagquery and tagquerytype=="postfqin":
            criteria.append(
                    [{'field':'stags__postfqin', 'op':'all', 'value':tagquery}]
            )
        if tagquery and tagquerytype=="tagname":

            criteria.append(
                    {'stags':[{'field':'tagname', 'op':'all', 'value':tagquery},
                                        {'field':'posttype', 'op':'eq', 'value':query['tagtype'][0]}
                    ]}
            )
        if postablequery and not userfqin:
            #print "NO USER", userfqin
            criteria.append(
                    [{'field':'posting__postfqin', 'op':'in', 'value':postablequery}]
            )

        if postablequery and userfqin:
                criteria.append(
                        [{'field':'posting__postfqin', 'op':'in', 'value':postablequery},
                         {'field':'hist__postedby', 'op':'eq', 'value':userfqin}
                        ]
                )
        #print "?OUTCRITERIA2222",criteria
        result=self._makeQuery(klass, currentuser, useras, criteria, None, None, shownfields, None)
        return result

    #Even though we have the posting docs, getTaggingsFromQuery may be easier done from here as we dont have to convert
    #the posting docs to taggings
    def _getTaggingsForQuery(self, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None):
        SHOWNFIELDS=[   'posting.postfqin',
                        'posting.posttype',
                        'posting.thingtopostfqin',
                        'posting.tagname',
                        'posting.whenposted',
                        'posting.tagmode',
                        'posting.postedby']
        result=self._getTaggingdocsForQuery(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, sort, pagtuple)
        return result

    #is this used? we use tagsforpostable but not sure we use taggingsforpostable. I dont see it.
    def getTaggingsForQuery(self, currentuser, useras, query, usernick=False, criteria=False, sort=None):
        results=self._getTaggingsForQuery(currentuser, useras, query, usernick, criteria, sort, None)
        return results


    #this returns fqtns, but perhaps tagnames are more useful? so that we can do more general queries?
    #IMPORTANT: the usernick here gives everything tagged by you, not owned by you
    #BUG currently bake in singletonmode
    def getTagsForQuery(self, currentuser, useras, query, usernick=False, criteria=False):
        SHOWNFIELDS=[ 'stags']
        specmode=False #we start with false but if we are in a postable we should be fine
        count, items=self._getTaggingsFromItems(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, specmode)
        #print "TAGGINGS", count, items, usernick
        fqtns=[]
        for i in items:
            ltns=[e.postfqin for e in i.stags if not e.singletonmode]
            fqtns=fqtns+ltns
        fqtns=set(fqtns)
        tags=[parseTag(f) for f in fqtns if self.canUseThisFqtn(currentuser, useras, f)]
        tagdict=defaultdict(list)
        for k in tags:
            tagdict[k[2]].append(k)
        return len(tags), tagdict

    def getTagsForQueryFromPostingDocs(self, currentuser, useras, query, usernick=False, criteria=False):
        SHOWNFIELDS=[ 'stags']
        specmode=False #we start with false but if we are in a postable we should be fine
        count, pds=self._getTaggingsFromPostingDocs(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, specmode)
        #print "TAGGINGS", count, items, usernick
        fqtns=[]
        for pd in pds:
            ltns=[e.postfqin for e in pd.stags if not e.singletonmode]
            fqtns=fqtns+ltns
        fqtns=set(fqtns)
        #print "FQTNS", fqtns
        tags=[parseTag(f) for f in fqtns if self.canUseThisFqtn(currentuser, useras, f)]
        #print "TAGS", tags
        tagdict=defaultdict(list)
        for k in tags:
            tagdict[k[2]].append(k)
        return len(tags), tagdict

    #BUG: DO WE NOT WANT ANY SINGLETON MODE HERE?
    def getTaggingsForSpec(self, currentuser, useras, itemfqinlist,  sort=None, fqpn=None):
        result={}
        resultfqpn={}
        resultdefault={}
        query={}
        #below could have been done through qproc too BUG: perhaps refactor?
        pfu=self.whosdb.membablesUserCanAccess(currentuser, useras, "library")
        #print "PFU", pfu
        postablesforuser=[e['fqpn'] for e in pfu]
        #print "PFU2", postablesforuser
        #Notice I cant send back pinpostables or I leak taggings that a user might have done which are not in this users ambit!
        SHOWNFIELDS=[   'posting.postfqin',
                        'posting.posttype',
                        'posting.thingtopostfqin',
                        'posting.thingtoposttype',
                        'posting.whenposted',
                        'posting.postedby',
                        'posting.tagname',
                        'posting.tagmode',
                        'posting.tagdescription']
        SHOWNFIELDS2 = [
            'pinpostables',
            'posting.thingtopostfqin'
        ]

        criteria=[]
        criteria.append([
                {'field':'pinpostables__postfqin', 'op':'in', 'value':postablesforuser},
                {'field':'posting__thingtopostfqin', 'op':'in', 'value':itemfqinlist}
        ])
        result1=self._getTaggingdocsForQuery(SHOWNFIELDS, currentuser, useras, query, False, criteria, sort, None, True)
        result2={}
        for i in itemfqinlist:
            result2[i]=[]
            resultfqpn[i]=[]
            resultdefault[i]=[]
        for td in result1[1]:
            ifqin = td.posting.thingtopostfqin
            result2[ifqin].append(td)
        for k in result2.keys():
            result[k] = (len(result2[k]),result2[k])
        #print "RESULT", itemfqinlist, result
        refqpn=self._getTaggingdocsForQuery(SHOWNFIELDS2, currentuser, useras, query, False, criteria, sort, None, True)
        udg=useras.nick+"/library:default"
        for rtd in refqpn[1]:
            #print "RTD",rtd
            res=False
            resd=False
            for p in rtd.pinpostables:
                #print "GEE",fqpn, p.postfqin
                if fqpn == p.postfqin:
                    res = (res or True)
                if p.postfqin == udg:
                    resd = (resd or True)
            resultfqpn[rtd.posting.thingtopostfqin].append(res)
            resultdefault[rtd.posting.thingtopostfqin].append(resd)

            #print fqin, fqpn, result[fqin][0], resultfqpn[fqin]
        return result, resultfqpn, resultdefault

    def getTaggingsConsistentWithUserAndItems(self, currentuser, useras, itemfqinlist, sort=None, fqpn=None):
        result, resultfqpn, resultdefault=self.getTaggingsForSpec(currentuser, useras, itemfqinlist, sort, fqpn)
        return result, resultfqpn, resultdefault

    def getTagsConsistentWithUserAndItems(self, currentuser, useras, itemfqinlist, sort=None):
        result, resultfqpn, resultdefault=self.getTaggingsConsistentWithUserAndItems(currentuser, useras, itemfqinlist, sort)
        #print result
        fqtns=[]
        for fqin in result:
            tags=result[fqin][1]
            for e in tags:
                fqtns.append(e.posting.postfqin)
        fqtns=set(fqtns)
        return len(fqtns), fqtns

    #issues: what if you run this twice? BUG: make sure libs has your current libraries
    #or blow away existing libraries
    def populateLibraries(self, currentuser, useras, libjson):
        authorize(False, self, currentuser, useras)
        li={}
        li=getlibs(li, libjson)
        for k in li.keys():
            useras, library=self.whosdb.addLibrary(useras, useras, dict(name=li[k][0], description=li[k][1], lastmodified=li[k][2]))
            bibdict={}
            for i in range(len(li[k][3])):
                bib=li[k][3][i]
                note=li[k][4][i]
                #this is for speed. the saveItem checks if item is already there and simply returns it.
                if not bibdict.has_key(bib):
                    paper={}
                    paper['name']=bib
                    paper['itemtype']='ads/itemtype:pub'
                    theitem=self.saveItem(useras, useras, paper)
                    bibdict[bib]=theitem
                self.postItemIntoLibrary(useras, useras, library.basic.fqin, bibdict[bib])
                if note != "":
                    i,t,it, td=self.tagItem(useras, useras, bibdict[bib], dict(tagtype="ads/tagtype:note", content=note, tagmode=library.basic.fqin))
                    #if i could override the non-routed tagging i use for notes, below is not needed
                    #however, lower should be faster
                    self.postTaggingIntoLibrary(useras, useras, library.basic.fqin, td)
        return 1




import datetime
def getlibs(libs, json):
    if not json.has_key('libraries'):
        return libs
    for l in json['libraries']:
        lname = l['name']
        #change to not allow : and /, replace both by -
        lname=lname.replace(':', '-').replace("/", '-')
        if not libs.has_key(lname):
            if l.has_key('lastmod'):
                try:
                    tstr=l['lastmod']
                    t=datetime.strptime(tstr,"%d-%b-%Y")
                except:
                    t=datetime.datetime.now()
            else:
                t=datetime.datetime.now()
            libs[lname]=[lname,  l.get('desc',""), t, [e['bibcode'] for e in l['entries']], [e.get('note',"") for e in l['entries']]]
        else:
            daset=set(libs[lname][2])
            newe=[e['bibcode'] for e in l['entries']]
            for e in newe:
                daset.add(e)
            libs[lname][2]=list(daset)
    return libs

def initialize_application(sess):
    currentuser=None
    postdb=Postdb(sess)
    whosdb=postdb.whosdb
    #print "getting adsgutuser"
    adsgutuser=whosdb._getUserForNick(currentuser, "adsgut")
    #print "getting adsuser"
    adsuser=whosdb._getUserForNick(adsgutuser, "ads")
    #adsapp=whosdb.getApp(adsuser, "ads@adslabs.org/app:publications")
    currentuser=adsuser
    postdb.addItemType(adsuser, dict(name="pub", membable=FLAGSHIPAPP))
    postdb.addItemType(adsuser, dict(name="search", membable=FLAGSHIPAPP))
    postdb.addTagType(adsuser, dict(name="tag",  membable=FLAGSHIPAPP))
    postdb.addTagType(adsuser, dict(name="note", membable=FLAGSHIPAPP, tagmode='1', singletonmode=True))


def initialize_testing(db_session):
    currentuser=None
    #print '(((((((((((((((((0000000000000000000000)))))))))))))))))))))'
    postdb=Postdb(db_session)
    whosdb=postdb.whosdb
    #print "getting adsgutuser"
    adsgutuser=whosdb._getUserForNick(currentuser, "adsgut")
    #print "getting adsuser"
    adsuser=whosdb._getUserForNick(adsgutuser, "ads")

    currentuser=adsuser

    #BUG: should this not be protected?
    rahuldave=whosdb._getUserForNick(adsgutuser, "rahuldave")
    jayluker=whosdb._getUserForNick(adsgutuser, "jayluker")


    import simplejson as sj
    papers=sj.loads(open("../fixtures/file.json").read())
    users=[rahuldave, jayluker]
    import random
    thedict={}
    for k in papers.keys():
        r=random.choice([0,1])
        user=users[r]
        paper={}
        paper['name']=papers[k]['bibcode']
        #paper['creator']=user.basic.fqin
        paper['itemtype']='ads/itemtype:pub'
        #print "========", paper
        item=postdb.saveItem(user, user, paper)
        print "------------------------------", user.basic.fqin
        item, posting = postdb.postItemIntoGroupLibrary(user,user, "rahuldave/group:ml", item)
        thedict[k]=item

    #BUG: we dont test here for someone else in the group to use my tag
    #And perhaps we need to go back to being strict on it and reducing the confusion
    #but then we would lose promiscuous autocompletion.
    #also how does the promiscuous tags look on the left side of tagging.
    #BUG: what leakage happens with publiv group? only tags? and not taggings?
    TAGS=['sexy', 'ugly', 'important', 'boring']
    for k in thedict.keys():
        tstr=random.choice(TAGS)
        r=random.choice([0,1])
        user=users[r]
        postdb.tagItem(user, user, thedict[k], dict(tagtype="ads/tagtype:tag", name=tstr))
    TAGS2=['asexy', 'augly', 'aimportant', 'aboring']
    for k in thedict.keys():
        tstr=random.choice(TAGS2)
        r=random.choice([0,1])
        user=users[r]
        postdb.tagItem(user, user, thedict[k], dict(tagtype="ads/tagtype:tag", name=tstr))
    for k in thedict.keys():
        r=random.choice([0,1])
        user=users[r]
        postdb.postItemIntoGroupLibrary(user, user, 'jayluker/group:sp', thedict[k])

    NOTES=["this paper is smart", "this paper is useless", "these authors are clueless"]
    notes={}
    for k in thedict.keys():
        nstr=random.choice(NOTES)
        r=random.choice([0,1])
        user=users[r]
        i,t,it,td=postdb.tagItem(user, user, thedict[k], dict(tagtype="ads/tagtype:note", content=nstr))
        notes[t.basic.name]=(user, i,t,it)
        #print t.basic.name
    mykey=notes.keys()[0]
    #print "USING", mykey
    niw=notes[mykey]
    #print niw[0].basic.fqin, niw[1].basic.fqin, niw[2].basic.fqin, niw[3].tagmode
    #BUG: if we expose this outside we leak. we do need a web sercide, etc to get tagging doc consistent with
    #access.

    #2 different ways of doing things. First just adds to public group. Second adds to all appropriate groups
    tdoutside=postdb.getTaggingDoc(niw[0], niw[0], niw[1].basic.fqin, niw[2].basic.fqin)
    postdb.postItemIntoGroupLibrary(niw[0], niw[0], PUBLICGROUP, niw[1])
    postdb.postTaggingIntoGroupLibrary(niw[0], niw[0], PUBLICGROUP, tdoutside)
    postdb.changeTagmodeOfTagging(niw[0], niw[0], niw[1].basic.fqin, niw[2].basic.fqin)

    LIBRARIES=["rahuldave/library:mll", "jayluker/library:spl"]
    for k in thedict.keys():
        r=random.choice([0,1])
        user=users[r]
        library=LIBRARIES[r]
        postdb.postItemIntoLibrary(user, user, library, thedict[k])

def _init(*args):

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
