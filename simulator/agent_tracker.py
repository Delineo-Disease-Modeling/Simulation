#agent tracker
#using the CSV files output by ai-counterfactual-analysis,
#generates "audits" for individual people or locations

import os
import csv
import math
import scipy.stats as st

def find_dir(run: int):
    run_name = "run"
    run_name += str(run)
    data_dir = os.getcwd() + "/data/raw/" + run_name
    return data_dir

def agent_track(data_dir: str):
    output_file = open(os.path.join(data_dir, "agent_track_output.txt"), "w")
    track_id = int(input("Please enter the ID of the agent you want to track (int).\n"))
    timestamp = 0
    total_movements = 0
    total_infections = 0
    total_catches = 0
    output_file.write("Tracking of agent " + str(track_id) + "\n")
    while (timestamp <= 1440):
        moved_flag = 0
        infected_flag = 0
        victim_flag = 0
        with open(os.path.join(data_dir, "movement_logs.csv"), mode="r") as move_file:
            move_table = csv.reader(move_file)
            for row in move_table:
                if str(row[0]) == str(timestamp) and str(row[1]) == str(track_id):
                    total_movements += 1
                    moved_flag = 1
                    move_str = "At time " + str(timestamp) + ", your agent moved from "
                    move_str += str(row[3]) + " " + str(row[2]) + " to "
                    move_str += str(row[5]) + " " + str(row[4]) + ".\n"
                    output_file.write(move_str)
            if moved_flag == 0: 
                move_str = "Your agent didn't move at time " + str(timestamp) + ".\n"
                output_file.write(move_str)
        with open(os.path.join(data_dir, "infection_logs.csv"), mode="r") as infect_file:
            infect_table = csv.reader(infect_file)
            for row in infect_table: 
                if str(row[0]) == str(timestamp) and str(row[6]) == str(track_id):
                    total_infections += 1
                    infected_flag = 1
                    infect_str = "At time " + str(timestamp) + ", your agent infected agent "
                    infect_str += str(row[1]) + " with disease " + str(row[15]) + ".\n"
                    output_file.write(infect_str)
                if str(row[0]) == str(timestamp) and str(row[1]) == str(track_id):
                    total_catches += 1
                    victim_flag = 1
                    victim_str = "At time " + str(timestamp) + ", your agent was infected "
                    victim_str += "with " + str(row[15])
                    if timestamp == 0:
                        victim_str += " at the start of the experiment.\n"
                    else: 
                        victim_str += " by agent " + str(row[6]) + ".\n"
                    output_file.write(victim_str)
            if infected_flag == 0: 
                infect_str = "Your agent didn't infect anyone at time " + str(timestamp) + ".\n"
                output_file.write(infect_str)
            if victim_flag == 0:
                victim_str = "Your agent did not catch any new diseases at time " + str(timestamp) + ".\n"
                output_file.write(victim_str)
        timestamp += 60
    last_str = "In total, your agent moved " + str(total_movements) + " time(s),\n"
    last_str += "directly infected " + str(total_infections) + " person(s),\n"
    last_str += "and caught " + str(total_catches) + " disease(s)."
    output_file.write(last_str)
    output_file.close()
    return 0

