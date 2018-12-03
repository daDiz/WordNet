#!/usr/bin/env python
import os
from json import dumps
from flask import Flask, g, Response, request
import numpy as np
from neo4j.v1 import GraphDatabase, basic_auth
import time

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
            start = time.time()
            results = db.run("MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                            "WHERE (w1.value =~ {v1} AND w2.value =~ {v2}) OR (w1.value =~ {v2} AND w2.value =~ {v1}) "
                            "RETURN DISTINCT r.name", {"v1": "(?i)" + w1, "v2": "(?i)" + w2})
            ser = [record['r.name'] for record in results]
            if not ser:
                end = time.time()
                return Response(dumps(['time: %.2f sec' % (end-start)]), mimetype="application/json")

            end = time.time()
            return Response(dumps([ser, 'time: %.2f sec' % (end-start)]), mimetype="application/json")

        elif mode == "max single":
            start = time.time()
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
                end = time.time()
                return Response(dumps([record['r.name'] for record in ser1]+['time: %.2f sec' % (end-start)]), mimetype="application/json")
            else:
                end = time.time()
                return Response(dumps([record['r.name'] for record in ser2]+['time: %.2f sec' % (end-start)]), mimetype="application/json")
        elif mode == "preferential attachment":
            start = time.time()
            result1 = db.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(:Index) "
                              "WHERE w.value =~ {v} "
                              "RETURN r.name, COUNT(r.name) AS frequency ORDER BY frequency DESC ", {"v": "(?i)" + w1})
            result2 = db.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(:Index) "
                              "WHERE w.value =~ {v} "
                              "RETURN r.name, COUNT(r.name) AS frequency ORDER BY frequency DESC", {"v": "(?i)" + w2})

            ser1 = []
            ser2 = []
            for record in result1:
                ser1.append({"r.name": record["r.name"],
                             "frequency": record["frequency"]})
            for record in result2:
                ser2.append({"r.name": record["r.name"],
                             "frequency": record["frequency"]})

            same = {}
            #diff = {}
            for record1 in ser1:
                for record2 in ser2:
                    if record1["r.name"] == record2["r.name"]:
                        same[record1["r.name"]] = record1["frequency"]*record2["frequency"]

            if len(same) > 0: # if in and out have shared relations, find the one with a maximum product
                maxi_same = 0
                for name, freq in same.items():
                    if freq > maxi_same:
                        maxi_same = freq
                        rel_same = name
                end = time.time()
                return Response(dumps([rel_same]+['time: %.2f sec' % (end-start)]), mimetype="application/json")

            else: # if they do not have common relation, pick one from any of them that has the highest frequency
                #for record1 in ser1:
                #    diff[record1["r.name"]] = record1["frequency"]
                #for record2 in ser2:
                #    diff[record2["r.name"]] = record2["frequency"]
                #maxi_diff = 0
                #for name, freq in diff.items():
                #    if freq > maxi_diff:
                #        maxi_diff = freq
                #        rel_diff = name

                maxi_diff = -1
                rel_diff = []
                for record in ser1:
                    fr = record["frequency"]
                    if fr > maxi_diff:
                        maxi_diff = fr
                        rel_diff = record["r.name"]

                for record in ser2:
                    fr = record["frequency"]
                    if fr > maxi_diff:
                        maxi_diff = fr
                        rel_diff = record["r.name"]

                if not rel_diff:
                    return Response(dumps([]), mimetype="application/json")
                end = time.time()
                return Response(dumps([rel_diff]+['time: %.2f sec' % (end-start)]), mimetype="application/json")


        elif mode == "jaccard index":
            start = time.time()
            result1 = db.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(idx:Index) "
                             "WHERE w.value =~ {v} "
                             "RETURN r.name, COLLECT(idx.value) AS ind", {"v": "(?i)" + w1})

            result2 = db.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(idx:Index) "
                             "WHERE w.value =~ {v} "
                             "RETURN r.name, COLLECT(idx.value) AS ind", {"v": "(?i)" + w2})

            ser1 = []
            ser2 = []
            for record in result1:
                ser1.append({"r.name": record["r.name"],
                             "ind": record["ind"]})
            for record in result2:
                ser2.append({"r.name": record["r.name"],
                             "ind": record["ind"]})


            x = {}
            y = {}
            for record in ser1:
                x[record["r.name"]] = record["ind"]

            for record in ser2:
                y[record["r.name"]] = record["ind"]

            xk = x.keys()
            yk = y.keys()
            zk = list(set(xk) | set(yk))

            max_name = None
            max_score = -1.0
            for k in zk:
                x_ = x.get(k)
                y_ = y.get(k)
                if x_ == None:
                    x_ = []
                if y_ == None:
                    y_ = []
                zu = float(len(list(set(x_) | set(y_))))
                zi = float(len(list(set(x_) & set(y_))))
                score = zi / zu
                if score > max_score:
                    max_name = k
                    max_score = score
            end = time.time()
            return Response(dumps([max_name]+['time: %.2f sec' % (end-start)]), mimetype="application/json")

        elif mode == "friends measure":
            start = time.time()
            results = db.run("MATCH (w1:Word)-[:ASSOCIATE_WITH]->(left1:Index)-[r1:POINT_TO]-(left2:Index)-[r2:POINT_TO]-(right2:Index)-[r3:POINT_TO]-(right1:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                             "WHERE w1.value=~{v1} AND w2.value=~{v2} "
                             "WITH [left2.value, right2.value] AS pair, r2.name AS name "
                             "RETURN name, COUNT(pair) AS frequency ORDER BY frequency DESC", {"v1": "(?i)" + w1, "v2": "(?i)" + w2})

            ser = []
            for record in results:
                ser.append({"name": record["name"], "frequency": record["frequency"]})

            if not ser:
                select = np.random.choice(rel_list, 1)[0]
                end = time.time()
                return Response(dumps([select]+['time: %.2f sec' % (end-start)]), mimetype="application/json")

            end = time.time()
            return Response(dumps([ser[0]["name"]]+['time: %.2f sec' % (end-start)]), mimetype="application/json")

"""
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
"""



if __name__ == '__main__':
    app.run(port=8080)
