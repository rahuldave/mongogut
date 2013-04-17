from mongoengine import *
import datetime

#BUG: at some point counters on collections should be built in
#
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
    dtype = StringField(default="adsgut/itemtype")
    basic = EmbeddedDocumentField(Basic)
    app = StringField(default="adsgut/adsgut", required=True)

class TagType(Document):
    dtype = StringField(default="adsgut/tagtype")
    basic = EmbeddedDocumentField(Basic)
    #if tagmode=true for this tagtype, then tagging an item published to a group does not
    #result in the tag being published to the group. This is true of notes.
    tagmode = BooleanField(default=False, required=True)
    #singleton mode, if true, means that a new instance of this tag must be created each time
    #once again example is note, which is created with a uuid as name
    singletonmode = BooleanField(default=False, required=True)

class Tag(Document):
    dtype = StringField(default="adsgut/tag")
    basic = EmbeddedDocumentField(Basic)
    tagtype = StringField(required=True)
    singletonmode = BooleanField(required=True, default=False)
    #The owner of a tag can be a user, group, or app
    #This is different from creator as ownership can be transferred. You
    #see this in groups and apps too. Its like a duck.
    owner = StringField(required=True)
    members = ListField(StringField())


class User(Document):
    adsid = StringField(required=True, unique=True)
    #Unless user sets nick, its equal to adsid
    nick = StringField(required=True, unique=True)
    groupsin = ListField(StringField())
    groupsowned = ListField(StringField())
    groupsinvitedto = ListField(StringField())
    appsin = ListField(StringField())
    appsowned = ListField(StringField())
    appsinvitedto = ListField(StringField())

class Group(Document):
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    members = ListField(StringField())
    personalgroup=BooleanField(default=False, required=True)

class App(Document):
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    members = ListField(StringField())
#One could use a Generic embedded document to store item specific metadata
##that
##Embedded docs are not join tables. Just little dict packets that
#go places

# class TimedUserAction(EmbeddedDocument):
#     doer = StringField(required=True)
#     whendone = DateTimeField(required=True)

# class GroupPost(EmbeddedDocument):
#     #Should we do references? Really we want these to act as references in
#     #insertion/deletion but not in searching.
#     fqin=StringField(required=True)
#     postings=ListField(EmbeddedDocumentField(TimedUserAction))
#     lastwhenposted=DateTimeField(required=True)
#     lastposter=StringField(required=True)

# class AppPost(EmbeddedDocument):
#     #Should we do references? Really we want these to act as references in
#     #insertion/deletion but not in searching.
#     fqin=StringField(required=True)
#     postings=ListField(EmbeddedDocumentField(TimedUserAction))
#     lastwhenposted=DateTimeField(required=True)
#     lastposter=StringField(required=True)

# class LibraryPost(EmbeddedDocument):
#     #Should we do references? Really we want these to act as references in
#     #insertion/deletion but not in searching.
#     fqin=StringField(required=True)
#     postings=ListField(EmbeddedDocumentField(TimedUserAction))
#     lastwhenposted=DateTimeField(required=True)
#     lastposter=StringField(required=True)

#This should work for groups, apps and libraries too!
##eg groups jluker/rahuldave/group:mlgroup means
#jluker tags as belonging to rahuldave/group:ml
#
#POSTING AND TAGGING ARE DUCKS
class Post(EmbeddedDocument):
    #includes posting to apps and groups
    #below is the wheretopostfqin
    meta = {'allow_inheritance':True}
    #this would be the fqin of the tag too.
    postfqin=StringField(required=True)
    thingtopostfqin=StringField(required=True)
    thingtoposttype=StringField(required=True)
    whenposted=DateTimeField(required=True, default=datetime.datetime.now)
    postedby=StringField(required=True)

#BUG:what uniqueness constraints on tagname, etc are needed?
class Tagging(Post):
    tagtype=StringField(default="ads/tag", required=True)
    tagname=StringField(required=True)
    tagdescription=StringField(default="", required=True)


class PostingDocument(Document):
    thething=EmbeddedDocumentField(Post)

class TaggingDocument(Document):
    thething=EmbeddedDocumentField(Tagging)
    pingrps = ListField(EmbeddedDocumentField(Post))
    pinapps = ListField(EmbeddedDocumentField(Post))

class Item(Document):
    dtype = StringField(default="adsgut/item")
    #itypefqin
    itemtype = StringField(required=True)
    basic = EmbeddedDocumentField(Basic)
    pingrps = ListField(EmbeddedDocumentField(Post))
    pinapps = ListField(EmbeddedDocumentField(Post))
    #a very specific tag is collected below, the library tag
    pinlibs = ListField(EmbeddedDocumentField(Tagging))
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