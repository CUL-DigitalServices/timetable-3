import itertools

import dateutil.parser

from userstats import base
from userstats.utils import ilen, window, average


class StartYearOperationListEnumerator(base.OperationListEnumerator):
    def enumerate_operation_lists(self, dataset):
        years = self.enumerate_values(dataset)
        return [[StartYearFilterOperation(year)] for year in years]

    def enumerate_values(self, dataset):
        years = set(
            user.get("start_year")
            for user in dataset.get_data()
            if "start_year" in user)
        return sorted(years)


class TriposOperationListEnumerator(base.OperationListEnumerator):
    def enumerate_operation_lists(self, dataset):
        triposes = self.enumerate_values(dataset)
        return [[TriposFilterOperation(tripos)] for tripos in triposes]

    def enumerate_values(self, dataset):
        triposes = set(
            plan["name"]
            for user in dataset.get_data()
            for plan in user.get("plans", [])
            if "name" in plan and plan["name"]
        )
        return sorted(triposes)


class ICalendarOperationListEnumerator(base.OperationListEnumerator):
    def enumerate_operation_lists(self, dataset):
        return [[ICalendarFetchPivotOperation()]]


class StartYearFilterOperation(base.FilterOperation):
    """
    A filter operation which includes users with a specified starting year.
    """
    def get_description(self):
        return "Filter by start year = {}".format(self.get_filter_value())

    def is_included(self, value):
        return value.get("start_year") == self.get_filter_value()


class TriposFilterOperation(base.FilterOperation):
    """
    A filter operation which includes users with a specified tripos.
    """
    def get_description(self):
        return "Filter by tripos = {}".format(self.get_filter_value())

    def is_included(self, value):
        return any(plan.get("name") == self.get_filter_value()
                   for plan in value.get("plans", []))


class ICalendarFetchPivotOperation(base.PivotOperation):
    """
    Pivot the by-user data into a list of individual ical fetches.

    Also parse "datetime" ISO date strings into actual datetime objects.
    """
    def get_description(self):
        return "Pivot by-user data to list of iCalendar fetches"

    def parse_date_string(self, fetch):
        assert isinstance(fetch, dict), (fetch,)
        parsed = dateutil.parser.parse(fetch["datetime"])
        return dict(
            (k, v if k != "datetime" else parsed)  # insert parsed datetime
            for k, v in fetch.iteritems()
        )

    def apply(self, data):
        fetches = (
            ical_fetch
            for user in data
            for ical_fetch in user.get("ical_fetches", [])
        )

        fetches = (
            self.parse_date_string(fetch) for fetch in fetches
        )
        return list(fetches)


def get_years_drilldown():
    return base.Drilldown(
        "years", StartYearOperationListEnumerator(), TimetableStats.factory)



class AverageICalFetchIntervalStatValue(base.StatValue):
    """
    Calculates the average number of seconds between iCal fetches.
    """
    name = "average_calendar_fetch_interval"

    def get_value(self, data):
        averages = list(self.get_per_calendar_subscriber_averages(data))

        if len(averages) == 0:
            return None
        # We want the average of the average fetch interval for each ical feed
        return average(averages)

    def get_per_calendar_subscriber_averages(self, data):
        # Group by crsid and user_agent so that we get intervals between fetches
        # for a sepecific user's calendar from a specific requester.
        # This is not fool proof, as a calendar may be added multiple times to
        # different instances of the same client. e.g. to Outlook on > 1
        # computer. The remote_host could help differentiate between requesters
        # in this instance, except it's likely to change too often to be useful.
        # Also web based providers may well use multiple servers to request
        # feeds.
        key = lambda fetch: (fetch["crsid"], fetch["user_agent"])
        data = sorted(data, key=key)

        for user, fetches in itertools.groupby(data, key=key):
            average_interval = self.get_average_fetch_interval(fetches)
            if average_interval is not None:
                yield average_interval

    def get_average_fetch_interval(self, fetches):
        intervals = window(fetch["datetime"] for fetch in fetches)
        deltas = [end - start for start, end in intervals]
        if len(deltas) == 0:
            return None
        return average(deltas, division_type=int).total_seconds()


class TotalStatValue(base.StatValue):
    def get_value(self, data):
        return len(data)


class TotalICalFetchesStatValue(TotalStatValue):
    name = "total_ical_fetches"


class TotalUsersStatValue(TotalStatValue):
    name = "total_users"


class TotalUsersWithCalendar(base.StatValue):
    name = "total_users_with_calendar"

    def get_value(self, data):
        return ilen(user for user in data
                    if len(user.get("calendar", [])) > 0)


class TotalUsersWithICalFetch(base.StatValue):
    name = "total_users_with_ical_fetch"

    def get_value(self, data):
        return ilen(user for user in data
                    if len(user.get("ical_fetches", [])) > 0)

ical_stat_values = [
    AverageICalFetchIntervalStatValue()
]

def ical_stats_factory(dataset):
    drilldowns = [
    ]

    return base.Stats(
        dataset,
        ical_stat_values,
        drilldowns
    )

# Default stat values used by all the drilldown levels
timetable_stat_values = [
    TotalUsersStatValue(),
    TotalUsersWithCalendar(),
    TotalUsersWithICalFetch()
]

def lvl2_tripos_stats_factory(dataset):
    drilldowns = [
    ]

    return base.Stats(
        dataset,
        timetable_stat_values,
        drilldowns
    )


def lvl2_year_stats_factory(dataset):
    drilldowns = [
    ]

    return base.Stats(
        dataset,
        timetable_stat_values,
        drilldowns
    )


def lvl1_tripos_stats_factory(dataset):
    drilldowns = [
        base.Drilldown(
            "years",
            StartYearOperationListEnumerator(),
            lvl2_year_stats_factory
        )
    ]

    return base.Stats(
        dataset,
        timetable_stat_values,
        drilldowns
    )


def lvl1_year_stats_factory(dataset):
    drilldowns = [
        base.Drilldown(
            "tripos",
            TriposOperationListEnumerator(),
            lvl2_tripos_stats_factory
        )
    ]

    return base.Stats(
        dataset,
        timetable_stat_values,
        drilldowns
    )


def root_stats_factory(dataset):
    drilldowns = [
        base.Drilldown(
            "years",
            StartYearOperationListEnumerator(),
            lvl1_year_stats_factory
        ),
        base.Drilldown(
            "tripos",
            TriposOperationListEnumerator(),
            lvl1_tripos_stats_factory
        ),
        base.Drilldown(
            "iCalendar",
            ICalendarOperationListEnumerator(),
            ical_stats_factory
        )
    ]

    return base.Stats(
        dataset,
        timetable_stat_values,
        drilldowns
    )
