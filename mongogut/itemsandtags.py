from classes import *
import uuid
import sys
import config
from permissions import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser
from permissions import authorize_ownable_owner, authorize_postable_member, authorize_postable_owner, authorize_membable_member
from errors import abort, doabort, ERRGUT
import types

from commondefs import *
from collections import defaultdict

from postables import Database

from blinker import signal

#BUG:replace obj by the sender
def receiver(f):
    ##print "SETTING UP SIGNAL"
    def realreceiver(sender, **data):
        ##print "In real reciever", data,f
        otherargs={}
        for e in data.keys():
            if e not in ['obj', 'currentuser', 'useras']:
                otherargs[e]=data[e]
        obj=data['obj']
        currentuser=data['currentuser']
        useras=data['useras']
        ##print "OTHERARGS", otherargs
        val=f(currentuser, useras, **otherargs)
        return val
    return realreceiver

# Agent.objects.filter(
#     name='ashraf',  
#     __raw__={"skills": {
#         "$elemMatch": {
#             "level": {"$gt": 5}, 
#             "name": "Computer Skills"
#         }
#     }}
# )
def elematchsimple(inqset, ed, **clauseargs):
    propclause={}
    for ele in clauseargs.keys():
        propclause[ed+'__'+ele]=clauseargs[ele]
    of=inqset.filter(**propclause)
    #print "PROPCALUSE", propclause
    return of

def elematch(inqset, ed, **clauseargs):
    f=elematchmaker(ed, clauseargs)
    of=inqset.filter(__raw__=f)
    #print "f",f, of.count()
    return of
#ONLY one level og embedding in elematch
def elematchmaker(ed, clauseargs):
    f={}
    f[ed]={}
    mq={}
    clauselist=[]
    for k in clauseargs.keys():
        klst=k.split('__')
        field=klst[0]
        op="eq"
        if len(klst) ==2:
            op=klst[1]
        clauselist.append((field, op, clauseargs[k]))
    for ele in clauselist:
        if ele[1] != 'eq':
            mq[ele[0]]={'$'+ele[1]: ele[2]}
        else:
            mq[ele[0]]=ele[2]
    f[ed]["$elemMatch"]=mq
    #print "f",f
    return f

#elematchmaker is wrong, atleast for now. so fix
def elematchmaker2(ed, clauseargs):
    f={}
    f[ed]={}
    clauselist=[]
    ##print "CLAUSEARGS", clauseargs
    for k in clauseargs.keys():
        klst=k.split('__')
        field=klst[0]
        op="eq"
        if len(klst) ==2:
            op=klst[1]
        clauselist.append((field, op, clauseargs[k]))
    #BUG:allow for onely one list for now
    ##print "CLAUSELIST", clauselist
    for ele in clauselist:
        if ele[1]=='all':
            thedicts=[{ele[0]:x} for x in ele[2]]
    d={}
    ##print "THEDICTS", thedicts
    for ele in clauselist:
        if ele[1]!='all':
            if ele[1] != 'eq':
                d[ele[0]]={'$'+ele[1]: ele[2]}
            elif ele[1] == 'eq':#got a list
                d[ele[0]]=ele[2]
    ##print "ddddddddddddd", d
    for e in thedicts:
        e.update(d)
    mq=[{'$elemMatch': e} for e in thedicts]
    f[ed]["$all"]=mq
    #print "fffffffffffffffff",f
    return f
