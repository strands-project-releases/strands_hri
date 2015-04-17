#! /usr/bin/env python
import rospy
import smach
import smach_ros
import sys
import getopt
import random
import json
import subprocess

from agent import Agent

import actionlib
from actionlib_msgs.msg import *
from std_msgs.msg import String
import topological_navigation.msg

import std_srvs.srv
from bellbot_action_server.srv import *
from bellbot_action_server.msg import * 

class BellbotStateMachine(Agent):

    """
    Definition of the bellbot state machine. 

    """
    def __init__(self):

        # the super().__init__() methods calls make_sm(),
        super(BellbotStateMachine,self).__init__()

       
    
    def make_sm(self):
        self.sm = smach.StateMachine(outcomes=['succeeded','aborted','preempted'])
        
        with self.sm:
            
            smach.StateMachine.add('Setup', Setup(), 
                                   transitions={ 'succeeded_mode1': 'WaitingForGoal', 
                                                 'succeeded_mode2': 'WaitingForMultipleGuests', 
                                                 'succeeded_mode3': 'WaitingForSingleGuest', 
                                                 'aborted': 'aborted',
                                                 'preempted': 'preempted' 
                                               })
            smach.StateMachine.add('WaitingForGoal', WaitingForGoal(), 
                                   transitions={ 'succeeded': 'Guiding', 
                                                 'aborted': 'aborted',
                                                 'preempted': 'preempted' 
                                               })
            smach.StateMachine.add('WaitingForMultipleGuests', WaitingForMultipleGuests(), 
                                   transitions={ 'succeeded': 'Guiding', 
                                                 'aborted': 'aborted',
                                                 'preempted': 'preempted' 
                                               })
            smach.StateMachine.add('WaitingForSingleGuest', WaitingForSingleGuest(), 
                                   transitions={ 'succeeded': 'Guiding', 
                                                 'aborted': 'aborted',
                                                 'preempted': 'preempted' 
                                               })
            smach.StateMachine.add('Guiding', Guiding(), 
                                   transitions={ 'succeeded': 'WaitingForFeedback', 
                                                 'aborted': 'aborted',
                                                 'preempted': 'preempted' 
                                               })
            smach.StateMachine.add('WaitingForFeedback', WaitingForFeedback(), 
                                   transitions={ 'succeeded': 'Setup',
                                                 'succeeded_mode3': 'Shutdown',
                                                 'aborted': 'aborted',
                                                 'preempted': 'preempted' 
                                               })
            smach.StateMachine.add('Shutdown', Shutdown(), 
                                   transitions={ 'succeeded': 'succeeded',
                                                 'aborted': 'aborted',
                                                 'preempted': 'preempted' 
                                               })
            return self.sm

    def set_sm_userdata(self, goal):
        """Set userdata for state machine."""
        rospy.loginfo('Getting parameters from server')

        self.sm.userdata.goal  = goal 
        
    def get_sm_userdata(self):
        return self.sm.userdata

class StatePublisher(object):
    """
    Class to pulish the state machine states. 
    """

    def __init__(self):
        rospy.loginfo("Running the init!")
        self.state_publisher = rospy.Publisher('/bellbot_state', BellbotState, latch=True, queue_size=1)
        
    def publish(self, state):
        self.state_publisher.publish(state)

#______________________________________________________________________________
# behavior

class Setup(smach.State, StatePublisher):

    """
    Move the robot to a requested location to provide the Bellbot service.
    """

    def __init__(self):
        smach.State.__init__(self,
                           outcomes=['succeeded_mode1','succeeded_mode2','succeeded_mode3', 'aborted', 'preempted'],
                           input_keys=['goal'],
                           output_keys=[])


        rospy.on_shutdown(self._on_node_shutdown)
        
        self.client = actionlib.SimpleActionClient('topological_navigation', topological_navigation.msg.GotoNodeAction)
        
        self.client.wait_for_server()
        StatePublisher.__init__(self)
        rospy.loginfo(" Setup ... Init done")
        
    def _on_node_shutdown(self):
        self.client.cancel_all_goals()

    def execute(self, userdata):
        rospy.loginfo('Executing state %s', self.__class__.__name__)
        self.publish(BellbotState(name=self.__class__.__name__))
        navgoal = topological_navigation.msg.GotoNodeGoal()
        
        rospy.loginfo("Requesting Navigation to %s", userdata.goal.starting_waypoint_name)
        navgoal.target = userdata.goal.starting_waypoint_name
        
        # Sends the goal to the action server.
        self.client.send_goal(navgoal)

        # Waits for the server to finish performing the action.
        status=self.client.get_state()
        while (status == GoalStatus.ACTIVE or status == GoalStatus.PENDING):
            if self.preempt_requested(): 
                self.service_preempt()
                self.client.cancel_all_goals()
                return 'preempted'
            else:
                status=self.client.get_state()
                rospy.sleep(rospy.Duration.from_sec(0.01))
        
        # Check if the naviation was successful 
        status = self.client.get_state()
        if status == GoalStatus.SUCCEEDED:
            mode = userdata.goal.mode
            if mode == 1:
                return 'succeeded_mode1'
            elif mode == 2:
                return 'succeeded_mode2'
            else: # mode == 3
                return 'succeeded_mode3'
        else:
            return 'aborted'

