# Work under either python2.5 or python2.7
try:
    import unittest2 as unittest
except ImportError:
    import unittest
import os
import snippets
import webtest   # may need to do 'pip install webtest'

from google.appengine.api import users
from google.appengine.ext import db
from google.appengine.ext import testbed


"""Tests for the snippets server.

This tests the functionality found at weekly-snippets.appspot.com.

c.f. http://code.google.com/appengine/docs/python/tools/localunittesting.html
"""

__author__ = 'Craig Silverstein <csilvers@khanacademy.org>'


class SnippetsTestBase(unittest.TestCase):
    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_user_stub()
        self.request_fetcher = webtest.TestApp(snippets.application)

    def tearDown(self):
        self.testbed.deactivate()

    def login(self, email):
        self.testbed.setup_env(user_email=email, overwrite=True)
        self.testbed.setup_env(user_id=email, overwrite=True)
        self.testbed.setup_env(user_is_admin='0', overwrite=True)

    def set_is_admin(self):
        self.testbed.setup_env(user_is_admin='1', overwrite=True)

    def assertNumSnippets(self, body, expected_count):
        """Asserts the page 'body' has exactly expected_count snippets in it."""
        # We annotate the element at the beginning of each snippet with
        # class="snippet_divider".
        self.assertEqual(expected_count, body.count('class="snippet_divider"'),
                         body)

    def _ith_snippet(self, body, snippet_number):
        """For user- and weekly-pages, return the i-th snippet, 0-indexed."""
        # The +1 is because the 0-th element is stuff before the 1st snippet
        return body.split('class="snippet_divider"',
                          snippet_number+2)[snippet_number+1]

    def assertInSnippet(self, text, body, snippet_number):
        """For snippet-page 'body', assert 'text' is in the i-th snippet.

        This works for both user-pages and weekly-pages -- we figure out
        the boundaries of the snippets, and check whether the text is
        in the given snippet.

        If text is a list or tuple, we check each item of text in turn.

        Arguments:
           text: the text to find in the snippet.  If a list or tuple,
             test each item in the list in turn.
           body: the full html page
           snippet_number: which snippet on the page to examine.
             Index starts at 0.
        """
        self.assertIn(text, self._ith_snippet(body, snippet_number))

    def assertNotInSnippet(self, text, body, snippet_number):
        """For snippet-page 'body', assert 'text' is not in the i-th snippet."""
        self.assertNotIn(text, self._ith_snippet(body, snippet_number))


class UserTestBase(SnippetsTestBase):
    """The common base: someone who is logged in as user@example.com."""
    def setUp(self):
        SnippetsTestBase.setUp(self)
        self.login('user@example.com')


class LoginRequiredTestCase(SnippetsTestBase):
    def testLoginRequiredForUserView(self):
        url = '/'
        response = self.request_fetcher.get(url)
        self.assertIn('must be logged in', response.body)

        self.login('user@example.com')
        response = self.request_fetcher.get(url)
        self.assertNotIn('must be logged in', response.body)

    def testLoginRequiredForWeeklyView(self):
        url = '/weekly'
        response = self.request_fetcher.get(url)
        self.assertIn('must be logged in', response.body)

        self.login('user@example.com')
        response = self.request_fetcher.get(url)
        self.assertNotIn('must be logged in', response.body)

    def testLoginRequiredForSettingsView(self):
        url = '/settings'
        response = self.request_fetcher.get(url)
        self.assertIn('must be logged in', response.body)

        self.login('user@example.com')
        response = self.request_fetcher.get(url)
        self.assertNotIn('must be logged in', response.body)

    def testLoginRequiredToUpdateSnippet(self):
        url = '/update_snippet?week=02-20-2012&snippet=my+snippet'
        response = self.request_fetcher.get(url)
        self.assertIn('must be logged in', response.body)

        self.login('user@example.com')
        response = self.request_fetcher.get(url)
        self.assertNotIn('must be logged in', response.body)
        
    def testLoginRequiredToUpdateSettings(self):
        url = '/update_settings'
        response = self.request_fetcher.get(url)
        self.assertIn('must be logged in', response.body)

        self.login('user@example.com')
        response = self.request_fetcher.get(url)
        self.assertNotIn('must be logged in', response.body)


