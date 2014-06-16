sh dbit $1
python social.py $1
python ptassets.py $1
# $2 is the directory the bson files are in
time python migrator.py $2 $1