def location_track(data_dir: str):
    output_file = open(os.path.join(data_dir, "location_track_output.txt"), "w")
    track_id = int(input("Please enter the ID of the location you want to track (int).\n"))
    timestamp = 0
    total_visits = 0
    total_exits = 0
    total_infections = 0
    intro_write_flag = 0
    with open(os.path.join(data_dir, "location_logs.csv"), mode="r") as intro_file: 
        intro_table = csv.reader(intro_file)
        for row in intro_table:
            if intro_write_flag == 0 and str(row[1]) == str(track_id): 
                output_file.write("Tracking of " + str(row[2]) + " " + str(row[1]) + "\n")
                intro_write_flag = 1
    while (timestamp <= 1440):
        visit_flag = 0
        exit_flag = 0
        catch_flag = 0
        with open(os.path.join(data_dir, "movement_logs.csv"), mode="r") as move_file:
            move_table = csv.reader(move_file)
            for row in move_table:
                if str(row[0]) == str(timestamp) and str(row[4]) == str(track_id):
                    total_visits += 1
                    visit_flag = 1
                    move_str = "At time " + str(timestamp) + ", agent "
                    move_str += str(row[1]) + " entered this location.\n"
                    output_file.write(move_str)
                if str(row[0]) == str(timestamp) and str(row[2]) == str(track_id): 
                    total_exits += 1
                    exit_flag = 1
                    move_str = "At time " + str(timestamp) + ", agent "
                    move_str += str(row[1]) + " exited this location.\n"
                    output_file.write(move_str)
            if visit_flag == 0: 
                move_str = "Nobody entered this location at time " + str(timestamp) + ".\n"
                output_file.write(move_str)
            if exit_flag == 0:
                move_str = "Nobody exited this location at time " + str(timestamp) + ".\n"
                output_file.write(move_str)
        with open(os.path.join(data_dir, "infection_logs.csv"), mode="r") as infect_file:
            infect_table = csv.reader(infect_file)
            for row in infect_table: 
                if str(row[0]) == str(timestamp) and str(row[11]) == str(track_id):
                    total_infections += 1
                    catch_flag = 1
                    infect_str = "At time " + str(timestamp) + ", agent " + str(row[6]) + " infected "
                    infect_str += str(row[1]) + " with disease " + str(row[15]) + "at your location.\n"
                    output_file.write(infect_str)
            if catch_flag == 0: 
                infect_str = "Your agent didn't infect anyone at time " + str(timestamp) + ".\n"
                output_file.write(infect_str)
        timestamp += 60
    last_str = "In total, agents went to this location " + str(total_visits) + " time(s),\n"
    last_str += "left the location " + str(total_exits) + " time(s),\n"
    last_str += "and got infected here " + str(total_infections) + " time(s)."
    output_file.write(last_str)
    output_file.close()
    return 0

def deadliest_agent(data_dir: str):
    deadliest_id = 0
    curr_max = 0
    deadliest_dict = dict({0: 0})
    with open(os.path.join(data_dir, "infection_logs.csv"), mode="r") as ifile: 
        itable = csv.reader(ifile)
        for row in itable:
            if str(row[6]) != "infector_person_id" and str(row[6]) != "":
                if deadliest_dict.get(row[6]) == None: 
                    deadliest_dict[row[6]] = 1
                else: 
                    deadliest_dict[row[6]] += 1
                if deadliest_dict[row[6]] > curr_max: 
                    deadliest_id = int(row[6])
                    curr_max = deadliest_dict[row[6]]

    print("The deadliest agent is the one with ID " + str(deadliest_id) + ".\n") 
    return 0

def deadliest_location(data_dir: str):
    deadliest_id = 0
    curr_max = 0
    deadliest_dict = dict({0: 0})
    with open(os.path.join(data_dir, "infection_logs.csv"), mode="r") as ifile: 
        itable = csv.reader(ifile)
        for row in itable:
            if str(row[11]) != "infection_location_id" and str(row[11]) != "":
                if deadliest_dict.get(row[11]) == None: 
                    deadliest_dict[row[11]] = 1
                else: 
                    deadliest_dict[row[11]] += 1
                if deadliest_dict[row[11]] > curr_max: 
                    deadliest_id = int(row[11])
                    curr_max = deadliest_dict[row[11]]

    print("The deadliest location is the one with ID " + str(deadliest_id) + ".\n") 
    return 0

