define([
	"jquery",
	"underscore",
	"view/admin/components/calendarComponents/listView",
	"view/admin/components/calendarComponents/adminCalendarContent",
	"view/admin/components/calendarComponents/adminCalendarHeading"
], function ($, _, ListView, CalendarContent, AdminCalendarHeading) {

	var AdminCalendar = function (opt) {
		_.extend(this, opt);
		this.initialize();
	};

	_.extend(AdminCalendar.prototype, {
		initialize: function () {
			_.defaults(this, {
				listView: new ListView({
					selector: "#adminListView"
				}),
				content: new CalendarContent({
					selector: "#calendar",
					parent: this
				}),
				heading: new AdminCalendarHeading({
					selector: this.headingSelector,
					parent: this
				}),
				selector: "body",
				$el: $(this.selector)
			});
		}
	});

	return AdminCalendar;
});