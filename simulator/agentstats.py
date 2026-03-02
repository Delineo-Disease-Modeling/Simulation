#graph implementation of agent tracking
#infectivity represented by number of children in the graph

import os
import csv
import math
import scipy.stats as st
import agent_tracker as agt

#Definition of Node class / linked list internal operations

class Node:
    def __init__(self, id: int, pid: int, parent):
        self.id = id
        self.pid = pid
        self.parent = parent
        self.fault = float(0.0)
        self.edges = []

    def addEdge(self, victim, location, time, fault):
        new = Edge(victim, location, time, fault)
        self.edges.append(new)

    def setFault(self, val):
        self.fault = val

    def searchByID(self, head, target: int):
        if (head):
            currentNode = head
            resultNode = head
            if resultNode == None:
                return None
            elif resultNode.id == target:
                return resultNode
            elif currentNode and (len(currentNode.edges) > 0):
                for n in currentNode.edges: 
                    resultNode = self.searchByID(n.victim, target)
                    if resultNode and resultNode.id == target:
                        return resultNode
        return None
    
    def printNodes(self, head):
        print("%d infected by %d at time %d ->" % (head.id, head.pid, head.time))
        for v in head.edges:
            self.printNodes(v.victim)
        return

#Definition of Edge class: stores victim as a node and location as an int

class Edge:
    def __init__(self, victim: Node, location: int, time: int, fault: float):
        self.victim = victim
        self.location = location    
        self.time = time
        self.fault = fault

#harmonic complexity analysis

def is_descendant(st: Node, dst: Node, len: int):
        #check if the current node is the target
        if (st.id == dst.id): 
            return len
        
        #check if any of this node's descendants lead to the target
        for v in st.edges:
            dfs = is_descendant(v.victim, dst, len + 1)
            if dfs != -1: 
                return dfs
            
        #we can't access the target from this node
        return -1

def dfs(st: Node, visited: set):
    visited.add(st)
    for v in st.edges:
        if v.victim not in visited:
            dfs(v.victim, visited)

def harmonic_complexity(st: Node, trgt: Node):
    count = float(0.0)

    #DFS to grab every node
    visited = set()
    dfs(st, visited)

    # test print to ensure dfs works (it works)
    # for item in visited:
    #     print(item.id, end = ' ')
    # print('\n')

    #find the harmonic complexity of the target
    for v in visited:
        if v.id != trgt.id: 
            dummy = is_descendant(trgt, v, 0)
            if dummy != -1:
                count += float(1 / dummy)

    #divide by normalizing constant
    nminus1 = len(visited) - 1
    count = float(count / nminus1)

    #update node's internal complexity then return
    trgt.setFault(count)
    return count

def normalize_all_harmonic(st: Node, visited: set):
    edge_total = float(0.0)
    node_total = float(0.0)

    #get the total weight of every node and every edge
    for trgt in visited:
        if trgt.id != -1:
            node_total += trgt.fault
            for e in trgt.edges:
                edge_total += e.fault

    #now that we have the total weights, normalize every node and edge
    for trgt in visited:
        if trgt.id != -1:
            trgt.fault *= (float(1.0) / node_total)
            for e in trgt.edges:
                e.fault *= (float(1.0) / edge_total)

    return 0

def calculate_all_harmonic(st: Node):
    visited = set()
    dfs(st, visited)

    #order every single location an infection occurred at by relative weight
    for trgt in visited:
        if trgt.id != -1:
            harmonic_complexity(st, trgt)
            cpx_total = float(0.0)
            for e in trgt.edges:
                cpx_total += harmonic_complexity(st, e.victim)
            for e in trgt.edges:
                if cpx_total > 0.0:
                    e.fault = (float(1 / (2 * len(trgt.edges))) + (((e.victim).fault / cpx_total) / 2)) * trgt.fault
                else:
                    e.fault = trgt.fault

    normalize_all_harmonic(st, visited)

    return 0

def check_sse(st: Node, report: list):
    visited = set()
    dfs(st, visited)

    #order every single node in the graph except start by harmonic complexity
    targets = list()
    for trgt in visited:
        if trgt.id != -1:
            pair = (trgt.id, trgt.fault)
            targets.append(pair)
    targets.sort(key=lambda x: x[1], reverse=True)

    #check if top (< 20%) of agents account for at least 50% of infections
    total_hc = float(0.0)
    total_elements = 0
    curr = 0
    top20 = float(0.2 * len(targets))
    while total_hc < 0.5:
        total_hc += targets[curr][1]
        curr += 1

    if curr < top20:
        report.append("Superspreader event detected! Potential superspreaders are: ")
        for i in range(0, curr + 1): 
            report.append(f"{targets[i][0]} ")
        report.append("\n")
        return True

    print("This run was not a superspreader event.\n")
    return False

