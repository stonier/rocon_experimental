# Software License Agreement (BSD License)
#
# Copyright (C) 2013, Jack O'Quin
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
#  * Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
#  * Redistributions in binary form must reproduce the above
#    copyright notice, this list of conditions and the following
#    disclaimer in the documentation and/or other materials provided
#    with the distribution.
#  * Neither the name of the author nor of other contributors may be
#    used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING,
# BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
# CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN
# ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

"""
.. module:: resource_pool

This module tracks all known resources managed by this scheduler.  The ROS
`scheduler_msgs/Resource`_ message describes resources used by the
`Robotics in Concert`_ (ROCON) project.

.. include:: weblinks.rst

"""
import copy
from itertools import chain, islice, permutations
import unique_id

## ROS messages
from scheduler_msgs.msg import Resource
try:
    from scheduler_msgs.msg import CurrentStatus
except ImportError:
    from rocon_scheduler_requests.resources import CurrentStatus

from rocon_scheduler_requests.resources import ResourceSet


class ResourcePool(object):
    """ This class tracks a pool of resources managed by this scheduler.

    :param resources: Initial resources for the pool.
    :type resources: :class:`.ResourceSet` or ``None``

    """
    def __init__(self, resources=None):
        self.pool = resources
        """ :class:`.ResourceSet` of current resource pool contents. """
        if resources is None:
            self.pool = ResourceSet()   # pool initially empty

    def allocate(self, request):
        """ Try to allocate all resources for a *request*.

        :param request: Scheduler request object, some resources may
            include regular expression syntax.
        :type request: :class:`.ResourceReply`

        :returns: List of ``scheduler_msgs/Resource`` messages
            allocated, in requested order with platform info fully
            resolved; or ``[]`` if not everything is available.

        If successful, matching ROCON resources are allocated to this
        *request*.  Otherwise, the *request* remains unchanged.

        """
        n_wanted = len(request.msg.resources)  # number of resources wanted

        # Make a list containing sets of the available resources
        # matching each requested item.
        matches = self._match_list(request.msg.resources)
        if not matches:                 # unsuccessful?
            return []                   # give up

        # See if there are as least as many different resources in the
        # matches set as the number requested.
        match_union = set(chain.from_iterable(matches))
        if len(match_union) < n_wanted:
            return []                   # not enough stuff

        # At least one resource is available that satisfies each item
        # requested.  Try to allocate them all in the order requested.
        alloc = self._allocate_permutation(range(n_wanted), request, matches)
        if alloc:                       # successful?
            return alloc
        if n_wanted > 3:                # lots of permutations?
            return []                   # give up

        # Look for some other permutation that satisfies them all.
        for perm in islice(permutations(range(n_wanted)), 1, None):
            alloc = self._allocate_permutation(perm, request, matches)
            if alloc:                   # successful?
                return alloc
        return []                       # failure

    def _allocate_permutation(self, perm, request, matches):
        """ Try to allocate some permutation of resources for a *request*.

        :param perm: List of permuted resource indices for this
            *request*, like [0, 1, 2] or [1, 2, 0].
        :param request: Scheduler request object, some resources may
            include regular expression syntax.
        :type request: :class:`.ResourceReply`
        :param matches: List containing sets of the available
            resources matching each element of *request.msg.resources*.
        :returns: List of ``scheduler_msgs/Resource`` messages
            allocated, in requested order with platform info fully
            resolved; or ``[]`` if not everything is available.

        If successful, matching ROCON resources are allocated to this
        *request*.  Otherwise, the *request* remains unchanged.

        """
        # Copy the list of Resource messages and all their contents.
        alloc = copy.deepcopy(request.msg.resources)

        # Search in permutation order for some valid allocation.
        names_allocated = set([])
        for i in perm:
            # try each matching name in order
            for name in matches[i]:
                if name not in names_allocated:  # still available?
                    names_allocated.add(name)
                    alloc[i].platform_info = name
                    break               # go on to next resource
            else:
                return []               # failure: no matches work

        # successful: allocate to this request
        req_id = request.get_uuid()
        for resource in alloc:
            self.pool[resource.platform_info].allocate(req_id)
        return alloc                    # success

    def _match_list(self, resources):
        """
        Make a list containing sets of the available resources
        matching each element of *resources*.

        *What if list is empty?*

        :returns: List of :class:`set` containing names of matching
            resources, empty if any item cannot be satisfied.
        """
        matches = []
        for res_req in resources:
            match_set = self._match_subset(res_req)
            if len(match_set) == 0:     # no matches for this resource?
                return []               # give up
            matches.append(match_set)
        return matches

    def _match_subset(self, resource_msg):
        """
        Make a set of names of all available resources matching *resource_msg*.

        :param resource_msg: Resource message from a scheduler Request.
        :type resource_msg: ``scheduler_msgs/Resource``

        :returns: :class:`set` containing matching resource names.
        """
        avail = set()
        for res in self.pool.resources.values():
            if (res.status == CurrentStatus.AVAILABLE
                    and res.match(resource_msg)):
                avail.add(res.platform_info)
        return avail

    def release_request(self, request):
        """ Release all the resources owned by this *request*.

        :param request: Current owner of resources to release.
        :type request: :class:`.ResourceReply`

        Only appropriate when this *request* is being closed.
        """
        rq_id = request.get_uuid()
        for res in request.allocations:
            self.pool[res.platform_info].release(rq_id)

    def release_resources(self, resources):
        """ Release a list of *resources*.

        :param resources: List of ``scheduler_msgs/Resource`` messages.

        This makes newly allocated *resources* available again when
        they cannot be assigned to a request for some reason.
        """
        for res in resources:
            pool_res = self.pool[res.platform_info]
            pool_res.release()
