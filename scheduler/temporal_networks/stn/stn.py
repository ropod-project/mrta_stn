import networkx as nx
from scheduler.temporal_networks.stn import Node
from json import JSONEncoder
from networkx.readwrite import json_graph
import json


class MyEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__


class STN(nx.DiGraph):
    """ Represents a Simple Temporal Network (STN) as a networkx directed graph
    """
    def __init__(self):
        super().__init__()
        self.add_zero_timepoint()

    def __str__(self):
        to_print = ""
        for (i, j, data) in self.edges.data():
            if self.has_edge(j, i) and i < j:
                # Constraints with the zero timepoint
                if i == 0:
                    timepoint = Node.from_dict(self.node[j]['data'])
                    lower_bound = -self[j][i]['weight']
                    upper_bound = self[i][j]['weight']
                    to_print += "Timepoint {}: [{}, {}]".format(timepoint, lower_bound, upper_bound)
                # Constraints between the other timepoints
                else:
                    if 'is_contingent' in self[j][i]:
                        to_print += "Constraint {} => {}: [{}, {}] ({})".format(i, j, -self[j][i]['weight'], self[i][j]['weight'], self[i][j]['distribution'])
                    else:

                        to_print += "Constraint {} => {}: [{}, {}]".format(i, j, -self[j][i]['weight'], self[i][j]['weight'])
                to_print += "\n"

        return to_print

    def add_zero_timepoint(self):
        node = Node()
        self.add_node(0, data=node.to_dict())

    def add_constraint(self, i=0, j=0, wji=0, wij=float('inf')):
        """
        Adds constraint between nodes i and j
        i: starting node
        j: ending node

        The constraint
        i --- [-wji, wij] ---> j
        Maps to two edges in a distance graph
        i --- wij ---> j
        i <--- -wji --- j

        -wji is the lower bound (minimum allocated time between i and j)
         wij is the upper bound (maximum allocated time between i and j)

        If there is no upper bound, its value is set to infinity
        """
        # Minimum allocated time between i and j
        min_time = -wji
        # Maximum allocated time between i and j
        # if wij == 'inf':
        #     wij = float('inf')
        max_time = wij

        # i = constraint.starting_node_id
        # j = constraint.ending_node_id

        self.add_edge(j, i, weight=min_time)
        self.add_edge(i, j, weight=max_time)

    def remove_constraint(self, i, j):
        """ i : starting node id
            j : ending node id
        """
        self.remove_edge(i, j)
        self.remove_edge(j, i)

    def get_node_pose(self, task, type):
        """ Returns the pose in the map where the task has to be executed
        """
        if type == 'navigation':
            # TODO: initialize the pose with the robot current position (read it from mongo)
            # this value will be overwriten once the task is allocated
            pose = ''
        elif type == 'start':
            pose = task.pickup_pose.name
        elif type == 'finish':
            pose = task.delivery_pose.name

        return pose

    def add_timepoint(self, id, task, type):
        """ A timepoint is represented by a node in the STN
        The node can be of type:
        - zero_timepoint: references the schedule to the origin
        - navigation: time at which the robot starts navigating towards the task
        - start: time at which the robot starts executing the task
        - finish: time at which the robot finishes executing the task
        """
        pose = self.get_node_pose(task, type)
        node = Node(task.id, pose, type)
        self.add_node(id, data=node.to_dict())

    def add_task(self, task, position):
        """ A task is added as 3 timepoints and 5 constraints in the STN"
        Timepoints:
        - navigation start
        - start time
        - finish time
        Constraints:
        - earliest and latest navigation times
        - navigation duration
        - earliest and latest start times
        - task duration
        - earliest and latest finish times
        If the task is not the first in the STN, add wait time constraint
        """
        print("Adding task {} in position {}".format(task.id, position))

        navigation_node_id = 2 * position + (position-2)
        start_node_id = navigation_node_id + 1
        finish_node_id = start_node_id + 1

        # Remove constraint linking navigation_node_id and previous node (if any)
        if self.has_edge(navigation_node_id-1, navigation_node_id) and navigation_node_id-1 != 0:
            print("Deleting constraint: {} => {}".format(navigation_node_id-1, navigation_node_id))

            self.remove_constraint(navigation_node_id-1, navigation_node_id)

        # Displace by 3 all nodes and constraints after position
        mapping = {}
        for node_id, data in self.nodes(data=True):
            if node_id >= navigation_node_id:
                mapping[node_id] = node_id + 3
        # print("mapping: ", mapping)
        nx.relabel_nodes(self, mapping, copy=False)

        # Add new timepoints
        self.add_timepoint(navigation_node_id, task, "navigation")
        self.add_timepoint_constraints(navigation_node_id, task, "navigation")

        self.add_timepoint(start_node_id, task, "start")
        self.add_timepoint_constraints(start_node_id, task, "start")

        self.add_timepoint(finish_node_id, task, "finish")
        self.add_timepoint_constraints(finish_node_id, task, "finish")

        # Add constraints between new nodes
        new_constraints_between = [navigation_node_id, start_node_id, finish_node_id]

        # Check if there is a node after the new delivery node
        if self.has_node(finish_node_id+1):
            new_constraints_between.append(finish_node_id+1)

        # Check if there is a node before the new start node
        if self.has_node(navigation_node_id-1):
            new_constraints_between.insert(0, navigation_node_id-1)

        # print("New constraints between nodes: ", new_constraints_between)

        constraints = [((i), (i + 1)) for i in new_constraints_between[:-1]]
        print("Constraints: ", constraints)

        self.add_intertimepoints_constraints(constraints, task)

        # for (i, j) in constraints:
        #     print("Adding constraint: ", (i, j))
        #     if self.node[i]['data']['type'] == "navigation":
        #         duration = self.get_navigation_duration(i, j)
        #         self.add_constraint(i, j, duration)
        #
        #     elif self.node[i]['data']['type'] == "start":
        #         duration = self.get_task_duration(task)
        #         self.add_constraint(i, j, duration)
        #
        #     elif self.node[i]['data']['type'] == "finish":
        #         # wait time between finish of one task and start of the next one. Fixed to [0, inf]
        #         self.add_constraint(i, j, 0)

    def add_intertimepoints_constraints(self, constraints, task):
        """ Adds constraints between the timepoints of a task
        Constraints between:
        - navigation start and start
        - start and finish
        - finish and next task (if any)
        Args:
            constraints (list) : list of tuples that defines the pair of nodes between which a new constraint should be added
            Example:
            constraints = [(1, 2), (2, 3)]
            New constraints will be added between nodes 1 and 2 and between 2 and 3

            task (Task): task represented by the constraints
        """
        for (i, j) in constraints:
            print("Adding constraint: ", (i, j))
            if self.node[i]['data']['type'] == "navigation":
                duration = self.get_navigation_duration(i, j)
                self.add_constraint(i, j, duration)

            elif self.node[i]['data']['type'] == "start":
                duration = self.get_task_duration(task)
                self.add_constraint(i, j, duration)

            elif self.node[i]['data']['type'] == "finish":
                # wait time between finish of one task and start of the next one. Fixed to [0, inf]
                self.add_constraint(i, j, 0)

    def get_navigation_duration(self, source, destination):
        """ Reads from the database the estimated duration for navigating from source to destination
        """
        # TODO: Read estimated duration from dataset
        duration = 6
        return duration

    def get_task_duration(self, task):
        """ Reads from the database the estimated duration of the task
        In the case of transportation tasks, the estimated duration is the navigation time from the pickup to the delivery location
        """
        duration = task.estimated_duration
        return duration

    def show_n_nodes_edges(self):
        """ Prints the number of nodes and edges in the stn
        """
        print("Nodes: ", self.number_of_nodes())
        print("Edges: ", self.number_of_edges())

    def remove_task(self, position):
        """ Removes the task from the given position"""

        print("Removing task at position: ", position)
        navigation_node_id = 2 * position + (position-2)
        start_node_id = navigation_node_id + 1
        finish_node_id = start_node_id + 1

        new_constraints_between = list()

        if self.has_node(navigation_node_id-1) and self.has_node(finish_node_id+1):
            new_constraints_between = [navigation_node_id-1, navigation_node_id]

        # Remove node and all adjacent edges
        self.remove_node(navigation_node_id)
        self.remove_node(start_node_id)
        self.remove_node(finish_node_id)

        # Displace by -3 all nodes and constraints after position
        mapping = {}
        for node_id, data in self.nodes(data=True):
            if node_id >= navigation_node_id:
                mapping[node_id] = node_id - 3
        # print("mapping: ", mapping)
        nx.relabel_nodes(self, mapping, copy=False)

        if new_constraints_between:
            constraints = [((i), (i + 1)) for i in new_constraints_between[:-1]]
            # print("Constraints: ", constraints)

            for (i, j) in constraints:
                if self.node[i]['data']['type'] == "finish":
                    # wait time between finish of one task and start of the next one
                    self.add_constraint(i, j, 0)

    def is_consistent(self, shortest_path_array):
        """The STN is not consistent if it has negative cycles"""
        consistent = True
        for node, nodes in shortest_path_array.items():
            if nodes[node] != 0:
                consistent = False
        return consistent

    def update_edges(self, shortest_path_array, create=False):
        """Update edges in the STN to reflect the distances in the minimal stn
        """
        print("Updating edges")
        for column, row in shortest_path_array.items():
            nodes = dict(row)
            for n in nodes:
                self.update_edge_weight(column, n, shortest_path_array[column][n])

    def update_edge_weight(self, i, j, weight, create=False):
        """ Updates the weight of the edge between node starting_node and node ending_node
        :param i: starting_node_id
        :parma ending_node: ending_node_id
        """
        if self.has_edge(i, j):
            self[i][j]['weight'] = weight

    def get_edge_weight(self, i, j):
        """ Returns the weight of the edge between node starting_node and node ending_node
        :param i: starting_node_id
        :parma ending_node: ending_node_id
        """
        if self.has_edge(i, j):
            return self[i][j]['weight']
        else:
            if i == j and self.has_node(i):
                return 0
            else:
                return float('inf')

    # def get_assigned_time(self, node_id):
    #     """ Returns to assigned time to a timepoint (node) in the STN"""
    #     if node_id == 0:
    #         # This is the zero_timepoint
    #         return 0.0
    #     if self.get_edge_data(0, node_id)['weight'] != -self.get_edge_data(node_id, 0)['weight']:
    #         return None
    #     return self.get_edge_data(0, node_id)['weight']

    # def floyd_warshall(self):
    #     minimal_stn = nx.floyd_warshall(self)
    #     return minimal_stn

    def get_completion_time(self):
        nodes = list(self.nodes())
        node_first_task = nodes[1]
        node_last_task = nodes[-1]

        start_time_lower_bound = -self[node_first_task][0]['weight']

        finish_time_upper_bound = self[0][node_last_task]['weight']

        completion_time = round(finish_time_upper_bound - start_time_lower_bound)

        return completion_time

    def get_makespan(self):
        nodes = list(self.nodes())
        node_last_task = nodes[-1]
        last_task_finish_time = self[0][node_last_task]['weight']

        return last_task_finish_time

    def add_timepoint_constraints(self, node_id, task, type):
        """ Adds the earliest and latest times to execute a timepoint (node)
        Navigation timepoint [0, inf]
        Start timepoint [earliest_start_time, latest_start_time]
        Finish timepoint [earliest_finish_time, lastest_finish_time]
        """
        # Maybe ?:
        # EStn = EPtn - TTt(n-1)tn
        # LStn = LPtn - TTt(n-1)tn

        if type == "navigation":
            self.add_constraint(0, node_id, 0)

        if type == "start":
            self.add_constraint(0, node_id, task.earliest_pickup_time, task.latest_pickup_time)

        elif type == "finish":
            self.add_constraint(0, node_id, task.earliest_delivery_time, task.latest_delivery_time)

    def to_json(self):
        dict_json = json_graph.node_link_data(self)
        MyEncoder().encode(dict_json)
        print(dict_json)
        stn_json = json.dumps(dict_json, cls=MyEncoder)

        return stn_json

    @staticmethod
    def from_json(stn_json):
        stn = STN()
        dict_json = json.loads(stn_json)
        graph = json_graph.node_link_graph(dict_json)
        stn.add_nodes_from(graph.nodes(data=True))
        stn.add_edges_from(graph.edges(data=True))

        return stn

    def from_dict(stn_json):
        stn = STN()
        dict_json = json.load(stn_json)
        print("Done with loading")
        graph = json_graph.node_link_graph(dict_json)
        stn.add_nodes_from(graph.nodes(data=True))
        stn.add_edges_from(graph.edges(data=True))
        return stn



    # def build_temporal_network(self, scheduled_tasks):
    #     """ Builds an STN with the tasks in the list of scheduled tasks"""
    #     self.clear()
    #     self.add_zero_timepoint()
    #
    #     print("Tasks: ", [task.id for task in scheduled_tasks])
    #
    #     position = 1
    #     for task in scheduled_tasks:
    #         print("Adding task {} in position {}".format(task.id, position))
    #         # Add three nodes per task
    #         node = Node(position, task, "start")
    #         self.add_node(node.id, data=node)
    #         self.add_start_end_constraints(node)
    #
    #         node = Node(position+1, task, "pickup")
    #         self.add_node(node.id, data=node)
    #         self.add_start_end_constraints(node)
    #
    #         node = Node(position+2, task, "delivery")
    #         self.add_node(node.id, data=node)
    #         self.add_start_end_constraints(node)
    #         position += 3
    #
    #     # Add constraints between nodes
    #     nodes = list(self.nodes) #[1:]
    #     print("Nodes: ", nodes)
    #     constraints = [((i), (i + 1)) for i in range(1, len(nodes)-1)]
    #     print("Constraints: ", constraints)
    #
    #     # Add tasks constraints
    #     for (i, j) in constraints:
    #         if self.node[i]['data'].type == "start":
    #             # TODO: Get travel time from i to j
    #             # constraint = Constraint(i, j, 6)
    #             self.add_constraint(i, j, 6)
    #
    #         elif self.node[i]['data'].type == "pickup":
    #             # constraint = Constraint(i, j, self.node[i]['data'].task.estimated_duration)
    #             self.add_constraint(i, j, self.node[i]['data'].task.estimated_duration)
    #
    #         elif self.node[i]['data'].type == "delivery":
    #             # constraint = Constraint(i, j, 0)
    #             self.add_constraint(i, j, 0)

    # def to_dict(self):
    #     stnu_dict = dict()
    #     stnu_dict['nodes'] = list()
    #     for node in self.nodes():
    #         stnu_dict['nodes'].append(self.node[node]['data'].to_dict())
    #         print("Printing the nodes")
    #         print(self.node[node]['data'])
    #     #     stnu_dict['nodes'].append(node.to_dict())
    #     stnu_dict['constraints'] = list()
    #     for (i, j), constraint in self.constraints.items():
    #         stnu_dict['constraints'].append(constraint.to_dict())
    #     return stnu_dict

    # @staticmethod
    # def from_dict(stn_dict):
    #     stn = STN()
    #     zero_timepoint_exists = False
    #
    #     for node_dict in stn_dict['nodes']:
    #         node = Node.from_dict(node_dict)
    #         stn.add_node(node.id, data=node)
    #         if node.id != 0:
    #             # Adding starting and ending node scheduler constraint
    #             if node.type == "start":
    #                 # TODO: Get travel time (TT) from previous task (or init position) to the pickup of next task
    #                 earliest_start_time = 0
    #                 # latest_start_time = 100
    #                 # start_time = Constraint(0, node.id, earliest_start_time)
    #                 stn.add_constraint(0, node.id, earliest_start_time)
    #
    #             elif node.type == "pickup":
    #                 # pickup_time = Constraint(0, node.id, node.task.earliest_pickup_time, node.task.latest_pickup_time)
    #                 stn.add_constraint(0, node.id, node.task.earliest_pickup_time, node.task.latest_pickup_time)
    #
    #             elif node.type == "delivery":
    #                 # delivery_time = Constraint(0, node.id, node.task.earliest_delivery_time, node.task.latest_delivery_time)
    #                 stn.add_constraint(0, node.id, node.task.earliest_delivery_time, node.task.latest_delivery_time)
    #
    #         else:
    #             zero_timepoint_exists = True
    #
    #     if zero_timepoint_exists is not True:
    #         # Adding the zero timepoint
    #         zero_timepoint = Node(0)
    #         stn.add_node(0, data=zero_timepoint)
    #
    #     for constraint_dict in stn_dict['constraints']:
    #         constraint = Constraint.from_dict(constraint_dict)
    #         stn.add_constraint(constraint)
    #
    #     return stn

    # def __repr__(self):
    #     return json.dumps(self.__dict__)
