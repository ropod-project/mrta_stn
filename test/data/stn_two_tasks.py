{
  "nodes":[
    {
      "id": 1,
      "task":
      {
        "id": "0d06fb90-a76d-48b4-b64f-857b7388ab70",
        "pickup_start_time": -1,
        "cart_id": "",
        "cart_type": "mobidik",
        "delivery_pose":
        {
            "floorNumber": 0,
            "id": "",
            "name": "AMK_TDU-TGR-1_X_5.82_Y_6.57",
            "subAreas": [],
            "type": ""
        },
        "earliest_finish_time": 1540719653.0,
        "earliest_start_time": 1540719649,
        "estimated_duration": 4.0,
        "finish_time": -1,
        "latest_finish_time": 1540719658.0,
        "latest_start_time": 1540719654,
        "loadId": "",
        "loadType": "",
        "pickup_pose":
        {
            "floorNumber": 0,
            "id": "",
            "name": "AMK_TDU-TGR-1_X_9.7_Y_5.6",
            "subAreas": [],
            "type": ""
        },
        "priority": 5,
        "robot_actions": {},
        "start_time": -1,
        "status":
        {
            "completed_robot_actions": {},
            "current_robot_actions": {},
            "estimated_task_duration": 4.0,
            "status": "unallocated",
            "task_id": "0d06fb90-a76d-48b4-b64f-857b7388ab70"
        },
        "team_robot_ids": null
      },
      "is_task_start": true,
      "is_task_end": false
    },
    {
      "id": 2,
      "task":
      {
        "id": "0d06fb90-a76d-48b4-b64f-857b7388ab70",
        "pickup_start_time": -1,
        "cart_id": "",
        "cart_type": "mobidik",
        "delivery_pose":
        {
            "floorNumber": 0,
            "id": "",
            "name": "AMK_TDU-TGR-1_X_5.82_Y_6.57",
            "subAreas": [],
            "type": ""
        },
        "earliest_finish_time": 1540719653.0,
        "earliest_start_time": 1540719649,
        "estimated_duration": 4.0,
        "finish_time": -1,
        "latest_finish_time": 1540719658.0,
        "latest_start_time": 1540719654,
        "loadId": "",
        "loadType": "",
        "pickup_pose":
        {
            "floorNumber": 0,
            "id": "",
            "name": "AMK_TDU-TGR-1_X_9.7_Y_5.6",
            "subAreas": [],
            "type": ""
        },
        "priority": 5,
        "robot_actions": {},
        "start_time": -1,
        "status":
        {
            "completed_robot_actions": {},
            "current_robot_actions": {},
            "estimated_task_duration": 4.0,
            "status": "unallocated",
            "task_id": "0d06fb90-a76d-48b4-b64f-857b7388ab70"
        },
        "team_robot_ids": null
      },
      "is_task_start": false,
      "is_task_end": true
    },
    {
      "id": 3,
      "task":
      {
        "pickup_start_time": -1,
        "cart_id": "",
        "cart_type": "mobidik",
        "delivery_pose":
        {
            "floorNumber": 0,
            "id": "",
            "name": "AMK_TDU-TGR-1_X_15.09_Y_5.69",
            "subAreas": [],
            "type": ""
        },
        "earliest_finish_time": 1540719708.0,
        "earliest_start_time": 1540719704,
        "estimated_duration": 4.0,
        "finish_time": -1,
        "id": "0616af00-ec3b-4ecd-ae62-c94a3703594c",
        "latest_finish_time": 1540719713.0,
        "latest_start_time": 1540719709,
        "loadId": "",
        "loadType": "",
        "pickup_pose":
        {
            "floorNumber": 0,
            "id": "",
            "name": "AMK_TDU-TGR-1_X_14.03_Y_9.55",
            "subAreas": [],
            "type": ""

        },
        "priority": 5,
        "robot_actions": {},
        "start_time": -1,
        "status":
        {
            "completed_robot_actions": {},
            "current_robot_actions": {},
            "estimated_task_duration": 4.0,
            "status": "unallocated",
            "task_id": "0616af00-ec3b-4ecd-ae62-c94a3703594c"
        },

        "team_robot_ids": null
      },
      "is_task_start": true,
      "is_task_end": false
    },
    {
      "id": 4,
      "task":
      {
          "pickup_start_time": -1,
          "cart_id": "",
          "cart_type": "mobidik",
          "delivery_pose":
          {
              "floorNumber": 0,
              "id": "",
              "name": "AMK_TDU-TGR-1_X_15.09_Y_5.69",
              "subAreas": [],
              "type": ""
          },
          "earliest_finish_time": 1540719708.0,
          "earliest_start_time": 1540719704,
          "estimated_duration": 4.0,
          "finish_time": -1,
          "id": "0616af00-ec3b-4ecd-ae62-c94a3703594c",
          "latest_finish_time": 1540719713.0,
          "latest_start_time": 1540719709,
          "loadId": "",
          "loadType": "",
          "pickup_pose":
          {
              "floorNumber": 0,
              "id": "",
              "name": "AMK_TDU-TGR-1_X_14.03_Y_9.55",
              "subAreas": [],
              "type": ""

          },
          "priority": 5,
          "robot_actions": {},
          "start_time": -1,
          "status":
          {
              "completed_robot_actions": {},
              "current_robot_actions": {},
              "estimated_task_duration": 4.0,
              "status": "unallocated",
              "task_id": "0616af00-ec3b-4ecd-ae62-c94a3703594c"
          },

          "team_robot_ids": null
      },
      "is_task_start": false,
      "is_task_end": true
    }
  ],
  "edges":[
    {
      "starting_node":1,
      "ending_node":2,
      "weight":4,
      "distribution": "N_4_1"
    },
    {
      "starting_node":3,
      "ending_node":4,
      "weight":4,
      "max_duration":"inf",
      "distribution": "N_4_1"
    },

    {
      "starting_node":2,
      "ending_node":3,
      "weight":6,
      "distribution": "N_6_1"
    }
  ],
  "num_agents":1
}