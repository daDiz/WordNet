## setup 

virtualenv venv

. venv/bin/activate

pip install -r requirements.txt

## get neo4j ready

(install neo4j)

sudo service neo4j start

cp data/wn18rr/\* /var/lib/neo4j/import

login neo4j (http://localhost:7474/browser/)

## build database

### load word

load csv from "file:///wn18rr/word.txt" as line create (:Word {value: line[0]});

load csv from "file:///wn18rr/id.txt" as line create (:Index {value: line[0]});

create index on :Word(value)

create index on :Index(value)

### load word-index relationship

load csv from "file:///wn18rr/word\_id\_pair.txt" as line fieldterminator "\t"

merge (w:Word {value : line[0]})

merge (i:Index {value : line[1]})

create (w)-[:ASSOCIATE\_WITH {name : '_associate_with'}]->(i)


### load ein-rel-eout 

using periodic commit 1000

load csv from "file:///wn18rr/all.txt" as line fieldterminator "\t"

merge (ein:Index {value : line[0]})

merge (eout:Index {value : line[2]})

create (ein)-[:POINT\_TO {name : line[1]}]->(eout)

## run 

export NEO4J\_PASSWORD="my-password"

export FLASK\_ENV=development

python wn.py

open a browser, and type http://localhost:8080/

