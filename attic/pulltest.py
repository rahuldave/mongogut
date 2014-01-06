#mongo junktest --eval "db.dropDatabase();"
from mongoengine import *
db_session=connect("junktest")
class B(EmbeddedDocument):
    bs = StringField()
    bi = IntField()
    bii = IntField()

class A(Document):
    abs = ListField(EmbeddedDocumentField(B))


b1 = B(bs="v", bi=1, bii=10)
b2 = B(bs="x", bi=2, bii=10)
b3 = B(bs="v", bi=1, bii=11)
b4 = B(bs="v", bi=2, bii=10)
a1 = A()
a1.save(safe=True)
a1.update(safe_update=True, push__abs=b1)
a1.update(safe_update=True, push__abs=b2)
a1.update(safe_update=True, push__abs=b3)

#a1.update(safe_update=True, pull__abs__bs='v')

a1.update(safe_update=True, pull__abs={'bi':2, 'bii':10})