from classes import *
import config
from permissions import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser
from permissions import authorize_ownable_owner, authorize_postable_member
from errors import abort, doabort, ERRGUT
import types

from commondefs import *


from postables import Database

from blinker import signal

def reciever(f):
    def realreciever(sender, data):
        otherargs{}
        if e not in ['obj', 'currentuser', 'useras']:
            otherargs[e]=data[e]
        obj=data['obj']
        currentuser=data['currentuser']
        useras=data['useras']
        val=f(obj, currentuser, useras, **otherargs)
        return val
    return realreciever



class Postdb(Database):
    SIGNALS={
        "added-to-group":[reciever(self.postItemIntoPersonal)]
        "added-to-app":[]
        "added-to-library":[]
    }
    def __init__(self, db_session, wdb):
        self.session=db_session
        self.whosdb=wdb
        self.isSystemUser=self.whosdb.isSystemUser
        self.isOwnerOfOwnable=self.whosdb.isOwnerOfOwnable
        self.isOwnerOfPostable=self.whosdb.isOwnerOfPostable
        self.isMemberOfPostable=self.whosdb.isMemberOfPostable
        self.signals={}
        for ele in SIGNALS:
            self.signals[ele]=signal(ele)
            for r in SIGNALS[ele]:
                self.signals[ele].connect(r)

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
        typespec=augmenttypespec(typespec)
        useras=self.whosdb.getUserForNick(currentuser,typespec['basic'].creator)
        authorize(False, self, currentuser, useras)
        app=self.whosdb.getApp(currentuser, typespec['postable'])
        #user must be owner of app whos namespece he is using
        authorize_ownable_owner(False, self, currentuser, useras, app)
        try:
            itemtype=ItemType(**typespec)
            itemtype.save(safe=True)
        except:
            # import sys
            # print sys.exc_info()
            doabort('BAD_REQ', "Failed adding itemtype %s" % typespec['fqin'])
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
        typespec=augmenttypespec(typespec, "tagtype")
        useras=self.whosdb.getUserForNick(currentuser,typespec['basic'].creator)
        authorize(False, self, currentuser, useras)
        try:
            tagtype=TagType(**typespec)
            tagtype.save(safe=True)
        except:
            doabort('BAD_REQ', "Failed adding tagtype %s" % typespec['fqin'])
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

    def postItemIntoPostable(self, currentuser, useras, fqpn, itemfqin):
        ptype=gettype(fqpn)
        postable=self.whosdb.getPostable(currentuser, fqpn)
        typename=classname(postable).lower()
        item=self._getItem(currentuser, itemfqin)
        #Does the False have something to do with this being ok if it fails?BUG
        permit(self.isMemberOfPostable(useras, postable),
            "Only member of %s %s can post into it" % (classname(postable), postable.basic.fqin))

        try:#BUG:what if its already there?
            newposting=Post(postfqin=grp.basic.fqin, posttype=getNSTypeName(fqpn), 
                postedby=useras.nick, thingtopostfqin=itemfqin, 
                thingtoposttype=item.itemtype)
            postingdoc=PostingDocument(thing=newposting)
            postingdoc.save(safe=True)
            #Not sure instance updates work but we shall try.
            item.update(safe_update=True, push__pinpostables=newposting)
        except:
            import sys
            print sys.exc_info()
            doabort('BAD_REQ', "Failed adding newposting of item %s into %s %s." % (item.basic.fqin, ctypename, postable.basic.fqin))
        #BUG: now send to personal group via routing
        self.signals['added-to-'+typename].send(self, obj=self, currentuser=currentuser, useras=useras, itemfqin=itemfqin)
        return item

    def postItemIntoGroup(self, currentuser, useras, fqgn, itemfqin):
        item=postItemIntoPostable(self, currentuser, useras, fqpn, itemfqin)
        return item

    def postItemIntoPersonal(self, currentuser, useras, **kwargs):
        kwargs=musthavekeys(kwargs,['itemfqin'])
        itemfqin=kwargs['itemfqin']
        personalfqgn=useras.nick+"/group:default"
        item=self._getItem(currentuser, itemfqin)
        if postable.basic.fqin!=personalfqgn:
            if personalfqgn in [ptt.postfqin for ptt in item.pingrps]:
                print "NOT IN PERSONAL GRP"
                self.postItemIntoPostable(currentuser, useras, personalfqgn, itemfqin)

    def postItemIntoApp(self, currentuser, useras, fqan, itemfqin):
        item=postItemIntoPostable(self, currentuser, useras, fqan, itemfqin)
        return item

    def postItemIntoLibrary(self, currentuser, useras, fqln, itemfqin):
        item=postItemIntoPostable(self, currentuser, useras, fqln, itemfqin)
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

    def saveItem(self, currentuser, useras, itemspec):
        #permit(currentuser==useras or self.whosdb.isSystemUser(currentuser), "User %s not authorized or not systemuser" % currentuser.nick)
        authorize(False, self, currentuser, useras)#sysadmin or any logged in user where but cu and ua must be same
        fqgn=useras.nick+"/group:default"
        itemspec=augmentitspec(itemspec)
        #Information about user useras goes as namespace into newitem, but should somehow also be in main lookup table
        try:
            print "was the item found?"
            newitem=self._getItem(currentuser, itemspec['basic'].fqin)
            #TODO: do we want to handle an updated saving date here by making an array
            #this way we could count how many times 'saved'
        except:
            #the item was not found. Create it
            print "SO CREATING ITEM %s\n" % itemspec['basic'].fqin
            try:
                print "ITSPEC", itemspec
                newitem=Item(**itemspec)
                newitem.save(safe=True)
                # print "Newitem is", newitem.info()
            except:
                # import sys
                # print sys.exc_info()
                doabort('BAD_REQ', "Failed adding item %s" % itemspec['basic'].fqin)

        self.postItemIntoGroup(currentuser, useras, fqgn, newitem.basic.fqin)
        print '**********************'
        #IN LIEU OF ROUTING
        #BUG: shouldnt this be done by routing
        fqan=self._getItemType(currentuser, newitem.itemtype).postable
        self.postItemIntoApp(currentuser, useras, fqan, newitem.basic.fqin)
        #NOTE: above is now done via saving item into group, which means to say its auto done on personal group addition
        #But now idempotency, when I add it to various groups, dont want it to be added multiple times
        #thus we'll do it only when things are added to personal groups: which they always are
        print '&&&&&&&&&&&&&&&&&&&&&&', 'FINISHED SAVING'
        return newitem

    def isMemberOfTag(self, currentuser, useras, tagfqin):
        tag=self._getTag(currentuser, tagfqin)
        ismember=self.whosdb.isMemberOfMembable(currentuser, useras, tag)
        return ismember


    #BUG when will we make these useras other memberables?
    #BUG need to deal with tagmode and singletonmode here
    def canUseThisTag(self, currentuser, useras, tag):
        "return true is this user can use this tag from access to tagtype, namespace, etc"
        #If you OWN this tag
        if useras.basic.fqin==tag.owner:
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
        if self.isMemberOfTag(currentuser, useras, tag):
            return True
        return False

    #can pattern below be refactored out?
    def canCreateThisTag(self, currentuser, useras, tagtype):
        "return true is this user can use this tag from access to tagtype, namespace, etc"
        tagype=self._getTagType(currentuser, tagtype)
        ttowner=tagtype.owner
        ttownertype=gettype(ttowner)
        if ttownertype==User:
            if useras.basic.fqin==ttowner:
                return True
        elif ttownertype in POSTABLES:
            postable=self.getPostable(currentuser,ttowner)
            if self.isMemberOfPostable(currentuser, useras, postable):
                return True
        return False

    #this is done for making a standalone tag, without tagging anything with it
    def makeTag(self, currentuser, useras, tagspec, tagmode=False):
        tagspec=augmentitspec(tagspec, spectype='tag')
        authorize(False, self, currentuser, useras)

        try:
            print "was tha tag found"
            #this gets the tag regardless of if you are allowed to.
            tag=self._getTag(currentuser, tagspec['basic'].fqin)           
        except:
            #yes it was. Throw an exception.
            doabort('BAD_REQ', "Tag %s already exists" % tagspec['basic'].fqin)
        if not self.canUseThisTag(currentuser, useras, tag):
            doabort('NOT_AUT', "Not authorized for tag %s" % tagspec['basic'].fqin)
        try:
            print "TRY CREATING TAG"
            #not needed for now tags dont have members tagspec['push__members']=useras.nick
            if not self.canCreateThisTag(currentuser, useras, tagspec['tagtype']):
                doabort('NOT_AUT', "Not authorized for tag %s" % tagspec['basic'].fqin)
            tag=Tag(**tagspec)
            tag.save(safe=True)
        except:
            import sys
            print sys.exc_info()
            doabort('BAD_REQ', "Failed adding tag %s" % tagspec['basic'].fqin)
        return tag

    #BUG: not creating a delete tag until we know what it means
    #
    def deleteTag(self, currentuser, useras, fqtn):
        pass

    def tagItem(self, currentuser, useras, fullyQualifiedItemName, tagspec, tagmode=False):
        authorize(False, self, currentuser, useras)
        print "FQIN", fullyQualifiedItemName
        itemtobetagged=self._getItem(currentuser, fullyQualifiedItemName)
        tag = self.makeTag(currentuser, useras, tagspec, tagmode)
        #Now that we have a tag item, we need to create a tagging
        try:
            print "was the itemtag found"
            itemtag=self._getTagging(currentuser, tag, itemtobetagged)
        except:
            print "NOTAGGING YET. CREATING"
            tagtype=self._getTagType(currentuser, tag.tagtype)
            #BUG in tags shouldnt singleton mode enforce a tagdescription, unlike what augmentitspec does?
            if tagtype.singletonmode:
                tagdescript=tag.basic.description
            else:
                tagdescript=""
            try:
                itemtag=Tagging(postfqin=tag.basic.fqin,
                                posttype="tag",
                                postedby=useras.nick,
                                thingtopostfqin=itemtobetagged.basic.fqin,
                                thingtoposttype=itemtobetagged.itemtype,
                                tagname=tag.basic.name,
                                tagtype=tag.tagtype,
                                tagdescription=tagdescript
                )
                #itemtag.save(safe=True)
                taggingdoc=TaggingDocument(thething=itemtag)
                taggingdoc.save(safe=True)
                print "LALALALALALALALA990"
                itemtobetagged.update(safe_update=True, push__stags=itemtag)
            except:
                doabort('BAD_REQ', "Failed adding newtagging on item %s with tag %s" % (itemtobetagged.basic.fqin, tag.basic.fqin))

            personalfqgn=useras.nick+"/group:default"
            print "adding to %s" % personalfqgn
            self.postTaggingIntoGroup(currentuser, useras, personalfqgn, taggingdoc)
        #at this point it goes to the itemtypes app too.
        #BUG: must add to groups item is posted into
        #BUG: All tagmode stuff to be done via routing
        # if tagmode:
        #     groupsitemisin=itemtobetagged.get_groupsin(useras)
        #     #the groups user is in that item is in: in tagmode we make sure, whatever groups item is in, tags are in
        #     for grp in groupsitemisin:
        #         if grp.fqin!=personalfqgn:
        #             #wont be added to app for these
        #             self.postTaggingIntoGroupFromItemtag(currentuser, useras, grp, itemtag)
        # #print itemtobetagged.itemtags, "WEE", newtag.taggeditems, newtagging.tagtype.name

        #if itemtag found just return it, else create, add to group, return
        return taggingdoc

    def untagItem(self, currentuser, useras, fullyQualifiedTagName, fullyQualifiedItemName):
        #Do not remove item, do not remove tag, do not remove tagging
        #just remove the tag from the personal group
        authorize(False, self, currentuser, useras)
        #BUG POSTPONE until we have refcounting implementation
        return OK

    def postTaggingIntoPostable(self, currentuser, useras, fqpn, taggingdoc):
        itemtag=taggingdoc.thething
        postable=self.whosdb.getPostable(currentuser, fqpn)
        authorize_postablecontext_owner(False, self, currentuser, useras, postable)

        permit(self.whosdb.isMemberOfPostable(useras, postable),
            "Only member of gpostable %s can post into it" % postable.basic.fqin)
        permit(useras.nick==itemtag.postedby,
            "Only creator of tag can post into group %s" % postable.basic.fqin)
        #item=self._getItem(currentuser, itemtag.thingtopostfqin)
        try:
            newposting=Post(postfqin=postable.basic.fqin, posttype=getNSTypeName(postable),
                postedby=useras.nick, thingtopostfqin=itemtag.postfqin, thingtoposttype=itemtag.thingtoposttype)
            taggingdoc.update(safe_update=True, push__pinpostables=newposting)
            tag=self._getTag(currentuser, itemtag.postfqin)
            tag.update(safe_update=True, push__members=postable.basic.fqin)
        except:
            import sys
            print sys.exc_info()
            doabort('BAD_REQ', "Failed adding newtagging on item %s with tag %s in postable %s" % (itemtag.thingtopostfqin, itemtag.postfqin, postable.basic.fqin))


        #use routing for make sure we go into itemtypes app?
        #personalfqgn=useras.nick+"/group:default"
        #only when we do post tagging to personal group do we post tagging to app. this ensures app dosent have multiples.
        # if grp.fqin==personalfqgn:
        #     personalgrp=self.whosdb.getGroup(currentuser, personalfqgn)
        #     appstring=itemtag.item.itemtype.app
        #     itemtypesapp=self.whosdb.getApp(currentuser, appstring)
        #     self.postTaggingIntoAppFromItemtag(currentuser, useras, itemtypesapp, itemtag)
        #grp.groupitems.append(newitem)
        # self.commit()
        # print itemtag.groupsin, 'jee', grp.itemtags
        # itgto=self.session.query(TagitemGroup).filter_by(itemtag=itemtag, group=grp).one()
        # print itgto
        return itemtag

    #BUG: currently not sure what the logic for everyone should be on this, or if it should even be supported
    #as other users have now seen stuff in the group. What happens to tagging. Leave alone for now.
    def removeTaggingFromPostable(self, currentuser, useras, fqpn, fqin, fqtn):

        grp=self.whosdb.getGPostable(currentuser, fqpn)

        authorize_postablecontext_owner(False, self, currentuser, useras, grp)
        #BUG: no other auths. But the model for this must be figured out.
        #The itemtag must exist at first
        # itemtag=self._getTagging(currentuser, tag, item)
        # itgtoberemoved=self.getGroupTagging(currentuser, itemtag, grp)
        # self.session.remove(itgtoberemoved)
        # Removed for now handle via refcounting.
        return OK


    def postTaggingIntoGroup(self, currentuser, useras, fqgn, taggingdoc):
        itemtag=postTaggingIntoPostable(self, currentuser, useras, fqgn, taggingdoc)
        return itemtag

    def postTaggingIntoApp(self, currentuser, useras, fqan, taggingdoc):
        itemtag=postTaggingIntoPostable(self, currentuser, useras, fqan, taggingdoc)
        return itemtag

    def postTaggingIntoLibrary(self, currentuser, useras, fqln, taggingdoc):
        itemtag=postTaggingIntoPostable(self, currentuser, useras, fqln, taggingdoc)
        return itemtag

    def removeTaggingFromGroup(self, currentuser, useras, fqgn, itemfqin, tagfqin):
        removeTaggingFromPostable(self, currentuser, useras, fqgn, itemfqin, tagfqin)

    def removeItemFromApp(self, currentuser, useras, fqan, itemfqin):
        removeTaggingFromPostable(self, currentuser, useras, fqan, itemfqin, tagfqin)

    def removeItemFromLibrary(self, currentuser, useras, fqln, itemfqin):
        removeTaggingFromPostable(self, currentuser, useras, fqln, itemfqin, tagfqin)

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
    def _makeQuery(self, klass, currentuser, useras, criteria, postablecontext=None, sort=None, shownfields=None, pagtuple=None):
        DEFPAGOFFSET=0
        DEFPAGSIZE=10
        kwdict={}
        qterms=[]
        #make sure we are atleast logged in and useras or superuser

        authorize(False, self, currentuser, useras)
        for l in criteria:
            kwdict={}
            for d in l:
                if d['op']=='eq':
                    kwdict[d['field']]=d['value']
                else:
                    kwdict[d['field']+'__'+d['op']]=d['value']
            qterms.append(Q(**kwdict))
        if len(qterms) == 1:
            qclause=qterms[0]
        else:
            qclause = reduce(lambda q1, q2: q1.__and__(q2), qterms)

        userthere=False
        if not postablecontext:
            postablecontext={'user':True, 'type':'group', 'value':useras.basic.fqin}
        #BUG validate the values this can take. for eg: type must be a postable. none of then can be None

        userthere=postablecontext['user']
        ctype=postablecontext['type']
        ctarget=postablecontext['value']
        itemqset=klass.objects.filter(qclause)

        postable=self.whosdb.getPostable(currentuser, ctarget)
        #BUG: no pinpostables for Tag. How does that work?
        if userthere:
            itemqset=itemqset.filter(pinpostables__postfqin=ctarget, pinpostables__postedby=useras.basic.fqin)
        else:
            itemqset=itemqset.filter(pinpostables__postfqin=ctarget)

        if sort:
            prefix=""
            if not sort['ascending']:
                prefix='-'
            sorter=prefix+sort['field']
            itemqset=itemqset.order_by(sorter)
        else:
            print "NO SORT"
        if shownfields:
            itemqset=itemqset.only(*shownfields)
        count=itemqset.count()

        if pagtuple:
            pagoffset=pagtuple[0]
            pagsize=pagtuple[1]
            if pagsize==None:
                pagsize=DEFPAGSIZE
            pagend=pagoffset+pagsize
            retset=itemqset[pagoffset:pagend]
        else:
            pagoffset=DEFPAGOFFSET
            pagsize=DEFPAGSIZE
            retset=itemqset

        return count, retset

    #This can be used to somply get tags in a particular context
    def getTagsForTagspec(self, currentuser, useras, criteria, context=None, sort=None):
        SHOWNFIELDS=['tagtype', 'singletonmode', 'basic.fqin', 'basic.description', 'basic.name', 'basic.uri', 'basic.creator', 'owner']
        klass=Tag
        result=self._makeQuery(klass, currentuser, useras, criteria, context, sort, SHOWNFIELDS, None)
        return result


    #the next two are for autocomplete and stuff. They are NOT the tags consistent with the current search.(left hand tags)
    #indeed i am not sure if context works there at all!!!
    #get tags by owner and tagtype. remember this does not do libraries for us anymore.
    #we assume that tagtype based restrictions were taken care of at tag addition time
    def getTagsAsOwnerOnly(self, currentuser, useras, tagtype=None, context=None, singletonmode=False):
        criteria=[
            {'field':'owner', 'op':'eq', 'value':useras.basic.fqin},
            {'field':'singleton', 'op':'eq', 'value':singletonmode}
        ]
        if tagtype:
            criteria.append({'field':'tagtype', 'op':tagtype[0], 'value':tagtype[1]})
        result=self.getTagsForTagspec(currentuser, useras, criteria, context, sort)
        return result

    #You also have access to tags through group ownership of tags
    #no singletonmodes are usually transferred to group ownership
    #this will give me all
    def getTagsAsMemberOnly(self, currentuser, useras, tagtype=None, ptypestring=None, singletonmode=False, context=None, sort=None):
        #the postables for which user is a member
        postablesforuser=self.whosdb.postablesForUser(currentuser, useras, ptypestring)
        #notice in op does OR not AND
        criteria=[
            {'field':'owner', 'op':'ne', 'value':useras.basic.fqin},
            {'field':'members', 'op':'in', 'value':postablesforuser},
            {'field':'singleton', 'op':'eq', 'value':singletonmode}
        ]
        if tagtype:
            criteria.append({'field':'tagtype', 'op':tagtype[0], 'value':tagtype[1]})
        result=self.getTagsForTagspec(currentuser, useras, criteria, context, sort)
        return result

    def getItemsForItemspec(self, currentuser, useras, criteria, context=None, sort=None, pagtuple=None):
        SHOWNFIELDS=['itemtype', 'basic.fqin', 'basic.description', 'basic.name', 'basic.uri']
        klass=Item
        result=self._makeQuery(klass, currentuser, useras, criteria, context, sort, SHOWNFIELDS, pagtuple)
        return result

    #gets frpm groups, apps and libraries..ie items in them, not tags posted in them

    #TODO: add userthere in here so that requests are symmetric rather 
    #than having overriding context in which all this operates
    #BUG: do we need a context. context only provides a background thing to operate on now.
    #The actual stuff is done in here.
    def getItemsForTagquery(self, currentuser, useras, query, context=None, sort=None, pagtuple=None):
        #tagquery is currently assumed to be a list of [{'tagtype', 'tagname'}]
        #or [{"posttype","postfqin"}]
        #we assume that
        tagquery=query.get("stags",[])
        postablequery=query.get("postables",[])
        criteria=[]
        for v in tagquery:
            criteria.append([
                {'field':'stags__tagname', 'op':'eq', 'value':v['tagname']},
                {'field':'stags__tagtype', 'op':'eq', 'value':v['tagtype']}
            ])
        for v in postablequery:
            criteria.append([
                {'field':'pinpostables__postfqin', 'op':'eq', 'value':v['postfqin']}
            ])
        result=self.getItemsForItemspec(currentuser, useras, criteria, context, sort, pagtuple)
        return result


    #PTYPESTRING MUST BE GROUP ONLY TO GET APPROPRIATE POSTABLES FOR USER

    #Get TaggingDocs consistent with the users perms
    #BUG: in more general screens, when all we want to draw is all the tags of type lensing, how do we do it?
    def getTaggingsForTagquery(self, currentuser, useras, query, ptypestring=None, context=None, sort=None, pagtuple=None):
        #tagquery is currently assumed to be a list of [{'tagfqin'}]
        #or [{"postfqin"}]
        #we assume that
        postablesforuser=self.whosdb.postablesForUser(currentuser, useras, ptypestring)
        klass=TaggingDocument
        tagquery=query.get("stags",[])
        #postablequery=query.get("postables",[])
        criteria=[]
        SHOWNFIELDS=[   'thething.postfqin',
                        'thething.posttype',
                        'thething.thingtopostfqin',
                        'thething.thingtoposttype',
                        'thething.whenposted',
                        'thething.postedby',
                        'thething.tagtype',
                        'thething.tagname',
                        'thething.tagdescription']
        #BUG: the split is not between tagname and tagtype, but whether their ought to be a namespace ot not

        #this is to get the correct items in taggingdocs we need
        for v in tagquery:
            criteria.append([
                {'field':'thething__tagfqin', 'op':'eq', 'value':v['tagfqin']}
            ])
        #this is to make sure what we get the tagguings posted to groups i have access to.
        #note this is for posting of taggings not items
        criteria.append([
                {'field':'pinpostables__postfqin', 'op':'in', 'value':postablesforuser}
            ])
        
        result=self.makeQuery(klass, currentuser, useras, criteria, context, sort, SHOWNFIELDS, pagtuple)
        return result

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
    def getTaggingsForSpec(self, currentuser, useras, itemfqinlist, ptypestring=None, criteria=[], context=None, sort=None, pagetuple=None):
        result={}
        postablesforuser=self.whosdb.postablesForUser(currentuser, useras, ptypestring)
        klass=TaggingDocument
        if not context:
            context={'user':True, 'type':'group', 'value':useras.basic.fqin}
        #BUG validate the values this can take. for eg: type must be a postable. none of then can be None
                
        userthere=postablecontext['user']
        ctype=postablecontext['type']
        ctarget=postablecontext['value']

        SHOWNFIELDS=[   'thething.postfqin',
                        'thething.posttype',
                        'thething.thingtopostfqin',
                        'thething.thingtoposttype',
                        'thething.whenposted',
                        'thething.postedby',
                        'thething.tagtype',
                        'thething.tagname',
                        'thething.tagdescription']
        for fqin in itemfqinlist:
            criteria=[]
            #construct a query consistent with the users access
            #this includes the users personal group and the public group
            #should op be in?
            #BUG:understand how restricting to a particular kind of postable, or all postable affects this
            #QUESTION: should there be any libraries here?
            criteria.append([
                {'field':'pinpostables__postfqin', 'op':'in', 'value':postablesforuser},
                {'field':'thething__thingtopostfqin', 'op':'eq', 'value':fqin}
            ])
            result[fqin]=self._makeQuery(klass, currentuser, useras, criteria, context, sort, pagetuple)
        return result

    #and this us the postings consistent with items  to show a groups list
    #for all these items to further filter them down. 
    #No context here as PostingDocument has none. This is purely items
    def getPostingsForSpec(self, currentuser, useras, itemfqinlist, ptypestring=None, criteria=[], sort=None, pagetuple=None):
        result={}
        postablesforuser=self.whosdb.postablesForUser(currentuser, useras, ptypestring)
        SHOWNFIELDS=[   'thething.postfqin',
                        'thething.posttype',
                        'thething.thingtopostfqin',
                        'thething.thingtoposttype',
                        'thething.whenposted',
                        'thething.postedby']

        klass=PostingDocument
        for fqin in itemfqinlist:
            criteria=[]
            #construct a query consistent with the users access
            #this includes the users personal group and the public group
            #should op be in?
            #BUG:understand how restricting to a particular kind of postable, or all postable affects this
            #QUESTION: should there be any libraries here?
            #QUESTION: should there be any libraries here?
            criteria.append([
                {'field':'thething__postfqin', 'op':'in', 'value':postablesforuser},
                {'field':'thething__thingtopostfqin', 'op':'eq', 'value':fqin}
            ])

            result[fqin]=self._makeQuery(klass, currentuser, useras, criteria, None, sort, pagetuple)
        return result

    #this should be the one giving us tags consistent with a context
    #QUESTION:does this give us a list of tags for each item in a group?
    #I dont believe we need this. More precisely i think we get this implicitly from the taggings
    def getTagPostingsForSpec(self, currentuser, useras, itemfqinlist, criteria=[], context=None, sort=None, pagetuple=None):
        pass