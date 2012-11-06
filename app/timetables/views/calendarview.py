import calendar
import itertools

from django.http import HttpResponseNotFound, HttpResponse,\
    HttpResponseForbidden
from django.shortcuts import render
from django.utils import simplejson as json
from django.utils import timezone
from django.utils.datastructures import SortedDict
from django.utils.datetime_safe import datetime, date
from django.views.generic.base import View

from timetables.models import HierachicalModel, Thing
from timetables.utils.Json import JSON_CONTENT_TYPE, JSON_INDENT
from timetables.utils.date import DateConverter
from timetables.utils import datetimes
from timetables.backend import HierachicalSubject


class CalendarView(View):
    '''
    Renders a json stream suitable for use in the calendar.
    '''
    
    @classmethod
    def to_fullcalendar(cls, event):
        metadata = event.metadata
        allday = bool(metadata.get("x-allday"))
        lecturer = metadata.get("people") or []
        eventtype = metadata.get("type") or False
        if allday:
            return {
                "djid": event.id,
                "title" : event.title,
                "allDay" : True,
                "start" : DateConverter.from_datetime(event.start_local(), True).isoformat(),
                "location" : event.location,
                "lecturer" : lecturer,
                "type" : eventtype
            }
        else:
            return {
                "djid": event.id,
                "title" : event.title,
                "allDay" : False,
                "start" : DateConverter.from_datetime(event.start_local(), False).isoformat(),
                "end" : DateConverter.from_datetime(event.end_local(), False).isoformat(),
                "start_origin" : DateConverter.from_datetime(event.start_origin(), False).isoformat(),
                "end_origin" : DateConverter.from_datetime(event.end_origin(), False).isoformat(),
                "starttz" : event.starttz,
                "endtz" : event.endtz,
                "location" : event.location,
                "lecturer" : lecturer,
                "type" : eventtype
            }
    
    def get(self, request, thing):
        if not request.user.has_perm(HierachicalModel.PERM_READ,HierachicalSubject(fullpath=thing)):
            return HttpResponseForbidden("Denied")
        hashid = HierachicalModel.hash(thing)
        try:
            thing = Thing.objects.get(pathid=hashid)
            def generate():
                yield "[\n"
                # TODO: Support ranges
                pattern = "%s"
                for e in thing.get_events():
                    event_obj = self.to_fullcalendar(e)
                    event_obj["className"] = "thing_%s" % thing.type
                    yield pattern % json.dumps(event_obj, indent=JSON_INDENT)
                    pattern = ",\n%s"
                yield "]\n"




            response = HttpResponse(generate(),content_type=JSON_CONTENT_TYPE)
            response.streaming = True
            return response

        except Thing.DoesNotExist:
            return HttpResponseNotFound()


class CalendarHtmlView(View):
    '''
    Renders a calendar view of the events associated with the thing.
    '''
    
    def get(self, request, thing, depth="0"):
        if not request.user.has_perm(HierachicalModel.PERM_READ,HierachicalSubject(fullpath=thing,depth=depth)):
            return HttpResponseForbidden("Denied")
        hashid = HierachicalModel.hash(thing)
        try:
            return  render(request, "calendar.html",  { "thing" : Thing.objects.get(pathid=hashid) }) 
        except Thing.DoesNotExist:
            return HttpResponseNotFound()

class EventListView(View):
    '''
    Renders an event list view of events associated with a thing.
    '''
    
    def get(self, request, thing):
        if not request.user.has_perm(HierachicalModel.PERM_READ,HierachicalSubject(fullpath=thing)):
            return HttpResponseForbidden("Denied")
        year = request.GET.get("y") or None
        month = request.GET.get("m") or None

        assert not bool(year) ^ bool(month), "provide both or neither year, month"
        # Default to current month/year if not provided
        now = datetimes.server_datetime_now()
        year = int(year or now.year)
        month = int(month or now.month)

        hashid = HierachicalModel.hash(thing)
        try:
            return render(request, "event-list.html", {
                        "calendar": MonthListCalendar(year, month, Thing.objects.get(pathid=hashid).get_events())
                        })
        except Thing.DoesNotExist:
            return HttpResponseNotFound()