class WaitingForGoal(smach.State, StatePublisher):

    """
    Show the GUI and wait for input.
    """

    def __init__(self):
        smach.State.__init__(self,
                           outcomes=['succeeded', 'aborted', 'preempted'],
                           input_keys=[],
                           output_keys=['target'])

        StatePublisher.__init__(self)

        service_name = '/bellbot_new_target'
        try:
            rospy.wait_for_service(service_name, timeout=1)
        except:
            rospy.loginfo('Setting up service: %s', service_name )
            self.service = rospy.Service(service_name, NewTarget, self.service_cb)
            rospy.loginfo('Service running: %s', service_name )

        self._got_request = False
        self._target = None

        
    def service_cb(self, request):
        self._got_request = True
        self._target = request.target
        return NewTargetResponse()

    def execute(self, userdata):
        rospy.loginfo('Executing state %s', self.__class__.__name__)
        state = BellbotState()
        state.name = self.__class__.__name__
        self.publish(state)
        
        #Here we wait until a target arived. 
        while self._target == None:
            if self.preempt_requested():
                self.service_preempt()
                return 'preempted'
            else:
                rospy.sleep(rospy.Duration.from_sec(0.01))

        userdata.target = self._target
        self._target = None
        self._got_request = True

        return 'succeeded' 

class WaitingForMultipleGuests(smach.State, StatePublisher):

    """
    Show the GUI and wait for input.
    """

    def __init__(self):
        smach.State.__init__(self,
                           outcomes=['succeeded', 'aborted', 'preempted'],
                           input_keys=['goal'],
                           output_keys=['target'])
        
        service_name = '/bellbot_accept_target_mult'
        try:
            rospy.wait_for_service(service_name, timeout=1)
        except:
            rospy.loginfo('Setting up service: %s', service_name )
            self.service = rospy.Service(service_name, NewTarget, self.service_cb)
            rospy.loginfo('Service running: %s', service_name )

        self._got_request = False
        StatePublisher.__init__(self)

    def service_cb(self, request):
        self._got_request = True
        
    def execute(self, userdata):
        rospy.loginfo('Executing state %s', self.__class__.__name__)
        state = BellbotState()
        state.name = self.__class__.__name__
        state.goal = userdata.goal.preselected_goal
        state.text = userdata.goal.text
        self.publish(state)
        
        #Here we wait until a target arived. 
        while self._got_request == False:
            if self.preempt_requested():
                self.service_preempt()
                return 'preempted'
            else:
                rospy.sleep(rospy.Duration.from_sec(0.01))

        userdata.target = userdata.goal.preselected_goal
        self._got_request = False

        return 'succeeded'

class WaitingForSingleGuest(smach.State, StatePublisher):

    """
    Show the GUI and wait for input.
    """

    def __init__(self):
        smach.State.__init__(self,
                           outcomes=['succeeded', 'aborted', 'preempted'],
                           input_keys=['goal'],
                           output_keys=['target'])

        service_name = '/bellbot_accept_target_single'
        try:
            rospy.wait_for_service(service_name, timeout=1)
        except:
            rospy.loginfo('Setting up service: %s', service_name )
            self.service = rospy.Service(service_name, NewTarget, self.service_cb)
            rospy.loginfo('Service running: %s', service_name )

        self._got_request = False
        StatePublisher.__init__(self)

    def service_cb(self, request):
        self._got_request = True

    def execute(self, userdata):
        rospy.loginfo('Executing state %s', self.__class__.__name__)
        state = BellbotState()
        state.name = self.__class__.__name__
        state.goal = userdata.goal.preselected_goal
        state.text = userdata.goal.text
        self.publish(state)
        
        #Here we wait until a target arived. 
        while self._got_request == False:
            if self.preempt_requested():
                self.service_preempt()
                return 'preempted'
            else:
                rospy.sleep(rospy.Duration.from_sec(0.01))

        userdata.target = userdata.goal.preselected_goal
        self._got_request = False

        return 'succeeded' 

