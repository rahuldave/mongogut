from mongoclasses import *
from exc import *
OK=200

#Initial starting points for barrier functions in perms.py
LOGGEDIN_A_SUPERUSER_O_USERAS=False
MEMBER_OF_POSTABLE=False
MEMBER_OF_MEMBABLE=False

#map for words to classes. used to translate parts of fqins
MAPDICT={
    'group':Group,
    'app':App,
    'user':User,
    'library':Library
}

def classname(instance):
    return instance.classname

def classtype(instance):
    return type(instance)

#from a fqin, get its type, eg: item/library
def getNSTypeName(fqin):
    lst=fqin.split(':')
    nslist=lst[-2].split('/')
    nstypename=nslist[-1]
    return nstypename

#from an fqin, get the name part of it
def getNSVal(fqin):
    lst=fqin.split(':')
    return lst[-1]

#this gets the classname we baked into every mongo class
def getNSTypeNameFromInstance(instance):
    return classname(instance).lower()

#return the Class corresponding to the type in the fqin
def gettype(fqin):
    nstypename=getNSTypeName(fqin)
    return MAPDICT[nstypename]

#parses a tag, eg:#jayluker/ads/tagtype:tag:asexy
def parseTag(fqtn):
    tagname=fqtn.split('tagtype:tag:')[-1]
    spl=fqtn.split('/',1)
    taguser=spl[0]
    n=spl[1].find(tagname)
    tagtype=spl[1][0:n-1]
    return fqtn, taguser, tagtype, tagname

#use this to convert an app or a group to that apps or groups library
def getLibForMembable(fqin):
    lst=fqin.split(':')
    nslist=lst[-2].split('/')
    nshead=nslist[0]
    nstail=lst[-1]
    return nshead+"/library:"+nstail

#used to make sure that object SPECs have the right keys
def musthavekeys(indict, listofkeys):
    for k in listofkeys:
        if not indict.has_key(k):
            doabort('BAD_REQ', "Indict does not have key %s" % k)
    return indict

#make a uuid for the user
import uuid
def makeUuid():
    return str(uuid.uuid4())


###### The next few functions set up and make sure that SPEC's for various classes
#are set up properly

#set up a new group/app/library/user.
#the membable must have a creator and name coming in
#owner is set to creator and name is used in fqin
#for user, we must have the adsid which is an email coming in.
#a uuid is assigned as the nick for the user, and thus the name.
def augmentspec(specdict, specstr="user"):
    basicdict={}
    spectype=MAPDICT[specstr]
    spectypestring = spectype.classname

    if spectype in MEMBABLES:
        specdict=musthavekeys(specdict, ['creator', 'name'])
        specdict['owner']=specdict['creator']
        basicdict['creator']=specdict['creator']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        crnick=getNSVal(specdict['creator'])
        basicdict['fqin']=crnick+"/"+spectypestring+":"+specdict['name']
        #specdict['nick']=basicdict['fqin']
        if not specdict.has_key('nick'):
            specdict['nick']=makeUuid()
        if specstr=="library":#islibrarypublic set by default process
            if not specdict.has_key("librarykind"):
                specdict['librarykind']='library'
        del specdict['name']
    elif spectype==User:
        specdict=musthavekeys(specdict, ['adsid'])
        if not specdict.has_key('nick'):
            specdict['nick']=makeUuid()
        if not specdict.has_key('cookieid'):
            specdict['cookieid']=specdict['adsid']
        specdict['creator']="adsgut/user:adsgut"
        basicdict['creator']=specdict['creator']
        crnick=getNSVal(specdict['creator'])
        basicdict['name']=specdict['nick']
        basicdict['description']=specdict.get('description','')
        basicdict['fqin']=crnick+"/"+spectypestring+":"+specdict['nick']
    specdict['basic']=Basic(**basicdict)

    del specdict['creator']
    if specdict.has_key('description'):
        del specdict['description']
    if specstr!="library" and specdict.has_key("librarykind"):
        del specdict['librarykind']
    return specdict

#the SPEC augmenter for items and tags
#creator, name, and type are compulsory
#notice item is a bit different in how it is set, we use the namespace
#of thew itemtype eg ads/bibcode with no colon
def augmentitspec(specdict, spectype="item"):
    basicdict={}
    specdict=musthavekeys(specdict,['creator', 'name'])
    if spectype=='item' or spectype=='tag':
        basicdict['creator']=specdict['creator']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        if spectype=="item":
            specdict=musthavekeys(specdict,['itemtype'])
            itemtypens=specdict['itemtype'].split('/')[0]
            basicdict['fqin']=itemtypens+"/"+specdict['name']
        else:
            specdict=musthavekeys(specdict,['tagtype'])
            specdict['owner']=basicdict['creator']
            #tag, note, library, group and app are reserved and treated as special forms
            crnick=getNSVal(specdict['creator'])
            basicdict['fqin']=crnick+"/"+specdict['tagtype']+':'+specdict['name']

        if not specdict.has_key('uri'):
            basicdict['uri']=specdict['name']
        else:
            basicdict['uri']=specdict['uri']
            del specdict['uri']
    specdict['basic']=Basic(**basicdict)
    del specdict['name']
    del specdict['creator']
    if specdict.has_key('description'):
        del specdict['description']
    return specdict

#item types and tagtypes. The creator here must be a user.
#notice here we have a membable in addition to creators name
#we are using it right now for apps that the type was created in
#for bibgroups we would want to extend this to groups as well
def augmenttypespec(specdict, spectype="itemtype"):
    basicdict={}
    #for itemtype, come in with an postabletype=app and a postable=appfqin
    specdict=musthavekeys(specdict,['creator', 'name', 'membable'])
    #BUG validate its in the choices wanted ie app and grp (what about tagtypes in libs)
    specdict['membabletype']=getNSVal(specdict['membable'])
    basicdict['creator']=specdict['creator']
    specdict['owner']=specdict['creator']
    basicdict['name']=specdict['name']
    basicdict['description']=specdict.get('description','')
    crnick=getNSVal(specdict['creator'])
    basicdict['fqin']=crnick+"/"+spectype+":"+specdict['name']
    specdict['basic']=Basic(**basicdict)
    del specdict['name']
    del specdict['creator']
    if specdict.has_key('description'):
        del specdict['description']
    return specdict


#TODO: generally we should add some validation code in here.
