$('#signin').on('click', function() {
    navigator.id.request();
});

$('#signout').on('click', function() {
    navigator.id.logout();
});

navigator.id.watch({
  loggedInUser: $('#session-email').data().email || null,
  onlogin: function(assertion) {
    $.ajax({
      type: 'POST',
      url: '/auth/login',
      data: {assertion: assertion},
      success: function(res, status, xhr) { window.location.reload(); },
      error: function(xhr, status, err) {
        navigator.id.logout();
        alert("Login failure: " + err);
      }
    });
  },
  onlogout: function() {
    $.ajax({
      type: 'POST',
      url: '/auth/logout',
      success: function(res, status, xhr) { window.location.reload(); },
      error: function(xhr, status, err) { alert("Logout failure: " + err); }
    });
  }
});

$('#debug').on('submit', function() {
  if ('MozActivity' in window) {
    var activity = new MozActivity({
      name: "marketplace-app",
      data: {slug: $('#debug input:eq(0)').val()}
    });
  } else {
    alert('Not installed as an app.');
  }
});

$('#install').on('click', function() {
  var request = window.navigator.mozApps.install('https://metaplace.paas.allizom.org/manifest.webapp', null);
  request.onerror = function(e) {
    alert("Error installing app : " + request.error.name);
  };
});