class AccessTestCase(UserTestBase):
    """Tests that you can't modify someone who is not yourself."""

    def testCanViewOtherSnippets(self):
        url = '/?u=notuser@example.com'
        # Raises an error if we don't get a 200 response.
        self.request_fetcher.get(url)

    def testCanViewWeeklyPage(self):
        """u is ignored for /weekly, but included for completeness."""
        url = '/weekly?u=notuser@example.com'
        self.request_fetcher.get(url)

    def testCannotEditOtherSnippets(self):
        url = ('/update_snippet?week=02-20-2012&snippet=my+snippet'
               '&u=notuser@example.com')
        # Raises an error if we don't get a 500 response (meaning no perm).
        self.request_fetcher.get(url, status=500)

    def testCannotViewOtherSettings(self):
        url = '/settings?u=notuser@example.com'
        self.request_fetcher.get(url, status=500)

    def testCannotEditOtherSettings(self):
        url = '/update_settings?u=notuser@example.com'
        self.request_fetcher.get(url, status=500)
        
    def testCanEditOwnSnippets(self):
        url = ('/update_snippet?week=02-20-2012&snippet=my+snippet'
               '&u=user@example.com')
        self.request_fetcher.get(url)

    def testCanViewOwnSettings(self):
        url = '/settings?u=user@example.com'
        self.request_fetcher.get(url)

    def testCanEditOwnSettings(self):
        url = '/update_settings?u=user@example.com'
        self.request_fetcher.get(url)
        
    def testCanEditOtherSnippetsAsAdmin(self):
        self.set_is_admin()
        url = ('/update_snippet?week=02-20-2012&snippet=my+snippet'
               '&u=notuser@example.com')
        self.request_fetcher.get(url)

    def testCanViewOtherSettingsAsAdmin(self):
        self.set_is_admin()
        url = '/settings?u=notuser@example.com'
        self.request_fetcher.get(url)

    def testCanEditOtherSettingsAsAdmin(self):
        self.set_is_admin()
        url = '/update_settings?u=notuser@example.com'
        self.request_fetcher.get(url)


