'''
Created on Oct 18, 2012

@author: ieb
'''
from django.views.generic.base import View
from timetables.models import HierachicalModel, Thing
from django.http import HttpResponseNotFound, HttpResponseForbidden
from django.shortcuts import render
from timetables.backend import HierachicalSubject


class ViewEvents(View):
    '''
    Renders a view of a thing based on its type.
    '''
    
    def get(self, request, thing):
        if not request.user.has_perm(HierachicalModel.PERM_READ,HierachicalSubject(fullpath=thing)):
            return HttpResponseForbidden("Denied")
        hashid = HierachicalModel.hash(thing)
        try:
            thing = Thing.objects.get(pathid=hashid)
            typeofthing = thing.type
            if typeofthing is None:
                typeofthing = "default"
            context = { "thing" : thing,
                       "events" : thing.get_events() }
            try:
                return  render(request, "things/thing-events-%s.html" % typeofthing, context)
            except:
                return  render(request, "things/thing-events-default.html" , context)
                
        except Thing.DoesNotExist:
            return HttpResponseNotFound()

