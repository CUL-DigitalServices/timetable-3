'''
Created on Oct 18, 2012
Updated on 2013-08-27

@author: ieb, gcm23
'''
import json
import logging

from operator import itemgetter

from django.db import models
from django.http import HttpResponseNotFound, HttpResponseBadRequest,\
    HttpResponseForbidden, HttpResponse
from django.shortcuts import render
from django.views.generic.base import View
from timetables.backend import ThingSubject
from timetables.models import Thing, EventSource, EventSourceTag, ThingTag, sorted_naturally

log = logging.getLogger(__name__)

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
            
            raw_modules = Thing.objects.filter(parent__pathid=thing.pathid).prefetch_related(
                "eventsourcetag_set__eventsource",
                "thing_set__eventsourcetag_set__eventsource"
            )

            modules = []
            for raw_module in raw_modules:
                module = {
                    "id": raw_module.id,
                    "title": raw_module.fullname,
                    "fullpath": raw_module.fullpath,
                    "in_calendar": raw_module.fullpath in relatedthings
                }

                series = []
                for eventsourcetag in raw_module.eventsourcetag_set.all():
                    raw_series = eventsourcetag.eventsource
                    single_series = {
                        "id": raw_series.id,
                        "title": raw_series.title,
                        "date_pattern": raw_series.metadata.get("datePattern", ""),
                        "location": raw_series.metadata.get("location", ""),
                        "people": raw_series.metadata.get("people", []),
                        "in_calendar": raw_series.id in relatedsources
                    }
                    series.append(single_series)

                module["series"] = sorted_naturally(series, key=itemgetter("title"))
                modules.append(module)

            raw_links = ThingTag.objects.filter(annotation="link", thing=thing)
            links = []

            for raw_link in raw_links:
                target = raw_link.targetthing
                if target.type == "part":
                    name = target.parent.fullname + ", " + target.fullname
                else:
                    name = target.fullname + " " + "(" + target.parent.parent.fullname + "), " + target.parent.fullname
                link = {
                    "fullpath": target.fullpath,
                    "name": name
                }

                links.append(link)

            context = {
                "modules": sorted_naturally(modules, key=itemgetter("title")),
                "links": sorted_naturally(links, key=itemgetter("name"))
            }
            return render(request, "student/modules-list/base.html", context)
        except Thing.DoesNotExist:
            return HttpResponseNotFound()

class SeriesSubjectTitle(View):
    """
    Used to retrieve the title of the identified EventSource (series)
    """

    def get(self, request, series_id):
        # get the Thing data
        tags = EventSourceTag.objects.\
            filter(eventsource=series_id, annotation="home").\
            prefetch_related("thing", "thing__parent", "thing__parent__parent",
            "thing__parent__parent__parent")[:2] # eek :s

        # return 404 if not found
        if len(tags) == 0:
            return HttpResponseNotFound()

        # log if we have more than one hit
        if len(tags) > 1:
            log.warning("Series with id %s has multiple parent Things",
                        series_id)

        # get the subject object
        subject = tags[0].thing.parent.as_subject()
        subject_title = subject.get_name_without_part()+"; "+subject.get_part().fullname

        # return data
        response = {
            "subject": subject_title,
            "series_id": series_id
        }

        return HttpResponse(json.dumps(response), mimetype="application/json")