#BUG need signal handlers for added to app, added to lib. Especially for lib, do we post tags to lib.
#what does that even mean? We will do it but i am not sure what it means. I mean we will get tags
#consistent with user from his groups, not libs, so what does it mean to get tags posted to a lib?
#BUG:is there conflict between spreadOwnedTaggingIntoPostable and postTaggingIntoItemtypesApp
class Postdb():
    
    def __init__(self, db_session):
        self.session=db_session
        self.whosdb=Database(db_session)
        self.isSystemUser=self.whosdb.isSystemUser
        self.isOwnerOfOwnable=self.whosdb.isOwnerOfOwnable
        self.isOwnerOfPostable=self.whosdb.isOwnerOfPostable
        self.isMemberOfPostable=self.whosdb.isMemberOfPostable
        self.canIPostToPostable=self.whosdb.canIPostToPostable
        self.isMemberOfMembable=self.whosdb.isMemberOfMembable
        self.signals={}
        #CHECK taking out  receiver(self.recv_postTaggingIntoItemtypesApp) 
        # , from tagged items as will happen by appr.
        #postables. General BUG tho that we can post taggings multiple times. Add check
        #"added-to-group":[receiver(self.recv_postItemIntoPersonal), receiver(self.recv_spreadOwnedTaggingIntoPostable)],


        SIGNALS={
            "saved-item":[receiver(self.recv_postItemIntoPersonal), receiver(self.recv_postItemIntoItemtypesApp)],
            "added-to-group":[receiver(self.recv_spreadOwnedTaggingIntoPostable)],
            "save-to-personal-group-if-not":[receiver(self.recv_postItemIntoPersonal)],
            "tagged-item":[
                        receiver(self.recv_spreadTaggingToAppropriatePostables), receiver(self.recv_postTaggingIntoPersonal)
                    ],
            "tagmode-changed":[receiver(self.recv_spreadTaggingToAppropriatePostables)],
            "added-to-app":[receiver(self.recv_spreadOwnedTaggingIntoPostable)],
            "added-to-library":[receiver(self.recv_spreadOwnedTaggingIntoPostable)],
        }
        for ele in SIGNALS:
            self.signals[ele]=signal(ele)
            ##print ele, len(SIGNALS[ele])
            for r in SIGNALS[ele]:
                self.signals[ele].connect(r, sender=self, weak=False)
            ##print "[[]]", self.signals[ele], self.signals[ele].receivers
        ##print "ssiiggnnaallss", self.signals['saved-item'].receivers

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


    #BUG: add a protected getTagInfo and getItemInfo

    #BUG useras must be a user. Not a general postable for now
    #one must change ownership
    def addItemType(self, currentuser, typespec):
        "add an itemtype. only owners of apps can do this for now"
        typespec['creator']=currentuser.basic.fqin
        typespec=augmenttypespec(typespec)
        useras=currentuser
        authorize(False, self, currentuser, useras)
        postable=self.whosdb.getPostable(currentuser, typespec['postable'])
        #To add a new itemtype you must be owner!
        authorize_ownable_owner(False, self, currentuser, useras, postable)
        try:
            itemtype=ItemType(**typespec)
            itemtype.save(safe=True)
            itemtype.reload()
        except:
            # import sys
            # #print sys.exc_info()
            doabort('BAD_REQ', "Failed adding itemtype %s" % typespec['basic'].name)
        return itemtype



    #BUG: completely not dealing with all the things of that itemtype
    #if refcount is even 1, one shouldnt allow it
    #should this have a useras?
    def removeItemType(self, currentuser, fullyQualifiedItemType):
        itemtype=self._getItemType(currentuser, fullyQualifiedItemType)
        authorize(False, self, currentuser, currentuser)#any logged in user
        permit(currentuser.nick==itemtype.creator, "User %s not authorized." % currentuser.nick)
        itemtype.delete(safe=True)
        return OK

    def addTagType(self, currentuser, typespec):
        typespec['creator']=currentuser.basic.fqin
        typespec=augmenttypespec(typespec, "tagtype")
        useras=currentuser
        authorize(False, self, currentuser, useras)
        postable=self.whosdb.getPostable(currentuser, typespec['postable'])
        #BUG CHECK: do we want anyone to be able to add stuff to an app? or only groups and libraries?
        #or should we revert to only owners having tagtypes
        #also what are implications for personal and public groups and all that, either way.
        #can you post a tag to a group if the tagtype is not in that groups scope?
        authorize_postable_member(False, self, currentuser, useras, postable)
        try:
            #print "TAGSPEC", typespec, typespec['basic'].to_json()
            tagtype=TagType(**typespec)
            tagtype.save(safe=True)
            tagtype.reload()
        except:
            doabort('BAD_REQ', "Failed adding tagtype %s" % typespec['basic'].name)
        return tagtype

    #BUG: completely not dealing with all the things of that itemtype
    #should this have a useras
    def removeTagType(self, currentuser, fullyQualifiedTagType):
        tagtype=self._getTagType(currentuser, fullyQualifiedTagType)
        authorize(False, self, currentuser, currentuser)#any logged in user
        permit(currentuser.nick==tagtype.creator, "User %s not authorized" % currentuser.nick)
        tagtype.delete(safe=True)
        return OK

    def changeOwnershipOfItemType(self, currentuser, owner, fqitype, fqno):
        #BUG put something here to make sure itype and such
        newowner=self.changeOwnershipOfOwnableType(currentuser, owner, fqitype, fqno)
        return newowner

    def changeOwnershipOfTagType(self, currentuser, owner, fqttype, fqno):
        #BUG put something here to make sure itype and such
        newowner=self.changeOwnershipOfOwnableType(currentuser, owner, fqttype, fqno)
        return newowner

    def postItemIntoPostable(self, currentuser, useras, fqpn, item):
        #print "FQPN=======", fqpn
        ptype=gettype(fqpn)
        postable=self.whosdb.getPostable(currentuser, fqpn)
        typename=getNSTypeNameFromInstance(postable)
        #item=self._getItem(currentuser, itemfqin)
        #Does the False have something to do with this being ok if it fails?BUG
        #BUG:we dont need both of these, i think
        authorize_postable_member(False, self, currentuser, useras, postable)
        permit(self.canIPostToPostable(currentuser, useras, postable),
            "No perms to post into postable %s %s" % (typename, postable.basic.fqin))
        postablefqpns=[ele.postfqin for ele in item.pinpostables]
        #ALREADY POSTED IDEMPOTENCY. REVISIT
        #DONT RETURN POSTINGDOC currently as how to search. THUS return newposting
        for p in item.pinpostables:
            if p.postfqin==fqpn:
                return item, p
        # if fqpn in postablefqpns:
        #     return item
        try:#BUG:what if its already there? Now fixed?
            #BUG: what if someone else had also posted it into a group, should we do it again or not?
            #or do a unique on the query later in postings...
            newposting=Post(postfqin=postable.basic.fqin, posttype=getNSTypeName(fqpn), 
                postedby=useras.adsid, thingtopostfqin=item.basic.fqin, 
                thingtoposttype=item.itemtype)
            postingdoc=PostingDocument(posting=newposting)
            postingdoc.save(safe=True)
            postingdoc.reload()
            #Not sure instance updates work but we shall try.
            item.update(safe_update=True, push__pinpostables=newposting)
        except:
            import sys
            #print sys.exc_info()
            doabort('BAD_REQ', "Failed adding newposting of item %s into %s %s." % (item.basic.fqin, typename, postable.basic.fqin))
        #BUG: now send to personal group via routing. Still have to add to datatypes app
        personalfqgn=useras.nick+"/group:default"
        #not sure below is needed. Being defensive CHECK
        if postable.basic.fqin!=personalfqgn:
            #print "RUNNING FOR", typename, postable.basic.fqin
            self.signals['added-to-'+typename].send(self, obj=self, currentuser=currentuser, useras=useras, item=item, fqpn=fqpn)
        item.reload()
        return item, newposting

    def postItemIntoGroup(self, currentuser, useras, fqgn, item):
        item=self.postItemIntoPostable(currentuser, useras, fqgn, item)
        return item

    def recv_postItemIntoPersonal(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['item'])
        #print "POST ITEM INTO PERSONAL", kwargs
        item=kwargs['item']
        personalfqgn=useras.nick+"/group:default"
        #item=self._getItem(currentuser, itemfqin)
        if personalfqgn not in [ptt.postfqin for ptt in item.pinpostables]:
            #print "NOT IN PERSONAL GRP"
            self.postItemIntoGroup(currentuser, useras, personalfqgn, item)

    def postItemIntoApp(self, currentuser, useras, fqan, item):
        item=self.postItemIntoPostable(currentuser, useras, fqan, item)
        return item

    def postItemIntoLibrary(self, currentuser, useras, fqln, item):
        item=self.postItemIntoPostable(currentuser, useras, fqln, item)
        return item

    def removeItemFromPostable(self, currentuser, useras, fqpn, itemfqin):
        ptype=gettype(fqpn)
        postable=self.whosdb.getPostable(currentuser, fqpn)
        item=self._getItem(currentuser, itemfqin)
        #BUG posting must somehow be got from item
        postingtoremove=item
        permit(useras==postingtoremove.user and self.isMemberOfPostable(useras, postable),
            "Only member of group %s who posted this item can remove it from the app" % grp.basic.fqin)
        #NO CODE HERE YET
        return OK

    def removeItemFromGroup(self, currentuser, useras, fqgn, itemfqin):
        removeItemFromPostable(self, currentuser, useras, fqgn, itemfqin)

    def removeItemFromApp(self, currentuser, useras, fqan, itemfqin):
        removeItemFromPostable(self, currentuser, useras, fqan, itemfqin)

    def removeItemFromLibrary(self, currentuser, useras, fqln, itemfqin):
        removeItemFromPostable(self, currentuser, useras, fqln, itemfqin)

    def recv_postItemIntoItemtypesApp(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['item'])
        #print "POST ITEM INTO ITEMTYPES APP", kwargs
        item=kwargs['item']
        #tem=self._getItem(currentuser, itemfqin)
        fqan=self._getItemType(currentuser, item.itemtype).postable
        self.postItemIntoApp(currentuser, useras, fqan, item)

    def saveItem(self, currentuser, useras, itemspec):
        #permit(currentuser==useras or self.whosdb.isSystemUser(currentuser), "User %s not authorized or not systemuser" % currentuser.nick)
        authorize(False, self, currentuser, useras)#sysadmin or any logged in user where but cu and ua must be same
        personalfqgn=useras.nick+"/group:default"
        itemspec['creator']=useras.basic.fqin
        itemspec=augmentitspec(itemspec)
        #Information about user useras goes as namespace into newitem, but should somehow also be in main lookup table
        #print "ITEMSPEC", itemspec, itemspec['basic'].to_json()
        try:
            #print "was the item found?"
            #this does idempotency for us. 
            newitem=self._getItem(currentuser, itemspec['basic'].fqin)
            #TODO: do we want to handle an updated saving date here by making an array
            #this way we could count how many times 'saved'
        except:
            #the item was not found. Create it
            #print "SO CREATING ITEM %s\n" % itemspec['basic'].fqin
            try:
                #print "ITSPEC", itemspec
                newitem=Item(**itemspec)
                newitem.save(safe=True)
                newitem.reload()
                # #print "Newitem is", newitem.info()
            except:
                # import sys
                # #print sys.exc_info()
                doabort('BAD_REQ', "Failed adding item %s" % itemspec['basic'].fqin)

        ##print "RECEIBERS", self.signals['saved-item'], self.signals['saved-item'].receivers
        self.signals['saved-item'].send(self, obj=self, currentuser=currentuser, useras=useras, item=newitem)
        #not needed due to above:self.postItemIntoGroup(currentuser, useras, personalfqgn, newitem.basic.fqin)
        #SIGNALS needed even if item is already saved so we add it to personal group! Tres cool! What about itemtypes app?
        #Since posting into postables is idempotent it will not be reposted (hopefully :-))
        #print '**********************'
        #IN LIEU OF ROUTING
        #BUG: shouldnt this be done by routing
        #Now taken care of by routingp
        #fqan=self._getItemType(currentuser, newitem.itemtype).postable
        #self.postItemIntoApp(currentuser, useras, fqan, newitem.basic.fqin)
        #NOTE: above is now done via saving item into group, which means to say its auto done on personal group addition
        #But now idempotency, when I add it to various groups, dont want it to be added multiple times
        #thus we'll do it only when things are added to personal groups: which they always are
        #print '&&&&&&&&&&&&&&&&&&&&&&', 'FINISHED SAVING'
        return newitem

    def isMemberOfTag(self, currentuser, useras, tagfqin):
        tag=self._getTag(currentuser, tagfqin)
        ismember=self.whosdb.isMemberOfMembable(currentuser, useras, tag)
        return ismember

    def canUseThisFqtn(self, currentuser, useras, fqtn):
        tag=self._getTag(currentuser, fqtn)
        return self.canUseThisTag(currentuser, useras, tag)

    #BUG when will we make these useras other memberables? like a group

    def isOwnerOfTag(self, currentuser, useras, tag):
        if useras.basic.fqin==tag.owner:
            return True
        else
            return False

    def canUseThisTag(self, currentuser, useras, tag):
        "return true is this user can use this tag from access to tagtype, namespace, etc"
        #If you OWN this tag
        if self.isOwnerOfTag(currentuser, useras, tag):
            return True
        #if you could have created this tag
        if not self.canCreateThisTag(currentuser, useras, tag.tagtype):
            return False
        tagownertype=gettype(tag.owner)
        #you are member of a group.app/library which owns this tag
        #CHECK this means owner is member of tag
        # if tagownertype in POSTABLES:
        #     tagowner=self.getPostable(currentuser,tag.owner)
        #     if self.isMemberOfPostable(currentuser, useras, tagowner):
        #         return True
        #finally when a tagging is posted to a group, the group becomes a member of the tag
        #(not tagging)
        #and members of the group(postable) can use it
        # memberables=tag.members
        # #CHECK: a tags members are only postables so we short cut. we catch the first.
        # for m in memberables:
        #     if self.isMemberOfPostable(currentuser, useras, m):
        #         return True
        if self.isMemberOfTag(currentuser, useras, tag.basic.fqin):
            return True
        return False

    #can pattern below be refactored out?
    #BUG: currently only works for user creating tag. But i think this should be the way it is
    #only users can create tags. Groups etc can own them. perhaps a CREATABLE interface?

    def canAccessThisType(self, currentuser, useras, thetype, isitemtype=True):
        if isitemtype:
            typeobj=self._getItemType(currentuser, thetype)
        else:
            typeobj=self._getTagType(currentuser, thetype)
        postable=self.whosdb.getPostable(currentuser, typeobj.postable)
        if self.isMemberOfPostable(currentuser, useras, postable):
                return True
        return False

    def canCreateThisTag(self, currentuser, useras, tagtype):
        "return true is this user can use this tag from access to tagtype, namespace, etc"
        return self.canAccessThisType(currentuser, useras, tagtype, False)

    #this is done for making a standalone tag, without tagging anything with it
    def makeTag(self, currentuser, useras, tagspec):
        authorize(False, self, currentuser, useras)

        try:
            #print "was tha tag found"
            #this gets the tag regardless of if you are allowed to.
            tag=self._getTag(currentuser, tagspec['basic'].fqin)
                  
        except:
            #it wasnt, make it
            try:
                #print "TRY CREATING TAG"
                #not needed for now tags dont have members tagspec['push__members']=useras.nick
                if not self.canCreateThisTag(currentuser, useras, tagspec['tagtype']):
                    doabort('NOT_AUT', "Not authorized for tag %s" % tagspec['basic'].fqin)
                
                tag=Tag(**tagspec)
                tag.save(safe=True)
                memb=MembableEmbedded(mtype=User.classname, fqmn=useras.basic.fqin, readwrite=True, pname=useras.presentable_name())
                #tag.update(safe_update=True, push__members=postable.basic.fqin)
                tag.update(safe_update=True, push__members=memb)
                tag.reload()
                #can obviously use tag if i created it
            except:
                doabort('BAD_REQ', "Failed making tag %s" % tagspec['basic'].fqin)
        #print "TAG FOUND OR MADE", tag.basic.fqin
        if not self.canUseThisTag(currentuser, useras, tag):
            doabort('NOT_AUT', "Not authorized for tag %s" % tagspec['basic'].fqin)
        return tag

    #BUG: not creating a delete tag until we know what it means
    #
    def deleteTag(self, currentuser, useras, fqtn):
        pass

    #tagspec here needs to have name and tagtype, this gives, given the useras, the fqtn and allows
    #us to create a new tag or tag an item with an existing tag. If you want to use someone elses tag, 
    #on the assumption u are allowed to (as code in makeTag..BUG..refactor), add a creator into the tagspec
    def tagItem(self, currentuser, useras, item, tagspec):
        tagspec=musthavekeys(tagspec, ['tagtype'])
        tagtypeobj=self._getTagType(currentuser, tagspec['tagtype'])
        #print "smode", tagtypeobj.singletonmode
        if not tagspec.has_key('singletonmode'):
            tagspec['singletonmode']=tagtypeobj.singletonmode
        if not tagspec.has_key('creator'):
            tagspec['creator']=useras.basic.fqin
        if tagspec.has_key('content') and tagspec['singletonmode']:
            tagspec['name']=str(uuid.uuid4())
            tagspec['description']=tagspec['content']
            del tagspec['content']
        tagspec=augmentitspec(tagspec, spectype='tag')
        authorize(False, self, currentuser, useras)
        #print "FQIN", item.basic.fqin
        #itemtobetagged=self._getItem(currentuser, fullyQualifiedItemName)
        itemtobetagged=item

        #print "TAGSPEC IS", tagspec
        if tagspec.has_key('tagmode'):
            tagmode = tagspec['tagmode']
            del tagspec['tagmode']
        else:
            tagmode=tagtypeobj.tagmode

        #makeTag handles idempotency
        tag = self.makeTag(currentuser, useras, tagspec)
        singletonmode=tag.singletonmode
        #Now that we have a tag item, we need to create a tagging
        try:
            #print "was the taggingdoc found?"
            #QUESTION: should we really be looking at a existing tagmode? What if i wanted to make a note public?
            #note we put the posted by in. This function itself prevents posted_by twice
            #but BUG: we have uniqued on the other terms in constructor below. This requires us
            #to get our primary key and uniqueness story right. (or does this func do it for us)
            taggingdoc=self._getTaggingDoc(currentuser, itemtobetagged.basic.fqin, tag.basic.fqin, useras.adsid)
            itemtag=taggingdoc.posting
            #if tagmode for this tag changed, change it (we update it) [no ui for this as yet]
            if tagspec.has_key('tagmode') and itemtag.tagmode!=tagmode:#tagmode has updated value
                taggingdoc.posting.tagmode = tagmode
                taggingdoc.save(safe=True)
                taggingdoc.reload()
        except:
            #print "NOTAGGING YET. CREATING", tagmode,']'
            tagtype=self._getTagType(currentuser, tag.tagtype)
            #BUG in tags shouldnt singleton mode enforce a tagdescription, unlike what augmentitspec does?
            if tagtype.singletonmode:
                tagdescript=tag.basic.description
            else:
                tagdescript=""
            try:
                itemtag=Tagging(postfqin=tag.basic.fqin,
                                posttype="tag",
                                postedby=useras.adsid,
                                thingtopostfqin=itemtobetagged.basic.fqin,
                                thingtoposttype=itemtobetagged.itemtype,
                                tagname=tag.basic.name,
                                tagtype=tag.tagtype,
                                tagmode=tagmode,
                                singletonmode=singletonmode,
                                tagdescription=tagdescript
                )
                #itemtag.save(safe=True)
                taggingdoc=TaggingDocument(posting=itemtag)
                taggingdoc.save(safe=True)
                taggingdoc.reload()
                #print "LALALALALALALALA990"
                itemtobetagged.update(safe_update=True, push__stags=itemtag)
            except:
                doabort('BAD_REQ', "Failed adding newtagging on item %s with tag %s" % (itemtobetagged.basic.fqin, tag.basic.fqin))
            ##print "adding to %s" % personalfqgn
            self.signals['save-to-personal-group-if-not'].send(self, obj=self, currentuser=currentuser, useras=useras, 
                item=itemtobetagged)
            #now since in personal group, appropriate postables will pick it up
            #tagmode here must be from taggingdoc, not from tag
            self.signals['tagged-item'].send(self, obj=self, currentuser=currentuser, useras=useras, 
                taggingdoc=taggingdoc, tagmode=tagmode, item=itemtobetagged)
        #if itemtag found just return it, else create, add to group, return
        itemtobetagged.reload()
        return itemtobetagged, tag, itemtag, taggingdoc

    #So this is the removal of the tagging doc associated with the userAS
    #only that taggingdoc will be removed.
    def untagItem(self, currentuser, useras, fullyQualifiedTagName, fullyQualifiedItemName):
        #Do not remove item, do not remove tag, do not remove tagging
        #just remove the tag from the personal group
        authorize(False, self, currentuser, useras)
        #BUG POSTPONE until we have refcounting implementation
        tag=self._getTag(currentuser, fullyQualifiedTagName)
        item=self._getItem(currentuser, fullyQualifiedItemName)
        if not self.isOwnerOfTag(currentuser, useras, tag):
            doabort('NOT_AUT', "Not authorized for tag %s" % tag.basic.fqin)
        taggingdoc=self._getTaggingDoc(currentuser, itemd.basic.fqin, tag.basic.fqin, useras.adsid)
        #removing the taggingdoc will remove pinpostables will thus 
        #remove it from all the places the tagging was spread too
        taggingdoc.delete(safe=True)
        #Now we must deal with tag's membership.
        #note that tags are namespaced, so others never use the same tag, they may just use the same name.
        #but that tag might have been used here in another context.
        #if we add a counter for membeble embedded in tags we could count how many times
        #a tag was used in a group(this would be a specific tag, so this would be the users usage)
        #then isf only one user used this tag, on disusing it, group wouldnt see it any more.
        #but why? just let the tag be accessible to these groups.
        #Now if it is a note, then we dont want this to be the case, but wre are deleting all
        #singletomode tags anyways, so this sluttiness can continue to be there, and that tagname
        #will be forever seen in this group
        if tag.singletonmode==True:
            tag.delete(safe=True)
        return OK

    #Note that the following provide a model for the uniqueness of posting and tagging docs.
    def _getTaggingDoc(self, currentuser, fqin, fqtn, adsid):
        taggingdoc=elematchsimple(TaggingDocument.objects, "posting", thingtopostfqin=fqin, postfqin=fqtn, postedby=adsid).get()
        return taggingdoc

    #expose this one outside. currently just a simple authorize currentuser to useras.
    def getTaggingDoc(self, currentuser, useras, fqin, fqtn):
        authorize(False, self, currentuser, useras)
        taggingdoc=self._getTaggingDoc(currentuser, fqin, fqtn, useras.adsid)
        return taggingdoc
    #BUG: protection of this tagging? Use useras.basic.fqin for now
    #BUG: this does not work in the direction of making tagging private for now
    def changeTagmodeOfTagging(self, currentuser, useras, fqin, fqtn, tomode='0'):
        #below makes sure user owned that tagging doc
        taggingdoc=self.getTaggingDoc(currentuser, useras, fqin, fqtn)
        taggingdoc.update(safe_update=True, set__posting__tagmode=tomode)
        taggingdoc.reload()
        #Ok to assume here that item exists? Check
        itemtobetagged=self._getItem(currentuser, fqin)
        self.signals['tagmode-changed'].send(self, obj=self, currentuser=currentuser, useras=useras, 
                taggingdoc=taggingdoc, tagmode=tomode, item=itemtobetagged)
        return taggingdoc

    def _getTaggingDocsForItemandUser(self, currentuser, fqin, adsid):
        taggingdocs=elematchsimple(TaggingDocument.objects, "posting", thingtopostfqin=fqin, postedby=adsid)
        return taggingdocs

    def _getPostingDoc(self, currentuser, fqin, fqpn, adsid):
        postingdoc=elematchsimple(PostingDocument.objects, "posting", thingtopostfqin=fqin, postfqin=fqpn, postedby=adsid).get()
        return postingdoc

    def _getPostingDocsForItemandUser(self, currentuser, fqin, adsid):
        postingdocs=elematchsimple(PostingDocument.objects, "posting", thingtopostfqin=fqin, postedby=adsid)
        return postingdocs

    #CHECK: Appropriate postables takes care of this. not needed.
    def recv_postTaggingIntoItemtypesApp(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['item', 'taggingdoc', 'tagmode'])
        item=kwargs['item']
        taggingdoc=kwargs['taggingdoc']
        tagmode=kwargs['tagmode']
        if tagmode=='0':
            #item=self._getItem(currentuser, itemfqin)
            fqan=self._getItemType(currentuser, item.itemtype).postable
            self.postTaggingIntoApp(currentuser, useras, fqan, taggingdoc)
    #BUG how do things get into apps? Perhaps a bit solved
    #As it is now it will automatically post YOUR tags to apps, libraries, groups you are a member of
    #if tagmode allows it
    def recv_spreadTaggingToAppropriatePostables(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['tagmode', 'item', 'taggingdoc'])
        #print "0000kwargs", kwargs
        item=kwargs['item']
        taggingdoc=kwargs['taggingdoc']
        tagmode=kwargs['tagmode']
        #item=self._getItem(currentuser, itemfqin)
        personalfqgn=useras.nick+"/group:default"
        if tagmode=='0':
            postablesin=[]
            for ptt in item.pinpostables:
                pttfqin=ptt.postfqin
                #BUG: many database hits. perhaps cached? if not do it or query better.
                postable=self.whosdb.getPostable(currentuser, pttfqin)
                if pttfqin!=personalfqgn and self.isMemberOfPostable(currentuser, useras, postable) and self.canIPostToPostable(currentuser, useras, postable):
                    postablesin.append(postable)
            for postable in postablesin:
                self.postTaggingIntoPostable(currentuser, useras, postable.basic.fqin, taggingdoc)
        if tagmode not in ['0','1']:
            fqpn=tagmode
            postable=self.whosdb.getPostable(currentuser, fqpn)
            if fqpn!=personalfqgn and self.isMemberOfPostable(currentuser, useras, postable) and self.canIPostToPostable(currentuser, useras, postable):
                self.postTaggingIntoPostable(currentuser, useras, postable.basic.fqin, taggingdoc)
    #this one reacts to the posted-to-postable kind of signal. It takes the taggings on the item that I made and
    def recv_spreadOwnedTaggingIntoPostable(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['item', 'fqpn'])
        item=kwargs['item']
        fqpn=kwargs['fqpn']
        #item=self._getItem(currentuser, itemfqin)
        personalfqgn=useras.nick+"/group:default"
        taggingstopost=[]
        #Now note this will NOT do libraries. BUG: have we changed model to group is member of libraries? i think so
        #print "ITEM.STAGS", item.stags
        for tagging in item.stags:
            if tagging.postedby==useras.basic.fqin:#you did this tagging
                taggingstopost.append(tagging)
        for tagging in taggingstopost:
            #BUG:not sure this will work, searching on a full embedded doc, at the least it would be horribly slow
            #so we shall map instead on some posting properties
            taggingdoc=elematchsimple(TaggingDocument.objects, "posting", postfqin=tagging.postfqin, 
                    thingtopostfqin=tagging.thingtopostfqin, 
                    postedby=tagging.postedby).get()
            #if tagmode allows us to post it, then we post it. This could be made faster later
            #tagmode = self._getTagType(currentuser, tagging.tagtype).tagmode
            #Shut down the above as taggingmode is there in taggingdoc
            if taggingdoc.posting.tagmode=='0':
                self.postTaggingIntoPostable(currentuser, useras, fqpn, taggingdoc)

    #BUG only do if postable does not exist
    #DONT WE HAVE TO ASSUME THAT STUFF EXISTS AT THIS POINT?
    #What if item does not exist? But we never do this directly so it should, its only a
    #reply to routing so we should be ok using _getItem. CHECK
    def postTaggingIntoPostable(self, currentuser, useras, fqpn, taggingdoc):
        itemtag=taggingdoc.posting
        postable=self.whosdb.getPostable(currentuser, fqpn)
        ptype=classtype(postable)
        #why did we have this before?
        #authorize_postable_owner(False, self, currentuser, useras, postable)
        #BUG:we dont need both of these, i think
        authorize_postable_member(False, self, currentuser, useras, postable)
        permit(self.canIPostToPostable(currentuser, useras, postable),
            "No perms to post into postable %s %s" % (ptype, postable.basic.fqin))
        # permit(self.whosdb.isMemberOfPostable(currentuser, useras, postable),
        #     "Only member of postable %s can post into it" % postable.basic.fqin)
        #Now that we are allowing posting via canuse thistag
        # permit(useras.nick==itemtag.postedby,
        #     "Only creator of tag can post into group %s" % postable.basic.fqin)
        tag=self._getTag(currentuser, itemtag.postfqin)
        item=self._getItem(currentuser, itemtag.thingtopostfqin)
        itemsfqpns =[ele.postfqin for ele in item.pinpostables]
        if not fqpn in itemsfqpns:
            doabort('NOT_AUT', "Cant post tag %s in postable %s if item %s is not there" % (tag.basic.fqin, fqpn, item.basic.fqin))
        

        if not self.canUseThisTag(currentuser, useras, tag):
            doabort('NOT_AUT', "Not authorized for tag %s" % tag.basic.fqin)
        postablefqpns =[ele.postfqin for ele in taggingdoc.pinpostables]
        #CHECK: if you alreasy posted this we should be done. CHECK API
        #BUG: why does this yet have no routing. this is the big question associated
        #with posting notes public and stuff.

        #FOR idempotency, if someone has posted this taggingdoc in group, just get it.
        #This is confusing. What does it mean? taggingdocs are so unique its not
        #going to happen i think. CHECK
        for p in taggingdoc.pinpostables:
            if p.postfqin==fqpn:
                return item, tag, taggingdoc.posting, p
        # if fqpn in postablefqpns:
        #     return taggingdoc
        try:
            newposting=Post(postfqin=postable.basic.fqin, posttype=getNSTypeNameFromInstance(postable),
                postedby=useras.adsid, thingtopostfqin=itemtag.postfqin, thingtoposttype=itemtag.tagtype)
            taggingdoc.update(safe_update=True, push__pinpostables=newposting)
            
            #BUG:postables will be pushed multiple times here. How to unique? i think we ought to have this
            #happen at mongoengine/mongodb level
            if postable.basic.fqin==useras.nick+"/group:default":
                rw=True
            else:
                rw=RWDEFMAP[ptype]
            memb=MembableEmbedded(mtype=postable.classname, fqmn=postable.basic.fqin, readwrite=rw, pname=postable.presentable_name())
            #tag.update(safe_update=True, push__members=postable.basic.fqin)
            tag.update(safe_update=True, push__members=memb)
            tag.reload()
            taggingdoc.reload()
        except:
            import sys
            #print sys.exc_info()
            doabort('BAD_REQ', "Failed adding newtagging on item %s with tag %s in postable %s" % (itemtag.thingtopostfqin, itemtag.postfqin, postable.basic.fqin))

        return item, tag, taggingdoc.posting, newposting

    # #BUG: currently not sure what the logic for everyone should be on this, or if it should even be supported
    # #as other users have now seen stuff in the group. What happens to tagging. Leave alone for now.
    # def removeTaggingFromPostable(self, currentuser, useras, fqpn, fqin, fqtn):

    #     grp=self.whosdb.getGPostable(currentuser, fqpn)

    #     authorize_postable_member(False, self, currentuser, useras, grp)
    #     #BUG: no other auths. But the model for this must be figured out.
    #     #The itemtag must exist at first
    #     # itemtag=self._getTagging(currentuser, tag, item)
    #     # itgtoberemoved=self.getGroupTagging(currentuser, itemtag, grp)
    #     # self.session.remove(itgtoberemoved)
    #     # Removed for now handle via refcounting.
    #     return OK


    def postTaggingIntoGroup(self, currentuser, useras, fqgn, taggingdoc):
        itemtag=self.postTaggingIntoPostable(currentuser, useras, fqgn, taggingdoc)
        return itemtag

    def recv_postTaggingIntoPersonal(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['taggingdoc'])
        taggingdoc=kwargs['taggingdoc']
        personalfqgn=useras.nick+"/group:default"
        if personalfqgn not in [ptt.postfqin for ptt in taggingdoc.pinpostables]:
            self.postTaggingIntoGroup(currentuser, useras, personalfqgn, taggingdoc)

    def postTaggingIntoApp(self, currentuser, useras, fqan, taggingdoc):
        itemtag=self.postTaggingIntoPostable(currentuser, useras, fqan, taggingdoc)
        return itemtag

    def postTaggingIntoLibrary(self, currentuser, useras, fqln, taggingdoc):
        itemtag=self.postTaggingIntoPostable(currentuser, useras, fqln, taggingdoc)
        return itemtag

    # def removeTaggingFromGroup(self, currentuser, useras, fqgn, itemfqin, tagfqin):
    #     removeTaggingFromPostable(self, currentuser, useras, fqgn, itemfqin, tagfqin)

    # def removeItemFromApp(self, currentuser, useras, fqan, itemfqin):
    #     removeTaggingFromPostable(self, currentuser, useras, fqan, itemfqin, tagfqin)

    # def removeItemFromLibrary(self, currentuser, useras, fqln, itemfqin):
    #     removeTaggingFromPostable(self, currentuser, useras, fqln, itemfqin, tagfqin)

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

        authorize(False, self, currentuser, useras)
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
                f=elematchmaker2(precursor, kwdict)
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
        #     postable=self.whosdb.getPostable(currentuser, ctarget)
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
    def getTagsAsMemberOnly(self, currentuser, useras, tagtype=None, singletonmode=False):
        #the postables for which user is a member
        #this is only for group so ok to use postablesForUser
        postablesforuser=[e['fqpn'] for e in self.whosdb.postablesForUser(currentuser, useras, "group")]
        ##print "gtamo", postablesforuser
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

    def getAllTagsForUser(self, currentuser, useras, tagtype=None, singletonmode=False):
        a=self.getTagsAsOwnerOnly(currentuser, useras, tagtype, singletonmode)
        b=self.getTagsAsMemberOnly(currentuser, useras, tagtype, singletonmode)
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
                    postablequery=[useras.nick+"/group:default"]
                elif default=="uag":
                    #BUG: should this have all libraries too?
                    #if its a group postablesForUSer is just fine, as there are no wierd access issues
                    postablegroupsforuser=[e['fqpn'] for e in self.whosdb.postablesForUser(currentuser, useras, "group")]
                    ##print "pgfu", postablegroupsforuser
                    postablesforuser = postablegroupsforuser
                    #postablesforuser = postablegroupsforuser + postablelibrariesforuser
                    postablequery=[p.basic.fqin for p in postablesforuser]
        for ele in postablequery:
            postable=self.whosdb.getPostable(currentuser, ele)
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
        return tagquery, tagquerytype, postablequery, userfqin

    #gets frpm groups, apps and libraries..ie items in them, not tags posted in them

    #TODO: add userthere in here so that requests are symmetric rather 
    #than having overriding context in which all this operates
    #BUG: do we need a context. context only provides a background thing to operate on now.
    #The actual stuff is done in here.

    #BUG: this is nor for fqins. Should we have something just for tagnames
    #incoming criteria should not be pinpostables or stags
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
                                        {'field':'tagtype', 'op':'eq', 'value':query['tagtype'][0]}
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
                                        {'field':'posting__tagtype', 'op':'eq', 'value':query['tagtype'][0]}
                    ]
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
        #print "?OUTCRITERIAtdocs",criteria,  sort, pagtuple
        result=self._makeQuery(klass, currentuser, useras, criteria, None, sort, shownfields, pagtuple)
        return result

    def _getTaggingdocsForQuery2(self, shownfields, currentuser, useras, query, usernick=False, criteria=False, specmode=False):
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
                                        {'field':'tagtype', 'op':'eq', 'value':query['tagtype'][0]}
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

    def _getPostingdocsForQuery(self, shownfields, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None, specmode=False):
        #tagquery is currently assumed to be a list of stags=[tagfqin] or tagnames={tagtype, [names]}
        #or postables=[postfqin]
        klass=PostingDocument
        #NO TAG QUERY IN THIS cASE
        tagquery, tagquerytype, postablequery, userfqin = self._qproc(currentuser, useras, query, usernick, specmode)
        if not criteria:
            criteria=[]
        #CHECK:should we separate out the n=1 case as eq not all?
        #Do we need a any instead of all for tagging documents?
        if postablequery and not userfqin:
            #print "NO USER", userfqin
            criteria.append(
                    [{'field':'posting__postfqin', 'op':'in', 'value':postablequery}]
            )

        if postablequery and userfqin:
            #print "USER", userfqin
            criteria.append(
                    [{'field':'posting__postfqin', 'op':'in', 'value':postablequery},
                     {'field':'posting__postedby', 'op':'eq', 'value':userfqin}
                    ]
            )
        #print "?OUTCRITERIA",criteria,  sort, pagtuple
        result=self._makeQuery(klass, currentuser, useras, criteria, None, sort, shownfields, pagtuple)
        return result


    def getItemsForItemspec(self, currentuser, useras, criteria, context=None, sort=None, pagtuple=None):
        SHOWNFIELDS=['itemtype', 'basic.fqin', 'basic.description', 'basic.name', 'basic.uri']
        klass=Item
        #print "CRITERIA", criteria
        result=self._makeQuery(klass, currentuser, useras, criteria, context, sort, SHOWNFIELDS, pagtuple)
        return result

    def getItemsForQuery(self, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None):
        SHOWNFIELDS=['itemtype', 'basic.fqin', 'basic.description', 'basic.name', 'basic.uri']
        #print "USERNICK", usernick
        result=self._getItemsForQuery(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, sort, pagtuple)
        return result

    #not sure this is useful at all because of the leakage issue. But there is a web service which could take advantage
    def getPostingsForQuery(self, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None):
        SHOWNFIELDS=[   'posting.postfqin',
                        'posting.posttype',
                        'posting.thingtopostfqin',
                        'posting.thingtoposttype',
                        'posting.whenposted',
                        'posting.postedby']
        result=self._getPostingdocsForQuery(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, sort, pagtuple)
        return result




    def _getTaggingsForQuery(self, currentuser, useras, query, usernick=False, criteria=False, sort=None, pagtuple=None):
        # SHOWNFIELDS=[   'posting.postfqin',
        #                 'posting.posttype',
        #                 'posting.thingtopostfqin',
        #                 'posting.thingtoposttype',
        #                 'posting.whenposted',
        #                 'posting.postedby',
        #                 'posting.tagtype',
        #                 'posting.tagname',
        #                 'posting.tagdescription']
        SHOWNFIELDS=[   'posting.postfqin',
                        'posting.posttype',
                        'posting.thingtopostfqin',
                        'posting.tagname',
                        'posting.whenposted',
                        'posting.tagmode',
                        'posting.postedby']
        result=self._getTaggingdocsForQuery(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, sort, pagtuple)
        return result

    #get those consistent with users group access
    def getTaggingsForQuery(self, currentuser, useras, query, usernick=False, criteria=False, sort=None):
        #BUG: when is this consistency stuff needed? There is a mode in which I want everything I have access to,
        #and we want to use all those postables. But having ditched contexts, it dosent seem to be needed.
        #we dont take any other postables in this query, bcoz we dont want libs and such
        #query['postables']=groupfqinsforuser
        results=self._getTaggingsForQuery(currentuser, useras, query, usernick, criteria, sort, None)
        return results


    #this returns fqtns, but perhaps tagnames are more useful? so that we can do more general queries?
    #IMPORTANT: the usernick here gives everything tagged by you, not owned by you
    #BUG currently bake in singletonmode
    def getTagsForQuery(self, currentuser, useras, query, usernick=False, criteria=False):
        SHOWNFIELDS=[ 'stags']
        specmode=False #we start with false but if we are in a postable we should be fine
        count, items=self._getTaggingdocsForQuery2(SHOWNFIELDS, currentuser, useras, query, usernick, criteria, specmode)
        #print "TAGGINGS", count, items
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
    #one can use this to query the tag pingrps and pinapps
    #BUG we dont deal with stuff in the apps for now. Not sure
    #what that even means as apps are just copies.

    #filter taggings and postings by hand further if you want just your stuff
    #criteria exis to filter things down further, say by itemtype or tagtype
    #will be done on each item separately. Ditto for sort and pagetuple

    #BUG: not sure we handle libraries or tag ownership change correctly

    #run these without paginations to get everything we want.

    #BUG: in not enough, as we somehow separately need to get all the postings
    #consistent with the users access (array=individ item ok with eq
    #not other way around, and, well, in does or, but is that ok?)
    #BUG: no app access as yet

    #the context is critical here, as if you are in group or user/group
    #context i will only give you tagging docs for which that tagging
    #was  published to the context. So for u, u/g, u/a contexts, this does
    #the right thing.

    #but what about for libraries? There is no pinlibs in Taggingdocuments
    #so the context search will fail. I do want to restrict the search to be
    #to the subset of documents in a group or something which are tagged with the library
    
    #furthermore notice that in the main search too, the context only allows one thing
    #so if i want group and library how do i do it?

    #NOTE: we want users groups for these next ones, not users apps, as that might get in all kinds of stuff that the user is not
    #supposed to get. Thus we must write layered functions on top of this to make it the case

    #This one assumes the tag intersection was used to get the items, and now asks, consistent eith ptypestring and the users
    #access, what taggings do we get per item. This is meant to decorate the item listing.

    #IN SPEC FUNCS users groups are critical, as they scope down on a results page interestimng stuff about
    #the users items consistent with the user's access.

    #BUG: DO WE NOT WANT ANY SINGLETON MODE HERE?
    def getTaggingsForSpec(self, currentuser, useras, itemfqinlist, ptypestring=None, sort=None, fqpn=None):
        result={}
        resultfqpn={}
        query={}
        #below could have been done through qproc too BUG: perhaps refactor?
        #pfu=self.whosdb.postablesForUser(currentuser, useras, ptypestring)
        pfu=self.whosdb.postablesUserCanAccess(currentuser, useras, ptypestring)
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
                        'posting.tagtype',
                        'posting.tagname',
                        'posting.tagmode',
                        'posting.tagdescription']
        SHOWNFIELDS2 = [
            'pinpostables',
            'posting.thingtopostfqin'
        ]                
        # for fqin in itemfqinlist:
        #     criteria=[]
        #     #construct a query consistent with the users access
        #     #this includes the users personal group and the public group
        #     #should op be in?
        #     #BUG:understand how restricting to a particular kind of postable, or all postable affects this
        #     #QUESTION: should there be any libraries here?
        #     #Here we have in instead of all as now we want stuff consistent with any group we are in, not all
        #     criteria.append([
        #         {'field':'pinpostables__postfqin', 'op':'in', 'value':postablesforuser},
        #         {'field':'posting__thingtopostfqin', 'op':'eq', 'value':fqin}
        #     ])
        #     result[fqin]=self._getTaggingdocsForQuery(SHOWNFIELDS, currentuser, useras, query, False, criteria, sort, None, True)
        #     resultfqpn[fqin]=[]
        #     refqpn=self._getTaggingdocsForQuery(SHOWNFIELDS2, currentuser, useras, query, False, criteria, sort, None, True)
        #     #print fqin, result[fqin][0]
        #     resultfqpn[fqin]=[]
        #     for r in list(refqpn[1]):
        #         res=False
        #         for p in r.pinpostables:
        #             #print "GEE",fqpn, p.postfqin
        #             if fqpn == p.postfqin:
        #                 res = (res or True)
        #         resultfqpn[fqin].append(res)

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
        for td in result1[1]:
            ifqin = td.posting.thingtopostfqin
            result2[ifqin].append(td)
        for k in result2.keys():
            result[k] = (len(result2[k]),result2[k])
        #print "RESULT", itemfqinlist, result
        refqpn=self._getTaggingdocsForQuery(SHOWNFIELDS2, currentuser, useras, query, False, criteria, sort, None, True)
        for rtd in refqpn[1]:
            #print "RTD",rtd
            res=False
            for p in rtd.pinpostables:
                #print "GEE",fqpn, p.postfqin
                if fqpn == p.postfqin:
                    res = (res or True)
            resultfqpn[rtd.posting.thingtopostfqin].append(res)

            #print fqin, fqpn, result[fqin][0], resultfqpn[fqin]
        return result, resultfqpn

    def getTaggingsConsistentWithUserAndItems(self, currentuser, useras, itemfqinlist, sort=None, fqpn=None):
        result, resultfqpn=self.getTaggingsForSpec(currentuser, useras, itemfqinlist, None,  sort, fqpn)
        ##print "RESULT", result
        return result, resultfqpn

    #probably dont have a context to use the following
    def getTagsConsistentWithUserAndItems(self, currentuser, useras, itemfqinlist, sort=None):
        result, resultfqpn=self.getTaggingsConsistentWithUserAndItems(currentuser, useras, itemfqinlist, sort)
        #print result
        fqtns=[]
        for fqin in result:
            tags=result[fqin][1]
            for e in tags:
                fqtns.append(e.posting.postfqin)
        fqtns=set(fqtns)
        return len(fqtns), fqtns
    #and this us the postings consistent with items  to show a groups list
    #for all these items to further filter them down. 
    #No context here as PostingDocument has none. This is purely items

    #BUGHoever context can be useful here if all i want is the items in a group. But perhaps that ought to be another
    #function
    def getPostingsForSpec(self, currentuser, useras, itemfqinlist, ptypestring=None, sort=None):
        result={}
        query={}
        # if ptypestring==None:
        #     postablesforuser=[e['fqpn'] for e in self.whosdb.postablesForUser(currentuser, useras)]
        # else:
        #     postablesforuser=[e['fqpn'] for e in self.whosdb.postablesForUser(currentuser, useras, ptypestring)]
        if ptypestring==None:
            postablesforuser=[e['fqpn'] for e in self.whosdb.postablesUserCanAccess(currentuser, useras)]
        else:
            postablesforuser=[e['fqpn'] for e in self.whosdb.postablesUserCanAccess(currentuser, useras, ptypestring)]
        #print "gps", postablesforuser
        SHOWNFIELDS=[   'posting.postfqin',
                        'posting.posttype',
                        'posting.thingtopostfqin',
                        'posting.thingtoposttype',
                        'posting.whenposted',
                        'posting.postedby']

        klass=PostingDocument
        # for fqin in itemfqinlist:
        #     criteria=[]
        #     #construct a query consistent with the users access
        #     #this includes the users personal group and the public group
        #     #should op be in?
        #     #BUG:understand how restricting to a particular kind of postable, or all postable affects this
        #     #QUESTION: should there be any libraries here?
        #     #QUESTION: should there be any libraries here?
        #     criteria.append([
        #                     {'field':'posting__postfqin', 'op':'in', 'value':postablesforuser},
        #                     {'field':'posting__thingtopostfqin', 'op':'eq', 'value':fqin}
        #                 ])
        #     #print "=============================CRITERIA", criteria
        #     result[fqin]=self._getPostingdocsForQuery(SHOWNFIELDS, currentuser, useras, query, False, criteria, sort, None, True)
        criteria=[]
        criteria.append([
            {'field':'posting__postfqin', 'op':'in', 'value':postablesforuser},
            {'field':'posting__thingtopostfqin', 'op':'in', 'value':itemfqinlist}
        ])
        result1=self._getPostingdocsForQuery(SHOWNFIELDS, currentuser, useras, query, False, criteria, sort, None, True)
        result2={}
        for i in itemfqinlist:
            result2[i]=[]
        for pd in result1[1]:
            ifqin = pd.posting.thingtopostfqin
            result2[ifqin].append(pd)
        for k in result2.keys():
            result[k] = (len(result2[k]),result2[k])
        #print "RESULT", result
        return result

    #This should be whittled down further
    def getPostingsConsistentWithUserAndItems(self, currentuser, useras, itemfqinlist, ptypestring=None, sort=None):
        if ptypestring==None:
            result=self.getPostingsForSpec(currentuser, useras, itemfqinlist, None,  sort)
        else:
            result=self.getPostingsForSpec(currentuser, useras, itemfqinlist, ptypestring,  sort)
        return result
   
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
    adsgutuser=whosdb.getUserForNick(currentuser, "adsgut")
    #print "getting adsuser"
    adsuser=whosdb.getUserForNick(adsgutuser, "ads")
    #adsapp=whosdb.getApp(adsuser, "ads@adslabs.org/app:publications")
    currentuser=adsuser
    postdb.addItemType(adsuser, dict(name="pub", postable="ads/app:publications"))
    postdb.addItemType(adsuser, dict(name="search", postable="ads/app:publications"))
    postdb.addTagType(adsuser, dict(name="tag",  postable="ads/app:publications"))
    postdb.addTagType(adsuser, dict(name="note", 
        postable="ads/app:publications", tagmode='1', singletonmode=True))


