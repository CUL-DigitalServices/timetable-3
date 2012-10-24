from django.conf.urls.defaults import patterns, include, url

# Enable Django's admin interface
from django.contrib import admin
from django.views.decorators.csrf import csrf_exempt

from timetables.utils.repo import RepoView
from timetables.views.exportevents import ExportEvents
from timetables.views.linkthing import LinkThing
from timetables.views.viewthing import ViewThing, ChildrenView
from timetables.views.viewevents import ViewEvents
from timetables.views.indexview import IndexView
from timetables.views.adminview import AdminView
from timetables.views.calendarview import CalendarView, CalendarHtmlView


admin.autodiscover()

urlpatterns = patterns('',

    url(r"^$", IndexView.as_view(), name="thing view default"),
    url(r"^index.html$", IndexView.as_view(), name="thing view index"),

    url(r"^editor$", AdminView.as_view(), name="admin"),
    url(r"^editor/index.html$", AdminView.as_view(), name="admin"),

    # Django admin interface (NOT timetables administrators)
    url(r'^admin/', include(admin.site.urls)),
    url(r'^admin/doc/', include('django.contrib.admindocs.urls')),


    # This has to be csrf exempt. Look at the view to see what it does.
    url(r'repo/(?P<key>.*)', csrf_exempt(RepoView.as_view()), name="REPO"),
    
    url(r'(?P<thing>.*)\.events\.ics$', ExportEvents.as_view(), name="export ics"),
    url(r'(?P<thing>.*)\.events\.csv$', ExportEvents.as_view(), name="export csv"),
    url(r'(?P<thing>.*)\.events\.json$', ExportEvents.as_view(), name="export json"),
    # View of the things events
    url(r'(?P<thing>.*)\.events\.html$', ViewEvents.as_view(), name="thing events view"),
    # Generate an Html view of children
    url(r'(?P<  >.*?)\.children\.html$', ChildrenView.as_view(), name="thing childen view"),
    url(r'(?P<thing>.*?)\.cal\.json', CalendarView.as_view(), name="thing calendar view"),
    url(r'(?P<thing>.*?)\.cal\.html', CalendarHtmlView.as_view(), name="thing calendar htmlview"),


    # Generate an Html view of things
    url(r'(?P<thing>.*?)\.(?P<depth>.*)\.html$', ViewThing.as_view(), name="thing depth view"),
    
    # Update service end points
    url(r'(?P<thing>.*)\.link$', LinkThing.as_view(), name="thing link"),
    # View of the thing
    url(r'(?P<thing>.*)\.html$', ViewThing.as_view(), name="thing view"),
    
)
