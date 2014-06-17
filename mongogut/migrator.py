from mongoengine import *

import sys
import bson
import copy
dumpdir=sys.argv[1]
database=sys.argv[2]
host_uri=sys.argv[3]
connect(database, host=host_uri)
from mongoclasses import *

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

def uniq_lod(lod):
    temp={}
    for d in lod:
        if not temp.has_key(d['fqmn']):
            temp[d['fqmn']]=[]
        temp[d['fqmn']].append(d)
    return [temp[e][0] for e in temp.keys()]

tables=[
    "app",
    "group",
    "item",
    "library",
    "posting_document",
    "tag",
    "tagging_document",
    "user"
]

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



##############################################################################
datadict={}
for t in tables:
    datadict[t]=getlist(t)
finaldict={}
#Now we clean the list of dictionaries of unwanted fields so that we can use each as a spec with no extra fields
#adding new fields where appropriate

#NOTE: Some names have changed: default library for example. public group is also a public library now. list others here.
#we need to store default nicks from the new system in here as well, so we can use those for users.

existing_users=['adsgut/user:ads', 'adsgut/user:adsgut', 'adsgut/user:anonymouse']
existing_postables=['anonymouse/group:default','adsgut/app:adsgut', 'ads/app:publications', 'adsgut/group:public']
#TODO: not sure i am handling readwrites correctly. check
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

adsgutmembers=[e for e in adsgutmembers if e['fqmn'] not in existing_users]
adspubmembers=[e for e in adspubmembers if e['fqmn'] not in existing_users]

#TODO: remove the 3 users from here!
#note that members of adsgut app are inviteds as well, while those of the pub app are folks who have accepted
#the invitation
#print applist
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
    elif group['basic']['fqin']=='adsgut/group:public':
        publicmembers=group['members']
    else:
        groups.append(group)


# Handle special case:
#"06edcc36-7fcd-4f56-a76a-4a1d5f49c250/group:CfA Star Formation Journal Club" as user has created identical library

for g in groups:
    if g['basic']['fqin']=="06edcc36-7fcd-4f56-a76a-4a1d5f49c250/group:CfA Star Formation Journal Club":
        print g
        g['basic']['fqin']="06edcc36-7fcd-4f56-a76a-4a1d5f49c250/group:CfA Star Formation Journal Club-Group"
        g['basic']['name']="CfA Star Formation Journal Club-Group"
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

finaldict['library']=[]
finaldict['library'].append(personallibs)

###############################################################################
#3. Libraries
###############################################################################

liblist=datadict['library']
anonymousepin=[]
for lib in liblist:
    del lib['_id']
    if lib['basic']['fqin']=="06edcc36-7fcd-4f56-a76a-4a1d5f49c250/library:CfA Star Formation Journal Club":
        print lib
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



finaldict['library'].append(liblist)

###############################################################################
#4. Users
###############################################################################

userlist=datadict['user']
anonymouse=[u for u in userlist if u['basic']['fqin']=='adsgut/user:anonymouse'][0]
anonymousepin=[p for p in anonymouse['postablesin'] if p['fqpn'] not in existing_postables ]
userlist=[u for u in userlist if u['basic']['fqin'] not in existing_users]
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

finaldict['user']=[]
finaldict['user'].append(userlist)
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
        'pname':'library:'+p['basic']['name'],'readwrite':True, 'description':p['basic']['description']}
    presentname=None
    for u in userlist:
        if g['owner']==u['basic']['fqin']:
            presentname=u['adsid']
            u['postablesowned'].append(thelibrarymembe)
            u['postablesin'].append(thelibrarymembe)
    thelibrarymembe['owner']=presentname
    thegroupmembere={'fqmn':g['basic']['fqin'], 'mtype':'group', 'pname':'group:'+g['basic']['name'],'readwrite':True}
    theownermembere={'fqmn':g['owner'], 'mtype':'user', 'pname':presentname,'readwrite':True}

    g['postablesin'].append(thelibrarymembe)
    #there is no library corresponding to the group so initialize
    p['members']=[theownermembere, thegroupmembere]
    p['inviteds']=[]

# print groups[3]
# print "---------------------------------------------------------------"
# print grouplibs[3]

finaldict['group']=[]
finaldict['group'].append(groups)
finaldict['library'].append(grouplibs)
###############################################################################
#6. now we do tags
###############################################################################

tags=datadict['tag']

