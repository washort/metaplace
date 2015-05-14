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

function jump(val) {
  if ('MozActivity' in window) {
    var activity = new MozActivity({
      name: "marketplace-app",
      data: {slug: val}
    });
  } else {
    window.location = 'https://marketplace.firefox.com/app/' + val;
  }
}

function usage() {
  if ('MozActivity' in window) {
    console.log('marketplace-search');
    var activity = new MozActivity({
      name: 'marketplace-search',
      data: {type: 'firefox-os-app-stats'}
    });
  } else {
    window.location = 'https://marketplace.firefox.com/usage';
  }
}

$('#jump').on('submit', function() {
  jump($('#jump input:eq(0)').val());
});

$('a.jump').on('click', function() {
  jump($(this).data('slug'));
});

$('a.usage').on('click', function() {
  usage();
});

$('#install').on('click', function() {
  var request = window.navigator.mozApps.install('https://metaplace.paas.allizom.org/manifest.webapp', null);
  request.onerror = function(e) {
    alert("Error installing app : " + request.error.name);
  };
});

$('#show').on('click', function() {
    $('.hidden').removeClass('hidden');
    return false;
});
