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
        self.users = dict(adsgut=adsgutuser,
        ads=adsuser, rahuldave=rahuldave, jayluker=jayluker)

@pytest.fixture(scope="module")
def inidb(postdb):
    return Inifix(postdb)

def test_social0(inidb):
    assert inidb.users['rahuldave'].nick=="rahuldave"

#@pytest.mark.usefixtures("iniuserdb")
#class TestSocialUser:
def test_users_whotheyare(inidb, capsys):
    assert inidb.whosdb.isSystemUser(inidb.users['adsgut'])
    assert inidb.whosdb.getUserInfo(inidb.users['rahuldave'], "rahuldave")
    assert inidb.whosdb.getUserInfo(inidb.users['adsgut'], "rahuldave")
    #notallowed(inidb.whosdb.getUserInfo(inidb.users['jayluker'], "rahuldave"))
    out, err = capsys.readouterr()
    with raises(MongoGutError) as excinfo:
        assert inidb.whosdb.getUserInfo(inidb.users['jayluker'], "rahuldave")
    print_exc(excinfo)
    out, err = capsys.readouterr()
    assert "author" in out
    print out
    #assert "uthor" in excinfo.message