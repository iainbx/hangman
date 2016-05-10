"""models.py - This file contains the class definitions for the Datastore
entities used by the Game. Because these classes are also regular Python
classes they can include methods (such as 'to_form' and 'new_game')."""

import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb
import json
import logging


class User(ndb.Model):
    """User model"""
    name = ndb.StringProperty(required=True)
    email =ndb.StringProperty()
    total_score = ndb.IntegerProperty(default=0)
    total_played = ndb.IntegerProperty(default=0)


    def to_rank_form(self):
        return RankForm(user_name=self.name, total_score=self.total_score,
                         total_played=self.total_played)


class Game(ndb.Model):
    """Game model"""
    attempts_allowed = ndb.IntegerProperty(required=True)
    attempted_letters = ndb.StringProperty()
    game_over = ndb.BooleanProperty(required=True, default=False)
    user = ndb.KeyProperty(required=True, kind='User')
    word = ndb.KeyProperty(required=True, kind='Word')
    date = ndb.DateProperty(required=True)
    won = ndb.BooleanProperty(required=True, default=False)
    score = ndb.IntegerProperty(default=0)


    @classmethod
    def new_game(cls, user, word, attempts):
        """Creates and returns a new game"""
        
        game = Game(user=user,
                    word=word,
                    attempts_allowed=attempts,
                    attempted_letters = "",
                    game_over=False,
                    date=date.today(),
                    won=False,
                    score=0)
        game.put()
        return game

    def to_form(self, message=""):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.attempts_remaining = self.get_attempts_remaining()
        form.game_over = self.game_over
        form.message = message
        form.attempted_letters = self.attempted_letters
        form.date = str(self.date)
        form.score = self.score
        form.won = self.won
        word = self.word.get()
        form.clue = word.clue
        if self.game_over:
            # allow user to see the word
            form.guessed_word = word.name
        else:
            form.guessed_word = self.get_guessed_word(word)
        return form


    def to_score_form(self):
        return ScoreForm(user_name=self.user.get().name, won=self.won,
                            date=str(self.date), score=self.score)


    def to_history_form(self):
        """Returns a GameHistoryForm representation of the Game"""
        form = GameHistoryForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.attempts_remaining = self.get_attempts_remaining()
        form.game_over = self.game_over
        form.attempted_letters = self.attempted_letters
        form.date = str(self.date)
        form.score = self.score
        form.won = self.won
        word = self.word.get()
        form.clue = word.clue

        if self.game_over:
            # allow user to see the word
            form.guessed_word = word.name
            form.message = "Game Over."
            if self.won:
                form.message += " You Won! You scored {0}.".format(self.score)
            else:
                form.message += " You Lost!"
        else:
            form.guessed_word = self.get_guessed_word(word)
            form.message = "Game is unfinished."

        form.moves = json.dumps([{'guess': c, 'result': c in word.name} for c in self.attempted_letters])
        return form


    def get_guessed_word(self, word=None):
        """ Returns the word with guessed letters and blanks for letters not guessed"""
        if word is None:
            word = self.word.get()
        guessed_word = list("_" * len(word.name))
        for c in self.attempted_letters:
            indexes = [pos for pos, char in enumerate(word.name) if char == c]
            if indexes:
                for i in indexes:
                    guessed_word[i] = c
        return ''.join(guessed_word)


    def get_attempts_remaining(self):
        word = self.word.get().name
        attempts_remaining = self.attempts_allowed - len(self.attempted_letters)
        for c in self.attempted_letters:
            if c in word:
                attempts_remaining += 1
        return attempts_remaining


    def end_game(self, won=False):
        """Ends the game - if won is True, the player won. - if won is False,
        the player lost."""
        self.game_over = True
        # score = attempts remaining
        self.score=self.get_attempts_remaining()
        self.won = self.is_won()
        self.put()
    
    
    def is_won(self):
        return "_" not in self.get_guessed_word()


class Word(ndb.Model):
    """Word bank model"""
    name = ndb.StringProperty(required=True)
    clue =ndb.StringProperty(required=True)

    
    @staticmethod
    def get_random_word():
        """Return the key of a randomly selected word from word bank"""
        keys = Word.query().fetch(keys_only=True)
        return random.sample(keys,1)[0]


    @staticmethod
    def import_words():
        """Import words from json file"""
        with open("words.json") as json_file:
            json_data = json.load(json_file)
            for imported_word in json_data:
                logging.info(imported_word)
                word = Word(name=imported_word["name"],clue=imported_word["clue"])
                word.put()


class GameForm(messages.Message):
    """GameForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    attempts_remaining = messages.IntegerField(2, required=True)
    game_over = messages.BooleanField(3, required=True)
    message = messages.StringField(4, required=True)
    user_name = messages.StringField(5, required=True)
    guessed_word = messages.StringField(6, required=True)
    attempted_letters = messages.StringField(7, required=True)
    clue = messages.StringField(8, required=True)
    date = messages.StringField(9, required=True)
    won = messages.BooleanField(10, required=True)
    score = messages.IntegerField(11, required=True)


class GameHistoryForm(messages.Message):
    """GameHistoryForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    attempts_remaining = messages.IntegerField(2, required=True)
    game_over = messages.BooleanField(3, required=True)
    message = messages.StringField(4, required=True)
    user_name = messages.StringField(5, required=True)
    guessed_word = messages.StringField(6, required=True)
    attempted_letters = messages.StringField(7, required=True)
    clue = messages.StringField(8, required=True)
    date = messages.StringField(9, required=True)
    won = messages.BooleanField(10, required=True)
    score = messages.IntegerField(11, required=True)
    moves = messages.StringField(12, required=True)


class GameForms(messages.Message):
    """Return multiple GameForms"""
    items = messages.MessageField(GameForm, 1, repeated=True)


class NewGameForm(messages.Message):
    """Used to create a new game"""
    user_name = messages.StringField(1, required=True)
    email = messages.StringField(2)
    attempts = messages.IntegerField(3, default=6)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game"""
    guess = messages.StringField(1, required=True)


class ScoreForm(messages.Message):
    """ScoreForm for outbound Score information"""
    user_name = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    won = messages.BooleanField(3, required=True)
    score = messages.IntegerField(4, required=True)


class ScoreForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class RankForm(messages.Message):
    """RankForm for outbound Rank information"""
    user_name = messages.StringField(1, required=True)
    total_score = messages.IntegerField(2, required=True)
    total_played = messages.IntegerField(3, required=True)


class RankForms(messages.Message):
    """Return multiple RankForms"""
    items = messages.MessageField(RankForm, 1, repeated=True)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)
