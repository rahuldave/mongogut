from mongoengine import *
import datetime
from collections import defaultdict



# A list of globals
#the public group. Everyone belongs to this. This group can be added to libraries to give access
#to all ads users, read only, or read-write
PUBLICGROUP='adsgut/group:public'
#the library corresponding to the above group. We dont use this currently, but the idea is to add
#a public library so that posting to it becomes an endorsement of an item, and we can then do things
#in a user's preferences like autotweet from there.
PUBLICLIBRARY='adsgut/library:public'
#everyone belongs to this app but it has no use
MOTHERSHIPAPP='adsgut/app:adsgut'
#everyone belongsto this app and the use here is to make sure all have access to tags, notes
#pubs and searches. it may be wortj having the MOTHERSHIP app own tags and notes but this works for now.
FLAGSHIPAPP='ads/app:publications'
#this is the mongo user we use when there is no login. It lets us expose libraries to the general 
#public if we like
ANONYMOUSE='adsgut/user:anonymouse'

#The BASIC interface: its embedded and utilized by almost everything else
class Basic(EmbeddedDocument):
  name = StringField(required=True)#critial..eg bibcode for pubs
  uri = StringField(default="", required=True)#not really used yet
  creator=StringField(required=True)#person who created this object
  whencreated=DateTimeField(required=True, default=datetime.datetime.now)
  lastmodified=DateTimeField(required=True, default=datetime.datetime.now)
  #Below is a combination of namespace and name. see README(TODO) for section
  #on how fqins are constructed
  fqin = StringField(required=True, unique=True)
  #description of object. for eg description of group or the text of a note.
  #context dependent
  description = StringField(default="")

#an itemtype, eg ads/itemtype:pub
class ItemType(Document):
  classname="itemtype"
  basic = EmbeddedDocumentField(Basic)
  owner = StringField(required=True)#must be fqin of user
  #the membable specifies what app/group created this
  membable = StringField(default="adsgut/app:adsgut", required=True)
  #this last one is autoset, see augmenttypespec in utilities
  membabletype = StringField(required=True)

#a tagtype, eg ads/tagtype:tag
class TagType(Document):
  classname="tagtype"
  basic = EmbeddedDocumentField(Basic)
  owner = StringField(required=True)#must be fqin of user
  membable = StringField(required=True)
  membabletype = StringField(required=True)
  #tagmode='0' is promiscuous, means it will go to all libs item is in
  #tagmode=fqpn sets it to a particulat library
  #tagmode='1' heeps it private, so the tag is visible in personal library only
  tagmode = StringField(default='0', required=True)
  #singleton mode, if true, means that a new instance of this tag must be created each time
  #once again example is note, which is created with a uuid as name
  singletonmode = BooleanField(default=False, required=True)

#MembableEmbedded will be embedded in users and groups/apps(ie in memberables)
#This is anything that "CAN HAVE" a member. ie the membable interface
#thus its also used to embed groups/apps inside users
#most of this embedded is copied from the corresponding membable. This is part
#of our fully denormalized design.
class MembableEmbedded(EmbeddedDocument):
  fqpn = StringField(required=True)#fqin of membable
  ptype = StringField(required=True)#type, eg 'library'
  pname = StringField(required=True)#presentable name(ie what we will use on web page)
  owner = StringField(required=True)#must be fqin of user
  #if library, what are the memberable's perms in it
  readwrite = BooleanField(required=True, default=False)
  islibrarypublic = BooleanField(default=False)# is library, is it public
  description = StringField(default="")
  librarykind = StringField(default="")#"" is for not library, otherwise its keys in RWDEF

#The MemberableEmbedded represents a unit that is a member (MEMBER-IN), for example a user,
#group or app that is member of a library or tag, or a user or group that is member
#of an app, or a user who is a member of a group

class MemberableEmbedded(EmbeddedDocument):
  fqmn = StringField(required=True)#fqin of memberable
  mtype = StringField(required=True)#type of memberable: u/g/a
  pname = StringField(required=True)#presentable name
  readwrite = BooleanField(required=True, default=False)

