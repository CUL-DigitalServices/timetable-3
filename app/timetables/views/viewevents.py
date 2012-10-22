'''
Created on Oct 18, 2012

@author: ieb
'''
from django.views.generic.base import View
from timetables.models import HierachicalModel, Thing
from django.http import HttpResponseNotFound
from django.shortcuts import render


class ViewEvents(View):
    '''
    Renders a view of a thing based on its type.
    '''
    
    def get(self, request, thing):
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
