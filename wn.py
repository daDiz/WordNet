#!/usr/bin/env python
import os
from json import dumps
from flask import Flask, g, Response, request
import numpy as np
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
        rel_list = [ unicode("_also_see"), unicode("_derivationally_related_form"), unicode("_has_part"),\
                     unicode("_hypernym"), unicode("_instance_hypernym"), unicode("_member_meronym"),\
                     unicode("_member_of_domain_region"), unicode("_member_of_domain_usage"),\
                     unicode("_similar_to"), unicode("_synset_domain_topic_of"), unicode("_verb_group") ]

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
        elif mode == "jaccard index":
            #Response(dumps(["Quering now ..."]), mimetype="application/json")
            score = [];
            for rel in rel_list:
                result1 = [ item["words"] for item in \
                            db.run(
                                "MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                                "WHERE (w1.value=~ {v1}  AND r.name=~ {r1}) "
                                "RETURN w2.value AS words "
                                "UNION "
                                "MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                                "WHERE (w2.value=~ {v1} AND r.name=~ {r1}) "
                                "RETURN w1.value AS words", {"v1": "(?i)" + w1, "r1": "(?i)" + rel }
                            ) ];
                result2 = [ item["words"] for item in \
                            db.run(
                                "MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                                "WHERE (w1.value=~ {v2}  AND r.name=~ {r1}) "
                                "RETURN w2.value AS words "
                                "UNION "
                                "MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                                "WHERE (w2.value=~ {v2} AND r.name=~ {r1}) "
                                "RETURN w1.value AS words", {"v2": "(?i)" + w2, "r1": "(?i)" + rel }
                            ) ];
                NumIntersect = float(len( set(result1).intersection(set(result2)) ));
                NumUnion = float(len(set(result1+result2)));
                jaccard =  NumIntersect/NumUnion if NumUnion>0 else 0;
                score.append(jaccard)

            rel_out = rel_list[np.argmax( np.array(score) )]
            return Response(dumps([rel_out]), mimetype="application/json")

        elif mode == "friends measure":
            #Response(dumps(["Quering now ..."]), mimetype="application/json")
            score = [];
            for rel in rel_list:
                result1 = [ item["words"] for item in \
                            db.run(
                                "MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                                "WHERE (w1.value=~ {v1}  AND r.name=~ {r1}) "
                                "RETURN w2.value AS words "
                                "UNION "
                                "MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                                "WHERE (w2.value=~ {v1} AND r.name=~ {r1}) "
                                "RETURN w1.value AS words", {"v1": "(?i)" + w1, "r1": "(?i)" + rel }
                            ) ];
                result2 = [ item["words"] for item in \
                            db.run(
                                "MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                                "WHERE (w1.value=~ {v2}  AND r.name=~ {r1}) "
                                "RETURN w2.value AS words "
                                "UNION "
                                "MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                                "WHERE (w2.value=~ {v2} AND r.name=~ {r1}) "
                                "RETURN w1.value AS words", {"v2": "(?i)" + w2, "r1": "(?i)" + rel }
                            ) ];

                all_pair = [(x,y) for x in result1 for y in result2];
                result = db.run("MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                                 "WHERE (r.name=~ {r1}) "
                                 "RETURN w1.value, w2.value", {"r1": "(?i)" + rel } )
                result = [ item for item in result ];
                result = [ (item["w1.value"], item["w2.value"]) for item in result ];
                score.append( np.array( [ 1 if (( pair in result )|( pair[::-1] in result )) else 0 for pair in all_pair] ).sum() )
            rel_out = rel_list[np.argmax( np.array(score) )]
            return Response(dumps([rel_out]), mimetype="application/json")




if __name__ == '__main__':
    app.run(port=8080)
