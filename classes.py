from mongoengine import *
import datetime

#BUG: at some point counters on collections should be built in
#

#default indexes on basic.fqin

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
    pname = StringField(required=True)
    readwrite = BooleanField(required=True, default=False)
    description = StringField(default="")

#This is for the membable. But these are identical interfaces
#we will use this for members and inviteds instead of strings to implement readwrite
#discussed at the ADS meeting.
class MembableEmbedded(EmbeddedDocument):
    fqmn = StringField(required=True)
    mtype = StringField(required=True)
    pname = StringField(required=True)
    readwrite = BooleanField(required=True, default=False)

def Gget_member_fqins(memb):
    return [ele.fqmn for ele in memb.members]

def Gget_member_pnames(memb):
    return [ele.pname for ele in memb.users]

def Gget_member_rws(memb):
    perms={}
    for ele in memb.members:
        perms[ele.fqmn]=[ele.pname, ele.readwrite]
    return perms

def Gget_invited_fqins(memb):
    return [ele.fqmn for ele in memb.inviteds]

def Gget_invited_pnames(memb):
    return [ele.pname for ele in memb.inviteds]

def Gget_invited_rws(memb):
    perms={}
    for ele in memb.inviteds:
        perms[ele.fqmn]=[ele.pname, ele.readwrite]
    return perms


class Tag(Document):
    classname="tag"
    meta = {
        'indexes': ['owner', 'basic.name', 'tagtype','basic.whencreated'],
        'ordering': ['-basic.whencreated']
    }
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

    def presentable_name(self):
        return self.basic.name

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




#BUG: do we want a similar thing for tags?
class User(Document):
    classname="user"
    meta = {
        'indexes': ['nick', 'basic.name', 'adsid', 'basic.whencreated'],
        'ordering': ['-basic.whencreated']
    }
    adsid = StringField(required=True, unique=True)
    cookieid = StringField(required=True, unique=True)
    classicimported = BooleanField(default=False, required=True)
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

    #for this one i care to blame where we came from
    def postablesother_blame(self):
        plist=[]
        libs=[]
        for ele in self.postablesin:
            if ele.ptype == 'library':
                libs.append(ele)
        lfqpns=[l.fqpn for l in libs]
        names={}
        for l in lfqpns:
            names[l] = ""
        for ele in self.postablesin:
            if ele.ptype != 'library':
                p = MAPDICT[ele.ptype].objects(basic__fqin=ele.fqpn).get()
                ls = p.postablesin
                for e in ls:
                    if e.fqpn not in lfqpns:
                        if not names.has_key(e.fqpn):
                            names[e.fqpn]=[]
                        names[e.fqpn].append((ele.ptype, ele.pname))
                    plist.append(e)

        libs = libs + plist
        pdict={}
        rw={}
        for l in libs:
            if not pdict.has_key(l.fqpn):
                pdict[l.fqpn] = l
                rw[l.fqpn] = l.readwrite
            else:
                rw[l.fqpn] = rw[l.fqpn] or l.readwrite
        for k in pdict.keys():
            pdict[k].readwrite = rw[k]
        return pdict.values(), names

    def postablesnotlibrary(self):
        plist=[]
        for ele in self.postablesin:
            if ele.ptype != 'library':
                plist.append(ele)
        return plist
    #for this one i want one per library, dont care where the library perms came from
    def postableslibrary(self):
        plist=[]
        libs=[]
        for ele in self.postablesin:
            if ele.ptype != 'library':
                p = MAPDICT[ele.ptype].objects(basic__fqin=ele.fqpn).get()
                ls = p.postablesin
                for e in ls:
                    plist.append(e)
            else:
                libs.append(ele)
        libs = libs + plist
        pdict={}
        rw={}
        for l in libs:
            if not pdict.has_key(l.fqpn):
                pdict[l.fqpn] = l
                rw[l.fqpn] = l.readwrite
            else:
                rw[l.fqpn] = rw[l.fqpn] or l.readwrite
        for k in pdict.keys():
            pdict[k].readwrite = rw[k]
        return pdict.values()


        

    #this below is wrong as we dont take into account multiple groups that can be in a library
    # def postablesall_rws(self):
    #     perms2={}
    #     perms={}
    #     for ele in self.postablesin:
    #         if ele.ptype == 'library':
    #             perms[ele.fqpn]=[ele.pname, ele.readwrite]
    #         else:#in a group or app which can be members.
    #             perms[ele.fqpn]=[ele.pname, ele.readwrite]
    #             p = MAPDICT[ele.ptype].objects(basic__fqin=ele.fqpn).get()
    #             perms2[ele.fqpn] = p.get_postablesin_rws()
    #     #BUG: we dont distinguish group and app hierarchies. Currently only assuming groups.
    #     for k in perms2.keys():
    #         pdict = perms2[k]
    #         for l in pdict.keys():
    #             #if we are already member of library directly get perms from there
    #             if not perms.has_key(l):
    #                 perms[l] = pdict[l]
    #     return perms

    def presentable_name(self):
        return self.adsid

