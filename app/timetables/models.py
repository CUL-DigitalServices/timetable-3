# This is the holder for the model.

import hashlib
import base64
import os
import time
import itertools

from django.db import models
from django.db.models.signals import pre_save
from django.conf import settings
from django.utils import simplejson as json

import logging
log = logging.getLogger(__name__)

# Length of a hash required to idedentify items.
# The item can be retrieved by hashing an external identifier and selecting
# based on the hash. This allows simple linking of data where we dont know the source.
HASH_LENGTH=64
# Maximum length of paths.
MAX_PATH_LENGTH=2048
# Maximum length of URLs
MAX_URL_LENGTH=2048
# 
MAX_NAME_LENGTH=32
# Size of long names
MAX_LONG_NAME=512
# Size of a UID, some ical feeds generate massive ones.
MAX_UID_LENGTH=512
# Max length of a Thing's type
THING_TYPE_LENGTH=12


class HierachicalModel(models.Model):
    class Meta:
        abstract=True
    # Things are hierarchical, so may have parents
    parent = models.ForeignKey("Thing",blank=True, null=True, help_text="The parent of this thing, leave as none for a top level thing.")
    # So that we can access deep into the hierarchy we have a pathid such that hash(path) = fullpath 
    pathid = models.CharField(max_length=HASH_LENGTH,unique=True, help_text="Unique Key for the thing, system generated")
    # This is the full path, for reference only, do not select on this, use the pathid
    fullpath = models.CharField(max_length=MAX_PATH_LENGTH, help_text="Path of this thing, system generated")
    # The name of the Thing. It will match the last element of fullpath. Its limited in length and not the full name. Think of it as the URL element.
    name = models.CharField(max_length=MAX_NAME_LENGTH, help_text="short name of this thing, used in the path and urls")


    @classmethod
    def hash(cls, key):
        m = hashlib.sha1()
        m.update(key)
        return base64.urlsafe_b64encode(m.digest())
    
    @classmethod
    def _prepare_save(cls, sender, **kwargs):
        instance = kwargs['instance']
        if instance.pathid is None or instance.pathid == "":
            instance.pathid = HierachicalModel.hash(instance.fullpath)
            instance.name = os.path.basename(instance.fullpath)

    def __unicode__(self):
        return self.fullpath


class SchemalessModel(models.Model):
    class Meta:
        abstract=True
    # A block of objects, all the meta data associated with this thing.
    # This avoids forcing all objects to have the same schema.
    data = models.TextField(blank=True, help_text="Additional data in json format")
     
    
    @property
    def metadata(self):
        '''
        Get the medata data 
        '''
        if not hasattr(self,"_data") or self._data is None:
            if self.data is None or self.data == "":
                self._data = dict()
            else:
                try:
                    self._data = json.loads(self.data)
                except:
                    self._data = dict()
        return self._data
    
    def update_fields(self):
        '''
        Override this if there are fields that need to be updated from the metadata
        '''
        pass
        
    @classmethod
    def _prepare_save(cls, sender, **kwargs):
        '''
        Called before save and makes certain data contains a pickled version of _data
        '''
        instance = kwargs['instance']
        if hasattr(instance,"_data") and instance._data is not None:
            instance.update_fields()
            instance.data = json.dumps(instance._data)
        else:
            instance.data = ""
        


class Thing(SchemalessModel, HierachicalModel):
    '''
    I have no idea what I should call this, Node, Name, Category, Noun... so I am choosing a Thing.
    This is the "Language with which we refer to events."
    
    Things include:
        tripos
        users
        rooms
        source
        
    to find a users timetable, given the thing that represents the users timetable will be
    
    Event.objects.filter(models.Q(source__eventsourcetag__thing=userthing)|models.Q(eventtag__thing=userthing)).order_by(start)
    
    to find the aggregate table of a bunch of things
    Event.objects.filter(models.Q(source__eventsourcetag__thing__in=bunchofthings)|models.Q(eventtag__thing__in=bunchofthings)).order_by(start)


    If we want to apply permissions, they should be applied to Things.
    Probably in a separate Hierarchical model, where the permission is resolved hierarchically.
    '''
    type = models.CharField("Type",
            max_length=THING_TYPE_LENGTH, blank=True, db_index=True, default="", help_text="The type of the thing used to control its behavior")

    # Full name of this thing.
    fullname = models.CharField("Full Name", max_length=2048,help_text="Full name of the thing, to be displayed to end users.")
    
    
    def get_events(self):
        return Event.objects.filter(models.Q(source__eventsourcetag__thing=self)|
                                    models.Q(eventtag__thing=self))
        
    @classmethod
    def get_all_events(cls, things):
        return Event.objects.filter(models.Q(source__eventsourcetag__thing__in=things)|
                                    models.Q(eventtag__thing__in=things))

    def prepare_save(self):
        Thing._pre_save(Event,instance=self)

        
    @classmethod
    def _pre_save(cls, sender, **kwargs):
        # Invoking multiple parent class or instnace methods is broken in python 2.6
        # So this is the only way
        HierachicalModel._prepare_save(sender,**kwargs)
        SchemalessModel._prepare_save(sender,**kwargs)
        log.debug("Done Calling Super on Pre-save")

        
        
pre_save.connect(Thing._pre_save, sender=Thing)

def _get_upload_path(instance, filename):
    
    tpart = time.strftime('%Y/%m/%d',time.gmtime())
    return "%s%s/%s" % ( settings.MEDIA_ROOT, tpart , HierachicalModel.hash(filename))

