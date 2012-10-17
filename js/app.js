$(function () {
	"use strict";

	//populate results list
	(function populateResults(toAdd) {
		var i,
			$singleResult = $('#results > ul > li');

		for (i = 0; i < toAdd; i += 1) {
			$('#results > ul').append($singleResult.clone());
		}
	}(12));

	//initiate fullcalendar
	$('#calendar').fullCalendar({
		defaultView: 'agendaWeek',
		allDaySlot: false,
		minTime: 7,
		maxTime: 20,
		header: false,
		columnFormat: {
			week: 'ddd dd/M'
		}
	});

	$('#calendarData a').click(function (event) {
		switch ($(this).text()) {
		case '<':
			$('#calendar').fullCalendar('prev');
			break;
		case '>':
			$('#calendar').fullCalendar('next');
			break;
		}
	});

	$('#calendarHolder .nav a').click(function (event) {
		if ($(this).parent().is('.active') === false) {
			$('#calendarHolder .nav li').removeClass('active');
			$(this).parent().addClass('active');

			switch ($(this).text().toLowerCase()) {
			case 'week':
				$('#calendar').fullCalendar('changeView', 'agendaWeek');
				break;
			case 'month':
				$('#calendar').fullCalendar('changeView', 'month');
				break;
			case 'list':
				break;
			}
		}

		event.preventDefault();
	});

	$('a[href="#"]').click(function (event) {
		event.preventDefault();
	});

});