def location_impact(st: Node, report: list):
    visited = set()
    dfs(st, visited)
    calculate_all_harmonic(st)

    #order every single location an infection occurred at by relative weight
    weighted_locs = list()
    for trgt in visited:
        if trgt.id != -1:
            for e in trgt.edges:
                if any(e.location == x[0] for x in weighted_locs):
                    for y in weighted_locs:
                        if e.location == y[0]:
                            y[1] += e.fault
                            break 
                else: 
                    pair = [e.location, e.fault]
                    weighted_locs.append(pair)
    weighted_locs.sort(key=lambda x: x[1], reverse=True)

    count = min(len(weighted_locs), 5)
    report.append(f"Top {count} locations by relative weight: ")
    for i in range(0, count):
        report.append(f"{weighted_locs[i][0]} ")
    report.append("\n")

    return 0

def time_weight_calc(st: Node): 
    visited = set()
    dfs(st, visited)
    calculate_all_harmonic(st)

    #order every single time an infection occurred at by relative weight
    weighted_times = list()
    for trgt in visited:
        if trgt.id != -1:
            for e in trgt.edges:
                if any(e.time == x[0] for x in weighted_times):
                    for y in weighted_times:
                        if e.time == y[0]:
                            y[1] += e.fault
                            break 
                else: 
                    pair = [e.time, e.fault]
                    weighted_times.append(pair)

    return weighted_times

def time_gates(st: Node, report: list):
    weighted_times = time_weight_calc(st)
    weighted_times.sort(key=lambda x: x[0], reverse=True)
    curr_fault = float(0.0)

    flag50 = False
    for i in range(0,len(weighted_times)):
        curr_fault += weighted_times[i][1]
        if curr_fault >= 0.5 and not flag50:
            report.append(f"50%% of the infection damage was done by time {i}\n")
            flag50 = True
        if curr_fault >= 0.8:
            report.append(f"80%% of the infection damage was done by time {i}\n")
            break
    
    return 0

def time_impact(st: Node, report: list):
    weighted_times = time_weight_calc(st)
    weighted_times.sort(key=lambda x: x[1], reverse=True)

    count = min(len(weighted_times), 5)
    report.append(f"Top {count} times by relative weight: ")
    for i in range(0, count):
        report.append(f"{weighted_times[i][0]} ")
    report.append("\n")

    return 0

#Construct graph, find the infectivity of one agent

def build_agent_graph_nodupes(start: Node, data_dir: str):
    with open(data_dir, mode="r") as ifile: 
        itable = csv.reader(ifile)
        for row in itable:
            if str(row[6]) != "infector_person_id":
                if str(row[6]) == "":
                    new_node = Node(int(row[1]), -1, start)
                    start.addEdge(new_node, int(row[11]), 0, 0)
                else:
                    infector = start.searchByID(start, int(row[6]))
                    infected = start.searchByID(start, int(row[1]))
                    if not infected:
                        new_node = Node(int(row[1]), int(row[6]), infector)
                        infector.addEdge(new_node, int(row[11]), int(row[0]), 0)
    return 0

def direct_infectivity(head: Node, target: int):
    count = 0
    target_node = head.searchByID(head, target)
    if target_node:
        for v in target_node.edges:
            count += 1
    return count

def total_infectivity_nodupes(head: Node, target_int: int): 
    count = 0
    target = head.searchByID(head, target_int)
    if not target:
        return 0
    count += direct_infectivity(head, target_int)
    if len(target.edges) > 0:
        for v in target.edges:
            vic = v.victim
            count += total_infectivity_nodupes(head, vic.id)
    return count

#Main

def main():
    return 1
    # code for testing stat analysis functions
    # start_flag = int(input("For testing graph features, type 0. For CI, type 1. For superspreader check, type 2.\n"))
    # if (start_flag == 0):
    #     testnum = int(input("Please select which test to run.\n"))
    #     if (testnum == 1):
    #         graph_test_1()
    #     elif (testnum == 2):
    #         graph_test_2()
    #     elif (testnum == 3):
    #         mean_var_test()
    #     else: 
    #        print("Not implemented!\n")
    # if (start_flag == 1):
    #     infectivity_ci_multi()
    # if (start_flag == 2):
    #     run_superspreader_check()
    # else:
    #     print("Not implemented!\n")
    # return 1
    
if __name__ == "__main__":
    main()