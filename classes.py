from mongoengine import *
import datetime

#BUG: at some point counters on collections should be built in
#


#BEHAVIOUR BASIC
class Basic(EmbeddedDocument):
    #namespace = StringField(required=True)
    #Is above needed? should it be saved?
    #how about a creator? or does it matter?
    name = StringField(required=True)
    uri = StringField(default="", required=True)
    creator=StringField(required=True)
    whencreated=DateTimeField(required=True, default=datetime.datetime.now)
    #Below is a combination of namespace and name
    fqin = StringField(required=True, unique=True)
    description = StringField(default="")

class ItemType(Document):
    classname="itemtype"
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    postable = StringField(default="adsgut/adsgut", required=True)
    postabletype = StringField(required=True)

class TagType(Document):
    classname="tagtype"
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    postable = StringField(required=True)
    postabletype = StringField(required=True)
    #if tagmode=true for this tagtype, then tagging an item published to a group does not
    #result in the tag being published to the group. This is true of notes.
    tagmode = BooleanField(default=False, required=True)
    #singleton mode, if true, means that a new instance of this tag must be created each time
    #once again example is note, which is created with a uuid as name
    singletonmode = BooleanField(default=False, required=True)

#This is for the postable
class PostableEmbedded(EmbeddedDocument):
    fqpn = StringField(required=True)
    ptype = StringField(required=True)
    readwrite = BooleanField(required=True, default=False)

#This is for the membable. But these are identical interfaces
#we will use this for members and inviteds instead of strings to implement readwrite
#discussed at the ADS meeting.
class MembableEmbedded(EmbeddedDocument):
    fqmn = StringField(required=True)
    mtype = StringField(required=True)
    readwrite = BooleanField(required=True, default=False)


class Tag(Document):
    classname="tag"    
    basic = EmbeddedDocumentField(Basic)
    tagtype = StringField(required=True)
    singletonmode = BooleanField(required=True)#default is false but must come from tagtype
    #The owner of a tag can be a user, group, or app
    #This is different from creator as ownership can be transferred. You
    #see this in groups and apps too. Its like a duck.
    owner = StringField(required=True)
    #Seems like this was needed for change ownership
    members = ListField(EmbeddedDocumentField(MembableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MembableEmbedded))

    def get_member_fqins(self):
        return [ele.fqmn for ele in self.members]

    def get_member_rws(self):
        perms={}
        for ele in self.members:
            perms[ele.fqmn]=ele.readwrite
        return perms

    def get_invited_fqins(self):
        return [ele.fqmn for ele in self.inviteds]

    def get_invited_rws(self):
        perms={}
        for ele in self.inviteds:
            perms[ele.fqmn]=ele.readwrite
        return perms

#BUG: do we want a similar thing for tags?
class User(Document):
    classname="user"
    adsid = StringField(required=True, unique=True)
    #Unless user sets nick, its equal to adsid
    #ISMEMBER INTERFACE
    nick = StringField(required=True, unique=True)
    basic = EmbeddedDocumentField(Basic)
    postablesin=ListField(EmbeddedDocumentField(PostableEmbedded))
    postablesowned=ListField(EmbeddedDocumentField(PostableEmbedded))
    postablesinvitedto=ListField(EmbeddedDocumentField(PostableEmbedded))
    # groupsin = ListField(StringField())
    # groupsowned = ListField(StringField())
    # groupsinvitedto = ListField(StringField())
    # appsin = ListField(StringField())
    # appsowned = ListField(StringField())
    # appsinvitedto = ListField(StringField())
    # librariesin = ListField(StringField())
    # librariesowned = ListField(StringField())
    # librariesinvitedto = ListField(StringField())