for tag in tags:
    del tag['_id']
    members=tag['members']
    #print members[0]
    for m in members:
        if m['mtype'] in ['group','app','library']:
            sp=m['fqmn'].split(':')
            m['pname']=sp[0].split('/')[-1]+':'+sp[-1]
        if m['mtype']=='user' and not m.has_key('pname'):
            for u in userlist:
                if m['fqmn']==u['basic']['fqin']:
                    m['pname']=u['adsid']
        if m['pname']=='group:default':
            m['fqmn']=group_to_lib(m['fqmn'])
            m['pname']='library:default'
            m['mtype']='library'
    tag['members']=uniq_lod(members)
#print tags[0]

# I am not dure what it means for tags to go into groups as well as libs. This needs more
#thought which we must put in
finaldict['tag']=[]
finaldict['tag'].append(tags)
###############################################################################
#7. now we do items
###############################################################################

items = datadict['item']
c=0
c2=0
itemdict={}
for item in items:
    del item['_id']
    pinpostables=item['pinpostables']
    for p in pinpostables:
        c=c+1
        p['thingtopostname']=p['thingtopostfqin'].split('/')[-1]
        p['thingtopostdescription']=""
        if p['posttype']=='group':
            p['posttype']='library'
            p['postfqin']=group_to_lib(p['postfqin'])
    stags=item['stags']
    for s in stags:
        c2=c2+1
        s['posttype']=s['tagtype']
        del s['tagtype']
        s['thingtopostname']=s['thingtopostfqin'].split('/')[-1]
        s['thingtopostdescription']=""
    item['stags']=[e for e in stags if e['posttype']!="ads/tagtype:note"]
    itemdict[item['basic']['fqin']]=item
#print items[0]['stags']
print "items x pinpostables=", c
print "items x stags=", c2
finaldict['item']=[]
finaldict['item'].append(items)
###############################################################################
#7. now we do tagging documents
###############################################################################

tds=datadict['tagging_document']
tagposteddict={}
for td in tds:
    del td['_id']
    tagging=td['posting']
    tagging['posttype']=tagging['tagtype']
    del tagging['tagtype']
    tagging['thingtopostname']=tagging['thingtopostfqin'].split('/')[-1]
    tagging['thingtopostdescription']=""
    pinpostables=td['pinpostables']
    for p in pinpostables:
        p['thingtopostname']=tagging['tagname']
        p['thingtopostdescription']=tagging['tagdescription']
        if p['posttype']=='group':
            p['posttype']='library'
            p['postfqin']=group_to_lib(p['postfqin'])
        if not tagposteddict.has_key(p['postfqin']):
            tagposteddict[p['postfqin']]=[]
        if tagging['posttype']!="ads/tagtype:note":
            tagposteddict[p['postfqin']].append(tagging)


print "taggingdocs", len(tds)
# print tds[0]['posting']
# print "---------------"
# print tds[0]['pinpostables']
finaldict['tagging_document']=[]
finaldict['tagging_document'].append(tds)
###############################################################################
#8. now we do posting documents
###############################################################################
#remember we now have to handle hists

pds=datadict['posting_document']
print "all posting documents",len(pds)
postingdict={}
for pd in pds:
    del pd['_id']
    posting=pd['posting']
    fqin=posting['thingtopostfqin']
    posting['thingtopostname']=fqin.split('/')[-1]
    if not postingdict.has_key(fqin):
        postingdict[fqin]=[]
    posting['thingtopostdescription']=""
    if posting['posttype']=='group':
            posting['posttype']='library'
            posting['postfqin']=group_to_lib(posting['postfqin'])
    postingdict[fqin].append(pd)

print len(postingdict.keys())
#now that we have got the correct fqpns let us consolidate
postingdocuments=[]
posting2dict={}
for fqin in postingdict.keys():
    if not posting2dict.has_key(fqin):
        posting2dict[fqin]={}
        for fqpn,e in [(e['posting']['postfqin'],e) for e in postingdict[fqin]]:
            if not posting2dict[fqin].has_key(fqpn):
                posting2dict[fqin][fqpn]=[]
            posting2dict[fqin][fqpn].append(e)

print len(posting2dict.keys())