def initialize_testing(db_session):
    currentuser=None
    #print '(((((((((((((((((0000000000000000000000)))))))))))))))))))))'
    postdb=Postdb(db_session)
    whosdb=postdb.whosdb
    #print "getting adsgutuser"
    adsgutuser=whosdb.getUserForNick(currentuser, "adsgut")
    #print "getting adsuser"
    adsuser=whosdb.getUserForNick(adsgutuser, "ads")

    currentuser=adsuser

    #BUG: should this not be protected?
    rahuldave=whosdb.getUserForNick(adsgutuser, "rahuldave")
    jayluker=whosdb.getUserForNick(adsgutuser, "jayluker")


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
        #print "------------------------------"
        item, posting = postdb.postItemIntoGroup(user,user, "rahuldave/group:ml", item)
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
        postdb.postItemIntoGroup(user, user, 'jayluker/group:sp', thedict[k])

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
    postdb.postItemIntoGroup(niw[0], niw[0], "adsgut/group:public", niw[1])
    postdb.postTaggingIntoGroup(niw[0], niw[0], "adsgut/group:public", tdoutside)
    postdb.changeTagmodeOfTagging(niw[0], niw[0], niw[1].basic.fqin, niw[2].basic.fqin)

    LIBRARIES=["rahuldave/library:mll", "jayluker/library:spl"]
    for k in thedict.keys():
        r=random.choice([0,1])
        user=users[r]
        library=LIBRARIES[r]
        postdb.postItemIntoLibrary(user, user, library, thedict[k])


if __name__=="__main__":
    import sys
    if len(sys.argv)==1:
        db_session=connect("adsgut")
    elif len(sys.argv)==3:
        db_session=connect("adsgut", host="mongodb://%s:%s@localhost/adsgut" % (sys.argv[1], sys.argv[2]))
    else:
        print "Not right number of arguments. Exiting"
        sys.exit(-1)
    initialize_application(db_session)
    #initialize_testing(db_session)
