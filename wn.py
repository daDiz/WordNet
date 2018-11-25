#!/usr/bin/env python
import os
from json import dumps
from flask import Flask, g, Response, request

from neo4j.v1 import GraphDatabase, basic_auth

app = Flask(__name__, static_url_path='/static/')

#app = Flask(__name__)

password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver('bolt://localhost',auth=basic_auth("neo4j", password))

def get_db():
    if not hasattr(g, 'neo4j_db'):
        g.neo4j_db = driver.session()
    return g.neo4j_db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'neo4j_db'):
        g.neo4j_db.close()

@app.route("/")
def get_index():
    return app.send_static_file('index.html')

@app.route("/about")
def get_about():
    return app.send_static_file('about.html')

@app.route("/search")
def get_search():
    try:
        w1 = request.args["w1"]
        w2 = request.args["w2"]
        mode = request.args["mode"]
    except KeyError:
        return []
    else:
        db = get_db()
        if mode == "default":
            results = db.run("MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                            "WHERE (w1.value =~ {v1} AND w2.value =~ {v2}) OR (w1.value =~ {v2} AND w2.value =~ {v1}) "
                            "RETURN DISTINCT r.name", {"v1": "(?i)" + w1, "v2": "(?i)" + w2})
            return Response(dumps([record['r.name'] for record in results]), mimetype="application/json")

        elif mode == "max single":
            result1 = db.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(:Index) "
                              "WHERE w.value =~ {v} "
                              "RETURN r.name, COUNT(r.name) AS frequency ORDER BY frequency DESC LIMIT 1", {"v": "(?i)" + w1})
            result2 = db.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(:Index) "
                              "WHERE w.value =~ {v} "
                              "RETURN r.name, COUNT(r.name) AS frequency ORDER BY frequency DESC LIMIT 1", {"v": "(?i)" + w2})
            ser1 = []
            ser2 = []
            for record in result1:
                ser1.append({"r.name": record["r.name"],
                             "frequency": record["frequency"]})
            for record in result2:
                ser2.append({"r.name": record["r.name"],
                             "frequency": record["frequency"]})

            if ser1[0]["frequency"] >= ser2[0]["frequency"]:
                return Response(dumps([record['r.name'] for record in ser1]), mimetype="application/json")
            else:
                return Response(dumps([record['r.name'] for record in ser2]), mimetype="application/json")



if __name__ == '__main__':
    app.run(port=8080)
