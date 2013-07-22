define([
    "jquery"
], function ($) {
    "use strict";

    var doAjax = function doAjax(url, type, data, callback) {
        $.ajax({
            url: url,
            type: type,
            data: data,
            success: function (response) {
                callback(null, response);
            },
            error: function (jqXHR) {
                callback({
                    code: jqXHR.status,
                    msg: jqXHR.responseText || jqXHR.statusText
                });
            }
        });
    };

    var addToTimetable = function addToTimetable(userPath, fullpath, eventsourceId, eventId, crsfToken, callback) {
        var url =  "/" + userPath + ".link",
            type = "post",
            data = {
                t: fullpath,
                es: eventsourceId,
                e: eventId,
                csrfmiddlewaretoken: crsfToken
            };
        doAjax(url, type, data, callback);
    };

    var removeFromTimetable = function removeFromTimetable(userPath, fullpath, eventsourceId, eventId, crsfToken, callback) {
        var url = "/" + userPath + ".link",
            type = "post",
            data = {
                td: fullpath,
                esd: eventsourceId,
                ed: eventId,
                csrfmiddlewaretoken: crsfToken
            };
        doAjax(url, type, data, callback);
    };

    var getModulesList = function getModulesList(fullpath, userPath, callback) {
        var url = "/" + fullpath + ".children.html",
            type = "get",
            data = {
                t: userPath
            };
        doAjax(url, type, data, callback);
    };

    var getUserEventsList = function getUserEventsList(userPath, year, month, callback) {
        var url = "/" + userPath + ".callist.html",
            type = "get",
            data = {
                y: year,
                m: month
            };
        doAjax(url, type, data, callback);
    };

    var resetUserFeed = function resetUserFeed(userPath, callback) {
        var url = "/" + userPath + ".resetfeed",
            type = "post";
        doAjax(url, type, undefined, callback);
    };

    return {
        addToTimetable: addToTimetable,
        removeFromTimetable: removeFromTimetable,
        getModulesList: getModulesList,
        getUserEventsList: getUserEventsList,
        resetUserFeed: resetUserFeed
    };
});
