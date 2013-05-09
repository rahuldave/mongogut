from classes import *
OK=200
LOGGEDIN_A_SUPERUSER_O_USERAS=False
MEMBER_OF_POSTABLE=False
POSTABLES=[Group, App, Library]#things that can be posted to, and you can be a member of
MEMBERABLES=[Group, App, User]#things that can be members
#above all use nicks
OWNABLES=[Group, App, Library, ItemType, TagType]#things that can be owned
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
    ns, val=fqin.split(':')
    nslist=ns.split('/')
    nstypename=nslist[-1]

def gettype(fqin):
    return classtype(MAPDICT[getNSTypeName(fqin)])

#BUG: add a function musthave which can then be used to validate in augmentitspec

def augmentspec(specdict, spectype='user'):
    basicdict={}
    print "INSPECDICT", specdict
    spectypestring = spectype.classname
    if spectype in POSTABLES:
        specdict['owner']=specdict['creator']
        basicdict['creator']=specdict['creator']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        basicdict['fqin']=specdict['creator']+"/"+spectypestring+":"+specdict['name']
        specdict['nick']=basicdict['fqin']
    elif spectype==User:
        basicdict['creator']="adsgut/user:adsgut"
        basicdict['description']=specdict.get('description','')
        basicdict['fqin']=specdict['creator']+"/"+spectypestring+":"+specdict['nick']
    specdict['basic']=Basic(**basicdict)
    
    del specdict['name']
    del specdict['creator']
    if specdict.has_key('description'):
        del specdict['description']
    return specdict

def augmentitspec(specdict, spectype="item"):
    basicdict={}
    print "INSPECDICT", specdict
    if spectype=='item' or spectype=='tag':
        basicdict['creator']=specdict['creator']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        #BUG:item is different. should it be so?
        if spectype=="item":
            specdict['itemtype']=specdict.get('itemtype','adsgut/item')
            itemtypens=specdict['itemtype'].split('/')[0]
            basicdict['fqin']=itemtypens+"/"+specdict['name']
        else:
            specdict['tagtype']=specdict.get('tagtype','ads/tag')
            specdict['owner']=basicdict['creator']
            #tag, note, library, group and app are reserved and treated as special forms
            basicdict['fqin']=specdict['creator']+"/"+specdict['tagtype']+':'+specdict['name']

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
    #for itemtype, come in with an postabletype=app and a postable=appfqin
    print "INSPECDICT", specdict
    if spectype=='itemtype' or spectype=='tagtype':
        basicdict['creator']=specdict['creator']
        specdict['creator']=specdict['owner']
        basicdict['name']=specdict['name']
        basicdict['description']=specdict.get('description','')
        basicdict['fqin']=specdict['creator']+"/"+spectype+":"+specdict['name']
    specdict['basic']=Basic(**basicdict)
    del specdict['name']
    del specdict['creator']
    if specdict.has_key('description'):
        del specdict['description']
    return specdict
