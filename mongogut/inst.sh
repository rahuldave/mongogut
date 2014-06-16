sh dbit $1
python social.py $1
python ptassets.py $1
time python migrator.py /Users/rahul/play/adsgut_20140612-154709/adsgut $1
