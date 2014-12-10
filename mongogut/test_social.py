import pytest

@pytest.fixture(scope="module")
def iniuserdb(postdb):
    whosdb=postdb.whosdb
    currentuser=None
    adsgutuser=whosdb._getUserForNick(currentuser, "adsgut")
    adsuser=whosdb._getUserForNick(adsgutuser, "ads")
    rahuldave=whosdb._getUserForNick(adsgutuser, "rahuldave")
    jayluker=whosdb._getUserForNick(adsgutuser, "jayluker")
    iniuserdb=dict(db=whosdb, users=dict(adsgut=adsgutuser,
        ads=adsuser, rahuldave=rahuldave, jayluker=jayluker))
    return iniuserdb


def test_social0(iniuserdb):
    assert iniuserdb['users']['rahuldave'].nick=="rahuldave"