def infectivity_ci(data_dir: str):
    #check to see if we want a multi-run ci
    multi_check = int(input("To perform the CI calculation with multiple runs, type 1. Otherwise, type 0.\n"))
    if (multi_check == 1):
        return infectivity_ci_multi()
    #get an alpha value
    alpha = float(input("Please type an OPPOSITE decimal from 0 to 1 representing the confidence (ex. for a 95 percent CI, type 0.05).\n"))
    #define the flags through which we will filter people
    flag_vals = []
    flag_vals.append(input("Please enter a minimum age to observe, as an integer. Type -1 if irrelevant.\n"))
    flag_vals.append(input("Please enter a maximum age to observe, as an integer. Type -1 if irrelevant.\n"))
    flag_vals.append(input("Please enter which sex to track as an integer, 0 for males, 1 otherwise. Type -1 if irrelevant.\n"))
    flag_vals.append(input("Please write Vaccinated or Unvaccinated (case-sensitive) to pick a vaccination status at start of run to track. Type -1 if irrelevant.\n"))
    #verify parameters 
    print("You have entered: alpha = %f, min age = %f, max age = %f, sex = %f, vaccination = %s" % (alpha, int(flag_vals[0]), int(flag_vals[1]), int(flag_vals[2]), flag_vals[3]))
    #grab all the people from all the runs who we will be analyzing 
    usable_ids = get_all_ids(data_dir, flag_vals)
    print("We found %s people who fit your criteria.\n" % len(usable_ids))
    if (len(usable_ids) == 0):
        print("Since we didn't find anyone, we can't run a CI. Returning.\n")
        return 0
    #calculate the ci proper
    zscore = st.norm.ppf(1.0 - (alpha / 2))
    print("z-table value given alpha = %f" % zscore)
    mean = infectivity_mean(data_dir, usable_ids)
    print("mean = %f" % mean)
    var = infectivity_var(data_dir, usable_ids, mean)
    print("variance = %f" % var)
    sd = math.sqrt(var)
    rootn = math.sqrt(len(usable_ids))
    hi = mean + (zscore * (sd / rootn))
    lo = mean - (zscore * (sd / rootn))
    print("Given the specified parameters, your CI is [%f,%f]" % (lo, hi))
    return 0

def infectivity_ci_multi():
    runcount = int(input("Please type how many runs you would like to analyze.\n"))
    runlist = []
    i = 0
    while (i < runcount):
        runlist.append(int(input("Please type ONE of the runs you are using. Runs input so far: %f\n" % i)))
        i += 1
    #get an alpha value
    alpha = float(input("Please type an OPPOSITE decimal from 0 to 1 representing the confidence (ex. for a 95 percent CI, type 0.05).\n"))
    zscore = st.norm.ppf(1.0 - (alpha / 2))
    #define the flags through which we will filter people
    flag_vals = []
    flag_vals.append(input("Please enter a minimum age to observe, as an integer. Type -1 if irrelevant.\n"))
    flag_vals.append(input("Please enter a maximum age to observe, as an integer. Type -1 if irrelevant.\n"))
    flag_vals.append(input("Please enter which sex to track as an integer, 0 for males, 1 otherwise. Type -1 if irrelevant.\n"))
    flag_vals.append(input("Please write Vaccinated or Unvaccinated (case-sensitive) to pick a vaccination status at start of run to track. Type -1 if irrelevant.\n"))
    #verify parameters 
    print("You have entered: alpha = %f, min age = %f, max age = %f, sex = %f, vaccination = %s" % (alpha, int(flag_vals[0]), int(flag_vals[1]), int(flag_vals[2]), flag_vals[3]))
    n = 0
    mean = float(0)
    var = float(0)
    #get the sample count and mean
    for run in runlist: 
        data_dir = find_dir(run)
        usable_ids = get_all_ids(data_dir, flag_vals)
        n += len(usable_ids)
        if (len(usable_ids) > 0):
            mean += (infectivity_mean(data_dir, usable_ids) * len(usable_ids))
    if (n == 0):
        print("Since we didn't find anyone, we can't run a CI. Returning.\n")
        return 0
    mean = float(mean) / float(n)
    #now that we have our full sample mean, we can get the variance
    for run in runlist:
        data_dir = find_dir(run)
        usable_ids = get_all_ids(data_dir, flag_vals)
        if (len(usable_ids) > 0):
            var += (infectivity_var(data_dir, usable_ids, mean) * len(usable_ids))
    var = float(var) / float(n)
    sd = math.sqrt(var)
    rootn = math.sqrt(n)
    hi = mean + (zscore * (sd / rootn))
    lo = mean - (zscore * (sd / rootn))
    print("The distribution containing the specified persons has %d samples, mean %f, and variance %f." % (n, mean, var))
    print("Your a = %f CI is [%f,%f].\n" % (alpha, lo, hi))
    outlier_flag = int(input("Type 1 to check if a specific indivdual is an outlier and 0 otherwise.\n"))
    if (outlier_flag > 0):
        return outlier_check(mean, sd, n, alpha)
    return 0