#some generic functions we will use in instance methods below
#get fqins of members
def Gget_member_fqins(memb):
    return [ele.fqmn for ele in memb.members]

#get presentable names of members
def Gget_member_pnames(memb):
    return [ele.pname for ele in memb.members]

#get presentable name with read-write permissions of members
def Gget_member_rws(memb):
    perms={}
    for ele in memb.members:
        perms[ele.fqmn]=[ele.pname, ele.readwrite]
    return perms

#get fqins of invited users
def Gget_invited_fqins(memb):
    return [ele.fqmn for ele in memb.inviteds]

#get presentable names of invited users
def Gget_invited_pnames(memb):
    return [ele.pname for ele in memb.inviteds]

#get presentable name with read-write permissions of invited users
def Gget_invited_rws(memb):
    perms={}
    for ele in memb.inviteds:
        perms[ele.fqmn]=[ele.pname, ele.readwrite]
    return perms

#a class representing a Tag. Remember, this is a tag, not a tagging
#5e412bfa-c183-4e44-bbfd-687a54f07c9c/ads/tagtype:tag:random
#501e05e4-4576-4dbe-845d-876042d2d614/ads/tagtype:note:769c1d1f-a242-49cb-82ba-fbb6761ee4a8
class Tag(Document):
  classname="tag"
  meta = {
      'indexes': ['owner', 'basic.name', 'tagtype','basic.whencreated'],
      'ordering': ['-basic.whencreated']
  }
  basic = EmbeddedDocumentField(Basic)
  tagtype = StringField(required=True)
  #the singletonmode default comes from tagtype unless u set it explicitly, so for notes
  #if u make it so that other members of a library can see it, u set this explicitly(checkbox)
  singletonmode = BooleanField(required=True)#default is false but must come from tagtype
  #This is different from creator as ownership can be transferred.
  owner = StringField(required=True)#must be a user

  #memberable: can be users/groups/apps
  members = ListField(EmbeddedDocumentField(MemberableEmbedded))
  #must only be users below
  inviteds = ListField(EmbeddedDocumentField(MemberableEmbedded))

  #METHODS
  def presentable_name(self):
      return self.basic.name

  def get_member_fqins(self):
      return Gget_member_fqins(self)

  def get_member_pnames(memb):
      return Gget_member_pnames(memb)

  #Invitations to tags make no sense for now
  # def get_invited_fqins(self):
  #     return Gget_invited_fqins(self)

  # def get_invited_pnames(memb):
  #     return Gget_invited_pnames(memb)

  # def get_invited_rws(self):
  #     return Gget_invited_rws(self)



