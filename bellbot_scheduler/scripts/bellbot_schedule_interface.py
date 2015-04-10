#!/usr/bin/env python


import rospy
import sys
import StringIO

from mongodb_store_msgs.msg import StringPair
from mongodb_store.message_store import MessageStoreProxy
from strands_executive_msgs import task_utils
from strands_executive_msgs.msg import Task
from strands_executive_msgs.srv import AddTask, SetExecutionStatus
from bellbot_scheduler.msg import BellbotScheduleRequest

from datetime import time, timedelta
from dateutil.tz import tzutc, tzlocal
import datetime as dt




class BellbotScheduler() :
    def __init__(self, gui_topic_name, bellbot_action_server_name) :

        self.bellbot_as_name = bellbot_action_server_name
        add_task_srv_name = '/task_executor/add_task'
        set_exe_stat_srv_name = '/task_executor/set_execution_status'
        
        rospy.loginfo("Waiting for task_executor service...")
        rospy.wait_for_service(add_task_srv_name)
        rospy.wait_for_service(set_exe_stat_srv_name)
        rospy.loginfo("Done")
        self.msg_store = MessageStoreProxy()
        self.add_task_srv = rospy.ServiceProxy(add_task_srv_name, AddTask)
        self.set_execution_status = rospy.ServiceProxy(set_exe_stat_srv_name, SetExecutionStatus)
        self.task_duration = rospy.Duration(3000)
        self.subscriber = rospy.Subscriber(gui_topic_name, BellbotScheduleRequest, self.callback)

    def callback(self, request):
        print request

        # find out when to schedule task
        time_list = request.start_time.split('_');
        date_now = dt.datetime.now()
        new_date = date_now.replace(hour = int(time_list[0]), minute = int(time_list[1]))
	print 'Schedule date ',new_date
	on_demand = False
        if (new_date < date_now) :
            delta = 600 # minimum number of seconds for the scheduler to schedule
	    on_demand = True
        else:
            tdelta = new_date - date_now
            delta = tdelta.seconds

        if (delta < 600):
            delta = 600

	print 'seconds delta ',delta
        start_time = rospy.get_rostime()
        print 'original start time ',start_time
	start_time.secs += delta
	print 'start time after updating ',start_time
        end_time = rospy.get_rostime()
	end_time.secs += delta
        end_time.secs+=3600
	print 'end time ', end_time

	print "Scheduling a new bellbot task from ",request.start_waypoint, " to ", request.end_waypoint, " start time: ",new_date, "for a duration of ", self.task_duration
        self.schedule_bellbot_task(request.mode, request.start_waypoint, request.end_waypoint, request.description, start_time, end_time, on_demand)


    def schedule_bellbot_task(self, mode, start_wp, end_wp, description, start_time, end_time, on_demand=False):
        try:

	    if on_demand :
            	task = Task(start_node_id="WayPoint4", action=self.bellbot_as_name, max_duration=self.task_duration)
	    else :
            	task = Task(start_node_id="WayPoint4", action=self.bellbot_as_name, max_duration=self.task_duration , start_after=start_time, end_before=end_time)
            task_utils.add_int_argument(task, mode)
            task_utils.add_string_argument(task, start_wp)
            task_utils.add_string_argument(task, end_wp)
            task_utils.add_string_argument(task, description)
            print task


            if on_demand:
                print "Demanding task be run NOW."
                add_task_srv_name = '/task_executor/demand_task'
            else:
                add_task_srv_name = '/task_executor/add_task'
                set_exe_stat_srv_name = '/task_executor/set_execution_status'

            print self.add_task_srv(task)
            #Make sure the task executor is running
            self.set_execution_status(True)

        except rospy.ServiceException, e:
            print "Service call failed: %s"%e


#def schedule_task

if __name__ == '__main__':
    rospy.init_node("bellbot_scheduler")

    scheduler = BellbotScheduler("/gui_topic", "/bellbot_action_server")
    rospy.spin()
#    scheduler.schedule_bellbot_task(1, 'WayPoint4', 'WayPoint3','Something important will be writen here I tell you.',"20_45", "21_45")





