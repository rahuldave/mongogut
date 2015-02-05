import pytest
from pytest import raises
from exc import MongoGutError

def notallowed(assertion):
    with raises(MongoGutError) as excinfo:
        assert assertion
    assert 1==1, "["+str(excinfo.value.message)+" "+str(excinfo.value.status_code)+"]"

def print_exc(excinfo):
    print ">>>"+str(excinfo.value.message)+"<<<"+str(excinfo.value.status_code)+"==="
class Inifix:

    def __init__(self, postdb):
        self.whosdb = postdb.whosdb
        currentuser=None
        adsgutuser=self.whosdb._getUserForNick(currentuser, "adsgut")
        adsuser=self.whosdb._getUserForNick(adsgutuser, "ads")
        rahuldave=self.whosdb._getUserForNick(adsgutuser, "rahuldave")
        jayluker=self.whosdb._getUserForNick(adsgutuser, "jayluker")
        mlg=self.whosdb._getMembable(adsgutuser, "rahuldave/group:ml")
        spg=self.whosdb._getMembable(adsgutuser, "jayluker/group:sp")
        mlgl=self.whosdb._getMembable(adsgutuser, "rahuldave/library:ml")
        spgl=self.whosdb._getMembable(adsgutuser, "jayluker/library:sp")
        mll=self.whosdb._getMembable(adsgutuser, "rahuldave/library:mll")
        spl=self.whosdb._getMembable(adsgutuser, "jayluker/library:spl")
        self.users = dict(adsgut=adsgutuser, ads=adsuser, rahuldave=rahuldave, jayluker=jayluker)
        self.groups=dict(mlg=mlg, spg=spg)
        self.group_libraries=dict(mlgl=mlgl, spgl=spgl)
        self.libraries=dict(mll=mll, spl=spl)
        self.adsgutuser=adsgutuser

@pytest.fixture(scope="module")
def inidb(postdb):
    return Inifix(postdb)

def test_social0(inidb):
    assert inidb.users['rahuldave'].nick=="rahuldave"

#@pytest.mark.usefixtures("iniuserdb")
#class TestSocialUser:
def test_users_getuser_allowed(inidb, capsys):
    assert inidb.whosdb.isSystemUser(inidb.users['adsgut'])
    assert inidb.whosdb.getUserInfo(inidb.users['rahuldave'], "rahuldave")
    assert inidb.whosdb.getUserInfo(inidb.users['adsgut'], "rahuldave")
    assert inidb.whosdb.getUserInfoFromAdsid(inidb.users['adsgut'], "rahuldave@gmail.com")
    assert inidb.whosdb.getUserInfoFromAdsid(inidb.users['rahuldave'], "rahuldave@gmail.com")
    #notallowed(inidb.whosdb.getUserInfo(inidb.users['jayluker'], "rahuldave"))

def test_user_getuser_notallowed(inidb, capsys):
    with raises(MongoGutError) as excinfo:
        assert inidb.whosdb.getUserInfo(inidb.users['jayluker'], "rahuldave")
    print_exc(excinfo)
    out, err = capsys.readouterr()
    assert "not authorized" in out

    out, err = capsys.readouterr()
    with raises(MongoGutError) as excinfo:
        assert inidb.whosdb.getUserInfoFromAdsid(inidb.users['jayluker'], "rahuldave@gmail.com")
    print_exc(excinfo)
    out, err = capsys.readouterr()
    assert "not authorized" in out
    print out
    #assert "uthor" in excinfo.message

#ation should not be run but be a statement, so it needs to be "quoted"
def capture_error(capsys, ation, astring):
    with raises(MongoGutError) as excinfo:
        assert ation
    print_exc(excinfo)
    out, err = capsys.readouterr()
    assert astring in out

#errors in this dont raise mongogut, but send False
def test_membership_ismember_allowed(inidb, capsys):
    assert inidb.whosdb.isMemberOfMembable(inidb.adsgutuser,inidb.users['rahuldave'], inidb.libraries['mll'])
    assert inidb.whosdb.isMemberOfMembable(inidb.adsgutuser,inidb.users['rahuldave'], inidb.groups['mlg'])
    assert inidb.whosdb.isMemberOfMembable(inidb.adsgutuser,inidb.users['rahuldave'], inidb.group_libraries['mlgl'])
    assert inidb.whosdb.isMemberOfMembable(inidb.adsgutuser,inidb.users['jayluker'], inidb.libraries['spl'])
    assert inidb.whosdb.isMemberOfMembable(inidb.adsgutuser,inidb.users['jayluker'], inidb.groups['spg'])
    assert inidb.whosdb.isMemberOfMembable(inidb.adsgutuser,inidb.users['jayluker'], inidb.group_libraries['spgl'])

def test_membership_ismember_notallowed(inidb, capsys):
    assert not inidb.whosdb.isMemberOfMembable(inidb.adsgutuser,inidb.users['jayluker'], inidb.libraries['mll'])

def test_membership_getmembableinfo_allowed(inidb, capsys):
    inidb.whosdb.getMembableInfo(inidb.users['rahuldave'], inidb.users['rahuldave'], "rahuldave/library:mll")
    inidb.whosdb.getMembableInfo(inidb.adsgutuser, inidb.users['rahuldave'], "rahuldave/library:mll")
    #currently will still work as even tho adsgutuser masquerades as jayluker, he is superuser
    #should this be the case?
    inidb.whosdb.getMembableInfo(inidb.adsgutuser, inidb.users['jayluker'], "rahuldave/library:mll")


def test_membership_getmembableinfo_allowed(inidb, capsys):
    #notice i am allowed to masquerade as jayluker by perms system. need to shut this down TODO
    #so eventually the first of these two should give a different mongogut error
    with raises(MongoGutError) as excinfo:
        assert inidb.whosdb.getMembableInfo(inidb.users['rahuldave'], inidb.users['jayluker'], "rahuldave/library:mll")
    print_exc(excinfo)
    out, err = capsys.readouterr()
    assert "must be member" in out
    with raises(MongoGutError) as excinfo:
        assert inidb.whosdb.getMembableInfo(inidb.users['jayluker'], inidb.users['jayluker'], "rahuldave/library:mll")
    print_exc(excinfo)
    out, err = capsys.readouterr()
    assert "must be member" in out