#adsgut/user:ads
#adsgut/user:5e412bfa-c183-4e44-bbfd-687a54f07c9c
class User(Document):
    "the adsgut user object in mongodn. distinct from the giovanni user object"
    classname="user"
    meta = {
      'indexes': ['nick', 'basic.name', 'adsid', 'basic.whencreated'],
      'ordering': ['-basic.whencreated']
    }
    adsid = StringField(required=True, unique=True)#email in ads system
    cookieid = StringField(required=True, unique=True)# cookie in ads system
    classicimported = BooleanField(default=False, required=True)
    #Unless user sets nick ahead of time, it is set to a uuid
    #its set for anonymouse/adsgut/ads
    nick = StringField(required=True, unique=True)
    #basic.name is set to nick
    basic = EmbeddedDocumentField(Basic)
    #use this to temporarily turn off a user
    dormant=BooleanField(default=False)
    #@interface=MEMBERSHIP-IN (augmented by owned)
    #note the postables is now a misnomer, it is anything you
    #can be a member in
    postablesin=ListField(EmbeddedDocumentField(MembableEmbedded))
    postablesowned=ListField(EmbeddedDocumentField(MembableEmbedded))
    postablesinvitedto=ListField(EmbeddedDocumentField(MembableEmbedded))

    def membableslibrary(self, pathinclude_p=False):
        "get a list of libraries for user, with indirect membership included"
        plist=[]
        libs=[]
        lfqpns=[]
        pathincludes=defaultdict(list)
        #first get the libraries etc we are directly members of
        for ele in self.postablesin:
            if ele.ptype == 'library':
                libs.append(ele)
                lfqpns.append(ele.fqpn)
                pathincludes[ele.fqpn].append((ele.ptype, ele.pname, ele.fqpn))
        #TODO:the below is removed for an array. Any code which depends on this in the JS should be changed.
        # for l in lfqpns:
        #     pathincludes[l] = ""
        #ok now lets target the non-directs
        for ele in self.postablesin:
            if ele.ptype != 'library':
                p = MAPDICT[ele.ptype].objects(basic__fqin=ele.fqpn).get()
                #this is a group or app so get the postables it is in
                ls = p.postablesin
                for e in ls:
                    #dont pick up anything else than libraries that the groups and apps are in
                    if e.ptype=='library':
                        pathincludes[e.fqpn].append((ele.ptype, ele.pname, ele.fqpn))
                        plist.append(e)
        #put all the libraries together. there might be dupes
        libs = libs + plist
        pdict={}
        rw={}
        for l in libs:
            #this does the set like behaviour so that we have the library only once
            if not pdict.has_key(l.fqpn):
                pdict[l.fqpn] = l
                rw[l.fqpn] = l.readwrite
            else:
                #this ensures that we get the most permissive permission of the library
                rw[l.fqpn] = rw[l.fqpn] or l.readwrite

        #This is a hack. We never save in mongodb so to be cheap we just overwrite the reference we saved
        #to the library with the most general read-write
        for k in pdict.keys():
            pdict[k].readwrite = rw[k]

        #see if we want dictionary as well as values.
        if pathinclude_p:
            return pdict.values(), pathincludes
        else:
            return pdict.values()

    def membablesnotlibrary(self):
        plist=[]
        for ele in self.postablesin:
          if ele.ptype != 'library':
              plist.append(ele)
        #print "membnotlib", [e.fqpn for e in plist]
        return plist


    def presentable_name(self):
        return self.adsid

#POSTABLES
class Group(Document):
    classname="group"
    meta = {
        'indexes': ['owner', 'basic.name', 'nick','basic.whencreated'],
        'ordering': ['-basic.whencreated']
    }

    #DEPRECATED: it has now become a personal library
    personalgroup=BooleanField(default=False, required=True)

    #@interface=BASIC
    nick = StringField(required=True, unique=True)
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)

    #@interface=MEMBERS
    members = ListField(EmbeddedDocumentField(MemberableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MemberableEmbedded))#only fqmn

    #@interface=MEMBERSHIP-IN
    postablesin=ListField(EmbeddedDocumentField(MembableEmbedded))

    def get_member_fqins(self):
        return Gget_member_fqins(self)

    def get_member_pnames(memb):
        return Gget_member_pnames(memb)

    def get_member_rws(self):
        return Gget_member_rws(self)

    def get_invited_fqins(self):
        return Gget_invited_fqins(self)

    def get_invited_pnames(memb):
        return Gget_invited_pnames(memb)

    def get_invited_rws(self):
        return Gget_invited_rws(self)

    def get_postablesin_rws(self):
        perms={}
        for ele in self.postablesin:
            perms[ele.fqpn]=[ele.pname, ele.readwrite]
        return perms

    def presentable_name(self, withoutclass=False):
        if withoutclass:
            return self.basic.name
        return self.classname+":"+self.basic.name

class App(Document):
    classname="app"
    meta = {
        'indexes': ['owner', 'basic.name', 'nick', 'basic.whencreated'],
        'ordering': ['-basic.whencreated']
    }

    #@interface=BASIC
    nick = StringField(required=True, unique=True)
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)

    #@interface=MEMBERS
    members = ListField(EmbeddedDocumentField(MemberableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MemberableEmbedded))

    #@interface=MEMBERSHIP-IN
    postablesin=ListField(EmbeddedDocumentField(MembableEmbedded))


    def get_member_fqins(self):
        return Gget_member_fqins(self)

    def get_member_pnames(memb):
        return Gget_member_pnames(memb)

    def get_member_rws(self):
        return Gget_member_rws(self)

    def get_invited_fqins(self):
        return Gget_invited_fqins(self)

    def get_invited_pnames(memb):
        return Gget_invited_pnames(memb)

    def get_invited_rws(self):
        return Gget_invited_rws(self)

    def get_postablesin_rws(self):
        perms={}
        for ele in self.postablesin:
            perms[ele.fqpn]=[ele.pname, ele.readwrite]
        return perms

    def presentable_name(self, withoutclass=False):
        if withoutclass:
            return self.basic.name
        return self.classname+":"+self.basic.name

