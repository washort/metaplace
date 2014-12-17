// If you add a source here, you'll need to add a column in the HTML table
// also. The order of the sources here must match the order of tables created
// in the template.
var sources = {
    'local': 'http://mp.dev/api/v1/services/config/site/',
    'altdev': 'https://marketplace-altdev.allizom.org/api/v1/services/config/site/',
    'dev': 'https://marketplace-dev.allizom.org/api/v1/services/config/site/',
    'stage': 'https://marketplace.allizom.org/api/v1/services/config/site/',
    'altpay': 'https://payments-alt.allizom.org/api/v1/services/config/site/',
    'prod': 'https://marketplace.firefox.com/api/v1/services/config/site/',
}

var plate_of_waffles = {};

function Waffle() {

    /* One assumption is that flags, switches, and samples will never share a
     * name.  Originally I made a key which combined ID and name but the IDs
     * across all the servers didn't line up.  Once prod syncs to the other
     * servers they line up, but when developing that isn't guaranteed often.
     * It shouldn't be a problem as I don't expect the names to ever clash, but
     * be aware of it.
     */

    this.id = 0;
    this.name = '';
    this.note = '';
    this.active = {};

    // @TODO - this should be in the active object above since a flag could just
    // be straight on for one server and only enabled for some groups on
    // another.  The icons will still show up correctly, the alt texts will just
    // be confusing.
    this.alttext = '';

    this.draw = function() {

        // First we see if a row already exists.  If not, add it.
        if ($('#' + this.name).length == 0) {

            var tr = $('<tr />');
            tr.attr('id', this.name);

            var info_td = $('<td><strong>' + this.name + '</strong> (' + this.type + '): ' + this.note + '</td>');
            tr.append(info_td);

            var that = this; // no idea if this is legit!
            $.each(sources, function(source, _) {
                var x = $('<td id="' + source + '-' + that.name + '"></td>');
                tr.append(x);
            });

            $('#output > tbody:last').append(tr);
        }

        // The table cells should exist now, just flip the values
        var that = this;
        $.each(this.active, function(source, active) {
            console.log("  Source: " + source + ": " + active);
            var id = "#" + source + '-' + that.name;
            if (active == 1) {
                $(id).attr('class', 'true');
                $(id).html('<span title="' + that.alttext + '">✔</span>');
            } else if (active == 2) {
                $(id).attr('class', 'kinda');
                $(id).html('<span title="' + that.alttext + '">☃</span>');
            } else {
                $(id).attr('class', 'false');
                $(id).html('<span title="' + that.alttext + '">✘</span>');
            }
        });
    };
}

/* Simple function which is passed a waffle and adds it to our collection of
 * waffle objects so we can draw it on the page. */
function consume(source, data, type) {

    var waffle = {};
    var key = data.name;

    if (key in plate_of_waffles) {
        waffle = plate_of_waffles[key];
    } else {
        waffle = new Waffle();
    }

    waffle.id = data.id;
    waffle.type = type;
    waffle.name = data.name;
    waffle.note = data.note;
    waffle.alttext = '';
    if (data.active) {
         // It's a switch
        waffle.active[source] = true;
    } else {
        // It's a flag
        if (data.everyone) {
            waffle.active[source] = true;
        } else if (data.percent || data.testing || data.superusers || data.staff || data.authenticated || data.languages || (data.users && data.users.length) || (data.groups && data.groups.length)) {
            if (data.percent) {
                waffle.alttext += "Percent: " + data.percent + "; ";
            }
            if (data.testing) {
                waffle.alttext += "Testing: " + data.testing + "; ";
            }
            if (data.superusers) {
                waffle.alttext += "Super Users: " + data.superusers + "; ";
            }
            if (data.staff) {
                waffle.alttext += "Staff: " + data.staff + "; ";
            }
            if (data.authenticated) {
                waffle.alttext += "Authed Users: " + data.authenticated + "; ";
            }
            if (data.languages) {
                waffle.alttext += "Languages: " + data.languages + "; ";
            }
            if (data.users && data.users.length) {
                waffle.alttext += data.users.length + " users allowed; ";
            }
            if (data.groups && data.groups.length) {
                waffle.alttext += data.groups.length + " groups allowed; ";
            }
            waffle.active[source] = 2; // kinda sour we need a 3rd value now!
        } else {
            waffle.active[source] = false;
        }
    }

    plate_of_waffles[key] = waffle;

    plate_of_waffles[key].draw();
}

/* The success function for jQuery's getJSON().  This gets the raw data straight
 * from the API */
function tastywaffles(source, data) {

    if (!data.waffle) {
        console.log("Skipping malformed input from " + source);
        return;
    }

     var call_me_maybe = function(things, type) {
         if (things) {
             $.each(things, function(_, thingy) { consume(source, thingy, type); });
         }
     };

     call_me_maybe(data.waffle.switches, 'switch');
     call_me_maybe(data.waffle.flags, 'flag');
     call_me_maybe(data.waffle.samples, 'sample');
}

$(document).ready(function() {

    $.each(sources, function(source,url) {
        $.getJSON(url, function(data) { tastywaffles(source, data); });
    });

});
