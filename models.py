"""Class definitions for the Datastore entities used by the Hangman API."""

import random
from datetime import date
from protorpc import messages
from google.appengine.ext import ndb
import json


class User(ndb.Model):
    """User model

    Attributes:
        name: User name
        email: Optional email address of user for spamming purposes
        total_score: Total score of all games played by user
        total_played: Total number of games played by user
        average_score: total_score / total_played
    """
    name = ndb.StringProperty(required=True)
    email = ndb.StringProperty()
    total_score = ndb.IntegerProperty(default=0)
    total_played = ndb.IntegerProperty(default=0)
    average_score = ndb.IntegerProperty(default=0)

    def to_rank_form(self):
        """Return a RankForm representation of the User."""
        return RankForm(user_name=self.name, total_score=self.total_score,
                        total_played=self.total_played,
                        average_score=self.average_score)


class Game(ndb.Model):
    """Game model

    Attributes:
        failed_attempts_allowed: Number of failed attempts to guess a word
            allowed in the game
        game_over: Game over flag
        user: User entity key
        current_level: Entity key of current level being played
        date: Game started date
        score: Game score, updated when level completed and the end of game
    """
    failed_attempts_allowed = ndb.IntegerProperty(required=True)
    game_over = ndb.BooleanProperty(required=True, default=False)
    user = ndb.KeyProperty(required=True, kind='User')
    current_level = ndb.KeyProperty(kind='Level')
    date = ndb.DateProperty(required=True)
    score = ndb.IntegerProperty(default=0)

    @classmethod
    def new_game(cls, user_key, failed_attempts_allowed):
        """Create and return a new game
        Args:
            user_key: user entity key
            failed_attempts_allowed: number of failed attempts to guess a word
            allowed in the game
        Returns:
            Game object
        """
        game = Game(user=user_key,
                    failed_attempts_allowed=failed_attempts_allowed,
                    game_over=False,
                    date=date.today(),
                    score=0)
        game.put()
        game.new_level()
        return game

    def new_level(self):
        """Create a new game level with a new word."""
        level = Level.new_level(self.key)
        self.current_level = level.key
        self.put()

    def update_game(self, guess):
        """Update the game state after a guess is made."""
        level = self.current_level.get()
        level.update_level(guess)

        if level.complete:
            if level.won:
                # update game score
                self.score += level.attempts_remaining
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
        """Return a GameForm representation of the Game."""
        form = GameForm()
        form.urlsafe_key = self.key.urlsafe()
        form.user_name = self.user.get().name
        form.game_over = self.game_over
        form.message = message
        form.date = str(self.date)
        form.score = self.score
        # get current level
        level = self.current_level.get()
        form.guesses = level.guesses
        form.level_complete = level.complete
        # get current word
        word = level.word.get()
        form.attempts_remaining = level.attempts_remaining
        form.clue = word.clue

        if self.game_over:
            # allow user to see the word
            form.guessed_word = word.name
        else:
            form.guessed_word = word.get_guessed_word(level.guesses)

        return form

    def to_score_form(self):
        """Return a ScoreForm representation of the Game."""
        return ScoreForm(user_name=self.user.get().name,
                         date=str(self.date), score=self.score)

    def to_history_form(self):
        """Return a GameHistoryForm representation of the Game."""
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
            guesses = []
            for guess in level.guesses:
                guesses.append(guess)
                moves.append({'level': level.level_number,
                              'guessed_word': word.get_guessed_word(guesses),
                              'guess': guess, 'result': guess in word.name})

        form.moves = json.dumps(moves)
        return form


class Level(ndb.Model):
    """Game level model

    Attributes:
        game: Game entity key
        level_number: Level number in a game, used for history display
        word: Word entity key
        guesses: List of user guesses made in a level
        attempts_remaining: Number of attempts remaining in a level
        complete = Level complete flag (complete is when a word is guessed or
                    a game is over)
        won = Level won flag
    """
    game = ndb.KeyProperty(required=True, kind='Game')
    level_number = ndb.IntegerProperty(default=0)
    word = ndb.KeyProperty(required=True, kind='Word')
    guesses = ndb.StringProperty(repeated=True)
    attempts_remaining = ndb.IntegerProperty(required=True)
    complete = ndb.BooleanProperty(required=True, default=False)
    won = ndb.BooleanProperty(required=True, default=False)

    @classmethod
    def new_level(cls, game_key):
        """Create and return a new game level with a new word
        Args:
            game_key: Game entity key
        Returns:
            Level object
        """
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
                      guesses=[],
                      attempts_remaining=game.failed_attempts_allowed,
                      complete=False,
                      won=False)
        level.put()
        return level

    def update_level(self, guess):
        """Update the level state after a guess is made."""
        self.guesses.append(guess)

        word = self.word.get()

        if len(guess) == len(word.name):
            # word guess
            if guess == word.name:
                # successful word guess, level complete
                self.complete = True
                self.won = True
            else:
                # failed word guess
                self.attempts_remaining -= 1
        else:
            # letter guess
            if "_" not in word.get_guessed_word(self.guesses):
                # successful letter guess, level complete
                self.complete = True
                self.won = True
            elif guess not in word.name:
                # failed letter guess
                self.attempts_remaining -= 1

        if self.attempts_remaining < 1:
            # level failed
            self.complete = True
            self.won = False

        self.put()


