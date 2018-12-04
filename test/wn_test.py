#!/usr/bin/env python
import os
from json import dumps
from flask import Flask, g, Response, request
import numpy as np
from neo4j.v1 import GraphDatabase, basic_auth
import time


password = os.getenv("NEO4J_PASSWORD")

driver = GraphDatabase.driver('bolt://localhost',auth=basic_auth("neo4j", password))


def read_test_data(file_name):
    data = np.loadtxt(file_name, dtype=str, delimiter='\t')
    return data

def search_default(tx, w1, w2, query_result):
    results = tx.run("MATCH (w1:Word)-[:ASSOCIATE_WITH]->(ein:Index)-[r:POINT_TO]->(eout:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                    "WHERE (w1.value =~ {v1} AND w2.value =~ {v2}) OR (w1.value =~ {v2} AND w2.value =~ {v1}) "
                    "RETURN DISTINCT r.name", {"v1": "(?i)" + w1, "v2": "(?i)" + w2})

    ser = [str(record['r.name']) for record in results]

    #if len(ser) > 1:
        #raise Exception("Error: result not unique")
        #print(ser)

    #if len(ser) == 0:
    #    raise Exception("Error: no result")

    query_result.append(ser)



def search_max_single(tx, w1, w2, query_result):
    result1 = tx.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(:Index) "
                    "WHERE w.value =~ {v} "
                    "RETURN r.name, COUNT(r.name) AS frequency ORDER BY frequency DESC", {"v": "(?i)" + w1})
    result2 = tx.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(:Index) "
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

    if ser1[0]["frequency"] >= ser2[0]["frequency"]:
        max_freq = ser1[0]["frequency"]
        query_result.append([str(record['r.name']) for record in ser1 if record['frequency'] == max_freq])
    else:
        max_freq = ser2[0]["frequency"]
        query_result.append([str(record['r.name']) for record in ser2 if record['frequency'] == max_freq])


def search_preferential_attachment(tx, w1, w2, query_result):
    result1 = tx.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(:Index) "
                    "WHERE w.value =~ {v} "
                    "RETURN r.name, COUNT(r.name) AS frequency ORDER BY frequency DESC ", {"v": "(?i)" + w1})
    result2 = tx.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(:Index) "
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
        return query_result.append([str(rel_same)])

    else: # if they do not have common relation, pick one from any of them that has the highest frequency
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
            return query_result.append([])

        return query_result.append([str(rel_diff)])

def search_jaccard_index(tx, w1, w2, query_result):
    result1 = tx.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(idx:Index) "
                    "WHERE w.value =~ {v} "
                    "RETURN r.name, COLLECT(idx.value) AS ind", {"v": "(?i)" + w1})

    result2 = tx.run("MATCH (w:Word)-[:ASSOCIATE_WITH]->(:Index)-[r:POINT_TO]-(idx:Index) "
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
            max_name = [str(k)]
            max_score = score
        elif score == max_score:
            max_name.append(str(k))

    return query_result.append(max_name)



def search_friends_measure(tx, w1, w2, query_result):
    results = tx.run("MATCH (w1:Word)-[:ASSOCIATE_WITH]->(left1:Index)-[r1:POINT_TO]-(left2:Index)-[r2:POINT_TO]-(right2:Index)-[r3:POINT_TO]-(right1:Index)<-[:ASSOCIATE_WITH]-(w2:Word) "
                    "WHERE w1.value=~{v1} AND w2.value=~{v2} "
                    "WITH [left2.value, right2.value] AS pair, r2.name AS name "
                    "RETURN name, COUNT(pair) AS frequency ORDER BY frequency DESC", {"v1": "(?i)" + w1, "v2": "(?i)" + w2})

    ser = []
    for record in results:
        ser.append({"name": record["name"], "frequency": record["frequency"]})

    if not ser:
        rel_list = ["_also_see", "_derivationally_related_form", "_has_part",\
                    "_hypernym", "_instance_hypernym", "_member_meronym",\
                    "_member_of_domain_region", "_member_of_domain_usage",\
                    "_similar_to", "_synset_domain_topic_of", "_verb_group"]

        select = np.random.choice(rel_list, 1)[0]
        return query_result.append([select])

    return query_result.append([str(record["name"]) for record in ser if record["frequency"] == ser[0]["frequency"]])



def run_test(driver, mode, search_method, data_file):
    data = read_test_data(data_file)
    query_result = []
    true_result = []
    t1 = time.time()
    with driver.session() as session:
        for i in range(len(data)):
            true_result.append(data[i][1])
            session.read_transaction(search_method, data[i][0], data[i][2], query_result)

    t2 = time.time()
    acc = 0
    n = len(true_result)
    for i in range(n):
        rel = true_result[i]
        if rel in query_result[i]:
            acc += 1

    print("-----------------------")
    #print(query_result)
    #print(true_result)
    print("%s: %s out of %s correct, acc = %.3f" % (mode, acc, n, float(acc) / float(n)))
    print("%s: ave query time = %.3f\n" % (mode, (t2-t1)/float(n)))

if __name__ == '__main__':
    run_test(driver, 'max_single', search_max_single, '../data/wn18rr/test.txt')
    run_test(driver, 'preferential_attachment', search_preferential_attachment, '../data/wn18rr/test.txt')
    run_test(driver, 'jaccard_index', search_jaccard_index, '../data/wn18rr/test.txt')
    run_test(driver, 'friends_measure', search_friends_measure, '../data/wn18rr/test.txt')

