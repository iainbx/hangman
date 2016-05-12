#!/usr/bin/env python

"""main.py - This file contains handlers that are called by taskqueue and/or
cronjobs."""
import logging

import webapp2
from google.appengine.api import mail, app_identity

from models import User, Game


class SendReminderEmail(webapp2.RequestHandler):
    def get(self):
        """ Send a reminder email to each User with an email and unfinshed games.
            Called every day using a cron job."""
        app_id = app_identity.get_application_id()
        users = User.query(User.email != None)
        for user in users:
            games = Game.query(Game.user == user.key, Game.game_over == False)
            if games.count() == 0:
                continue

            subject = 'A reminder from the hangman!'
            body = """Hello {0}, we have unfinshed business at {1}.appspot.com.
            """.format(user.name, app_id)

            html = """Hello {0}, we have unfinshed business:<br/>
            """.format(user.name)

            for game in games:
                html += """<a href='https://{0}.appspot.com#/game/{1}'>
                    unfinished game</a>
                    <br/>""".format(app_id, game.key.urlsafe())

            # This will send test emails, the arguments to send_mail are:
            # from, to, subject, body
            mail.send_mail(sender='noreply@{}.appspotmail.com'.format(app_id),
                           to=user.email,
                           subject=subject,
                           body=body,
                           html=html)


app = webapp2.WSGIApplication([
    ('/crons/send_reminder', SendReminderEmail),
], debug=True)
