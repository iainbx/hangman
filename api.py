"""An API for a Hangman game that runs on the Google App Engine platform."""


import logging
import endpoints
from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.ext import ndb

from models import User, Game, Level, Word
from models import StringMessage, NewGameForm, GameForm, MakeMoveForm, \
    ScoreForms, GameForms, RankForms, GameHistoryForm
from utils import get_by_urlsafe

NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
GAME_REQUEST = endpoints.ResourceContainer(
    urlsafe_game_key=messages.StringField(1),)
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1),)
USER_REQUEST = endpoints.ResourceContainer(
    user_name=messages.StringField(1),
    email=messages.StringField(2))
HIGH_SCORES_REQUEST = endpoints.ResourceContainer(
    number_of_results=messages.IntegerField(1))


@endpoints.api(name='hangman', version='v1')
class HangmanApi(remote.Service):
    """API for a hangman game."""

    def __init__(self):
        # initialize word bank
        key = Word.query().get(keys_only=True)
        if key is None:
            # import word bank from file
            Word.import_words()

    @endpoints.method(request_message=NEW_GAME_REQUEST,
                      response_message=GameForm,
                      path='game',
                      name='new_game',
                      http_method='POST')
    def new_game(self, request):
        """ Creates new game.
            Creates a new user, if it doesnt already exist.
        """
        if request.attempts_allowed not in range(1, 10):
            raise endpoints.BadRequestException('Attempts allowed must be '
                                                'between 1 and 10!')

        user = User.query(User.name == request.user_name).get()
        if not user:
            # create new user
            user = User(name=request.user_name,
                        email=request.email,
                        total_score=0,
                        total_played=0)
            user_key = user.put()
        else:
            user_key = user.key

        game = Game.new_game(user_key, request.attempts_allowed)

        return game.to_form('Make your move, {0}!'.format(user.name))

    @endpoints.method(request_message=GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Returns the specified game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            if game.game_over:
                msg = "You scored {0}.".format(game.score)
            else:
                level = game.current_level.get()
                if level.complete:
                    msg = "Level complete."
                else:
                    msg = "Make your move, {0}!".format(game.user.get().name)

            return game.to_form(msg)
        else:
            raise endpoints.NotFoundException('Game not found!')

    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move in a game. 
            Guess a letter of the word, or the whole word.
            Returns the game state."""
        if not request.guess.isalpha():
            raise endpoints.BadRequestException('Guess should be at least 1 '
                                                'letter!')

        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            return game.to_form('Game already over!')
        
        level = game.current_level.get()
        if level.complete:
            return game.to_form('Level already complete, get the next level!')
            
        word = level.word.get()
        if len(request.guess) != len(word.name) and len(request.guess) != 1:
            raise endpoints.BadRequestException('Guess 1 letter or the whole '
                                                'word!')

        if request.guess in level.guesses:
            raise endpoints.BadRequestException('You already made this guess!')

        game.update_game(request.guess)

        if game.game_over:
            return game.to_form('Game Over! You scored {0}.'
                                .format(game.score))

        level = game.current_level.get()
        if level.complete:
            return game.to_form('Level complete, get the next level.')

        if request.guess in word.name:
            msg = "You chose well!"
        else:
            msg = "You chose poorly!"

        return game.to_form(msg)

    @endpoints.method(request_message=GAME_REQUEST,
                      response_message=GameForm,
                      path='game/next_level/{urlsafe_game_key}',
                      name='next_level',
                      http_method='PUT')
    def next_level(self, request):
        """Gets the next word in a game. Returns the game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            return game.to_form('Game already over!')
        if not game.current_level.get().complete:
            return game.to_form('Current level is not complete!')

        # create a new level with a new word
        game.new_level()

        return game.to_form('Make your move, {0}!'
                            .format(game.user.get().name))

    @endpoints.method(request_message=GAME_REQUEST,
                      response_message=StringMessage,
                      path='game/cancel/{urlsafe_game_key}',
                      name='cancel_game',
                      http_method='DELETE')
    def cancel_game(self, request):
        """Deletes the specified game."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            return game.to_form('Game completed. Cannot delete.')

        # delete any levels
        level_keys = Level.query(Level.game == game.key).fetch(keys_only=True)
        ndb.delete_multi(level_keys)

        game.key.delete()
        return StringMessage(message='Game deleted.')

    @endpoints.method(request_message=HIGH_SCORES_REQUEST,
                      response_message=ScoreForms,
                      path='scores/high_scores',
                      name='get_high_scores',
                      http_method='GET')
    def get_high_scores(self, request):
        """ Returns top scores.
            If number_of_reults parameter is omitted, will return top 10."""
        result_count = 10
        if request.number_of_results is not None:
            result_count = request.number_of_results
        return ScoreForms(items=[
            game.to_score_form() for game in Game
            .query(Game.game_over == True)
            .order(-Game.score).fetch(result_count)])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=GameForms,
                      path='games/user/{user_name}',
                      name='get_user_games',
                      http_method='GET')
    def get_user_games(self, request):
        """Returns all of an individual User's active games."""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A User with that name does not exist!')
        games = Game.query(Game.user == user.key, Game.game_over == False)
        return GameForms(items=[game.to_form() for game in games])

    @endpoints.method(request_message=USER_REQUEST,
                      response_message=GameForms,
                      path='games/completed/user/{user_name}',
                      name='get_user_games_completed',
                      http_method='GET')
    def get_user_games_completed(self, request):
        """Returns all of an individual User's completed games."""
        user = User.query(User.name == request.user_name).get()
        if not user:
            raise endpoints.NotFoundException(
                    'A User with that name does not exist!')
        games = Game.query(Game.user == user.key, Game.game_over == True)
        return GameForms(items=[game.to_form() for game in games])

    @endpoints.method(response_message=RankForms,
                      path='user/rankings',
                      name='get_user_rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        """Returns all user rankings."""
        users = User.query().order(-User.average_score)
        return RankForms(items=[user.to_rank_form() for user in users])

    @endpoints.method(request_message=GAME_REQUEST,
                      response_message=GameHistoryForm,
                      path='game/history/{urlsafe_game_key}',
                      name='get_game_history',
                      http_method='GET')
    def get_game_history(self, request):
        """Returns the history of the specified game."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            return game.to_history_form()
        else:
            raise endpoints.NotFoundException('Game not found!')


api = endpoints.api_server([HangmanApi])
