from mongoengine import *

class Basic(EmbeddedDocument):
    #namespace = StringField(required=True)
    #Is above needed? should it be saved?
    #how about a creator? or does it matter?
    name = StringField(required=True)
    uri = StringField()
    creator=StringField(required=True)
    whencreated=DateTimeField(required=True)
    #Below is a combination of namespace and name
    fqin = StringField(required=True, unique=True)
    description = StringField(default="")

class Itemtype(Document):
    dtype = StringField(default="adsgut/itemtype")
    basic = EmbeddedDocumentField(Basic)

class TagType(Document):
    dtype = StringField(default="adsgut/tagtype")
    basic = EmbeddedDocumentField(Basic)

class Tag(Document):
    dtype = StringField(default="adsgut/tag")
    basic = EmbeddedDocumentField(Basic)
    ttypefqin = StringField(required=True)


class User(Document):
    adsid = StringField(required=True, unique=True)
    #Unless user sets nick, its equal to adsid
    nickname = StringField(required=True, unique=True)
    groupsIn = ListField(StringField())
    groupsOwned = ListField(StringField())
    groupsInvitedTo = ListField(StringField())
    appsIn = ListField(StringField())
    appsOwned = ListField(StringField())
    appsInvitedTo = ListField(StringField())

class Group(Document):
    basic = EmbeddedDocumentField(Basic)
    owner_ptr = ReferenceField(User)
    owner = StringField(required=True)
    members = ListField(StringField())

class App(Document):
    basic = EmbeddedDocumentField(Basic)
    owner_ptr = ReferenceField(User)
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
class PostToTag(EmbeddedDocument):
    #includes posting to apps and groups
    #below is the wheretopostfqin
    meta = {'allow_inheritance':True}
    tagfqin=StringField(required=True)
    thingtotagfqin=StringField(required=True)
    whentagged=DateTimeField(required=True)
    taggedby=StringField(required=True)


class Tagging(PostToTag):
    tagdescription=StringField(default="")
    postedInGroups = ListField(EmbeddedDocumentField(PostToTag))
    postedInApps = ListField(EmbeddedDocumentField(PostToTag))

class TaggingDocument(Document):
    thething=EmbeddedDocumentField(PostToTag)

class Item(Document):
    dtype = StringField(default="adsgut/item")
    #itypefqin
    itypefqin = StringField(required=True)
    basic = EmbeddedDocumentField(Basic)
    postedInGroups = ListField(EmbeddedDocumentField(PostToTag))
    postedInApps = ListField(EmbeddedDocumentField(PostToTag))
    #a very specific tag is collected below, the library tag
    postedInLibraries = ListField(EmbeddedDocumentField(Tagging))
    #anything not library, group, or app
    simpleTags = ListField(EmbeddedDocumentField(Tagging))
    #Really want a tagging or posting here
    #Should below be a ref field as only used for refcounting?
    #this includes groups and apps here
    allTags = ListField(ReferenceField(TaggingDocument))

#Have specific collections for @group, @app, @library
##but not for other tags. Do full intersections there.
#for each collection have items, not tags
if __name__=="__main__":
    pass