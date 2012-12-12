define(["jquery", "underscore", "backbone", "util/django-forms", "util/assert"],
		function($, _, Backbone, DjangoForms, assert) {
	"use strict";

	/** Strip leading zeros from an integer such as: 01, 05, 005 etc. */
	function stripZeros(str) {
		var groups = /0*(\d+)/.exec(str);
		if(!groups)
			return undefined;
		return groups[1];
	}

	/** As parseInt() except handles strings with leading zeros correctly. */
	function safeParseInt(str) {
		return parseInt(stripZeros(str));
	}

	/**
	 * Wraps a .js-module in the page to update the "> v" arrows when the
	 * module's content is shown/hidden. The actual showing/hiding is done by
	 * Bootstrap's collapse plugin.
	 */
	var ModuleView = Backbone.View.extend({
		constructor: function ModuleView() {
			ModuleView.__super__.constructor.apply(this, arguments);
		},

		events: function() {
			return {
				"show .js-module-content": this.onExpand,
				"hide .js-module-content": this.onCollapse,
				"shown .js-module-content": this.onShown
			};
		},

		initialize: function() {
			_.bindAll(this, "onExpand", "onCollapse");

			this.$expansionIndicator = this.$(
					".js-module-heading .js-expansion-indicator")
		},

		onExpand: function() {
			this.$expansionIndicator
				.removeClass("icon-chevron-right")
				.addClass("icon-chevron-down");
		},

		onCollapse: function() {
			this.$expansionIndicator
				.removeClass("icon-chevron-down")
				.addClass("icon-chevron-right");
			this.$(".js-module-content").removeClass("shown");
		},

		onShown: function() {
			this.$(".js-module-content").addClass("shown");
		}
	});
	
	var SeriesView = Backbone.View.extend({
		constructor: function SeriesView() {
			SeriesView.__super__.constructor.apply(this, arguments);
		},

		events: function() {
			return {
				"show .js-events": this.onExpand,
				"shown .js-events": this.onShown,
				"hide .js-events": this.onCollapse,
			};
		},

		initialize: function() {
			_.bindAll(this);
		},

		isLoaded: function() {
			return this.$("table").length > 0;
		},

		isLoading: function() {
			return this.$(".js-loading-indicator").length > 0;
		},

		getSeriesId: function() {
			return this.$el.data("series-id");
		},

		/**
		 * Called when the series is first expanded in order to load events via
		 * AJAX.
		 */
		loadEvents: function() {
			// First we need to insert the loading indicator...
			
			// Find and copy the global loading indicator HTML
			var loadingEl = $(".js-loading-indicator-prototype").clone()
				.show()
				.removeClass("js-loading-indicator-prototype");
			this.loadingIndicator = new LoadingIndicatorView({el: loadingEl});
			this.$(".js-events").empty().append(this.loadingIndicator.el);
			this.loadingIndicator.on("retry", this.startEventsRequest, this);

			// Make the HTTP request to fetch the events
			this.startEventsRequest();
		},

		getEventsRequestOptions:  function() {
			return {};
		},

		startEventsRequest: function() {
			this.loadingIndicator.showLoadingState();

			// make the ajax request to fetch the events
			$.ajax("/series/" + encodeURIComponent(this.getSeriesId()) 
				+ "/list-events", this.getEventsRequestOptions())
				.done(this.onEventsFetched)
				.fail(this.onEventsFetchFailed);
		},

		onEventsFetched: function(response) {
			delete this.loadingIndicator;
			this.$(".js-loading-indicator").remove();
			this.$(".js-events").prepend(response);
		},

		onEventsFetchFailed: function() {
			this.loadingIndicator.showErrorState();
		},

		onExpand: function(event) {
			event.stopPropagation();
			this.$(".js-expansion-indicator")
				.removeClass("icon-chevron-right")
				.addClass("icon-chevron-down");

			if(this.isLoaded() || this.isLoading()) {
				return;
			}

			this.loadEvents();
		},

		onCollapse: function(event) {
			event.stopPropagation();
			this.$(".js-expansion-indicator")
				.removeClass("icon-chevron-down")
				.addClass("icon-chevron-right");
			this.$(".js-events").removeClass("shown");
		},

		onShown: function() {
			this.$(".js-events").addClass("shown");
		}
	});

	var WritableSeriesView = SeriesView.extend({
		constructor: function WritableSeriesView() {
			WritableSeriesView.__super__.constructor.apply(this, arguments);
		},

		events: function() {
			var superEvents = WritableSeriesView.__super__.events.call(this);
			
			return _.extend(superEvents, {
				"click .js-btn-cancel": this.onCancel,
				"click .js-btn-save": this.onSave,
				"click .js-btn-add-event": this.onAddEvent
			});
		},

		initialize: function() {
			WritableSeriesView.__super__.initialize.apply(this, arguments);

			_.bindAll(this);
		},

		getEventsRequestOptions: function() {
			var baseOptions = WritableSeriesView.__super__
				.getEventsRequestOptions();

			return _.extend(baseOptions, {
				data: {writeable: true}
			});
		},

		onEventsFetched: function() {
			// Call through to the superclass implementation in order to insert
			// the event elements into the page's DOM tree.
			WritableSeriesView.__super__.onEventsFetched.apply(this, arguments);

			// At this point the events exist in the page. Instanciate a 
			// WritableEventView wrapping each event and store the list of these
			// views in this.events
			this.events = _.map(this.$(".js-event"), function(eventEl) {
				var eventView = new WritableEventView({el: eventEl});

				// Watch for events being modified
				eventView.on("event:savedStatusChanged",
					this.onSavedStatusChanged);

				return eventView;
			}, this);

			this.$cancelSaveBtns = this.$(".js-save-cancel-btns");
		},

		onSavedStatusChanged: function() {
			// Check for any events being changed and hide/show cancel/save
			// button as needed.
			var changesExist = _.any(this.events, function(event) {
				return event.model.hasChangedFromOriginal();
			});

			// Make the cancel/save buttons visible/hidden as required

			if(changesExist && !this.$cancelSaveBtns.is(":visible")) {
				this.$cancelSaveBtns.slideDown();
			}

			if(!changesExist && this.$cancelSaveBtns.is(":visible")) {
				this.$cancelSaveBtns.slideUp();	
			}
		},

		onCancel: function(event) {
			_.each(this.events, function(eventView) {
				eventView.model.reset();

				// This works, but is a bit hacky
				eventView.unfocusForEditing();
			});
		},

		onSave: function(event) {
			// Build a JSON representation of the form. 

			var forms = _.map(this.events, function(eventView) {
				return eventView.model.asJSONDjangoForm();
			});

			var outerForm = {
				"event_set": {
					// can't add forms yet so this is OK
					"initial": forms.length,
					"forms": forms
				}
			};

			var formData = DjangoForms.encodeJSONForm(outerForm);

			// Create a modal dialog to prevent actions taking place while
			// saving.
			this.saveDialogView = new SaveEventsDialogView();
			this.saveDialogView.on("saved", this.onEventsSaved)

			// Show the dialog & kick off the form POST.
			this.saveDialogView.postEventsForm(this.getSavePath(), formData)
		},

		onEventsSaved: function(response) {
			delete this.saveDialogView;
			this.$(".js-events").empty();
			this.onEventsFetched(response);
		},

		/** Gets the path to the endpoint the POST changes to when saving. */
		getSavePath: function() {
			return this.$el.data("save-path");
		},

		onAddEvent: function(event) {
			return false;
		}
	});

	/**
	 * 
	 */
	var WritableEventView = Backbone.View.extend({
		constructor: function WritableEventView() {
			WritableEventView.__super__.constructor.apply(this, arguments);
		},

		events: function() {
			return {
				// The following 2 events enable firing of "change" events from
				// contenteditable elements on blur.
				"focusin [contenteditable]": this.onContenteditableFocus,
				"focusout [contenteditable]": this.onContenteditableBlur,

				"focusin .js-field, input, select": this.focusForEditing,
				"focusout .js-field, input, select": this.unfocusForEditing,

				// Watch for fields changing
				"change .js-field": this.updateModel,
				
				// Start editing when the pencil edit icon is clicked
				"click .js-edit-icon": this.startEditing,

				"click .js-date-time-cell": this.toggleDateTimeDialog,
				"click .js-date-time-dialog": this.onDateTimeDialogClicked
			};
		},

		initialize: function() {
			_.bindAll(this);

			// focus/blur events have to be bound manually, otherwise the
			// delegated focusin/focusout verisons are used.
			this.$(".js-date-time-cell .js-focus-catcher")
				.on("focus", this.toggleDateTimeDialog);

			this.$title = this.$(".js-field-title");
			this.$location = this.$(".js-field-location");
			this.$type = this.$(".js-field-type");
			this.$people = this.$(".js-field-people");
			this.$week = this.$(".js-field-week");
			this.$term = this.$(".js-field-term");
			this.$day = this.$(".js-field-day");
			this.$startHour = this.$(".js-field-start-hour");
			this.$startMinute = this.$(".js-field-start-minute");
			this.$endHour = this.$(".js-field-end-hour");
			this.$endMinute = this.$(".js-field-end-minute");

			this.model = new EventModel();
			// Push the state of the HTML into the model
			this.updateModel();
			// Tell the model that it's current state is the initial one
			this.model.storeInitialState();

			this.model.on("change", this.render);
		},

		render: function() {
			this.$title.text(this.model.get("title"));
			this.$location.text(this.model.get("location"));
			this.$type.val(this.model.get("type"));
			this.$people.text(this.model.get("people"));

			this.$week.text(this.model.get("week"));
			this.$term.text(this.model.getPrettyTerm());
			this.$day.text(this.model.getPrettyDay());
			this.$startHour.text(this.model.get("startHour"));
			this.$startMinute.text(this.model.get("startMinute"));
			this.$endHour.text(this.model.get("endHour"));
			this.$endMinute.text(this.model.get("endMinute"));
		},

		updateModel: function() {
			// Update our model with the current state of the HTML
			this.model.set({
				id: safeParseInt(this.$el.data("id")),
				title: this.$title.text(),
				location: this.$location.text(),
				type: this.$type.val(),
				people: this.$people.text(),
				week: this.$week.text(),
				term: this.$term.text().toLowerCase(),
				day: this.$day.text().toLowerCase(),
				startHour: this.$startHour.text(),
				startMinute: this.$startMinute.text(),
				endHour: this.$endHour.text(),
				endMinute: this.$endMinute.text()
			});
		},

		focusForEditing: function() {
			console.log("focusForEditing", arguments);
			this.$el.addClass("being-edited");
		},

		/** S */
		unfocusForEditing: function(event) {
			console.log("unfocusForEditing", "event:", event, "focused:", $(":focus"));
			this.$el.removeClass("being-edited");

			// Mark the event as changed if it's been modified
			this.markAsChanged(this.model.hasChangedFromOriginal());
		},

		markAsChanged: function(isChanged) {
			isChanged = Boolean(isChanged);
			this.isUnsaved = isChanged;
			this.trigger("event:savedStatusChanged")
			
			if(isChanged)
				this.$el.addClass("unsaved");
			else
				this.$el.removeClass("unsaved");
		},

		/** Starts editing this event by focusing the title element. */
		startEditing: function() {
			this.$title.focus();
		},

		onDateTimeDialogClicked: function(event) {
			// Prevent click events on the date/time dialog reaching the 
			// toggleDateTimeDialog() handler, which would close the dialog.
			event.stopPropagation();
		},

		closeDateTimeDialog: function() {
			if(this.dateTimeDialog) {
				this.dateTimeDialog.remove();
				delete this.dateTimeDialog;
			}
		},

		toggleDateTimeDialog: function(event) {

			var isFocus = event.type === "focus";
			var isBeforeDialog = $(event.currentTarget)
				.hasClass("js-focus-catcher-before");

			if(this.dateTimeDialog) {
				console.log("closing dialog", event);
				this.closeDateTimeDialog();

				// Move focus from this focus catcher to a real element if the
				// dialog close was triggered by focusing a focus catching
				// element before/after the dialog in the DOM.
				if(isFocus) {
					if(isBeforeDialog)
						this.$(".js-field-type").focus();
					else
						this.$(".js-field-location").focus();
				}
			}
			else {
				console.log("opening dialog", event);
				this.dateTimeDialog = new DateTimeDialogView({
					el: $("#templates .js-date-time-dialog").clone(),
					model: this.model
				});
				// dialog:close is fired by the dialog when a click is made
				// outside its area, or the close icon is clicked.
				this.dateTimeDialog.on(
					"dialog:close", this.closeDateTimeDialog);

				this.$(".js-date-time-cell .js-dialog-holder")
					.append(this.dateTimeDialog.$el);
				this.dateTimeDialog.$el.show();

				if(!isFocus || isBeforeDialog)
					this.dateTimeDialog.focusStart();
				else
					this.dateTimeDialog.focusEnd();
			}
		},

		onContenteditableFocus: function(event) {
			// Stash the element's value in a data property before it's edited
			// so that we can fire a change event if it's modified.
			var $el = $(event.target);
			$el.data("__contenteditablePrevValue", $el.html());
		},

		onContenteditableBlur: function(event) {
			var $el = $(event.target);
			var html = $el.html();
			if($el.data("__contenteditablePrevValue") !== html) {
				// Delete the remembered HTML text
				$el.data("__contenteditablePrevValue", undefined);
				$el.trigger("change");
			}
		}
	});

	var EventModel = Backbone.Model.extend({
		constructor: function EventModel() {
			EventModel.__super__.constructor.apply(this, arguments);
		},

		initialize: function() {

			this.hasInitialState = false;
		},

		/** Reset the model's attributes to the initial values. */
		reset: function() {
			this.set(this.originalAttributes);
		},

		titleCase: function(str) {
			if(str.length > 0)
				return str[0].toUpperCase() + str.slice(1);
			return str;
		},

		getPrettyTerm: function() {
			var term = this.get("term");
			if(term)
				return this.titleCase(term);
			return term;
		},

		getPrettyDay: function() {
			var day = this.get("day");
			if(day)
				return this.titleCase(day);
			return day;
		},

		/**
		 * Mark the event's current state as being the original. After calling
		 * this, hasChangedFromOriginal() may be called.
		 */
		storeInitialState: function() {
			if(!this.hasInitialState === false) {
				throw new Error("Initial state already set.");
			}

			this.hasInitialState = true;
			this.originalAttributes = this.toJSON();
		},

		validate: function(attrs) {
			return;

			var errors = {};

			if(!attrs.title || attrs.title.trim() == "")
				errors.title = ["This field is required."];

			if(!attrs.type || attrs.type == "")
				errors.type = ["This field is required."];

			if(!attrs.location || attrs.location.trim() == "")
				errors.location = ["This field is required."];

			if(!attrs.people || attrs.people.trim() == "")
				errors.people = ["This field is required."];
		},

		/** 
		 * Returns true if the current attribute values differ from the initial
		 * values.
		 */
		hasChangedFromOriginal: function() {
			if(!this.hasInitialState === true) {
				throw new Error("No initial state set.");
			}
			return !_.isEqual(this.originalAttributes, this.toJSON());
		},

		/**
		 * Get an object of model attributes matching the Django form fields
		 * accepted by the series edit endpoint.
		 */
		asJSONDjangoForm: function() {
			var attrs = this.attributes;

			// Map our field names onto the server's Django form field names
			return {
				id: attrs.id,
				title: attrs.title,
				location: attrs.location,
				event_type: attrs.type,
				people: attrs.people,
				term_week: attrs.week,
				term_name: attrs.term,
				day_of_week: attrs.day,
				start_hour: attrs.startHour,
				start_minute: attrs.startMinute,
				end_hour: attrs.endHour,
				end_minute: attrs.endMinute
			};
		}
	});

	var DateTimeDialogView = Backbone.View.extend({
		constructor: function DateTimeDialogView() {
			DateTimeDialogView.__super__.constructor.apply(this, arguments);
		},

		events: function() {
			return {
				"click .js-close-btn": this.requestDialogClose,
				"change #date-time-week": this.onWeekChanged,
				"change select": this.syncToModel,
				"change .js-hour, .js-minute": this.onTimeInputChanged,
			};
		},

		initialize: function() {
			_.bindAll(this);

			this.backdrop = new DialogBackdropView();
			this.backdrop.$el.addClass("dialog-backdrop-date-time");
			$("body").append(this.backdrop.el);
			this.backdrop.on("clicked", this.requestDialogClose);

			this.$week = this.$("#date-time-week");
			this.$term = this.$("#date-time-term");
			this.$day = this.$("#date-time-day");
			this.$startHour = this.$("#date-time-start-hour");
			this.$startMinute = this.$("#date-time-start-minute");
			this.$endHour = this.$("#date-time-end-hour");
			this.$endMinute = this.$("#date-time-end-minute");

			// Initialise the inputs
			this.render();
		},

		/** Update the state of hte DOM with the model's state. */
		render: function() {
			this.$week.val(this.model.get("week"));
			this.$term.val(this.model.get("term"));
			this.$day.val(this.model.get("day"));
			this.$startHour.val(this.model.get("startHour"));
			this.$startMinute.val(this.model.get("startMinute"));
			this.$endHour.val(this.model.get("endHour"));
			this.$endMinute.val(this.model.get("endMinute"));
		},

		minutesFromTime: function(hours, minutes) {
			return (hours * 60) + minutes;
		},

		timeFromMinutes: function(minutes) {
			return [Math.floor(minutes / 60), minutes % 60];
		},

		/**
		 * Clamp a minute figure to a 24 hour period. Note that 0:00-24:00
		 * inclusive is permitted to allow times like 23:00-24:00.
		 */
		clampTime: function(minutes) {
			return Math.max(0, Math.min(this.minutesFromTime(24, 0), minutes));
		},

		/**
		 * Convert number into a string, padding it to be minWidth wide by
		 * prefixing it with zeros.
		 */
		zeroPad: function(number, minWidth) {
			minWidth = minWidth || 2;
			var width;
			if(number == 0)
				width = 1;
			else
				width = Math.floor(Math.log(Math.abs(number)) / Math.LN10) + 1;

			return (number < 0 ? "-" : "")
					+ new Array(Math.max(0, minWidth - width) + 1).join("0")
					+ Math.abs(number);
		},

		onWeekChanged: function() {
			// Reset week to the last good value if it's not an int
			if(isNaN(safeParseInt(this.$week.val())))
				this.$week.val(this.model.get("week"));

			this.syncToModel();
		},

		onTimeInputChanged: function(event) {
			var $target = $(event.target);

			var isStart = $target.hasClass("js-start");
			var isHour = $target.hasClass("js-hour");

			// Prevent invalid numbers creaping in
			if(isNaN(safeParseInt($target.val()))) {
				var attr = (isStart? "start" : "end")
					+ (isHour ? "Hour" : "Minute");

				$target.val(this.model.get(attr));
			}
			
			// Keep 'to' the same distance from 'from' when 'from' is updated.
			// The principle here is to only update 'to' automatically  wherever
			// possible. The only time this is broken is when 'from' is moved
			// to 24:00 in which case 'from' must be moved back to avoid a 0
			// length event.
			// The other principle behind this is not to have to show users
			// error messages.
			var from = this.minutesFromTime(
					safeParseInt(this.$startHour.val()),
					safeParseInt(this.$startMinute.val()));

			var oldFrom = this.minutesFromTime(
					safeParseInt(this.model.get("startHour")),
					safeParseInt(this.model.get("startMinute")));

			var to = this.minutesFromTime(
					safeParseInt(this.$endHour.val()),
					safeParseInt(this.$endMinute.val()));

			// Make to move with from when from changes
			// (+= 0 when to changed)
			to += from - oldFrom;

			// Don't allow values outside the range of valid times
			from = this.clampTime(from);
			to = this.clampTime(to);

			// Prevent end being <= start
			if(to <= from) {
				to = this.clampTime(from + 60);
			}

			if(to == from) {
				// This can only occur if from is moved to 24
				assert(from == this.minutesFromTime(24, 0));
				from = this.minutesFromTime(23, 0);
			}

			var fromTime = this.timeFromMinutes(from);
			var toTime = this.timeFromMinutes(to);

			this.$startHour.val(this.zeroPad(fromTime[0], 2));
			this.$startMinute.val(this.zeroPad(fromTime[1], 2));
			this.$endHour.val(this.zeroPad(toTime[0], 2));
			this.$endMinute.val(this.zeroPad(toTime[1], 0));

			this.syncToModel();
		},

		/** Update the state of the model with the DOM's state. */
		syncToModel: function() {
			this.model.set({
				week: this.$week.val(),
				term: this.$term.val(),
				day: this.$day.val(),
				startHour: this.$startHour.val(),
				startMinute: this.$startMinute.val(),
				endHour: this.$endHour.val(),
				endMinute: this.$endMinute.val()
			});
		},

		/** Focus the first form element. */
		focusStart: function() {
			this.$(".js-week").focus();
		},

		/** Focus the last form element. */
		focusEnd: function() {
			this.$(".js-minute.js-end").focus();
		},

		remove: function() {
			// Remove our backdrop element when we're removed.
			this.backdrop.remove();
			// Call the superclass's remove()
			DateTimeDialogView.__super__.remove.apply(this, arguments);
		},

		requestDialogClose: function() {
			this.trigger("dialog:close");
		}
	});

	var DialogBackdropView = Backbone.View.extend({
		constructor: function DialogBackdropView() {
			DialogBackdropView.__super__.constructor.apply(this, arguments);
		},

		tagName: "div",
		className: "dialog-backdrop",

		events: function() {
			return {
				"click": this.onClick
			};
		},

		onClick: function() {
			this.trigger("clicked");
		}
	});

	var SaveEventsDialogView = Backbone.View.extend({
		constructor: function() {
			SaveEventsDialogView.__super__.constructor.apply(this, arguments);
		},

		events: function() {
			return {
				"click .btn": this.dismissDialog
			};
		},

		initialize: function() {
			_.bindAll(this);

			this.setElement($("#templates .js-events-save-dialog")[0]);
			this.$(".js-body").hide();
			this.$(".js-body-saving").show();
		},

		showModal: function() {
			this.$el.modal({
				backdrop: "static",
				keyboard: false,
				show: true
			});
		},

		postEventsForm: function(url, eventsData) {
			this.showModal();

			$.ajax({
				url: url,
				type: "POST",
				data: eventsData
			}).done(this.onPOSTDone).fail(this.onPOSTFail)
		},

		onPOSTDone: function(response) {
			this.$(".js-body").hide();
			this.$(".js-body-success").show();
			this.trigger("saved", response);
		},

		onPOSTFail: function() {
			this.$(".js-body").hide();
			this.$(".js-body-error").show();
		},

		dismissDialog: function(event) {
			this.$el.modal("hide");
			this.trigger("close");
			event.preventDefault();
		}
	});

	/**
	 * Controlls a .js-loading-indicator. Shows a progress bar when loading
	 * and an error message with a retry button when failed.
	 */
	var LoadingIndicatorView = Backbone.View.extend({
		constructor: function LoadingIndicatorView() {
			LoadingIndicatorView.__super__.constructor.apply(this, arguments);
		},

		events: function() {
			return {
				"click .js-retry-btn": "onRetry"
			};
		},

		initialize: function() {
			_.bindAll(this, "onRetry");
		},

		onRetry: function() {
			this.trigger("retry");
		},

		showLoadingState: function() {
			$(".loading").show();
			$(".error").hide();
		},

		showErrorState: function() {
			$(".loading").hide();
			$(".error").show();
		}
	});

	return {
		ModuleView: ModuleView,
		SeriesView: SeriesView,
		WritableSeriesView: WritableSeriesView
	};
});