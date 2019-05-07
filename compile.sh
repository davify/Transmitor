cd $1
python3 -O -m compileall .
find . -name '*.pyc' -exec rename 's/.cpython-35.opt-1//' {} \;
find . -name '*.pyc' -execdir mv {} .. \;
###find . -name '*.py' -type f -print -exec rm {} \;
find . -name '__pycache__' -exec rmdir {} \;
zip -r ../$1.zip ./*
mv ../$1.zip ../dist/