class Library(Document):
    classname="library"
    meta = {
        'indexes': ['owner', 'basic.name', 'nick', 'basic.whencreated'],
        'ordering': ['-basic.whencreated']
    }

    #@interface=BASIC
    nick = StringField(required=True, unique=True)
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)

    #Two NEW fields added to library
    #this one can be "udg" (1 per user), "public" (1), "group" (1 per group), "app"(1 per app)
    librarykind = StringField(required=False, default="library")
    #did you make the library public? (public group and anonymouse support)
    #QUESTION: should it be public library (post or not), and anonymouse separate? I think so.
    islibrarypublic = BooleanField(default=False, required=False)

    #@interface=MEMBERS
    members = ListField(EmbeddedDocumentField(MemberableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MemberableEmbedded))


    def get_member_fqins(self):
        return Gget_member_fqins(self)

    def get_member_pnames(memb):
        return Gget_member_pnames(memb)

    def get_member_rws(self):
        return Gget_member_rws(self)

    def get_invited_fqins(self):
        return Gget_invited_fqins(self)

    def get_invited_pnames(memb):
        return Gget_invited_pnames(memb)

    def get_invited_rws(self):
        return Gget_invited_rws(self)


    def presentable_name(self, withoutclass=False):
        if withoutclass:
            return self.basic.name
        return self.classname+":"+self.basic.name

#
#POSTING AND TAGGING ARE DUCKS. A tagging is a kind-of post
#
class Post(EmbeddedDocument):

    meta = {'allow_inheritance':True}
    #for item posts, this is the postable ingo, for tag posts this would be the fqin/type of the tag too.
    postfqin=StringField(required=True)
    posttype=StringField(required=True)
    #below is the item and itemtype foritem  posts, and stuff about the tag for posting a tagging
    thingtopostfqin=StringField(required=True)
    thingtoposttype=StringField(required=True)
    thingtopostname=StringField(required=True)
    thingtopostdescription=StringField(default="", required=True)
    whenposted=DateTimeField(required=True, default=datetime.datetime.now)
    postedby=StringField(required=True)

class Tagging(Post):
    #tagtype=StringField(default="ads/tag", required=True)
    tagname=StringField(required=True)
    tagdescription=StringField(default="", required=True)
    tagmode = StringField(default='0', required=True)#0/1/fqon=promiscuous/private/library-wide
    singletonmode = BooleanField(default=False, required=True)

class TPHist(EmbeddedDocument):
    #postfqin=StringField(required=True)
    whenposted=DateTimeField(required=True, default=datetime.datetime.now)
    postedby=StringField(required=True)

class PostingDocument(Document):
    classname="postingdocument"
    meta = {
        'indexes': ['posting.postfqin', 'posting.posttype', 'posting.whenposted', 'posting.postedby', 'posting.thingtoposttype', 'posting.thingtopostfqin', 'posting.thingtopostname', ('posting.postfqin', 'posting.thingtopostfqin'), ('posting.postfqin', 'posting.thingtopostname')],
        'ordering': ['-posting.whenposted']
    }
    #update information in posting below to latest whenposted and posted-by
    posting=EmbeddedDocumentField(Post)
    hist=ListField(EmbeddedDocumentField(TPHist))
    #we capture this here so we only ever need to search posting documents
    stags = ListField(EmbeddedDocumentField(Tagging))

#unlike postingdocument, no hist here, as its the individual tagging that gets posted in a library
#in this sense the adsid is critical to identify the tagging document.
class TaggingDocument(Document):
    classname="taggingdocument"
    meta = {
        'indexes': ['posting.postfqin', 'posting.posttype', 'posting.whenposted', 'posting.postedby', 'posting.thingtoposttype', 'posting.tagname', 'posting.thingtopostfqin', ('posting.postfqin', 'posting.thingtopostfqin')],
        'ordering': ['-posting.whenposted']
    }
    posting=EmbeddedDocumentField(Tagging)
    #In which libraries has this tagging has been posted. Do we not need some kind of hist for this?
    pinpostables = ListField(EmbeddedDocumentField(Post))