def outlier_check(mean: float, sd: float, n: int, alpha: float):
    run = int(input("Please type the run your outlier is located in.\n"))
    person = int(input("Please type the ID of the person to analyze.\n"))
    benchmark = st.t.ppf(1 - (alpha / 2), n - 1)
    usable_ids = []
    usable_ids.append(person)
    data_dir = find_dir(run)
    #print("directory %s, usable_id %f\n" % (data_dir, usable_ids[0]))
    val = infectivity_mean(data_dir, usable_ids)
    #print("Your individual infected %f people.\n" % (val))
    test_stat = ((val - mean)/(sd / math.sqrt(n)))
    if (math.fabs(test_stat) > benchmark):
        print("Your individual has a statistically significant number of infections!\n")
    else:
        print("We have failed to find that your individual is a significant outlier.\n")
    print("The test statistic is %f relative to a benchmark of %f.\n" % (math.fabs(test_stat), benchmark))
    return 0

def check_person(row: list[str], flag_vals: list[str]):
    inspect = True
    if (int(flag_vals[0]) != -1) and (int(row[2]) < int(flag_vals[0])):
        #print("%f smaller than %f\n" % (int(row[2]), int(flag_vals[0])))
        inspect = False
    if (int(flag_vals[1]) != -1) and (int(row[2]) > int(flag_vals[1])):
        #print("%f larger than %f\n" % (int(row[2]), int(flag_vals[1])))
        inspect = False
    if (int(flag_vals[2]) != -1) and (int(row[3]) != int(flag_vals[2])):
        #print("%f different from %f\n" % (int(row[3]), int(flag_vals[2])))
        inspect = False
    if ((flag_vals[3] == "Vaccinated") or (flag_vals[3] == "Unvaccinated")) and (str(row[11]) != str(flag_vals[3])):
        #print("%s different from %s\n" % (str(row[11]), str(flag_vals[3])))
        inspect = False
    return inspect

def get_all_ids(data_dir: str, flag_vals: list[str]): 
    usable_ids = []
    with open(os.path.join(data_dir, "person_logs.csv"), mode="r") as person_file:
            person_table = csv.reader(person_file)
            for row in person_table:
                if((str(row[0]) != "timestep") and check_person(row, flag_vals)) and (row[1] not in usable_ids):
                    usable_ids.append(row[1])
    return usable_ids

def infectivity_mean(data_dir: str, usable_ids: list[int]):
    mean = float(0.0)
    num_people = len(usable_ids)
    with open(os.path.join(data_dir, "infection_logs.csv"), mode="r") as ifile: 
        itable = csv.reader(ifile)
        for row in itable:
            if (str(row[0]) != "timestep"):
                if (row[6] in usable_ids): 
                    mean += 1
    mean = float(mean) / float(num_people)
    return mean

def infectivity_var(data_dir: str, usable_ids: list[int], mean: float):
    var = float(0.0)
    curr_count = 0
    num_people = len(usable_ids)
    with open(os.path.join(data_dir, "infection_logs.csv"), mode="r") as ifile: 
        itable = csv.reader(ifile)
        for id in usable_ids:
            for row in itable:
                if (str(row[0]) != "timestep"):
                    if (row[6] == int(id)): 
                        curr_count += 1
            var += pow(float(float(curr_count) - mean),2)
            curr_count = 0
    var = float(var) / float(num_people)
    return var

def main():
    data_dir = find_dir(input("Please type what run you want to analyze (int).\n"))
    check_num = input("Please type 0 to track an agent or 1 to track a location.\n To find deadliest agent, type 2.\n To find deadliest location, type 3.\n To gather a confidence interval, press 4.\n")
    if int(check_num) == 0:
        agent_track(data_dir)
    if int(check_num) == 1:
        location_track(data_dir)
    if int(check_num) == 2:
        deadliest_agent(data_dir)
    if int(check_num) == 3:
        deadliest_location(data_dir)
    if int (check_num) == 4:
        infectivity_ci(data_dir)
    if int(check_num) > 4:
        print("Invalid number!\n")
    
    

if __name__ == "__main__":
    main()