db=${1-adsgut}
host=${2-localhost}
port=${3-27017}
dumpdir=${4}

sh dbit $db $host $port
python social.py $db "mongodb://adsgut:adsgut@${host}:${port}/$db"
python ptassets.py $db "mongodb://adsgut:adsgut@${host}:${port}/$db"
