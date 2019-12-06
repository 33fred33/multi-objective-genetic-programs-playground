#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Nov 28 10:52:52 2019

@author: 33fred33


Especifications:

GP structure:
    - Initial population is obtained and evaluated
    - The amount of mutations and crossovers to happen at each generation is established according to the population size
    - Generation structure:
        Offsprings are calculated using crossover and mutation only
        Parents and offsprings are evaluated together
        The best ones stay in the next generation's population

Tournament selection of size n: n individuals are uniformly randomly picked from the population. The best one is returned

"""

import math
import random as rd
import time
import numpy as np
import matplotlib.pyplot as plt
import pylab as py
from collections import defaultdict
import datetime
import os
import errno
import csv

class IndividualClass:
    def __init__(self, fenotype, objective_values = None):
        self.fenotype = fenotype
        self.evaluation = []
        self.objective_values = objective_values
        
    def __lt__(self, other): #less than
        """
        Each evaluation value is the tiebreak for the previous one in the same individual
        """
        if isinstance(self.evaluation, list):
            for eval_ind in range(len(self.evaluation)):
                if self.evaluation[eval_ind] > other.evaluation[eval_ind]:
                    return False
                if self.evaluation[eval_ind] < other.evaluation[eval_ind]:
                    return True
        else:
            return self.evaluation < other.evaluation
    
    def __eq__(self, other):
        if isinstance(self.evaluation, list):
            for eval_ind in range(len(self.evaluation)):
                if self.evaluation[eval_ind] != other.evaluation[eval_ind]:
                    return False
            return True
        else:
            return self.evaluation == other.evaluation
    
    def __str__(self):
        return "Fenotype: " + str(self.fenotype) + " Evaluations: " + str(self.evaluation)

class GeneticProgramClass:
    def __init__(
            self,
            population_size,
            generations,
            Model,
            objective_functions,
            objective_functions_arguments = None, #[[f1_arg1, ..., f1_argn], [f2_arg1, ..., f2_argn], ..., [fn_arg1, ..., fn_argn]]
            multiobjective_fitness = "SPEA2",
            sampling_method="tournament",
            mutation_ratio=0.4,
            tournament_size=2,
            experiment_name = None):
        """
        Positional arguments:
            population_size
            generations
            Model: class containing the methods:
                generate_individual(n): initialises n random individuals
                mutate(individual): returns the mutated the individual
                crossover(individual1, individual2): returns the crossover offspring individual from the given individuals
            objective_functions: expects an array of functions with the following characteristics:
                Positional arguments:
                    y: labels or classes to be achieved
                    y_predicted: a list of results to be compared with
                    Returns a single float
        Keyword arguments:
            objective_functions_arguments: list of list as: [[f1_arg1, ..., f1_argn], [f2_arg1, ..., f2_argn], ..., [fn_arg1, ..., fn_argn]]
            multiobjective_fitness: can be SPEA2 or NSGA2. Default is SPEA2
            sampling_method: can be tournament / weighted_random / random. Default is tournament
            mutation_ratio is the ratio of the next generation non-elite population to be filled with mutation-generated individuals
            tournament_size only used if sampling method is tournament. Best out from randomly selected individuals will be selected for sampling. Default is 2
            experiment_name is a string, used to create a new folder to store the outputs
        """  
        
        #Positional arguments variables assignment
        self.population_size = population_size
        self.generations = generations
        self.Model = Model
        if not isinstance(objective_functions, list):
            objective_functions = [objective_functions]
        self.objective_functions = objective_functions

        #Keyword arguments variables assignment
        if objective_functions_arguments is None:
            self.objective_functions_arguments = [[] for _ in range(len(self.objective_functions))]
        else:
            self.objective_functions_arguments = objective_functions_arguments
        self.multiobjective_fitness = multiobjective_fitness
        self.sampling_method = sampling_method
        self.mutation_ratio = mutation_ratio
        self.tournament_size = tournament_size
        if experiment_name is None:
            now = datetime.datetime.now()
            self.experiment_name = str(now.year) + "-" + str(now.month) + "-" + str(now.day) + "-" + str(now.hour) + "-" + str(now.minute)
        else:
            self.experiment_name = experiment_name
        
        #General variables initialisation
        self.logs_level = 0
        self.objectives = len(self.objective_functions)
        self.darwin_champion = None
        self.population = []
        self.x_train = []
        self.y_train = []
        self.x_test = []
        self.y_test = []
        self.logs = {}
        self.ran_generations = 0
        
    def fit(self
        , x_train
        , y_train
        ):
        """
        Positional arguments:
            x_train
            y_train
        Keyword arguments:
            fitness_method can be MSE, SPEA2, NSGA2
        """  
        #variables assignment
        self.x_train = x_train
        self.y_train = y_train
        self.ran_generations = 0
        
        #Initial population initialisation
        start_time = time.time()
        self.population = [IndividualClass(individual) for individual in self.Model.generate_population(self.population_size)]
        self._evaluate_population()
        self.population = sorted(self.population)

        self.logs_checkpoint(time.time() - start_time)

        if self.logs_level > 1:
            for i,ind in enumerate(self.population):
                print("\n ", str(i), "th individual's evaluation = ", ind.evaluation)
            input("wait!")
        
        #amounts of each population type and procedence     
        mutations = math.ceil(self.population_size * self.mutation_ratio)
        crossovers = self.population_size - mutations
        
        if self.logs_level >= 1:
            print("population_size: ", self.population_size)
            print("mutations per gen: ", mutations)
            print("crossovers per gen: ", crossovers)
            
        for generation in range(1,self.generations):
            self.ran_generations = generation
            
            start_time = time.time()
            if self.logs_level >= 1:
                print("Generation: ", generation)
                
            #Parents selection
            if self.sampling_method == "tournament":    
                selected_first_parents = self._tournament_selection(self.population, crossovers)
                selected_second_parents = self._tournament_selection(self.population, crossovers)
                selected_mutations = self._tournament_selection(self.population, mutations) 
            elif self.sampling_method == "weighted_random":
                selected_first_parents = self._weighted_random_sample(self.population, crossovers)
                selected_second_parents = self._weighted_random_sample(self.population, crossovers)
                selected_mutations = self._weighted_random_sample(self.population, mutations)
            else:
                selected_first_parents = rd.choices(self.population, k = crossovers)
                selected_second_parents = rd.choices(self.population,  k = crossovers)
                selected_mutations = rd.choices(self.population,  k = mutations)
            
            #increase population
            self.population.extend([IndividualClass(self.Model.mutate(individual.fenotype)) for individual in selected_mutations])
            self.population.extend([IndividualClass(self.Model.crossover(selected_first_parents[i].fenotype, selected_second_parents[i].fenotype)) for i in range(crossovers)])
            
            #evaluate population
            self._evaluate_population()
            
            #select next generation's population
            self.population = sorted(self.population)[:self.population_size]

            self.logs_checkpoint(time.time() - start_time)
            
            print("Generation ", generation, " time: ", str(time.time() - start_time))
            print("Darwin champion evaluations: ", self.population[0].evaluation)
            print("Darwin champion: ", self.population[0].fenotype)
            if self.logs_level >= 1:
                print("Darwin champion: ", self.population[0].fenotype)
                #print("Best individual so far: ", self.population[0].fenotype)
                if self.logs_level >= 2: 
                    for i,ind in enumerate(self.population):
                        print("\n ", str(i), "th individual's evaluation = ", ind.evaluation)
                    input("wait!") 
        
        #final individual selection
        self.darwin_champion = self.population[0].fenotype
        
        return self.darwin_champion

    def predict(self, x):
        prediction = self.Model.evaluate(self.darwin_champion, x)
        return prediction
    
    def _evaluate_population(self, x = None, y = None):
        if x is None:
            x = self.x_train
        if y is None:
            y = self.y_train



        for ind_idx, individual in enumerate(self.population):
            if individual.objective_values is None:
                prediction = self.Model.evaluate(individual.fenotype, x)
                individual.objective_values = [objective_function(y, prediction, *self.objective_functions_arguments[obj_idx]) 
                    for obj_idx, objective_function 
                    in enumerate(self.objective_functions)]

        """
        objective_values = []
        predictions = [self.Model.evaluate(individual.fenotype, x) for individual in self.population]
        for obj_idx, objective_function in enumerate(self.objective_functions):
            objective_values.append([objective_function(y, y_predicted, *self.objective_functions_arguments[obj_idx]) for y_predicted in predictions])
        """

        if self.objectives == 1:
            for ind_idx, individual in enumerate(self.population):
                #individual.evaluation = [objective_values[0][ind_idx]]
                individual.evaluation = individual.objective_values[0]
        else:
            if self.multiobjective_fitness == "SPEA2":
                #[print(idx, individual.objective_values) for idx, individual in enumerate(self.population)]
                objective_values = [[individual.objective_values[obj_idx] for individual in self.population] for obj_idx in range(self.objectives)] #added
                evaluations = self._spea2(objective_values)

                for ind_idx, individual in enumerate(self.population):
                    individual.evaluation = [evaluations[ind_idx]]

                title = "Gen " + str(self.ran_generations)
                colored_plot(objective_values[0], 
                                  objective_values[1], 
                                  evaluations, 
                                  title = title, 
                                  colormap = "cool", 
                                  markers = evaluations,
                                  marker_size = 200,
                                  save = True,
                                  path = self.experiment_name)
        

            elif self.multiobjective_fitness == "NSGA2":
                pass

            crowding_distances = self._crowding_distance(objective_values)
            for ind_idx, individual in enumerate(self.population):
                individual.evaluation.append(crowding_distances[ind_idx])
        """ 
        print("y: ", y[5])
        print("x: ", x[5])
        print("func: ", self.population[20].fenotype)
        print("y_pred: ", predictions[20][5])
        print("obj1: ", objective_values[0][20])
        print("obj2: ", objective_values[1][20])
        print("spea2: ", evaluations[20])
        print("cd: ", crowding_distances[20])
        print("evals: ", self.population[20].evaluation)
        """

    def _crowding_distance(self, objective_values):
        """
        Positional arguments:
            objective_values is a list of lists, with ordered values for each objective to be considered
        Returns: a list of values with a crowding distance as a float
        """
        items = list(zip(*objective_values, list(range(len(objective_values[0])))))
        distances = defaultdict(list)
        for objective_idx in range(len(objective_values)):
            items.sort(key=lambda item: item[objective_idx])
            distances[items[0][-1]].append(-np.inf)
            distances[items[-1][-1]].append(-np.inf)
            for i in range(1, len(items) - 1):
                distances[items[i][-1]].append(items[i + 1][objective_idx] - items[i - 1][objective_idx])
        indexes_mean_distances = [(item_index, sum(ds) / len(objective_values)) for item_index, ds in distances.items()]
        indexes_mean_distances.sort(key=lambda t: t[0])
        crowding_distances = [d for i, d in indexes_mean_distances]
        max_cd = max(crowding_distances)
        inverted_crowding_distances = [max_cd - cd for cd in crowding_distances]
        return inverted_crowding_distances

    def _spea2(self, objective_values):

        #strengths calculation
        individuals = len(objective_values[0])
        strengths = []
        for ind_idx in range(individuals):
            dominated_solutions = 0
            for comparison_ind_idx in range(individuals):
                dominated = True
                for obj_idx in range(self.objectives):
                    if objective_values[obj_idx][ind_idx] < objective_values[obj_idx][comparison_ind_idx]:
                        dominated = False
                        break
                if dominated:
                    dominated_solutions += 1   
            strengths.append(dominated_solutions - 1)

        #strengths sum
        evaluations = []
        for ind_idx in range(individuals):
            total_strengths = 0
            for comparison_ind_idx in range(individuals):
                dominates_me = True
                for obj_idx in range(self.objectives):
                    if objective_values[obj_idx][ind_idx] >= objective_values[obj_idx][comparison_ind_idx]:
                        dominates_me = False
                        break
                if dominates_me:
                    total_strengths += strengths[comparison_ind_idx]
            evaluations.append(total_strengths)

        return evaluations
    
    def _weighted_random_sample(self, parent_population, amount, probabilities = None):
        """
        returns randomly selected individuals 
        """
        sorted_population = sorted(parent_population)
        if probabilities is None:
            total_proportion = len(sorted_population)
            probabilities = []
            for i in range(total_proportion):
                probability = (total_proportion-i)/total_proportion
                probabilities.append(probability)
        sample = rd.choices(sorted_population, weights = probabilities, k = amount)
        return sample
    
    def _tournament_selection(self, parent_population, amount):
        selection = []
        for i in range(amount):
            competitors = rd.choices(parent_population, k = self.tournament_size)
            winner = sorted(competitors)[0]
            selection.append(winner)               
        return selection

    def logs_checkpoint(self, gen_time):
        for ind_idx, individual in enumerate(self.population):
            self.logs[(self.ran_generations,ind_idx,"fenotype")] = str(individual.fenotype)
            self.logs[(self.ran_generations,ind_idx,"depth")] = individual.fenotype.my_depth()
            self.logs[(self.ran_generations,ind_idx,"nodes")] = individual.fenotype.nodes_count()
            self.logs[(self.ran_generations,ind_idx,"evaluation")] = individual.evaluation
            #self.logs[(self.ran_generations, "time")] = gen_time
            logs_to_file(self.logs, self.experiment_name)
    
    def __str__(self):
        return str(self.__dict__)

def verify_path(tpath):
    if tpath is None:
        return ""
    else:
        if tpath[-1] != "/":
            tpath = "outputs/" + tpath + "/"

        if not os.path.exists(os.path.dirname(tpath)):
            try:
                os.makedirs(os.path.dirname(tpath))
            except OSError as exc: # Guard against race condition
                if exc.errno != errno.EEXIST:
                    raise
        return tpath

def logs_to_file(logs, path):
    """
    logs is a dictionary
    """
    path = verify_path(path)
    with open(path + "logs.csv", mode='w') as logs_file:
        logs_writer = csv.writer(logs_file, delimiter=',')
        logs_writer.writerow(['generation', 'individual_index', 'name', 'value'])
        for key, value in logs.items():
            logs_writer.writerow([str(key[0]), str(key[1]), key[2], str(value)])


def colored_plot(x, y, values, title = "default_title", colormap = "cool", markers = None, marker_size = 50, save = False, path = None):
        path = verify_path(path)
        f = plt.figure()   
        f, axes = plt.subplots(nrows = 1, ncols = 1, sharex=True, sharey = True, figsize=(10,10))
        """points are x, y pairs, values are used for graduated coloring"""
        max_value = max(values)
        min_value = min(values)
        colors = [(1 - (value - min_value)) / (max_value - min_value + 0.001) for value in values]
        if markers is None:
            plt.scatter(x, y, 
                        c = colors, 
                        cmap = colormap, 
                        alpha = 0.6)
        else:
            markers = [str(marker) for marker in markers]
            data = [[x[i], y[i], markers[i]] for i in range(len(x))]
            for i, d in enumerate(data):
                py.scatter(d[0], d[1], 
                            marker = r"$ {} $".format(d[2]),
                            s = marker_size,
                            edgecolors='none',
                            #c = colors[i], 
                            cmap = colormap, 
                            alpha = 0.9)
        plt.title(title)
        plt.xlabel("Objective 1: Accuracy in majority class")
        plt.ylabel("Objective 2: Accuracy in minority class")
        plt.grid()
        
        if save:
            name = path + title + ".png"
            plt.savefig(name)
        #plt.show()
        #plt.ioff()
    
    