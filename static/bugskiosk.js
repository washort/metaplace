$(document).ready(function() {

var spinner = new Spinner({'length': 50}).spin(document.getElementById('loading'));

var bugzilla = bz.createClient();
var components = {};

function buildSearchLink(bugs) {
  var searchlink = "https://bugzilla.mozilla.org/buglist.cgi?quicksearch=";

  bugs.forEach(function(bug) {
    searchlink += bug.id + ",";
  });

  return searchlink;
}

function draw(startdate) {
  $("#output").empty();

  Object.keys(components).sort().forEach(function(key, i) {

    var container = $('<div />');
    container.attr('class', 'col-sm-4');

    var panel = $('<div />');
    panel.attr('class', 'panel panel-default');

    var panelheader = $('<div />');
    panelheader.attr('class', 'panel-heading');
    panelheader.append('<h3 class="panel-title">' + components[key].name + '</h3>');

    var panelbody = $('<div />');
    panelbody.attr('class', 'panel-body');
    panelbody.append('<a target="_blank" href="' + buildSearchLink(components[key].bugs) + '" class="count">' + components[key].bugs.length + '</a>');

    panel.append(panelheader).append(panelbody);

    container.append(panel);

    $("#output").append(container);
    $("#dateheader").text("Closed Since " + startdate);

  });
}

function getComponent(name) {
  if (name in components) {
    return components[name];
  }
  components[name] = {'name': name, 'bugs': []}
  return components[name];
}

function gogo(startdate) {

  // Gets bugs which were closed since the date and which are still closed, including verified
  bugzilla.searchBugs({
      "changed_after": startdate,
      "product": "Marketplace",
      "changed_field": "status",
      "changed_field_to": "RESOLVED",
      "resolution": ["FIXED", "INVALID", "WONTFIX", "DUPLICATE", "WORKSFORME", "INCOMPLETE"]
    }, function(error, buglist) {

      if (error) {
        alert(error);
      }

      buglist.forEach(function(bug) {
        var component = getComponent(bug.component);
        component.bugs.push(bug);
      });

    draw(startdate);
    });
}

var startdate = $.url().param('date');

if (startdate == undefined || startdate.length < 10) {
    var d = new Date();
    d.setDate(d.getDate()-7);
    //lol?
    startdate = d.getFullYear() + "-" + (d.getMonth()+1) + "-" + d.getDate();
    console.log(startdate);
}
gogo(startdate);

});
