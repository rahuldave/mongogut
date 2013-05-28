from classes import *
import itemsandtags
import simplejson

currentuser=None
db_session=connect("adsgut")
postdb=itemsandtags.Postdb(db_session)
whosdb=postdb.whosdb

adsgutuser=whosdb.getUserForNick(currentuser, "adsgut")
adsuser=whosdb.getUserForNick(adsgutuser, "ads")
currentuser=adsgutuser

alberto=whosdb.addUser(currentuser, dict(nick='alberto', adsid="alberto"))
alberto, adsteam=whosdb.addGroup(alberto, alberto, dict(name='adsteam', description="ADS Team"))
alberto, adspubapp=whosdb.addUserToPostable(adsuser, 'ads/app:publications', 'alberto')
#BUG: this needs to happen with routing

loadopen = lambda f: simplejson.loads(open(f).read())
e72=loadopen("./fixtures/4201071e72.json")

def getlibs(libs, json):
    for l in json['libraries']:
        if not libs.has_key(l['name']):
            libs[l['name']]=[l['name'],  l.get('desc',""), [e['bibcode'] for e in l['entries']], [e.get('note',"") for e in l['entries']]]
        else:
            print "repeated key", l['name']
            daset=set(libs[l['name']][2])
            newe=[e['bibcode'] for e in l['entries']]
            for e in newe:
                daset.add(e)
            libs[l['name']][2]=list(daset)
    return libs

            
li={}
li=getlibs(li, e72)
e73=loadopen("./fixtures/4201071e73.json")
li=getlibs(li, e73)

for k in li.keys():
    alberto, library=whosdb.addLibrary(alberto, alberto, dict(name=li[k][0], description=li[k][1]))
    bibdict={}
    for i in range(len(li[k][2])):
        bib=li[k][2][i]
        note=li[k][3][i]
        #this is for speed. the saveItem checks if item is already there and simply returns it.
        if not bibdict.has_key(bib):
            paper={}
            paper['name']=bib
            paper['itemtype']='ads/itemtype:pub'
            theitem=postdb.saveItem(alberto, alberto, paper)
            bibdict[bib]=theitem
        postdb.postItemIntoLibrary(alberto, alberto, library.basic.fqin, bibdict[bib].basic.fqin)
        if note != "":
            i,t,td=postdb.tagItem(alberto, alberto, bibdict[bib].basic.fqin, dict(tagtype="ads/tagtype:note", content=note))
            #if i could override the non-routed tagging i use for notes, below is not needed
            #however, lower should be faster
            postdb.postTaggingIntoLibrary(alberto, alberto, library.basic.fqin, td)