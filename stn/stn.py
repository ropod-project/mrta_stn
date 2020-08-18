import json
import logging.config
import sys
from json import JSONEncoder
from stn.utils.uuid import generate_uuid

import networkx as nx
from networkx.readwrite import json_graph

from stn.node import Node
from uuid import UUID
import copy
import math
from stn.task import Timepoint

MAX_FLOAT = sys.float_info.max


class MyEncoder(JSONEncoder):
    def default(self, obj):
        if isinstance(obj, UUID):
            return obj.hex
        return obj.__dict__


class STN(nx.DiGraph):
    """ Represents a Simple Temporal Network (STN) as a networkx directed graph
    """

    logger = logging.getLogger('stn.stn')

    def __init__(self):
        super().__init__()
        self.add_zero_timepoint()
        self.max_makespan = MAX_FLOAT
        self.risk_metric = None

    def __str__(self):
        to_print = ""
        for (i, j, data) in self.edges.data():
            if self.has_edge(j, i) and i < j:
                # Constraints with the zero timepoint
                if i == 0:
                    timepoint = self.nodes[j]['data']
                    lower_bound = -self[j][i]['weight']
                    upper_bound = self[i][j]['weight']
                    to_print += "Timepoint {}: [{}, {}]".format(timepoint, lower_bound, upper_bound)
                    if timepoint.is_executed:
                        to_print += " Ex"
                # Constraints between the other timepoints
                else:
                    to_print += "Constraint {} => {}: [{}, {}]".format(i, j, -self[j][i]['weight'], self[i][j]['weight'])
                    if self[i][j]['is_executed']:
                        to_print += " Ex"

                to_print += "\n"

        return to_print

    def __eq__(self, other):
        if other is None:
            return False
        if len(other.nodes()) != len(self.nodes()):
            return False
        for (i, j, data) in self.edges.data():
            if other.has_edge(i, j):
                if other[i][j]['weight'] != self[i][j]['weight']:
                    return False
            else:
                return False
            if other.has_node(i):
                if other.nodes[i]['data'] != self.nodes[i]['data'] :
                    return False
            else:
                return False
        return True

    def __ne__(self, other):
        return not self.__eq__(other)

    def add_zero_timepoint(self):
        node = Node(generate_uuid(), 'zero_timepoint')
        self.add_node(0, data=node)

    def get_earliest_time(self):
        edges = [e for e in self.edges]
        first_edge = edges[0]
        return -self[first_edge[1]][0]['weight']

    def get_latest_time(self):
        edges = [e for e in self.edges]
        last_edge = edges[-1]
        return self[0][last_edge[0]]['weight']

    def is_empty(self):
        return nx.is_empty(self)

    def add_constraint(self, i, j, wji=0.0, wij=MAX_FLOAT):
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

        The default upper and lower bounds are 0 and infinity (MAX_FLOAT)
        """
        # Minimum allocated time between i and j
        min_time = -wji
        # Maximum allocated time between i and j
        max_time = wij

        self.add_edge(j, i, weight=min_time, is_executed=False)
        self.add_edge(i, j, weight=max_time, is_executed=False)

    def remove_constraint(self, i, j):
        """ i : starting node id
            j : ending node id
        """
        self.remove_edge(i, j)
        self.remove_edge(j, i)

    def get_constraints(self):
        """
        Two edges correspond to a constraint.
        returns     dict with constraints
                    {(starting_node, ending_node): self[i][j] }
        """
        constraints = dict()

        for (i, j) in self.edges():
            if i < j:
                constraints[(i, j)] = self[i][j]

        return constraints

    def add_timepoint(self, id, task, node_type, **kwargs):
        """ A timepoint is represented by a node in the STN
        The node can be of node_type:
        - zero_timepoint: references the schedule to the origin
        - start : time at which the robot starts navigating towards the pickup location
        - pickup : time at which the robot arrives starts the pickup action
        - delivery : time at which the robot finishes the delivery action
        """
        node = Node(task.task_id, node_type, **kwargs)
        self.add_node(id, data=node)

    def add_task(self, task, position=1):
        """ A task is added as 3 timepoints and 5 constraints in the STN"
        Timepoints:
        - start
        - pickup time
        - delivery time
        Constraints:
        - earliest and latest start times
        - travel time: time to go from current position to pickup position)
        - earliest and latest pickup times
        - work time: time to perform the task (time to transport an object from the pickup to the delivery location)
        - earliest and latest finish times
        If the task is not the first in the STN, add wait time constraint

        Note: Position 0 is reserved for the zero_timepoint
        Add tasks from postion 1 onwards
        """
        self.logger.info("Adding task %s in position %s", task.task_id, position)

        start_node_id = 2 * position + (position-2)
        pickup_node_id = start_node_id + 1
        delivery_node_id = pickup_node_id + 1

        # Remove constraint linking start_node_id and previous node (if any)
        if self.has_edge(start_node_id-1, start_node_id) and start_node_id-1 != 0:
            self.logger.debug("Deleting constraint: %s  => %s", start_node_id-1, start_node_id)

            self.remove_constraint(start_node_id-1, start_node_id)

        # Displace by 3 all nodes and constraints after position
        mapping = {}
        for node_id, data in self.nodes(data=True):
            if node_id >= start_node_id:
                mapping[node_id] = node_id + 3
        self.logger.debug("mapping: %s ", mapping)
        nx.relabel_nodes(self, mapping, copy=False)

        # Add new timepoints
        self.add_timepoint(start_node_id, task, "start")
        self.add_timepoint_constraint(start_node_id, task.get_timepoint("start"))

        self.add_timepoint(pickup_node_id, task, "pickup", action_id=task.pickup_action_id)
        self.add_timepoint_constraint(pickup_node_id, task.get_timepoint("pickup"))

        self.add_timepoint(delivery_node_id, task, "delivery", action_id=task.delivery_action_id)
        self.add_timepoint_constraint(delivery_node_id, task.get_timepoint("delivery"))

        # Add constraints between new nodes
        new_constraints_between = [start_node_id, pickup_node_id, delivery_node_id]

        # Check if there is a node after the new delivery node
        if self.has_node(delivery_node_id+1):
            new_constraints_between.append(delivery_node_id+1)

        # Check if there is a node before the new start node
        if self.has_node(start_node_id-1):
            new_constraints_between.insert(0, start_node_id-1)

        self.logger.debug("New constraints between nodes: %s", new_constraints_between)

        constraints = [((i), (i + 1)) for i in new_constraints_between[:-1]]
        self.logger.debug("Constraints: %s", constraints)

        self.add_intertimepoints_constraints(constraints, task)

    def add_intertimepoints_constraints(self, constraints, task):
        """ Adds constraints between the timepoints of a task
        Constraints between:
        - start and pickup
        - pickup and delivery
        - delivery and start next task (if any)
        Args:
            constraints (list) : list of tuples that defines the pair of nodes between which a new constraint should be added
            Example:
            constraints = [(1, 2), (2, 3)]
            New constraints will be added between nodes 1 and 2 and between 2 and 3

            task (Task): task represented by the constraints
        """
        for (i, j) in constraints:
            self.logger.debug("Adding constraint: %s ", (i, j))
            if self.nodes[i]['data'].node_type == "start":
                travel_time = self.get_travel_time(task)
                self.add_constraint(i, j, travel_time, travel_time)

            elif self.nodes[i]['data'].node_type == "pickup":
                work_time = self.get_work_time(task)
                self.add_constraint(i, j, work_time, work_time)

            elif self.nodes[i]['data'].node_type == "delivery":
                # wait time between finish of one task and start of the next one. Fixed to [0, inf]
                self.add_constraint(i, j)

    @staticmethod
    def get_travel_time(task):
        """ Returns the mean of the travel time (time for going from current pose to pickup pose)
        """
        travel_time = task.get_edge("travel_time")
        return travel_time.mean

    @staticmethod
    def get_work_time(task):
        """ Returns the mean of the work time (time to transport an object from the pickup to the delivery location)
        """
        work_time = task.get_edge("work_time")
        return work_time.mean

    @staticmethod
    def create_timepoint_constraints(r_earliest_pickup, r_latest_pickup, travel_time, work_time):
        start_constraint = Timepoint(name="start",
                                     r_earliest_time=r_earliest_pickup - travel_time.mean,
                                     r_latest_time=r_latest_pickup - travel_time.mean)
        pickup_constraint = Timepoint(name="pickup",
                                      r_earliest_time=r_earliest_pickup,
                                      r_latest_time=r_latest_pickup)
        delivery_constraint = Timepoint(name="delivery",
                                        r_earliest_time=r_earliest_pickup + work_time.mean,
                                        r_latest_time=r_latest_pickup + work_time.mean)
        return [start_constraint, pickup_constraint, delivery_constraint]

    def show_n_nodes_edges(self):
        """ Prints the number of nodes and edges in the stn
        """
        self.logger.info("Nodes: %s ", self.number_of_nodes())
        self.logger.info("Edges: %s ", self.number_of_edges())

    def update_task(self, task):
        position = self.get_task_position(task.task_id)
        start_node_id = 2 * position + (position-2)
        pickup_node_id = start_node_id + 1
        delivery_node_id = pickup_node_id + 1

        # Adding an existing timepoint constraint updates the constraint
        self.add_timepoint_constraint(start_node_id, task.get_timepoint("start"))
        self.add_timepoint_constraint(pickup_node_id, task.get_timepoint("pickup"))
        self.add_timepoint_constraint(delivery_node_id, task.get_timepoint("delivery"))

        # Add constraints between new nodes
        new_constraints_between = [start_node_id, pickup_node_id, delivery_node_id]

        # Check if there is a node after the new delivery node
        if self.has_node(delivery_node_id+1):
            new_constraints_between.append(delivery_node_id+1)

        # Check if there is a node before the new start node
        if self.has_node(start_node_id-1):
            new_constraints_between.insert(0, start_node_id-1)

        constraints = [((i), (i + 1)) for i in new_constraints_between[:-1]]
        self.add_intertimepoints_constraints(constraints, task)

    def remove_task(self, position=1):
        """ Removes the task from the given position"""

        self.logger.info("Removing task at position: %s", position)
        start_node_id = 2 * position + (position-2)
        pickup_node_id = start_node_id + 1
        delivery_node_id = pickup_node_id + 1

        new_constraints_between = list()

        if self.has_node(start_node_id-1) and self.has_node(delivery_node_id+1):
            new_constraints_between = [start_node_id-1, start_node_id]

        # Remove node and all adjacent edges
        self.remove_node(start_node_id)
        self.remove_node(pickup_node_id)
        self.remove_node(delivery_node_id)

        # Displace by -3 all nodes and constraints after position
        mapping = {}
        for node_id, data in self.nodes(data=True):
            if node_id >= start_node_id:
                mapping[node_id] = node_id - 3
        self.logger.debug("mapping: %s", mapping)
        nx.relabel_nodes(self, mapping, copy=False)

        if new_constraints_between:
            constraints = [((i), (i + 1)) for i in new_constraints_between[:-1]]
            self.logger.debug("Constraints: %s", constraints)

            for (i, j) in constraints:
                if self.nodes[i]['data'].node_type == "delivery":
                    # wait time between finish of one task and start of the next one
                    self.add_constraint(i, j)

    def remove_node_ids(self, node_ids):
        # Assumes that the node_ids are in consecutive order from node_id 1 onwards
        for node_id in node_ids:
            self.remove_node(node_id)

        # Displace all remaining nodes by 3
        mapping = {}
        for node_id, data in self.nodes(data=True):
            if node_id > 0:
                mapping[node_id] = node_id - 3
        nx.relabel_nodes(self, mapping, copy=False)

    def get_tasks(self):
        """
        Gets the tasks (in order)
        Each timepoint in the STN is associated with a task.
        return  list of task ids
        """
        tasks = list()
        for i in self.nodes():
            if self.nodes[i]['data'].task_id not in tasks and self.nodes[i]['data'].node_type != 'zero_timepoint':
                tasks.append(self.nodes[i]['data'].task_id)
        return tasks

    def is_consistent(self, shortest_path_array):
        """The STN is not consistent if it has negative cycles"""
        consistent = True
        for node, nodes in shortest_path_array.items():
            # Check if the tolerance is too large. Maybe it is better to use
            # only integers and change the resolution to seconds
            if not math.isclose(nodes[node], 0.0, abs_tol=1e-01):
                consistent = False
        return consistent

    def update_edges(self, shortest_path_array, create=False):
        """Update edges in the STN to reflect the distances in the minimal stn
        """
        for column, row in shortest_path_array.items():
            nodes = dict(row)
            for n in nodes:
                self.update_edge_weight(column, n, shortest_path_array[column][n])

    def update_edge_weight(self, i, j, weight, force=False):
        """ Updates the weight of the edge between node starting_node and node ending_node

        Updates the weight if the new weight is less than the previous weight
        :param i: starting_node_id
        :parma ending_node: ending_node_id
        """
        if self.has_edge(i, j):
            weight = round(float(weight), 2)

            if weight < self[i][j]['weight']:
                self[i][j]['weight'] = weight

            if force:
                self[i][j]['weight'] = weight

    def assign_timepoint(self, allotted_time, node_id, force=False):
        """
        Assigns the allotted time to the earliest and latest time of the timepoint
        in node_id
        Args:
            allotted_time (float): seconds after zero timepoint
            node_id (int): idx of the timepoint in the stn

        """
        self.update_edge_weight(0, node_id, allotted_time, force)
        self.update_edge_weight(node_id, 0, -allotted_time, force)

    def assign_earliest_time(self, time_, task_id, node_type, force=False):
        for i in self.nodes():
            node_data = self.nodes[i]['data']
            if node_data.task_id == task_id and node_data.node_type == node_type:
                self.update_edge_weight(i, 0, -time_, force)
                break

    def get_edge_weight(self, i, j):
        """ Returns the weight of the edge between node starting_node and node ending_node
        :param i: starting_node_id
        :parma ending_node: ending_node_id
        """
        if self.has_edge(i, j):
            return float(self[i][j]['weight'])
        else:
            if i == j and self.has_node(i):
                return 0
            else:
                return MAX_FLOAT

    def compute_temporal_metric(self, temporal_criterion):
        if temporal_criterion == 'completion_time':
            temporal_metric = self.get_completion_time()
        elif temporal_criterion == 'makespan':
            temporal_metric = self.get_makespan()
        elif temporal_criterion == 'idle_time':
            temporal_metric = self.get_idle_time()
        else:
            raise ValueError(temporal_criterion)
        return temporal_metric

    def get_completion_time(self):
        completion_time = 0
        task_ids = self.get_tasks()
        for i, task_id in enumerate(task_ids):
            completion_time += self.get_time(task_id, "delivery", lower_bound=False)

        return completion_time

    def get_makespan(self):
        nodes = list(self.nodes())
        node_last_task = nodes[-1]
        last_task_finish_time = - self[node_last_task][0]['weight']

        return last_task_finish_time

    def get_idle_time(self):
        idle_time = 0
        task_ids = self.get_tasks()

        for i, task_id in enumerate(task_ids):
            if i > 0:
                r_earliest_delivery_time_previous_task = self.get_time(task_ids[i-1], "delivery")
                r_earliest_start_time = self.get_time(task_ids[i], "start")
                idle_time += round(r_earliest_start_time - r_earliest_delivery_time_previous_task)
        return idle_time

    def add_timepoint_constraint(self, node_id, timepoint_constraint):
        """ Adds the earliest and latest times to execute a timepoint (node)
        Start timepoint [earliest_start_time, latest_start_time]
        Pickup timepoint [earliest_pickup_time, latest_pickup_time]
        Delivery timepoint [earliest_delivery_time, lastest_delivery_time]
        """
        self.add_constraint(0, node_id, timepoint_constraint.r_earliest_time, timepoint_constraint.r_latest_time)

    @staticmethod
    def get_prev_timepoint(timepoint_name, next_timepoint, edge_in_between):
        r_earliest_time = next_timepoint.r_earliest_time - edge_in_between.mean
        r_latest_time = next_timepoint.r_latest_time - edge_in_between.mean
        return Timepoint(timepoint_name, r_earliest_time, r_latest_time)

    @staticmethod
    def get_next_timepoint(timepoint_name, prev_timepoint, edge_in_between):
        r_earliest_time = prev_timepoint.r_earliest_time + edge_in_between.mean
        r_latest_time = prev_timepoint.r_latest_time + edge_in_between.mean
        return Timepoint(timepoint_name, r_earliest_time, r_latest_time)

    def get_time(self, task_id, node_type='start', lower_bound=True):
        _time = None
        for i, data in self.nodes.data():

            if task_id == data['data'].task_id and data['data'].node_type == node_type:
                if lower_bound:
                    _time = -self[i][0]['weight']
                else:  # upper bound
                    _time = self[0][i]['weight']

        return _time

    def get_node_earliest_time(self, node_id):
        return -self[node_id][0]['weight']

    def get_node_latest_time(self, node_id):
        return self[0][node_id]['weight']

    def get_nodes_by_action(self, action_id):
        nodes = list()
        for node_id, data in self.nodes.data():
            if data['data'].action_id == action_id:
                node = (node_id, self.nodes[node_id]['data'])
                nodes.append(node)
        return nodes

    def get_nodes_by_task(self, task_id):
        nodes = list()
        for node_id, data in self.nodes.data():
            if data['data'].task_id == task_id:
                node = (node_id, self.nodes[node_id]['data'])
                nodes.append(node)
        return nodes

    def get_node_by_type(self, task_id, node_type):
        for node_id, data in self.nodes.data():
            if data['data'].task_id == task_id and data['data'].node_type == node_type:
                return node_id, self.nodes[node_id]['data']

    def set_action_id(self, node_id, action_id):
        self.nodes[node_id]['data'].action_id = action_id

    def get_node(self, node_id):
        return self.nodes[node_id]['data']

    def get_task_id(self, position):
        """ Returns the id of the task in the given position

        Args:
            position: (int) position in the STN

        Returns: (string) task id

        """
        start_node_id = 2 * position + (position-2)
        pickup_node_id = start_node_id + 1
        delivery_node_id = pickup_node_id + 1

        if self.has_node(start_node_id):
            task_id = self.nodes[start_node_id]['data'].task_id
        elif self.has_node(pickup_node_id):
            task_id = self.nodes[pickup_node_id]['data'].task_id
        elif self.has_node(delivery_node_id):
            task_id = self.nodes[delivery_node_id]['data'].task_id
        else:
            self.logger.error("There is no task in position %s", position)
            return

        return task_id

    def get_task_position(self, task_id):
        for i, data in self.nodes.data():
            if task_id == data['data'].task_id and data['data'].node_type == 'start':
                return math.ceil(i/3)

    def get_earliest_task_id(self):
        """ Returns the id of the earliest task in the stn

        Returns: task_id (string)
        """
        # The first task in the graph is the task with the earliest start time
        # The first task is in node 1, node 0 is reserved for the zero timepoint

        if self.has_node(1):
            task_id = self.nodes[1]['data'].task_id
            return task_id

        self.logger.debug("STN has no tasks yet")

    def get_task_nodes(self, task_id):
        """ Gets the nodes in the stn associated with the given task_id

        Args:
            task_id: (string) id of the task

        Returns: list of node ids

        """
        nodes = list()
        for i in self.nodes():
            if task_id == self.nodes[i]['data'].task_id:
                nodes.append(self.nodes[i]['data'])

        return nodes

    def get_task_node_ids(self, task_id):
        """ Gets the node_ids in the stn associated with the given task_id

        Args:
            task_id: (string) id of the task

        Returns: list of node ids

        """
        node_ids = list()
        for i in self.nodes():
            if task_id == self.nodes[i]['data'].task_id:
                node_ids.append(i)

        return node_ids

    def get_task_graph(self, task_id):
        """ Returns a graph with the nodes of the task_id

        Args:
            task_id: ID of the task

        Returns: nx graph with nodes of task_id

        """
        node_ids = self.get_task_node_ids(task_id)
        node_ids.insert(0, 0)
        task_graph = self.subgraph(node_ids)
        return task_graph

    def get_subgraph(self, n_tasks):
        """ Returns a subgraph of the stn that includes the nodes of the first n_tasks
        and the zero timepoint

        Args:
            n_tasks (int): number of tasks to include int the subgraph

        Returns: graph

        """
        node_ids = list()
        tasks = self.get_tasks()[0: n_tasks]
        for task_id in tasks:
            node_ids += self.get_task_node_ids(task_id)

        # The first node in the subgraph is the zero timepoint
        node_ids.insert(0, 0)

        sub_graph = self.subgraph(node_ids)
        return sub_graph

    def execute_timepoint(self, node_id):
        self.nodes[node_id]['data'].is_executed = True

    def execute_edge(self, node_1, node_2):
        nx.set_edge_attributes(self, {(node_1, node_2): {'is_executed': True},
                                      (node_2, node_1): {'is_executed': True}})

    def execute_incoming_edge(self, task_id, node_type):
        finish_node_idx = self.get_edge_node_idx(task_id, node_type)
        if node_type == "start":
            return
        elif node_type == "pickup":
            start_node_idx = self.get_edge_node_idx(task_id, "start")
        elif node_type == "delivery":
            start_node_idx = self.get_edge_node_idx(task_id, "pickup")
        self.execute_edge(start_node_idx, finish_node_idx)

    def remove_old_timepoints(self):
        nodes_to_remove = list()
        for i in self.nodes():
            node_data = self.nodes[i]['data']
            if not node_data.is_executed:
                continue
            if node_data.is_executed and (self.has_edge(i, i+1) and self[i][i+1]['is_executed']):
                nodes_to_remove.append(i)

        for node in nodes_to_remove:
            self.remove_node(node)

    def get_edge_node_idx(self, task_id, node_type):
        for i in self.nodes():
            node_data = self.nodes[i]['data']
            if node_data.task_id == task_id and node_data.node_type == node_type:
                return i

    def get_edge_nodes_idx(self, task_id, node_type_1, node_type_2):
        for i in self.nodes():
            node_data = self.nodes[i]['data']
            if node_data.task_id == task_id and node_data.node_type == node_type_1:
                start_node_idx = i
            elif node_data.task_id == task_id and node_data.node_type == node_type_2:
                finish_node_idx = i

        return start_node_idx, finish_node_idx

    def to_json(self):
        stn_dict = self.to_dict()
        MyEncoder().encode(stn_dict)
        stn_json = json.dumps(stn_dict, cls=MyEncoder)
        return stn_json

    def to_dict(self):
        stn = copy.deepcopy(self)
        for i, data in self.nodes.data():
            stn.nodes[i]['data'] = self.nodes[i]['data'].to_dict()
        stn_dict = json_graph.node_link_data(stn)
        return stn_dict

    @classmethod
    def from_json(cls, stn_json):
        stn = cls()
        dict_json = json.loads(stn_json)
        graph = json_graph.node_link_graph(dict_json)
        stn.add_nodes_from([(i, {'data': Node.from_dict(graph.nodes[i]['data'])}) for i in graph.nodes()])
        stn.add_edges_from(graph.edges(data=True))

        return stn

    @classmethod
    def from_dict(cls, stn_dict):
        stn_json = json.dumps(stn_dict, cls=MyEncoder)
        stn = cls.from_json(stn_json)
        return stn

