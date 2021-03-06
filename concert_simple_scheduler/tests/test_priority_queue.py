#!/usr/bin/env python

# enable some python3 compatibility options:
# (unicode_literals not compatible with python2 uuid module)
from __future__ import absolute_import, print_function

import copy
import heapq
import uuid
import unittest

# ROS dependencies
import unique_id
from scheduler_msgs.msg import Request, Resource
from rocon_scheduler_requests.transitions import ActiveRequest

# module being tested:
from concert_simple_scheduler.priority_queue import *

# some resources for testing
RQR_ID = uuid.uuid4()
RQ1_UUID = uuid.uuid4()
RQ2_UUID = uuid.uuid4()
EXAMPLE_RAPP = 'tests/example_rapp'
MARVIN_NAME = 'rocon:/turtlebot/marvin'
MARVIN = Resource(uri=MARVIN_NAME, rapp=EXAMPLE_RAPP)
ROBERTO_NAME = 'rocon:/turtlebot/roberto'
ROBERTO = Resource(uri=ROBERTO_NAME, rapp=EXAMPLE_RAPP)

# some useful Resource and Request messages
MARVIN_RESOURCE = Resource(rapp=EXAMPLE_RAPP, uri=MARVIN_NAME)
MARVIN_REQUEST = ActiveRequest(Request(
    id=unique_id.toMsg(RQ1_UUID),
    resources=[MARVIN_RESOURCE]))
ROBERTO_RESOURCE = Resource(rapp=EXAMPLE_RAPP, uri=ROBERTO_NAME)
ROBERTO_REQUEST = ActiveRequest(Request(
    id=unique_id.toMsg(RQ2_UUID),
    resources=[ROBERTO_RESOURCE]))


###############################
# queue element tests
###############################


class TestQueueElement(unittest.TestCase):
    """Unit tests for queue element class.

    These tests do not require a running ROS core.
    """
    def test_constructor(self):
        qe1 = QueueElement(ROBERTO_REQUEST, RQR_ID)
        qe2 = QueueElement(MARVIN_REQUEST, RQR_ID)
        self.assertNotEqual(qe1, qe2)

    def test_hash(self):
        qe1 = QueueElement(ROBERTO_REQUEST, RQR_ID)
        qe2 = QueueElement(MARVIN_REQUEST, RQR_ID)
        self.assertNotEqual(qe1, qe2)
        self.assertTrue(qe1 != qe2)
        self.assertNotEqual(hash(qe1), hash(qe2))
        qe3 = QueueElement(ROBERTO_REQUEST, RQR_ID)
        self.assertEqual(qe1, qe3)      # same request ID
        self.assertFalse(qe1 != qe3)
        self.assertEqual(hash(qe1), hash(qe3))
        dict = {qe1: qe1}
        self.assertIn(qe1, dict)
        self.assertNotIn(qe2, dict)
        self.assertIn(qe3, dict)        # because hashes are equal
        dict[qe2] = qe2
        self.assertIn(qe2, dict)

    def test_heap_queue(self):
        qe1 = QueueElement(ActiveRequest(
                Request(id=unique_id.toMsg(RQ1_UUID),
                        resources=[ROBERTO_RESOURCE],
                        priority=10)
                ), RQR_ID)
        qe2 = QueueElement(ActiveRequest(
                Request(id=unique_id.toMsg(RQ1_UUID),
                        resources=[MARVIN_RESOURCE],
                        priority=0)
                ), RQR_ID)
        self.assertLess(qe1, qe2)       # due to higher priority
        h = []
        heapq.heappush(h, qe2)
        heapq.heappush(h, qe1)
        self.assertEqual(len(h), 2)
        self.assertEqual(heapq.heappop(h), qe1)
        self.assertEqual(len(h), 1)
        heapq.heappush(h, qe1)
        self.assertEqual(len(h), 2)
        self.assertEqual(heapq.heappop(h), qe1)

        qe3 = QueueElement(ActiveRequest(
                Request(id=unique_id.toMsg(RQ1_UUID),
                        resources=[ROBERTO_RESOURCE])
                ), RQR_ID)
        qe4 = QueueElement(ActiveRequest(
                Request(id=unique_id.toMsg(RQ1_UUID),
                        resources=[MARVIN_RESOURCE])
                ), RQR_ID)
        self.assertLess(qe3, qe4)       # due to sequence number
        heapq.heappush(h, qe4)
        heapq.heappush(h, qe3)
        heapq.heappush(h, qe1)
        self.assertEqual(len(h), 4)
        self.assertEqual(heapq.heappop(h), qe1)
        self.assertEqual(heapq.heappop(h), qe2)
        self.assertEqual(heapq.heappop(h), qe3)
        self.assertEqual(heapq.heappop(h), qe4)
        self.assertEqual(len(h), 0)
        self.assertRaises(IndexError, heapq.heappop, h)

    def test_sort_diff_priority(self):
        qe1 = QueueElement(ActiveRequest(
                Request(id=unique_id.toMsg(RQ1_UUID),
                        resources=[ROBERTO_RESOURCE],
                        priority=10)
                ), RQR_ID)
        qe2 = QueueElement(ActiveRequest(
                Request(id=unique_id.toMsg(RQ1_UUID),
                        resources=[MARVIN_RESOURCE],
                        priority=0)
                ), RQR_ID)
        self.assertLess(qe1, qe2)
        self.assertEqual(sorted([qe2, qe1]), [qe1, qe2])
        qe3 = QueueElement(ActiveRequest(
                Request(id=unique_id.toMsg(RQ1_UUID),
                        resources=[ROBERTO_RESOURCE])
                ), RQR_ID)
        qe4 = QueueElement(ActiveRequest(
                Request(id=unique_id.toMsg(RQ1_UUID),
                        resources=[MARVIN_RESOURCE])
                ), RQR_ID)
        self.assertEqual(sorted([qe4, qe3]), [qe3, qe4])
        self.assertEqual(sorted([qe4, qe1, qe3, qe2]),
                         [qe1, qe2, qe3, qe4])

    def test_sort_same_priority(self):
        qe1 = QueueElement(ROBERTO_REQUEST, RQR_ID)
        qe2 = QueueElement(MARVIN_REQUEST, RQR_ID)
        self.assertLess(qe1, qe2)
        list1 = [qe1]
        self.assertEqual(sorted(list1), [qe1])
        list2 = [qe2, qe1]
        list2.sort()                    # sort in-place
        self.assertEqual(list2, [qe1, qe2])