class EventSource(SchemalessModel):
    TYPES = (
        ('U', 'Url'),
        ('F', 'Upload'),
        ('S', 'Server Loaded'),
    )
    sourceid = models.CharField("Where the event came from", max_length=HASH_LENGTH, help_text="Brief description of the source, may be generated by the server")
    sourcetype = models.CharField("Type of source that created this item", max_length=1, choices=TYPES, help_text="The type of feed, currently only Url and Upload are supported.")
    # source url if the Event Source was loaded
    sourceurl = models.URLField("Url", max_length=MAX_URL_LENGTH, blank=True,null=True, help_text="If not uploading, enter a URL where the server can pull the events from, must be an ical feed.")
    # local copy of the file.
    
    sourcefile = models.FileField(upload_to=_get_upload_path, verbose_name="iCal file", help_text="Upload an Ical file to act as a source of events")
    
    def __unicode__(self):
        try:
            return "%s (%s bytes)" % ( self.sourceid, self.sourcefile.size)
        except:
            return "%s" % ( self.sourceid)
            
    def prepare_save(self):
        EventSource._pre_save(Event,instance=self)


    @classmethod
    def _pre_save(cls, sender, **kwargs):
        # Invoking multiple parent class or instnace methods is broken in python 2.6
        # So this is the only way
        SchemalessModel._prepare_save(sender,**kwargs)

        
pre_save.connect(EventSource._pre_save, sender=EventSource)
    
    

class Event(SchemalessModel):
    '''
    Events are the most basic representation of a physical event. Events have a start and an end.
    These are not metaevents with repeats
    Also, there could be 1000s of these in memory at anyone time, so we must not add a manager or do anything 
    that could increase the memory footprint more than necessary. Even the text field may be bad.
    '''
    # Basic Metadata that we need to operate on this event
    start = models.DateTimeField(help_text="Start of the Event")
    end = models.DateTimeField(help_text="End of the Event")
    title = models.CharField(max_length=MAX_LONG_NAME, help_text="Title of the event")
    location = models.CharField(max_length=MAX_LONG_NAME, help_text="Location of the event")
    uid = models.CharField(max_length=MAX_UID_LENGTH, help_text="The event UID that may be generated or copied from the original event in the Event Source")
    
    # Relationships
    # source is where the source comes from and contain the default tag.
    # this is dont to reduce the size of teh EventTag tables.
    source = models.ForeignKey(EventSource, verbose_name="Source of Events", help_text="The Event source that created this event",  blank=True, null=True)
    
    
    def __unicode__(self):
        return "%s %s %s - %s " % ( self.title, self.location, self.start, self.end)
    
    def prepare_save(self):
        Event._pre_save(Event,instance=self)
    
    @classmethod
    def _pre_save(cls, sender, **kwargs):
        # Invoking multiple parent class or instnace methods is broken in python 2.6
        # So this is the only way
        SchemalessModel._prepare_save(sender,**kwargs)
        instance = kwargs['instance']
        if instance.uid is None or instance.uid == "":
            instance.uid = HierachicalModel.hash("%s@%s" % (time.time(), settings.INSTANCE_NAME)) 

        
pre_save.connect(Event._pre_save, sender=Event)
    
    
    
class EventSourceTag(models.Model):
    '''
    EventTag could get huge. In many cases tings will need to be connected with a large set of orriginal
    events. This can be done via EventSourceTag which will connect to many events since there is a source
    '''
    thing = models.ForeignKey(Thing, help_text="The Thing that the EventSource is to be associated with")
    eventsource = models.ForeignKey(EventSource, verbose_name="Source of Events", help_text="The EventSource that the Thing is to be associated with")

    def prepare_save(self):
        pass # If you add a pre_save hook, please wire this method into it

    
class EventTag(models.Model):
    '''
    Where the connection between thing and event is not represented via EventSourceTag and explicit connection
    can me made, via Event tag.
    '''
    thing = models.ForeignKey(Thing, help_text="The Thing that the Event is to be associated with")
    event = models.ForeignKey(Event, help_text="The Event that the Thing is to be associated with")
    def prepare_save(self):
        pass # If you add a pre_save hook, please wire this method into it
    
    
def subjects():
    """
    Gets a sequence of all subjects.
    
    Subjects are grouped by tripos, and IDs are specified for the level the
    subject is under.
    
    Returns: A sequence containing objects of the form:
        {
            "tripos_name": "Natural Sciences Tripos",
            "subject_name": "Chemistry",
            "subject_ids_by_level": [
                {"subject_id": 1234, "level_name": "IA"}
            ]
        }
    """
    # Fetch subject name, subject id, subject's parent level name and subject's parent level's parent tripos name
    subject_values = (Thing.objects.filter(type__in=["subject", "experimental", "option"])
            .order_by("fullname", "parent__parent__fullname", "parent__fullname")
            .values("fullname", "id", "parent__fullname", "parent__parent__fullname"))
    
    # Group together subjects under the same tripos with the same name.
    for _, subjects in itertools.groupby(subject_values, 
            lambda s: (s["fullname"], s["parent__parent__fullname"])):
        tripos_name = None
        subject_name = None
        subject_ids_by_level = []
        
        for subject in subjects:
            tripos_name = tripos_name or subject["parent__parent__fullname"]
            subject_name = subject_name or subject["fullname"]

            subject_ids_by_level.append({
                "subject_id": subject["id"], 
                "level_name": subject["parent__fullname"]
            })
        
        yield {
            "tripos_name": tripos_name,
            "subject_name": subject_name,
            "subject_ids_by_level": subject_ids_by_level
        }