#POSTABLES
class Group(Document):
    classname="group"
    meta = {
        'indexes': ['owner', 'basic.name', 'nick','basic.whencreated'],
        'ordering': ['-basic.whencreated']
    }
    personalgroup=BooleanField(default=False, required=True)
    #ISMEMBER INTERFACE
    nick = StringField(required=True, unique=True)
    #@interface:POSTABLE
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    members = ListField(EmbeddedDocumentField(MembableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MembableEmbedded))#only fqmn
    postablesin=ListField(EmbeddedDocumentField(PostableEmbedded))

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

    def presentable_name(self):
        return self.classname+":"+self.basic.name

class App(Document):
    classname="app"
    meta = {
        'indexes': ['owner', 'basic.name', 'nick', 'basic.whencreated'],
        'ordering': ['-basic.whencreated']
    }
    #ISMEMBER INTERFACE
    nick = StringField(required=True, unique=True)
    #@interface:POSTABLE
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    members = ListField(EmbeddedDocumentField(MembableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MembableEmbedded))
    postablesin=ListField(EmbeddedDocumentField(PostableEmbedded))


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

    def presentable_name(self):
        return self.classname+":"+self.basic.name
#Do we need this at all?
class Library(Document):
    classname="library"
    meta = {
        'indexes': ['owner', 'basic.name', 'nick', 'basic.whencreated'],
        'ordering': ['-basic.whencreated']
    }
    #Libraries cant me members, but still we implement this ISMEMBER INTERFACE
    nick = StringField(required=True, unique=True)
    #@interface:POSTABLE
    basic = EmbeddedDocumentField(Basic)
    owner = StringField(required=True)
    members = ListField(EmbeddedDocumentField(MembableEmbedded))
    inviteds = ListField(EmbeddedDocumentField(MembableEmbedded))

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


    def presentable_name(self):
        return self.classname+":"+self.basic.name
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
    meta = {
        'indexes': ['thething.postfqin', 'thething.posttype', 'thething.whenposted', 'thething.postedby', 'thething.thingtoposttype'],
        'ordering': ['-thething.whenposted']
    }
    thething=EmbeddedDocumentField(Post)

class TaggingDocument(Document):
    classname="taggingdocument"
    meta = {
        'indexes': ['thething.postfqin', 'thething.posttype', 'thething.whenposted', 'thething.postedby', 'thething.thingtoposttype', 'thething.tagname', 'thething.tagtype'],
        'ordering': ['-thething.whenposted']
    }
    thething=EmbeddedDocumentField(Tagging)
    #pingrps = ListField(EmbeddedDocumentField(Post))
    #pinapps = ListField(EmbeddedDocumentField(Post))
    #pinlibs = ListField(EmbeddedDocumentField(Post))
    pinpostables = ListField(EmbeddedDocumentField(Post))
    #pinlibs = ListField(EmbeddedDocumentField(Tagging))


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
MAPDICT={
    'group':Group,
    'app':App,
    'user':User,
    'library':Library
}

if __name__=="__main__":
    pass