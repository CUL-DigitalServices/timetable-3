'''
Created on Oct 18, 2012

@author: ieb
'''
from django.views.generic.base import View
from timetables.models import Thing, EventSource
from django.http import HttpResponseNotFound, HttpResponseBadRequest,\
    HttpResponseForbidden
from django.shortcuts import render
from django.db import models
from timetables.backend import ThingSubject


class ViewThing(View):
    '''
    Renders a view of a things events based on its type.
    '''
    
    def get(self, request, thing, depth="0"):
        if not request.user.has_perm(Thing.PERM_READ,ThingSubject(fullpath=thing, depth=depth)):
            return HttpResponseForbidden("Denied")
        hashid = Thing.hash(thing)
        try:
            if depth == "0":
                thing = Thing.objects.get(pathid=hashid)
                typeofthing = thing.type
                if typeofthing is None:
                    typeofthing = "default"
                context = { "thing" : thing }
                try:
                    return  render(request, "student/things/thing-%s.html" % typeofthing, context) 
                except:
                    return  render(request, "student/things/thing-default.html" , context) 
            else:
                depth = int(depth)
                if depth > 10 or depth < 0:
                    return HttpResponseBadRequest("Sorry no more than 10 levels allowed")
                things = Thing.objects.filter(Thing.treequery([thing], max_depth=depth)).order_by("fullname")
                return render(request, "student/list-of-things.html", {"things": things})

        except Thing.DoesNotExist:
            return HttpResponseNotFound()


class ChildrenView(View):
    
    QUERY_RELATED = "t"
    
    def get(self, request, thing):
        if not request.user.has_perm(Thing.PERM_READ,ThingSubject(fullpath=thing,fulldepth=True)):
            return HttpResponseForbidden("Denied")
        try:
            thing = Thing.objects.get(pathid=Thing.hash(thing))
            relatedthings = frozenset()
            relatedsources = frozenset()
            
            related_path = request.GET[ChildrenView.QUERY_RELATED]
            if related_path:
                # Get the things linked to the thing supplied by EventTag or EventSourceTag
                # eventtag__event__eventtag__thing__in looks for things linked to the same event
                # eventsourcetag__eventsource__eventsourcetag__thing for things linked to the same eventsource
                related_children_q = Thing.treequery([related_path])
                related = Thing.objects.filter(related_children_q)
                
                contains_event_in_related = models.Q(
                        eventtag__event__eventtag__thing__in=related, 
                        eventtag__event__current=True)
                contains_eventseries_in_related = models.Q(
                        eventsourcetag__eventsource__eventsourcetag__thing__in=related, 
                        eventsourcetag__eventsource__current=True)

                relatedthings = frozenset(Thing.objects
                        .filter(contains_event_in_related |
                                contains_eventseries_in_related)
                        .values_list("fullpath", flat=True))
                
                # get all the sources that the target has related
                relatedsources = frozenset(EventSource.objects
                        .filter(eventsourcetag__thing__in=related, current=True)
                        .values_list("id", flat=True))
            
            
            # Currently the template renders sources after things. We may wish
            # to put them into one list and sort them as one. 
            context = {
                "things": Thing.objects.filter(parent__pathid=thing.pathid).prefetch_related(
                        "eventsourcetag_set__eventsource",
                        "thing_set__eventsourcetag_set__eventsource"
                ),
                "related" : relatedthings,
                "relatedsources" : relatedsources
            }
            return render(request, "student/list-of-things.html",
                          context)
        except Thing.DoesNotExist:
            return HttpResponseNotFound()