#POSTABLES
class Group(Document):
    classname="group"
    personalgroup=BooleanField(default=False, required=True)
    #ISMEMBER INTERFACE
    nick = StringField(required=True, unique=True)
    #@interface:POSTABLE
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    members = ListField(EmbeddedDocumentField(MembableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MembableEmbedded))#only fqmn

    def get_member_fqins(self):
        return [ele.fqmn for ele in self.members]

    def get_member_rws(self):
        perms={}
        for ele in self.members:
            perms[ele.fqmn]=ele.readwrite
        return perms

    def get_invited_fqins(self):
        return [ele.fqmn for ele in self.inviteds]

    def get_invited_rws(self):
        perms={}
        for ele in self.inviteds:
            perms[ele.fqmn]=ele.readwrite
        return perms

class App(Document):
    classname="app"
    #ISMEMBER INTERFACE
    nick = StringField(required=True, unique=True)
    #@interface:POSTABLE
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    members = ListField(EmbeddedDocumentField(MembableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MembableEmbedded))

    def get_member_fqins(self):
        return [ele.fqmn for ele in self.members]

    def get_member_rws(self):
        perms={}
        for ele in self.members:
            perms[ele.fqmn]=ele.readwrite
        return perms

    def get_invited_fqins(self):
        return [ele.fqmn for ele in self.inviteds]

    def get_invited_rws(self):
        perms={}
        for ele in self.inviteds:
            perms[ele.fqmn]=ele.readwrite
        return perms

#Do we need this at all?
class Library(Document):
    classname="library"
    #@interface:POSTABLE
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    members = ListField(EmbeddedDocumentField(MembableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MembableEmbedded))

    def get_member_fqins(self):
        return [ele.fqmn for ele in self.members]

    def get_member_rws(self):
        perms={}
        for ele in self.members:
            perms[ele.fqmn]=ele.readwrite
        return perms

    def get_invited_fqins(self):
        return [ele.fqmn for ele in self.inviteds]

    def get_invited_rws(self):
        perms={}
        for ele in self.inviteds:
            perms[ele.fqmn]=ele.readwrite
        return perms
#
#POSTING AND TAGGING ARE DUCKS

#
class Post(EmbeddedDocument):
    #includes posting to apps and groups
    #below is the wheretopostfqin
    meta = {'allow_inheritance':True}
    #this would be the fqin of the tag too.
    postfqin=StringField(required=True)
    posttype=StringField(required=True)
    #below is the item and itemtype
    thingtopostfqin=StringField(required=True)
    thingtoposttype=StringField(required=True)
    whenposted=DateTimeField(required=True, default=datetime.datetime.now)
    postedby=StringField(required=True)

#BUG:what uniqueness constraints on tagname, etc are needed? Add tagfqin? no its there as postfqin
class Tagging(Post):
    tagtype=StringField(default="ads/tag", required=True)
    tagname=StringField(required=True)
    tagdescription=StringField(default="", required=True)
    tagmode = BooleanField(default=False, required=True)
    singletonmode = BooleanField(default=False, required=True)


class PostingDocument(Document):
    classname="postingdocument"
    thething=EmbeddedDocumentField(Post)

class TaggingDocument(Document):
    classname="taggingdocument"
    thething=EmbeddedDocumentField(Tagging)
    #pingrps = ListField(EmbeddedDocumentField(Post))
    #pinapps = ListField(EmbeddedDocumentField(Post))
    #pinlibs = ListField(EmbeddedDocumentField(Post))
    pinpostables = ListField(EmbeddedDocumentField(Post))
    #pinlibs = ListField(EmbeddedDocumentField(Tagging))


class Item(Document):
    classname="item"
    #itypefqin
    itemtype = StringField(required=True)
    basic = EmbeddedDocumentField(Basic)
    pinpostables = ListField(EmbeddedDocumentField(Post))
    #a very specific tag is collected below, the library tag
    #pinlibs = ListField(EmbeddedDocumentField(Tagging))
    #anything not library, group, or app
    stags = ListField(EmbeddedDocumentField(Tagging))
    #Really want a tagging or posting here
    #Should below be a ref field as only used for refcounting?
    #this includes groups and apps here
    #BUG: currently now worrying about refcounting
    #alltags = ListField(ReferenceField(TaggingDocument))

#Have specific collections for @group, @app, @library
##but not for other tags. Do full intersections there.
#for each collection have items, not tags
if __name__=="__main__":
    pass