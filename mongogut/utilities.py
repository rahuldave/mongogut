from mongoclasses import *
from errors import *
OK=200
LOGGEDIN_A_SUPERUSER_O_USERAS=False
MEMBER_OF_POSTABLE=False
MEMBER_OF_MEMBABLE=False

#if the default for tag is false, and we actually do land up checking this, then we have to find a way to let other use tags.
#that i'd want is for it to be true for group and user members of tags, but not for apps.

#the above all have nicks
#TAGGISH=[Group, App, Library, Tag]: or should it be PostingDoc, TaggingDoc?
MAPDICT={
    'group':Group,
    'app':App,
    'user':User,
    'library':Library
}

def classname(instance):
    #return type(instance).__name__
    return instance.classname

def classtype(instance):
    return type(instance)

def getNSTypeName(fqin):
    #print "fqin", fqin
    lst=fqin.split(':')
    nslist=lst[-2].split('/')
    nstypename=nslist[-1]
    return nstypename

def getNSVal(fqin):
    #print "fqin", fqin
    lst=fqin.split(':')
    return lst[-1]

def getNSTypeNameFromInstance(instance):
    return classname(instance).lower()

def gettype(fqin):
    nstypename=getNSTypeName(fqin)
    #print 'FQIN',fqin, nstypename
    return MAPDICT[nstypename]

def parseTag(fqtn):
    #jayluker/ads/tagtype:tag:asexy
    tagname=fqtn.split('tagtype:tag:')[-1]
    spl=fqtn.split('/',1)
    taguser=spl[0]
    n=spl[1].find(tagname)
    tagtype=spl[1][0:n-1]
    return fqtn, taguser, tagtype, tagname

def getLibForMembable(fqin):
    lst=fqin.split(':')
    nslist=lst[-2].split('/')
    nshead=nslist[0]
    nstail=lst[-1]
    return nshead+"/library:"+nstail
#BUG: add a function musthave which can then be used to validate in augmentitspec
#this function currently dosent throw an exception it should when not in flask mode
def musthavekeys(indict, listofkeys):
    for k in listofkeys:
        if not indict.has_key(k):
            doabort('BAD_REQ', "Indict does not have key %s" % k)
    return indict

import uuid
def makeUuid():
    return str(uuid.uuid4())

def augmentspec(specdict, specstr="user"):
    basicdict={}
    #print "INSPECDICT", specdict
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
    #print "OUTSPECDICT", specdict
    if specstr!="library" and specdict.has_key("librarykind"):
        del specdict['librarykind']
    return specdict

def augmentitspec(specdict, spectype="item"):
    basicdict={}
    #print "INSPECDICT", specdict
    specdict=musthavekeys(specdict,['creator', 'name'])
    if spectype=='item' or spectype=='tag':
        basicdict['creator']=specdict['creator']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        #BUG:item is different. should it be so?
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

#The creator here must be a user. The owner can later be changed
#to a general memberable. If the memberable is a postable and you
#belong to it, you can use it. But until we are shifted only that
#user can use it.
def augmenttypespec(specdict, spectype="itemtype"):
    basicdict={}
    #BUG: validate the specdict
    #for itemtype, come in with an postabletype=app and a postable=appfqin
    #print "INSPECDICT", specdict
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