class MonthListCalendar(object):
    """
    Models the data shown in the calendar list page. i.e. a list of events under
    a month grouped by day, and a calendar representation.
    """
    def __init__(self, year, month, events, firstweekday=0):
        """
        Args:
            year: The numeric year of this calendar. 
            month: The numeric month of this calendar. range: [1,12]
            events: A sequence of Event objects. These should start inside the
                specified year & month. If not provided
        """
        self._month = month
        self._year = year
        self._cal = calendar.Calendar(firstweekday)
        start, end = self._month_range(year, month)
        self._events = events.in_range(start, end).order_by("start")
        
        # It's required that _events be sorted by starting date/time
        self.events_by_day = self._bucket_into_days(self.events)

    
    def _month_range(self, year, month):
        """
        Returns: a 2 pair of datetime objects at the start and end of the
            specified month (inclusive).
        """
        _, length = calendar.monthrange(year, month)
        return (datetime(year, month, 1),
                datetime(year, month, length, 23, 59, 59, 1000000 - 1))
    
    @property
    def month(self):
        return self._month
    
    @property
    def year(self):
        return self._year
    
    @property
    def events(self):
        """
        Returns: A sequence of the known Event model instances which are in this
            month.
        """
        return (e for e in self._events if self._event_in_month(e))

    def _event_in_month(self, event):
        datetime = event.start_local()
        return datetime.month == self.month and datetime.year == self.year

    @staticmethod
    def event_day(event):
        "Returns: The numeric day of the month the Event instance starts on."
        return event.start_local().day

    @staticmethod
    def _bucket_into_days(all_events):
        """
        Args:
            all_events: A sequence of Event objects.
        Returns: A (sorted) dictionary whose keys are days in a month (integers)
            and values are a list of events starting on the key's day.
        """
        by_day = itertools.groupby(all_events, MonthListCalendar.event_day)
        return SortedDict((day, list(events)) for (day, events) in by_day)
    
    def month_day(self, day):
        """
        Returns: A MonthDay instance for the specified day of this month.
        """
        return MonthListCalendar.MonthDay(self, day)
    
    def month_days(self):
        """
        Enumerates MonthDay instances for days of the month with at least one
        event.
        """
        for day in self.events_by_day.keys():
            yield self.month_day(day)
    
    def calendar_week_days(self):
        """
        Yields: The order of days in this calendars week. Values are integers
            where 0 is Monday and 6 is Sunday.
        """
        return self._cal.iterweekdays()
    
    def calendar_week_days_names(self):
        return (["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
                "Saturday", "Sunday"][day] for day in self.calendar_week_days())
                
    
    def calendar_month_days(self):
        """
        Generates a sequence of the days in a grid month calendar where cells
        representing days in preceding or subsequent months are None and days in
        our month are MonthDay instances. 
        
        The output is effected by the firstweekday init param.
        
        This works in the same way as the calendar module's 
        Calendar.itermonthdays method.
        """
        for day in self._cal.itermonthdays(self.year, self.month):
            if day == 0:
                yield None
            else:
                yield self.month_day(day)
    
    def calendar_month_days_by_row(self):
        """
        As calendar_month_days() except instead of producing one long sequence,
        multiple 7 day sequences are yielded.
        """
        # Break the complete sequence of month_days() into 7 day blocks
        for (_, row) in itertools.groupby(enumerate(self.calendar_month_days()),
                lambda (i,_): i/7):
            yield [monthday for (_, monthday) in row]
            
    
    def start_date(self):
        return date(self.year, self.month, 1)
    
    def next_month(self):
        return (self.month % 12) + 1
    def prev_month(self):
        return ((self.month - 2) % 12) + 1
    def next_year(self):
        return self.year + 1 if self.month == 12 else self.year
    def prev_year(self):
        return self.year - 1 if self.month == 1 else self.year
    
    class MonthDay(object):
        """
        Represents the events associated with a specific day of a month.
        """
        def __init__(self, monthlistcal, day):
            self.monthlistcal = monthlistcal
            self.day = day
        
        def has_events(self):
            """
            Returns: True if this day has any events in it.
            """
            return len(self.events()) > 0
        
        def events(self):
            """
            Returns: A sequence of events that occur in this MonthDay's day.
            """
            return self.monthlistcal.events_by_day.get(self.day, [])
        
        def date(self):
            """
            Returns: A datetime.date instance at the day this MonthDay is at.
            """
            return date(self.monthlistcal.year, self.monthlistcal.month,
                    self.day)