for fqin in posting2dict.keys():
    for fqpn in posting2dict[fqin].keys():
        listofpds=posting2dict[fqin][fqpn]
        hists=[{'whenposted':pd['posting']['whenposted'],
                'postedby':pd['posting']['postedby']} for pd in listofpds]
        thepostingdoc=copy.deepcopy(listofpds[0])
        thepostingdoc['hist']=hists
        maxer=max(hists, key=lambda x:x['whenposted'])
        thepostingdoc['posting']['whenposted']=maxer['whenposted']
        thepostingdoc['posting']['postedby']=maxer['postedby']
        if tagposteddict.has_key(fqpn):
            thepostingdoc['stags']=[e for e in tagposteddict[fqpn] if e['thingtopostfqin']==fqin]
        else:
            thepostingdoc['stags']=[]
        postingdocuments.append(thepostingdoc)

# print len(postingdocuments)
# print '=========='
# for i,p in enumerate(postingdocuments):
#     if len(p['stags']) > 3:
#         print i, len(p['stags']), [e['tagname'] for e in p['stags']]
# print postingdocuments[272]
finaldict['posting_document']=[]
finaldict['posting_document'].append(postingdocuments)


#below will not work as we dont create appropriate embeddables
#DELETE _CLS and use mongoengine throughout.

#we somehow seem to get into the situation where there are more posting documents than pinpostables in items.
#Something there must have failed at some point. We must adjust the pinpostables to match the posting documents or any action
#will fail on those docs. Ditto for tagging docs. The code below shows us the discrepanvy
#numbers dont exactly add up but.

#we use the initial pds for this
remaining=[]
for pd in pds:
    ifqin=pd['posting']['thingtopostfqin']
    fqpn=pd['posting']['postfqin']
    postedby=pd['posting']['postedby']
    pinpostables=itemdict[ifqin]['pinpostables']
    inok=0
    for p in pinpostables:
        if p['postfqin']==fqpn and p['postedby']==postedby:
            inok=inok+1
    if inok==0:
        remaining.append(pd)

remaining2=[]
for td in tds:
    ifqin=td['posting']['thingtopostfqin']
    fqtn=td['posting']['postfqin']
    postedby=td['posting']['postedby']
    stags=itemdict[ifqin]['stags']
    inok=0
    for t in stags:
        if t['postfqin']==fqtn and t['postedby']==postedby:
            inok=inok+1
    if inok==0:
        remaining2.append(td)

print 'nok', len(remaining)
print '=========================='
print 'nok', len(remaining2)
RUN=True
if RUN:
    counter=0
    for ele in finaldict.keys():
        daclass=tabledict[ele]
        for l in finaldict[ele]:
            for i in l:
                inst=daclass(**i)
                inst.save(safe_update=True)
                counter=counter+1
    print "Saved objects", counter

    #Finally
    #(1) add adsgutmembers to adsgut app, adsmembers to ads app
    #(2) add publicmembers to public group
    #(3) add wherever anonymouse is to the anonymouse users postables in

    # currentuser=None
    # adsgutuser=whosdb._getUserForNick(currentuser, "adsgut")
    # currentuser=adsgutuser
    # adsgutapp=whosdb._getMembable(currentuser, "adsgut/app:adsgut")
    # adsapp=whosdb._getMembable(currentuser, "ads/app:publications")

    # adsuser=whosdb._getUserForNick(currentuser, "ads")
    # anonymouseuser=whosdb._getUserForNick(currentuser, "anonymouse")
    #print App.objects.all()
    adsgutapp=App.objects(basic__fqin="adsgut/app:adsgut").get()
    #print adsgutmembers[0]
    for m in adsgutmembers:
        adsgutapp.members.append(MemberableEmbedded(**m))
    adsgutapp.save(safe_update=True)
    adsapp=App.objects(basic__fqin="ads/app:publications").get()
    for m in adspubmembers:
        adsapp.members.append(MemberableEmbedded(**m))
    adsapp.save(safe_update=True)
    pubgroup=Group.objects(basic__fqin="adsgut/group:public").get()
    for m in publicmembers:
        pubgroup.members.append(MemberableEmbedded(**m))
    pubgroup.save(safe_update=True)
    anonymouse=User.objects(basic__fqin="adsgut/user:anonymouse").get()
    for p in anonymousepin:
        anonymouse.postablesin.append(MembableEmbedded(**p))
    anonymouse.save(safe_update=True)
    #Things to deal with
    #(a) should anonymouse be in groups? no, currently only in libs
    #keep it that way. (b) remove adsgut and ads app libraries