class Guiding(smach.State, StatePublisher):

    """
    Guide a person to the required destination.
    """

    def __init__(self):
        smach.State.__init__(self,
                           outcomes=['succeeded', 'aborted', 'preempted'],
                           input_keys=['target'],
                           output_keys=[])
       
        rospy.on_shutdown(self._on_node_shutdown)
        
        self.client = actionlib.SimpleActionClient('topological_navigation', topological_navigation.msg.GotoNodeAction)
        
        self.client.wait_for_server()
 
        StatePublisher.__init__(self)
        
        rospy.loginfo('Guiding ... Init done')
        
    def _on_node_shutdown(self):
        self.client.cancel_all_goals()

    def execute(self, userdata):
        rospy.loginfo('Executing state %s', self.__class__.__name__)
        self.publish(BellbotState(name=self.__class__.__name__))
        navgoal = topological_navigation.msg.GotoNodeGoal()
        
        rospy.loginfo("Requesting Navigation to %s", userdata.target)
        navgoal.target = userdata.target
        
        # Sends the goal to the action server.
        self.client.send_goal(navgoal)

        # Waits for the server to finish performing the action.
        status=self.client.get_state()
        while (status == GoalStatus.ACTIVE or status == GoalStatus.PENDING):
            if self.preempt_requested(): 
                self.service_preempt()
                self.client.cancel_all_goals()
                return 'preempted'
            else:
                status=self.client.get_state()
                rospy.sleep(rospy.Duration.from_sec(0.01))
        
        # Check if the naviation was successful 
        status  = self.client.get_state()
        if status == GoalStatus.SUCCEEDED:
            return 'succeeded' 
        else:
            return 'aborted'

class WaitingForFeedback(smach.State, StatePublisher):

    """
    Wait for feedback on this bellbot tour. 
    """

    def __init__(self):
        smach.State.__init__(self,
                           outcomes=['succeeded', 'succeeded_mode3', 'aborted', 'preempted'],
                           input_keys=['goal'],
                           output_keys=[])

        StatePublisher.__init__(self)

        self._feedback_max_time = rospy.get_param('feedback_max_time','30')
        rospy.loginfo('max_time found: %s', self._feedback_max_time)

        #Create a service in order to wait for feedback
        service_name = '/bellbot_feedback'
        try:
            rospy.wait_for_service(service_name, timeout=1)
        except:
            rospy.loginfo('Setting up service: %s', service_name )
            self.service = rospy.Service(service_name, std_srvs.srv.Empty, self.service_cb)
            rospy.loginfo('Service running: %s', service_name )
        self._got_feedback = False
    
    def service_cb(self, request):
        self._got_feedback = True
        return std_srvs.srv.EmptyResponse()

    def execute(self, userdata):
        rospy.loginfo('Executing state %s', self.__class__.__name__)
        self.publish(BellbotState(name=self.__class__.__name__))
        
        self._endtime = rospy.get_time() + self._feedback_max_time
        #rospy.loginfo('start time: %s', rospy.get_time())
        #rospy.loginfo('end time: %s', self._endtime)
        rospy.loginfo('Waiting for feedback (Timeout after %s secs)', self._feedback_max_time)
        #Here we wait until feedback arrived. 
        while not self._got_feedback and rospy.get_time() < self._endtime:
            if self.preempt_requested():
                self.service_preempt()
                return 'preempted'
            else:
                rospy.sleep(rospy.Duration.from_sec(0.01))

        if self._got_feedback == True:
            rospy.loginfo('Feedback received')
        else:
            rospy.loginfo('Timeout')
                
        self._got_feedback = False

        mode = userdata.goal.mode
        if mode == 3:
            return 'succeeded_mode3'
        return 'succeeded' 

class Shutdown(smach.State, StatePublisher):

    """
    Shutdown state after serving a single guest (mode 3 only)
    """

    def __init__(self):
        smach.State.__init__(self,
                           outcomes=['succeeded','aborted', 'preempted'],
                           input_keys=[],
                           output_keys=[])


        StatePublisher.__init__(self)
        rospy.loginfo("Shutdown ... Init done")
        

    def execute(self, userdata):
        rospy.loginfo('Executing state %s', self.__class__.__name__)
        subprocess.call(["pkill", "florence"])
        self.publish(BellbotState(name=self.__class__.__name__))
        return 'succeeded'