class SetAndViewSnippetsTestCase(UserTestBase):
    """Set some snippets, then make sure they're viewable."""

    def testSetAndViewInUserMode(self):
        url = '/update_snippet?week=02-20-2012&snippet=my+snippet'
        self.request_fetcher.get(url)
        response = self.request_fetcher.get('/')
        self.assertNumSnippets(response.body, 1)
        self.assertInSnippet('>my snippet<', response.body, 0)

    def testSetAndViewInWeeklyMode(self):
        url = '/update_snippet?week=02-20-2012&snippet=my+snippet'
        self.request_fetcher.get(url)
        response = self.request_fetcher.get('/weekly?week=02-20-2012')
        self.assertNumSnippets(response.body, 1)
        self.assertInSnippet('>my snippet<', response.body, 0)

    def testCannotSeeInOtherWeek(self):
        url = '/update_snippet?week=02-20-2012&snippet=my+snippet'
        self.request_fetcher.get(url)
        response = self.request_fetcher.get('/weekly?week=02-13-2012')
        self.assertNumSnippets(response.body, 1)
        self.assertInSnippet('(no snippet this week)', response.body, 0)
        self.assertNotIn('>my snippet<', response.body)

    def testViewSnippetsForTwoUsers(self):
        url = '/update_snippet?week=02-20-2012&snippet=my+snippet'
        self.request_fetcher.get(url)
        self.login('other@example.com')
        url = '/update_snippet?week=02-20-2012&snippet=other+snippet'
        self.request_fetcher.get(url)

        # This is done as other
        response = self.request_fetcher.get('/')
        self.assertIn('other@example.com', response.body)
        self.assertNumSnippets(response.body, 1)
        self.assertInSnippet('>other snippet<', response.body, 0)
        self.assertNotIn('user@example.com', response.body)
        self.assertNotIn('>my snippet<', response.body)
        response = self.request_fetcher.get('/weekly?week=02-20-2012')
        self.assertNumSnippets(response.body, 2)
        self.assertInSnippet('other@example.com', response.body, 0)
        self.assertInSnippet('>other snippet<', response.body, 0)
        self.assertInSnippet('user@example.com', response.body, 1)
        self.assertInSnippet('>my snippet<', response.body, 1)

        # This is done as user
        self.login('user@example.com')
        response = self.request_fetcher.get('/')
        self.assertIn('user@example.com', response.body)
        self.assertNumSnippets(response.body, 1)
        self.assertInSnippet('>my snippet<', response.body, 0)
        self.assertNotIn('other@example.com', response.body)
        self.assertNotIn('>other snippet<', response.body)
        response = self.request_fetcher.get('/weekly?week=02-20-2012')
        self.assertNumSnippets(response.body, 2)
        self.assertInSnippet('other@example.com', response.body, 0)
        self.assertInSnippet('>other snippet<', response.body, 0)
        self.assertInSnippet('user@example.com', response.body, 1)
        self.assertInSnippet('>my snippet<', response.body, 1)

    def testViewSnippetsForTwoWeeks(self):
        url = '/update_snippet?week=02-20-2012&snippet=my+snippet'
        self.request_fetcher.get(url)
        url = '/update_snippet?week=02-27-2012&snippet=my+second+snippet'
        self.request_fetcher.get(url)

        response = self.request_fetcher.get('/')
        self.assertNumSnippets(response.body, 2)
        # Snippets go in reverse chronological order (i.e. newest first)
        self.assertInSnippet('>my second snippet<', response.body, 0)
        self.assertInSnippet('>my snippet<', response.body, 1)

        response = self.request_fetcher.get('/weekly?week=02-20-2012')
        self.assertNumSnippets(response.body, 1)
        self.assertInSnippet('user@example.com', response.body, 0)
        self.assertInSnippet('>my snippet<', response.body, 0)
        self.assertNotIn('>my second snippet<', response.body)

        response = self.request_fetcher.get('/weekly?week=02-27-2012')
        self.assertNumSnippets(response.body, 1)
        self.assertInSnippet('user@example.com', response.body, 0)
        self.assertInSnippet('>my second snippet<', response.body, 0)
        self.assertNotIn('>my snippet<', response.body)

        response = self.request_fetcher.get('/weekly?week=02-13-2012')
        self.assertNumSnippets(response.body, 1)
        self.assertInSnippet('(no snippet this week)', response.body, 0)
        self.assertNotIn('>my snippet<', response.body)
        self.assertNotIn('>my second snippet<', response.body)


    def testViewEmptySnippetsInWeekMode(self):
        url = '/update_snippet?week=02-20-2012&snippet=my+snippet'
        self.request_fetcher.get(url)
        self.login('other@example.com')
        url = '/update_snippet?week=02-27-2012&snippet=other+snippet'
        self.request_fetcher.get(url)

        response = self.request_fetcher.get('/weekly?week=02-20-2012')
        self.assertNumSnippets(response.body, 2)
        # Other-user comes first alphabetically.
        self.assertInSnippet('other@example.com', response.body, 0)
        self.assertInSnippet('(no snippet this week)', response.body, 0)
        self.assertInSnippet('user@example.com', response.body, 1)
        self.assertInSnippet('>my snippet<', response.body, 1)

        response = self.request_fetcher.get('/weekly?week=02-27-2012')
        self.assertNumSnippets(response.body, 2)
        self.assertInSnippet('other@example.com', response.body, 0)
        self.assertInSnippet('>other snippet<', response.body, 0)
        self.assertInSnippet('user@example.com', response.body, 1)
        self.assertInSnippet('(no snippet this week)', response.body, 1)

    def testViewEmptySnippetsInUserMode(self):
        """Occurs when there's a gap between two snippets."""
        url = '/update_snippet?week=02-20-2012&snippet=my+snippet'
        self.request_fetcher.get(url)
        url = '/update_snippet?week=02-06-2012&snippet=my+old+snippet'
        self.request_fetcher.get(url)

        response = self.request_fetcher.get('/')
        self.assertNumSnippets(response.body, 3)
        self.assertInSnippet('>my snippet<', response.body, 0)
        self.assertInSnippet('(No snippet for this week)', response.body, 1)
        self.assertInSnippet('>my old snippet<', response.body, 2)