#how to have indexes work within pinpostables abd stags? use those documents
#hopefully we are doing this but how to handle the multiple postings?
class Item(Document):
    classname="item"
    meta = {
        'indexes': ['itemtype', 'basic.whencreated', 'basic.name'],
        'ordering': ['-basic.whencreated']
    }
    #itypefqin
    itemtype = StringField(required=True)
    basic = EmbeddedDocumentField(Basic)
    #In which libraries have we been posted?
    pinpostables = ListField(EmbeddedDocumentField(Post))
    #What tags have been applied to these items?
    stags = ListField(EmbeddedDocumentField(Tagging))


MAPDICT={
    'group':Group,
    'app':App,
    'user':User,
    'library':Library
}


POSTABLES=[Library]#things that can be posted to
#Postables are both membable and ownable
MEMBERABLES=[Group, App, User]#things that can be members
MEMBERABLES_NOT_USER=[Group, App]
MEMBERABLES_FOR_TAG_NOT_USER=[Group, App, Library]
MEMBABLES=[Group, App, Library, Tag]#things you can be a member of
#above all use nicks
OWNABLES=[Group, App, Library, ItemType, TagType, Tag]#things that can be owned
#OWNERABLES=[Group, App, User]#things that can be owners. Do we need a shadow owner?
OWNERABLES=[User]
#The Memberable-Membable-Map tells you who can be a member of whom.
MMMAP={
    Group:{Group:False, App:False, User:True},
    App:{Group:True, App:False, User:True},
    Library:{Group:True, App:True, User:True},
    Tag:{Group:True, App:True, User:True}
}

#THIS NEEDS TO BE CHANGED. It has to refer to libraries
#The RWDEFMAP tells you about your membership mode. If you are a member of a group, it says u can read everything in
#the group and write to it, but for a library, you may read everything, but not necessarily write to it.
#(ie True maeans both read and write, false means read-only)
#i think App=True is a bug for now and we should use masquerading instead to get things into apps
#users ought not to add to apps directly.
RWDEFMAP={
    Group:True,
    App:True,#should apps use masquerading instead? BUG
    Library:False,
    Tag:False
}

#tells you whether the defaulr is rw-true ow r-false
#TODO: not sure what this does for tag

#the interpretation here is for any other group or app except the libraries group or app
RWDEF={
    'group':False,
    'app':False,#should apps use masquerading instead? BUG
    'library':False,
    'tag':False,
    'udl':True,
    'public':True
}

#tuple-1, type allowed. if None, any memberable
#tuple-2
#if true, then only the entity corresponding to the library or tag is allowed in
#the library (bbesides the owner). otherwise, anyone is. If None, only the owner
#For public, note that only the public group is allowed
RESTR={
    'group':(None,True),
    'app':(None, True),#should app libraries use masquerading instead? BUG
    'library':(None,False),
    'tag':(None, False),
    'udl':(User, None),
    'public':(None, True)
}

MMMAP2={
    Group:{Group:False, App:False, User:True},
    App:{Group:True, App:False, User:True},
    Library:{Group:True, App:True, User:True},
    Tag:{Group:True, App:True, User:True}
}
#Should above be more detailed, such as below?
# #Critically, the fact that you cannot read all items in an app is done in _qproc
# #not sure that is right place.
# READDEFMAP={
#     Group:{Group:False, App:False, User:True},
#     App:{Group:False, App:False, User:True},
#     Library:{Group:False, App:False, User:True},
#     Tag:{Group:False, App:False, User:True}
# }
# WRITEDEFMAP={
#     Group:{Group:False, App:False, User:True},
#     App:{Group:False, App:False, User:True},
#     Library:{Group:False, App:False, User:True},
#     Tag:{Group:False, App:False, User:True}
# }

if __name__=="__main__":
    pass
