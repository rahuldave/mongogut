from classes import *
import config
from permissions import permit, authorize, authorize_systemuser, authorize_loggedin_or_systemuser
from permissions import authorize_ownable_owner, authorize_postable_member
from errors import abort, doabort, ERRGUT
import types

from commondefs import *


from postables import Database



class Postdb(Database):

    def __init__(self, db_session, wdb):
        self.session=db_session
        self.whosdb=wdb
        self.isSystemUser=self.whosdb.isSystemUser
        self.isOwnerOfOwnable=self.whosdb.isOwnerOfOwnable
        self.isOwnerOfPostable=self.whosdb.isOwnerOfPostable
        self.isMemberOfPostable=self.whosdb.isMemberOfPostable

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
            doabort('BAD_REQ', "Failed adding newposting of item %s into %s %s." % (item.basic.fqin, classname(postable), postable.basic.fqin))
        personalfqgn=useras.nick+"/group:default"

        if postable.basic.fqin!=personalfqgn:
            if personalfqgn in [ptt.postfqin for ptt in item.pingrps]:
                print "NOT IN PERSONAL GRP"
                self.postItemIntoPostable(currentuser, useras, personalfqgn, itemfqin)
        return item

    def postItemIntoGroup(self, currentuser, useras, fqgn, itemfqin):
        item=postItemIntoPostable(self, currentuser, useras, fqpn, itemfqin)
        return item


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

    def canUseThisTag(self, currentuser, useras, tag):
        "return true is this user can use this tag from access to tagtype, namespace, etc"
        return True

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
        authorize_context_owner(False, self, currentuser, useras, postable)

        permit(self.whosdb.isMemberOfPostable(useras, postable),
            "Only member of gpostable %s can post into it" % postable.basic.fqin)
        permit(useras.nick==itemtag.postedby,
            "Only creator of tag can post into group %s" % postable.basic.fqin)
        #item=self._getItem(currentuser, itemtag.thingtopostfqin)
        try:
            newposting=Post(postfqin=postable.basic.fqin, posttype=getNSTypeName(postable),
                postedby=useras.nick, thingtopostfqin=itemtag.postfqin, thingtoposttype=itemtag.thingtoposttype)
            taggingdoc.update(safe_update=True, push__pinpostables=newposting)
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

        authorize_context_owner(False, self, currentuser, useras, grp)
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