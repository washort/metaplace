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