class Word(ndb.Model):
    """Word bank model

    Attributes:
        name: The word to be guessed
        clue: A clue for the word to be guessed
    """
    name = ndb.StringProperty(required=True)
    clue = ndb.StringProperty(required=True)

    @staticmethod
    def get_random_word():
        """Return the key of a randomly selected word from word bank."""
        keys = Word.query().fetch(keys_only=True)
        return random.sample(keys, 1)[0]

    @staticmethod
    def import_words():
        """Import words from json file."""
        with open("words.json") as json_file:
            json_data = json.load(json_file)
            for imported_word in json_data:
                word = Word(name=imported_word["name"],
                            clue=imported_word["clue"])
                word.put()

    def get_guessed_word(self, guesses):
        """ Return the word to be guessed, with guessed letters inserted,
            and underscores for letters that are not guessed,
            or if the whole word is guessed in a single attempt,
            return the whole word."""
        guessed_word = list(" _ " * len(self.name))
        for guess in guesses:
            if guess == self.name:
                # word guessed in single attempt
                return ''.join(" {} ".format(c) for c in self.name)
            if len(guess) > 1:
                # failed word guess, ignore
                continue
            indexes = [pos for pos, c in enumerate(self.name) if c == guess]
            if indexes:
                for i in indexes:
                    guessed_word[(i * 3) + 1] = guess
        return ''.join(guessed_word)


class GameForm(messages.Message):
    """GameForm for outbound game state information."""
    urlsafe_key = messages.StringField(1, required=True)
    attempts_remaining = messages.IntegerField(2, required=True)
    game_over = messages.BooleanField(3, required=True)
    message = messages.StringField(4, required=True)
    user_name = messages.StringField(5, required=True)
    guessed_word = messages.StringField(6, required=True)
    guesses = messages.StringField(7, repeated=True)
    clue = messages.StringField(8, required=True)
    date = messages.StringField(9, required=True)
    score = messages.IntegerField(10, required=True)
    level_complete = messages.BooleanField(11, required=True)


class GameHistoryForm(messages.Message):
    """GameHistoryForm for outbound game state information."""
    urlsafe_key = messages.StringField(1, required=True)
    user_name = messages.StringField(2, required=True)
    date = messages.StringField(3, required=True)
    score = messages.IntegerField(4, required=True)
    moves = messages.StringField(5, required=True)


class GameForms(messages.Message):
    """Return multiple GameForms."""
    items = messages.MessageField(GameForm, 1, repeated=True)


class NewGameForm(messages.Message):
    """Used to create a new game."""
    user_name = messages.StringField(1, required=True)
    email = messages.StringField(2)
    failed_attempts_allowed = messages.IntegerField(3, default=6)


class MakeMoveForm(messages.Message):
    """Used to make a move in an existing game."""
    guess = messages.StringField(1, required=True)


class ScoreForm(messages.Message):
    """ScoreForm for outbound Score information."""
    user_name = messages.StringField(1, required=True)
    date = messages.StringField(2, required=True)
    score = messages.IntegerField(3, required=True)


class ScoreForms(messages.Message):
    """Return multiple ScoreForms."""
    items = messages.MessageField(ScoreForm, 1, repeated=True)


class RankForm(messages.Message):
    """RankForm for outbound Rank information."""
    user_name = messages.StringField(1, required=True)
    total_score = messages.IntegerField(2, required=True)
    total_played = messages.IntegerField(3, required=True)
    average_score = messages.IntegerField(4, required=True)


class RankForms(messages.Message):
    """Return multiple RankForms."""
    items = messages.MessageField(RankForm, 1, repeated=True)


class StringMessage(messages.Message):
    """StringMessage-- outbound (single) string message."""
    message = messages.StringField(1, required=True)
