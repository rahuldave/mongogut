# test_fixtures.py
import pytest
from pytest import fixture
from mongoengine import connect
from social import _init as socialinit
from social import initialize_testing as social_testinit
from ptassets import _init as ptassetsinit
from ptassets import initialize_testing as ptassets_testinit

from ptassets import Postdb

@fixture(scope="module")  # Registering this function as a fixture.
def postdb():
	db_session=connect('testgut', host='mongodb://adsgut:adsgut@localhost:27017/testgut')
	db_session.drop_database('testgut')
	socialinit('testgut', 'mongodb://adsgut:adsgut@localhost:27017/testgut')
	ptassetsinit('testgut', 'mongodb://adsgut:adsgut@localhost:27017/testgut')
	social_testinit(db_session)
	ptassets_testinit(db_session)
	#db_session=connect('testgut', host='mongodb://adsgut:adsgut@localhost:27017/testgut')
	postdb=Postdb(db_session)
	return postdb


if __name__=="__main__":
	pytest.main()

