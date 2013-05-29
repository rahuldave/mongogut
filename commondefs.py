from classes import *
from errors import *
OK=200
LOGGEDIN_A_SUPERUSER_O_USERAS=False
MEMBER_OF_POSTABLE=False
Postables=["group", "app", "library"]
POSTABLES=[Group, App, Library]#things that can be posted to, and you can be a member of
#Postables are both membable and ownable
MEMBERABLES=[Group, App, User]#things that can be members
MEMBABLES=[Group, App, Library, Tag]#things you can be a member of
#above all use nicks
OWNABLES=[Group, App, Library, ItemType, TagType, Tag]#things that can be owned
#OWNERABLES=[Group, App, User]#things that can be owners. Do we need a shadow owner?
#the above all have nicks
#TAGGISH=[Group, App, Library, Tag]: or should it be PostingDoc, TaggingDoc?
MAPDICT={
    'group':Group,
    'app':App,
    'user':User,
    'library':Library
}

def classname(instance):
    return type(instance).__name__

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

#BUG: add a function musthave which can then be used to validate in augmentitspec
#this function currently dosent throw an exception it should when not in flask mode
def musthavekeys(indict, listofkeys):
    for k in listofkeys:
        if not indict.has_key(k):
            doabort('BAD_REQ', "Indict does not have key %s" % k)
    return indict

def augmentspec(specdict, specstr="user"):
    basicdict={}
    #print "INSPECDICT", specdict
    spectype=MAPDICT[specstr]
    spectypestring = spectype.classname

    if spectype in POSTABLES:
        specdict=musthavekeys(specdict, ['creator', 'name'])
        specdict['owner']=specdict['creator']
        basicdict['creator']=specdict['creator']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        crnick=getNSVal(specdict['creator'])
        basicdict['fqin']=crnick+"/"+spectypestring+":"+specdict['name']
        specdict['nick']=basicdict['fqin']
        del specdict['name']
    elif spectype==User:
        specdict=musthavekeys(specdict, ['adsid', 'nick'])
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
    return specdict

def augmentitspec(specdict, spectype="item"):
    basicdict={}
    print "INSPECDICT", specdict
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
    specdict=musthavekeys(specdict,['creator', 'name', 'postable'])
    #BUG validate its in the choices wanted ie app and grp (what about tagtypes in libs)
    specdict['postabletype']=getNSVal(specdict['postable'])
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
