import sys
import bson
from mongoclasses import *
import copy
dumpdir=sys.argv[1]
#open("/Users/rahul/mongodata/dump/adsgut/user.bson").read()

def group_to_lib(fqin):
    lst=fqin.split(':')
    nslist=lst[-2].split('/')
    nshead=nslist[0]
    nstail=lst[-1]
    return nshead+"/library:"+nstail

def lib_to_group(fqin):
    lst=fqin.split(':')
    nslist=lst[-2].split('/')
    nshead=nslist[0]
    nstail=lst[-1]
    return nshead+"/library:"+nstail

def getlist(tabletype):
    s=open(dumpdir+"/"+tabletype+".bson").read()
    table=bson.decode_all(s)
    return table


tables=["app",
"group",
"item",
"item_type",
"library",
"posting_document",
"tag",
"tag_type",
"tagging_document",
"user"]

tabledict=dict(
    app=App,
    group=Group,
    item=Item,
    library=Library,
    posting_document=PostingDocument,
    tag=Tag,
    tagging_document=TaggingDocument,
    user=User
)

datadict={}
for t in tables:
    datadict[t]=getlist(t)

#Now we clean the list of dictionaries of unwanted fields so that we can use each as a spec with no extra fields
#adding new fields where appropriate

#NOTE: Some names have changed: default library for example. public group is also a public library now. list others here.
#we need to store default nicks from the new system in here as well, so we can use those for users.

###############################################################################
# 1. Apps
###############################################################################

# 1. we'll let the nick change
# 2. but we must get the members from this and add it to the system app.
applist=datadict['app']
for app in applist:
    #print app
    #print '--------------------------------'
    if app['basic']['name']=='adsgut':
        adsgutmembers=app['members']
    if app['basic']['name']=='publications':
        adspubmembers=app['members']

#note that members of adsgut app are inviteds as well, while those of the pub app are folks who have accepted
#the invitation

###TODO now add these to the existing classes. There are no changes to the spec for members


###############################################################################
#2. Groups
###############################################################################

#A default group is replaced by a library with the same specs.

grouplist=datadict['group']
#print grouplist[0]
personallibs=[]
groups=[]
for group in grouplist:
    del group['_id']
    if group['basic']['name']=='default':#this becomes a library
        personallibs.append(group)
    else:
        groups.append(group)

#now, for each group, also create a library with the group inside it and the owner of the group as well


personallibs = [p for p in personallibs if p['basic']['fqin'] not in ['adsgut/group:default','ads/group:default','anonymouse/group:default']]

for p in personallibs:
    del p['personalgroup']
    p['basic']['fqin'] = group_to_lib(p['basic']['fqin'])
    p['librarykind'] = 'udl'
    p['islibrarypublic'] = False

#print personallibs[0]
#print '--------------------------------'
#print groups[0]

###TODO now add these to the existing classes. There are no changes to the spec for members

###############################################################################
#3. Libraries
###############################################################################

liblist=datadict['library']

for lib in liblist:
    del lib['_id']
    possiblegroup=lib_to_group(lib['basic']['fqin'])
    fqmns=[e['fqmn'] for e in lib['members']]
    if possiblegroup in fqmns:
        lib['librarykind']='group'
    else:
        lib['librarykind']='library'
    if "adsgut/group:public" in fqmns:
        lib['islibrarypublic']=True
    else:
        lib['islibrarypublic']=False
    #print lib
    #print '--------------------------------'


###TODO now add these to the existing classes. There are no changes to the spec for members


###############################################################################
#4. Users
###############################################################################

userlist=datadict['user']
userlist=[u for u in userlist if u['basic']['name'] not in ['ads', 'adsgut', 'anonymouse']]
for user in userlist:
    del user['_id']
    user['dormant']=False
    po=user['postablesowned']
    pin=user['postablesin']
    piv=user['postablesinvitedto']
    for p in po+pin+piv:
        if p['pname']=='group:default':
            p['pname']='library:default'
            p['fqpn']=group_to_lib(p['fqpn'])
            p['ptype']='library'
            p['librarykind']='udl'
            p['islibrarypublic']=False
    for p in po + pin + piv:
        if p['ptype'] in ['group', 'app']:
            p['librarykind']=''
            p['islibrarypublic']=False
        if p['pname']!='library:default' and p['ptype']=='library':
            fqpn=p['fqpn']
            hoot=0
            for l in liblist:
                if l['basic']['fqin']==fqpn:
                    p['librarykind']=l['librarykind']
                    p['islibrarypublic']=l['islibrarypublic']
                    hoot=hoot+1
            if hoot==0:
                print "HOOT", p['fqpn']


#print userlist[0]

###############################################################################
#5. now adjust the group libraries using information from the user table
###############################################################################

#we also need to update the user table to reflect these new libraries

grouplibs=[copy.deepcopy(e) for e in groups]

for g,p in zip(groups,grouplibs):
    del p['personalgroup']
    p['basic']['fqin'] = group_to_lib(g['basic']['fqin'])
    p['librarykind'] = 'group'
    p['islibrarypublic'] = False#start with false but now its a lib
    thelibrarymembe={'fqpn':p['basic']['fqin'], 'ptype':'library', 'owner':p['owner'],
        'librarykind':p['librarykind'], 'islibrarypublic':p['islibrarypublic'],
        'pname':'library:'+p['basic']['name'],'readwrite':False, 'description':p['basic']['description']}
    presentname=None
    for u in userlist:
        if g['owner']==u['basic']['fqin']:
            presentname=u['adsid']
            u['postablesowned'].append(thelibrarymembe)
            u['postablesin'].append(thelibrarymembe)
    thegroupmembere={'fqmn':g['basic']['fqin'], 'mtype':'group', 'pname':'group:'+g['basic']['name'],'readwrite':True}
    theownermembere={'fqmn':g['owner'], 'mtype':'user', 'pname':presentname,'readwrite':True}

    g['postablesin'].append(thelibrarymembe)
    #there is no library corresponding to the group so initialize
    p['members']=[theownermembere, thegroupmembere]
    p['inviteds']=[]

# print groups[3]
# print "---------------------------------------------------------------"
# print grouplibs[3]

###TODO now add these to the existing classes. There are no changes to the spec for members

###############################################################################
#6. now we do tags
###############################################################################

tags=datadict['tag']

for tag in tags:
    del tag['_id']
    members=tag['members']
    for m in members:
        if m['pname']=='group:default':
            m['fqmn']=group_to_lib(m['fqmn'])
            m['pname']='library:default'
            m['mtype']='library'
print tags[0]
