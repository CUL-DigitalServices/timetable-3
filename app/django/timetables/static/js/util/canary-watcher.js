define([
    "jquery",
    "underscore",
    "util/api",
    "util/page"
], function ($, _, api, page) {
    "use strict";

    var CanaryWatcher = function () {
        _.bindAll(this);
    };

    _.extend(CanaryWatcher.prototype, {
        startWatch: function (onCanaryDied) {
            this.onCanaryDied = onCanaryDied;
            $(document).on("ajaxError", this.onAjaxError);
        },

        stopWatch: function () {
            $(document).off("ajaxError", this.onAjaxError);
        },

        onAjaxError: function () {
            var self = this;
            api.checkCanaryStillAlive(function (error, response) {
                if (response && response.user) {
                    // Everything is still ok.
                    return;
                }

                self.onCanaryDied();
            });
        }
    });

    return new CanaryWatcher();
});