###############################
# priority queue tests
###############################


class TestPriorityQueue(unittest.TestCase):
    """Unit tests for simple scheduler FIFO request queue class.

    These tests do not require a running ROS core.
    """
    def test_add_duplicate_request(self):
        pq = PriorityQueue()
        self.assertEqual(len(pq), 0)
        elem = QueueElement(ROBERTO_REQUEST, RQR_ID)
        pq.add(elem)
        self.assertEqual(len(pq), 1)
        self.assertEqual(pq.peek(), elem)
        dup = copy.deepcopy(ROBERTO_REQUEST)
        pq.add(QueueElement(dup, RQR_ID))
        self.assertEqual(len(pq), 1)
        self.assertEqual(pq.peek(), elem)

    def test_add_one_request(self):
        pq = PriorityQueue()
        self.assertEqual(len(pq), 0)
        elem = QueueElement(ROBERTO_REQUEST, RQR_ID)
        pq.add(elem)
        self.assertEqual(len(pq), 1)
        self.assertEqual(pq.peek(), elem)

    def test_empty_constructor(self):
        pq0 = PriorityQueue()
        self.assertIsNotNone(pq0)
        self.assertEqual(len(pq0), 0)
        self.assertRaises(IndexError, pq0.pop)
        self.assertNotIn(RQ1_UUID, pq0)
        self.assertNotIn(RQ2_UUID, pq0)

    def test_one_request_constructor(self):
        elem = QueueElement(ROBERTO_REQUEST, RQR_ID)
        pq = PriorityQueue([elem])
        self.assertEqual(len(pq), 1)
        self.assertNotIn(RQ1_UUID, pq)
        self.assertIn(RQ2_UUID, pq)
        self.assertIn(elem, pq)
        rq1 = pq.pop()
        self.assertEqual(len(pq), 0)
        self.assertMultiLineEqual(str(rq1.request), str(ROBERTO_REQUEST))

    def test_pop_one_request(self):
        pq = PriorityQueue()
        pq.add(QueueElement(MARVIN_REQUEST, RQR_ID))
        pq.add(QueueElement(ROBERTO_REQUEST, RQR_ID))
        self.assertEqual(len(pq), 2)
        self.assertMultiLineEqual(str(pq.pop().request), str(MARVIN_REQUEST))

    def test_priority_update(self):
        pq = PriorityQueue()
        pq.add(QueueElement(MARVIN_REQUEST, RQR_ID))
        pq.add(QueueElement(ROBERTO_REQUEST, RQR_ID))
        self.assertEqual(len(pq), 2)
        pq.add(QueueElement(ROBERTO_REQUEST, RQR_ID), priority=10)
        self.assertEqual(len(pq), 2)
        qe = pq.pop()
        self.assertEqual(len(pq), 1)
        self.assertEqual(qe.request.uuid, RQ2_UUID)
        self.assertEqual(qe.request.msg.priority, 10)
        self.assertEqual(qe.request.msg.resources[0].uri, ROBERTO_NAME)

    def test_remove_one_request(self):
        pq = PriorityQueue()
        marvin = QueueElement(MARVIN_REQUEST, RQR_ID)
        pq.add(marvin)
        roberto = QueueElement(ROBERTO_REQUEST, RQR_ID)
        pq.add(roberto)
        self.assertEqual(len(pq), 2)
        pq.remove(RQ1_UUID)
        self.assertEqual(pq.peek(), roberto)
        self.assertEqual(len(pq), 1)
        self.assertMultiLineEqual(str(pq.pop().request), str(ROBERTO_REQUEST))

    def test_two_request_constructor(self):
        pq = PriorityQueue([
                QueueElement(MARVIN_REQUEST, RQR_ID),
                QueueElement(ROBERTO_REQUEST, RQR_ID)])
        self.assertEqual(len(pq), 2)
        self.assertEqual(pq.peek(), QueueElement(MARVIN_REQUEST, RQR_ID))

        rq1 = pq.pop()
        self.assertEqual(len(pq), 1)
        self.assertMultiLineEqual(str(rq1.request), str(MARVIN_REQUEST))
        self.assertEqual(pq.peek(), QueueElement(ROBERTO_REQUEST, RQR_ID))

        rq2 = pq.pop()
        self.assertEqual(len(pq), 0)
        self.assertMultiLineEqual(str(rq2.request), str(ROBERTO_REQUEST))

if __name__ == '__main__':
    import rosunit
    rosunit.unitrun('concert_simple_scheduler',
                    'test_queue_element',
                    TestQueueElement)
    rosunit.unitrun('concert_simple_scheduler',
                    'test_priority_queue',
                    TestPriorityQueue)
