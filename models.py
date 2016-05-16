"""Class definitions for the Datastore entities used by the Hangman API."""

import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb
import json
import logging


class User(ndb.Model):
    """User model"""
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()
    total_score = ndb.IntegerProperty(default=0)
    total_played = ndb.IntegerProperty(default=0)
    average_score = ndb.IntegerProperty(default=0)

    def to_rank_form(self):
        """Returns a RankForm representation of the User"""
        return RankForm(user_name=self.name, total_score=self.total_score,
                        total_played=self.total_played,
                        average_score=self.average_score)


class Game(ndb.Model):
    """Game model"""
    attempts_allowed = ndb.IntegerProperty(required=True)
    game_over = ndb.BooleanProperty(required=True, default=False)
    user = ndb.KeyProperty(required=True, kind='User')
    current_level = ndb.KeyProperty(kind='Level')
    date = ndb.DateProperty(required=True)
    score = ndb.IntegerProperty(default=0)

    @classmethod
    def new_game(cls, user_key, attempts_allowed):
        """Creates and returns a new game"""
        game = Game(user=user_key,
                    attempts_allowed=attempts_allowed,
                    game_over=False,
                    date=date.today(),
                    score=0)
        game.put()
        game.new_level()
        return game

    def new_level(self):
        """Creates a new game level with a new word"""
        level = Level.new_level(self.key)
        self.current_level = level.key
        self.put()

    def update_game(self, guess):
        """Update the game state after a guess"""
        level = self.current_level.get()
        level.update_level(guess, self.attempts_allowed)

        if level.complete:
            if level.won:
                # update game Score
                attempts = level.word.get() \
                            .get_failed_attempts_count(level.attempted_letters)
                self.score += self.attempts_allowed - attempts
            else:
                # game over
                self.game_over = True
                # update user totals for ranking
                user = self.user.get()
                user.total_played += 1
                user.total_score += self.score
                user.average_score = int(round(user.total_score /
                                         user.total_played))
                user.put()
            self.put()

    def to_form(self, message=""):
        """Returns a GameForm representation of the Game"""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.game_over = self.game_over
        form.message = message
        form.date = str(self.date)
        form.score = self.score
        # get current level
        level = self.current_level.get()
        form.attempted_letters = level.attempted_letters
        form.level_complete = level.complete
        # get current word
        word = level.word.get()
        form.attempts_remaining = self.attempts_allowed - \
            word.get_failed_attempts_count(level.attempted_letters)
        form.clue = word.clue

        if self.game_over:
            # allow user to see the word
            form.guessed_word = word.name
        else:
            form.guessed_word = word.get_guessed_word(level.attempted_letters)

        return form

    def to_score_form(self):
        """Returns a ScoreForm representation of the Game"""
        return ScoreForm(user_name=self.user.get().name,
                         date=str(self.date), score=self.score)

    def to_history_form(self):
        """Returns a GameHistoryForm representation of the Game"""
        form = GameHistoryForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.date = str(self.date)
        form.score = self.score

        # create a list of guesses made in the game
        moves = []
        levels = Level.query(Level.game == self.key).order(Level.level_number)
        for level in levels:
            word = level.word.get()
            letters = ""
            for c in level.attempted_letters:
                letters += c
                moves.append({'level': level.level_number,
                              'guessed_word': word.get_guessed_word(letters),
                              'guess': c, 'result': c in word.name})

        form.moves = json.dumps(moves)
        return form


class Level(ndb.Model):
    """Game level model"""
    game = ndb.KeyProperty(required=True, kind='Game')
    level_number = ndb.IntegerProperty(default=0)
    word = ndb.KeyProperty(required=True, kind='Word')
    attempted_letters = ndb.StringProperty()
    complete = ndb.BooleanProperty(required=True, default=False)
    won = ndb.BooleanProperty(required=True, default=False)

    @classmethod
    def new_level(cls, game_key):
        """Creates and returns a new game level with a new word"""
        game = game_key.get()

        level_number = Level.query(Level.game == game.key).count() + 1

        # try to get a word that has not been played by the user,
        # if there are any unplayed words left
        word_key = Word.get_random_word()
        used_word_keys = []
        user_game_keys = Game.query(Game.user == game.user) \
            .fetch(keys_only=True)
        for user_game_key in user_game_keys:
            user_level_keys = Level.query(Level.game == user_game_key) \
                                            .fetch(keys_only=True)
            for user_level_key in user_level_keys:
                used_word_keys.append(user_level_key.get().word)

        word_count = Word.query().count()
        if len(used_word_keys) < word_count:
            while word_key in used_word_keys:
                word_key = Word.get_random_word()

        level = Level(game=game_key,
                      word=word_key,
                      level_number=level_number,
                      attempted_letters="",
                      complete=False,
                      won=False)
        level.put()
        return level

    def update_level(self, guess, attempts_allowed):
        """Update the level state after a guess"""
        self.attempted_letters = self.attempted_letters + guess

        word = self.word.get()
        
        if len(guess) == len(word):
            # word guess
            if guess == word:
                # successful word guess

        if "_" not in word.get_guessed_word(self.attempted_letters):
            # level completed successfully
            self.complete = True
            self.won = True
        else:
            attempts_remaining = attempts_allowed - \
                    word.get_failed_attempts_count(self.attempted_letters)
            if attempts_remaining < 1:
                # level failed
                self.complete = True
                self.won = False

        self.put()


class Word(ndb.Model):
    """Word bank model"""
    name = ndb.StringProperty(required=True)
    clue = ndb.StringProperty(required=True)

    @staticmethod
    def get_random_word():
        """Return the key of a randomly selected word from word bank"""
        keys = Word.query().fetch(keys_only=True)
        return random.sample(keys, 1)[0]

    @staticmethod
    def import_words():
        """Import words from json file"""
        with open("words.json") as json_file:
            json_data = json.load(json_file)
            for imported_word in json_data:
                word = Word(name=imported_word["name"],
                            clue=imported_word["clue"])
                word.put()

    def get_guessed_word(self, attempted_letters):
        """ Returns the word with guessed letters inserted
            and blanks for letters not guessed"""
        guessed_word = list("_" * len(self.name))
        for c in attempted_letters:
            indexes = [pos for pos, char in enumerate(self.name) if char == c]
            if indexes:
                for i in indexes:
                    guessed_word[i] = c
        return ''.join(guessed_word)

    def get_failed_attempts_count(self, attempted_letters):
        """Returns count of failed attempts to guess a letter"""
        failed_attempts = 0
        for c in attempted_letters:
            if c not in self.name:
                failed_attempts += 1
        return failed_attempts


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
    score = messages.IntegerField(10, required=True)
    level_complete = messages.BooleanField(11, required=True)


class GameHistoryForm(messages.Message):
    """GameHistoryForm for outbound game state information"""
    urlsafe_key = messages.StringField(1, required=True)
    user_name = messages.StringField(2, required=True)
    date = messages.StringField(3, required=True)
    score = messages.IntegerField(4, required=True)
    moves = messages.StringField(5, required=True)


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
    score = messages.IntegerField(3, required=True)


class ScoreForms(messages.Message):
    """Return multiple ScoreForms"""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class RankForm(messages.Message):
    """RankForm for outbound Rank information"""
    user_name = messages.StringField(1, required=True)
    total_score = messages.IntegerField(2, required=True)
    total_played = messages.IntegerField(3, required=True)
    average_score = messages.IntegerField(4, required=True)


class RankForms(messages.Message):
    """Return multiple RankForms"""
    items = messages.MessageField(RankForm, 1, repeated=True)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message"""
    message = messages.StringField(1, required=True)