'''
# TODO(csilvers): allow mocking in a different day
_TODAY = datetime.datetime.now().date()


port = os.environ['SERVER_PORT']
if port and port != '80':
    HOST_NAME = '%s:%s' % (os.environ['SERVER_NAME'], port)
else:
    HOST_NAME = os.environ['SERVER_NAME']


# Note: I use email address rather than a UserProperty to uniquely
# identify a user.  As per
# http://code.google.com/appengine/docs/python/users/userobjects.html
# a UserProperty is an email+unique id, so if a person changes their
# email the UserProperty also changes; it's not a persistent
# identifier across email changes the way the unique-id alone is.  But
# non-google users can't have a unique id, so if I want to expand the
# snippet server later that won't scale.  So might as well use email
# as our unique identifier.  If someone changes email address and
# wants to take their snippets with them, we can add functionality to
# support that later.

class User(db.Model):
    """User preferences."""
    email = db.StringProperty(required=True)           # The key to this record
    category = db.StringProperty(default='(unknown)')  # used to group snippets
    wants_email = db.BooleanProperty(default=True)     # get nag emails?
    # TODO(csilvers): make a ListProperty instead.
    wants_to_view = db.TextProperty(default='all')     # comma-separated list


class Snippet(db.Model):
    """Every snippet is identified by the monday of the week it goes with."""
    email = db.StringProperty(required=True) # with week, the key to this record
    week = db.DateProperty(required=True)    # the monday of the week
    text = db.TextProperty(default='(No snippet for this week)')
    private = db.BooleanProperty(default=False)


def _login_page(request, response):
    """Write the login page to a response object."""
    template_values = {
        'login_url': users.create_login_url(request.uri),
    }
    path = os.path.join(os.path.dirname(__file__), 'login.html')
    response.out.write(template.render(path, template_values))    


def _current_user_email():
    """Return the logged-in user's email address, converted into lowercase."""
    return users.get_current_user().email().lower()


def _get_user(email):
    """Return the user object with the given email, or None if not found."""
    q = User.all()
    q.filter('email = ', email)
    return q.get()


def _get_or_create_user(email):
    """Return the user object with the given email, creating if if needed."""
    user = _get_user(email)
    if user:
        pass
    elif not _logged_in_user_has_permission_for(email):
        raise IndexError('User "%s" not found; did you specify'
                         ' the full email address?'% email)
    else:
        user = User(email=email)
        db.put(user)
    return user


def _newsnippet_monday(today):
    """Return a datetime.date object: the monday for new snippets.

    The rule is that up through wednesday, all snippets are assumed to
    be for the previous week.  Starting on thursday, by default you
    start putting in snippets for this week.

    Arguments:
       today: the current day, used to calculate the best monday.

    Returns:
       The Monday that we are accepting new snippets for, by default.
    """
    today_weekday = today.weekday()   # monday == 0, sunday == 6
    if today_weekday <= 2:            # wed or before
        end_monday = today - datetime.timedelta(today_weekday + 7)
    else:
        end_monday = today - datetime.timedelta(today_weekday)        
    return end_monday


def _existingsnippet_monday(today):
    """Return a datetime.date object: the monday for existing snippets.

    The rule is that we show the snippets for the previous week.  That
    means we subtract to the current monday, then subtract 7 more days
    to get the snippets for the previous week.

    Arguments:
       today: the current day, used to calculate the best monday.

    Returns:
       The Monday that we are accepting new snippets for, by default.
    """
    return today - datetime.timedelta(today.weekday() + 7)


def _logged_in_user_has_permission_for(email):
    """Return True if the current logged-in appengine user can edit this user."""
    return (email == _current_user_email()) or users.is_current_user_admin()


def _can_view_private_snippets(my_email, snippet_email):
    """Return true if I have permission to view other's private snippet.

    I have permission to view if I am in the same domain as the person
    who wrote the snippet (domain is everything following the @ in the
    email).

    Arguments:
      my_email: the email address of the currently logged in user
      snippet_email: the email address of the snippet we're trying to view.

    Returns:
      True if my_email has permission to view snippet_email's private
      emails, or False else.
    """
    my_at = my_email.rfind('@')
    snippet_at = snippet_email.rfind('@')
    if my_at == -1 or snippet_at == -1:
        return False    # be safe
    return my_email[my_at:] == snippet_email[snippet_at:]


def fill_in_missing_snippets(existing_snippets, user_email, today):
    """Make sure that the snippets array has a Snippet entry for every week.

    The db may have holes in it -- weeks where the user didn't write a
    snippet.  Augment the given snippets array so that it has no holes,
    by adding in default snippet entries if necessary.  Note it does
    not add these entries to the db, it just adds them to the array.

    Arguments:
       existing_snippets: a list of Snippet objects for a given user.
         The first snippet in the list is assumed to be the oldest
         snippet from that user (at least, it's where we start filling
         from).
       user_email: the email of the person whose snippets it is.
       today: a datetime.date object representing the current day.
         We fill up to then.  If today is wed or before, then we
         fill up to the previous week.  If it's thurs or after, we
         fill up to the current week.

    Returns:
      A new list of Snippet objects, without any holes.
    """
    end_monday = _newsnippet_monday(today)
    if not existing_snippets:         # no snippets at all?  Just do this week
        return [Snippet(email=user_email, week=end_monday)]

    # Add a sentinel, one week past the last week we actually want.
    # We'll remove it at the end.
    existing_snippets.append(Snippet(email=user_email,
                                     week=end_monday + datetime.timedelta(7)))

    all_snippets = [existing_snippets[0]]   # start with the oldest snippet
    for snippet in existing_snippets[1:]:
        while snippet.week - all_snippets[-1].week > datetime.timedelta(7):
            missing_week = all_snippets[-1].week + datetime.timedelta(7)
            all_snippets.append(Snippet(email=user_email, week=missing_week))
        all_snippets.append(snippet)

    # Get rid of the sentinel we added above.
    del all_snippets[-1]

    return all_snippets


class UserPage(webapp.RequestHandler):
    """Show all the snippets for a single user."""

    def get(self):
        if not users.get_current_user():
            return _login_page(self.request, self.response)

        user_email = self.request.get('u', _current_user_email())

        snippets_q = Snippet.all()
        snippets_q.filter('email = ', user_email)
        snippets_q.order('week')            # note this puts oldest snippet first
        snippets = snippets_q.fetch(1000)   # good for many years...

        snippets = fill_in_missing_snippets(snippets, user_email, _TODAY)
        snippets.reverse()                  # get to newest snippet first

        template_values = {
            'logout_url': users.create_logout_url('/'),
            'message': self.request.get('msg'),
            'username': user_email,
            'view_week': _existingsnippet_monday(_TODAY),
            'editable': _logged_in_user_has_permission_for(user_email),
            'snippets': snippets,
            }
        path = os.path.join(os.path.dirname(__file__), 'user_snippets.html')
        self.response.out.write(template.render(path, template_values))    


class SummaryPage(webapp.RequestHandler):
    """Show all the snippets for a single week."""
    
    def get(self):
        if not users.get_current_user():
            return _login_page(self.request, self.response)

        week_string = self.request.get('week')
        if week_string:
            week = datetime.datetime.strptime(week_string, '%m-%d-%Y').date()
        else:
            week = _existingsnippet_monday(_TODAY)

        snippets_q = Snippet.all()
        snippets_q.filter('week = ', week)
        snippets = snippets_q.fetch(1000)   # good for many users...
        # TODO(csilvers): filter based on wants_to_view

        # Get all the user records so we can categorize snippets.
        user_q = User.all()
        results = user_q.fetch(1000)
        email_to_category = {}
        for result in results:
            email_to_category[result.email] = result.category

        # Collect the snippets by category.  As we see each email,
        # delete it from email_to_category.  At the end of this,
        # email_to_category will hold people who did not give
        # snippets this week.
        snippets_by_category = {}
        for snippet in snippets:
            # Ignore this snippet if we don't have permission to view it.
            if (not snippet.private or
                _can_view_private_snippets(_current_user_email(),
                                           snippet.email)):
                category = email_to_category.get(snippet.email, '(unknown)')
                snippets_by_category.setdefault(category, []).append(snippet)
                del email_to_category[snippet.email]

        # Add in empty snippets for the people who didn't have any.
        for (email, category) in email_to_category.iteritems():
            snippet = Snippet(email=email, week=week,
                              text='(no snippet this week)')
            snippets_by_category.setdefault(category, []).append(snippet)

        # Now get a sorted list, categories in alphabetical order and
        # each snippet-author within the category in alphabetical
        # order.  The data structure is ((category, (snippet, ...)), ...)
        categories_and_snippets = []
        for category in snippets_by_category:
            snippets = snippets_by_category[category]
            snippets.sort(key=lambda snippet: snippet.email)
            categories_and_snippets.append((category, snippets))
        categories_and_snippets.sort()

        template_values = {
            'logout_url': users.create_logout_url('/'),
            'message': self.request.get('msg'),
            # Used only to switch to 'username' mode and to modify settings.
            'username': _current_user_email(),
            'prev_week': week - datetime.timedelta(7),
            'view_week': week,
            'next_week': week + datetime.timedelta(7),
            'categories_and_snippets': categories_and_snippets,
            }
        path = os.path.join(os.path.dirname(__file__), 'weekly_snippets.html')
        self.response.out.write(template.render(path, template_values))    


# TODO(csilvers): would like to move to an ajax model where each
# snippet has a button next to it that says 'edit', and if you click
# that it becomes a textbox with buttons saying 'save' and 'cancel'.
# 'cancel' will go back to the previous state, while 'save' will go
# back to the previous state and send an ajax request to update the
# snippet in the db.

class UpdateSnippet(webapp.RequestHandler):
    def get(self):
        if not users.get_current_user():
            return _login_page(self.request, self.response)

        email = self.request.get('u', _current_user_email())
        if not _logged_in_user_has_permission_for(email):
            raise RuntimeError('You do not have permissions to update user'
                               ' snippets for %s' % email)

        week_string = self.request.get('week')
        week = datetime.datetime.strptime(week_string, '%m-%d-%Y').date()
        assert week.weekday() == 0, 'passed-in date must be a Monday'

        text = self.request.get('snippet')

        private = self.request.get('private') == 'True'

        q = Snippet.all()
        q.filter('email = ', email)
        q.filter('week = ', week)
        result = q.get()
        if result:
            result.text = text   # just update the snippet text
            result.private = private
            db.put(result)       # update the snippet in the db
        else:                    # add the snippet to the db
            db.put(Snippet(email=email, week=week, text=text, private=private))

        # When adding a snippet, make sure we create a user record for
        # that email as well, if it doesn't already exist.
        _get_or_create_user(email)

        self.redirect("/?msg=Snippet+saved&u=%s" % urllib.quote(email))


class Settings(webapp.RequestHandler):
    """Page to display a user's settings (from class User), for modification."""

    def get(self):
        if not users.get_current_user():
            return _login_page(self.request, self.response)

        user_email = self.request.get('u', _current_user_email())
        if not _logged_in_user_has_permission_for(user_email):
            raise RuntimeError('You do not have permissions to view user'
                               ' settings for %s' % user_email)
        user = _get_or_create_user(user_email)

        template_values = {
            'logout_url': users.create_logout_url('/'),
            'message': self.request.get('msg'),
            'username': user.email,
            'view_week': _existingsnippet_monday(_TODAY),
            'user': user,
            # We could get this from user, but we want to replace
            # commas with newlines for printing.
            'wants_to_view': user.wants_to_view.replace(',', '\n'),
            }
        path = os.path.join(os.path.dirname(__file__), 'settings.html')
        self.response.out.write(template.render(path, template_values))


class UpdateSettings(webapp.RequestHandler):
    """Updates the db with modifications from the Settings page."""

    def get(self):
        if not users.get_current_user():
            return _login_page(self.request, self.response)

        user_email = self.request.get('u', _current_user_email())
        if not _logged_in_user_has_permission_for(user_email):
            raise RuntimeError('You do not have permissions to modify user'
                               ' settings for %s' % user_email)
        user = _get_or_create_user(user_email)

        category = self.request.get('category')

        wants_email = self.request.get('reminder_email') == 'yes'

        # We want this list to be comma-separated, but people are
        # likely to use both commas and newlines to separate.  Convert
        # here.  Also get rid of whitespace, which cannot be in emails.
        wants_to_view = self.request.get('to_view').replace('\n', ',')
        wants_to_view = wants_to_view.replace(' ', '')

        user.category = category or '(unknown)'
        user.wants_email = wants_email
        user.wants_to_view = wants_to_view
        db.put(user)

        self.redirect("/settings?msg=Changes+saved&u=%s"
                      % urllib.quote(user_email))


# The following two classes are called by cron.

def _get_email_to_current_snippet_map(today):
    """Return a map from email to True if they've written snippets this week.

    Goes through all users registered on the system, and checks if
    they have a snippet in the db for the appropriate snippet-week for
    'today'.  If so, they get entered into the return-map with value
    True.  If not, they have value False.

    Note that users whose 'wants_email' field is set to False will not
    be included in either list.

    Arguments:
      today: a datetime.date object representing the
        'current' day.  We use the normal algorithm to determine what is
        the most recent snippet-week for this day.

    Returns:
      a map from email (user.email for each user) to True or False,
      depending on if they've written snippets for this week or not.
    """
    user_q = User.all()
    users = user_q.fetch(1000)
    retval = {}
    for user in users:
        if not user.wants_email:         # ignore this user
            continue
        retval[user.email] = False       # assume the worst, for now

    week = _existingsnippet_monday(today)
    snippets_q = Snippet.all()
    snippets_q.filter('week = ', week)
    snippets = snippets_q.fetch(1000)
    for snippet in snippets:
        if snippet.email in retval:      # don't introduce new keys here
            retval[snippet.email] = True

    return retval


class SendReminderEmail(webapp.RequestHandler):
    """Send an email to everyone who doesn't have a snippet for this week."""

    def _send_mail(self, email):
        # TODO(csilvers): make this a template instead.
        body = """\
Just a reminder that weekly snippets are due at 5pm today!  Our
records show you have not yet entered snippet information for last
week.  To do so, visit
   http://weekly-snippets.appspot.com/

If you'd like to stop getting these reminder emails, visit
   http://weekly-snippets.appspot.com/settings
and click 'no' under 'Receive reminder emails'.

Regards,
your friendly neighborhood snippet server
"""
        mail.send_mail(sender=('Khan Academy Snippet Server'
                               ' <csilvers+snippets@khanacademy.org>'),
                       to=email,
                       subject='Weekly snippets due today at 5pm',
                       body=body)

    def get(self):
        email_to_has_snippet = _get_email_to_current_snippet_map(_TODAY)
        for (user_email, has_snippet) in email_to_has_snippet.iteritems():
            if not has_snippet:
                self._send_mail(user_email)


class SendViewEmail(webapp.RequestHandler):
    """Send an email to everyone telling them to look at the week's snippets."""

    def _send_mail(self, email, has_snippets):
        # TODO(csilvers): make this a template instead.
        body = """\
The weekly snippets for last week have been posted.  To see them, visit
   http://weekly-snippets.appspot.com/weekly
"""
        if not has_snippets:
            body += """
It's not too late to enter in snippets for last week if you haven't
already!  To do so, visit
   http://weekly-snippets.appspot.com/
"""
        body += """
If you'd like to stop getting these reminder emails, visit
   http://weekly-snippets.appspot.com/settings
and click 'no' under 'Receive reminder emails'.

Enjoy!
your friendly neighborhood snippet server
"""
        mail.send_mail(sender=('Khan Academy Snippet Server'
                               ' <csilvers+snippets@khanacademy.org>'),
                       to=email,
                       subject='Weekly snippets are ready!',
                       body=body)

    def get(self):
        email_to_has_snippet = _get_email_to_current_snippet_map(_TODAY)
        for (user_email, has_snippet) in email_to_has_snippet.iteritems():
            self._send_mail(user_email, has_snippet)


application = webapp.WSGIApplication([('/', UserPage),
                                      ('/weekly', SummaryPage),
                                      ('/update_snippet', UpdateSnippet),
                                      ('/settings', Settings),
                                      ('/update_settings', UpdateSettings),
                                      ('/admin/send_reminder_email',
                                       SendReminderEmail),
                                      ('/admin/send_view_email',
                                       SendViewEmail),
                                      ],
                                      debug=True)


def main():
    run_wsgi_app(application)


if __name__ == "__main__":
    main()
'''