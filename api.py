"""api.py - Create and configure the Game API exposing the resources.
This can also contain game logic. For more complex games it would be wise to
move game logic to another file. Ideally the API will be simple, concerned
primarily with communication to/from the API's users."""


import logging
import endpoints
from protorpc import remote, messages
from google.appengine.api import memcache
from google.appengine.api import taskqueue

from models import User, Game, Word
from models import StringMessage, NewGameForm, GameForm, MakeMoveForm,\
    ScoreForms, GameForms, RankForms, GameHistoryForm
from utils import get_by_urlsafe

NEW_GAME_REQUEST = endpoints.ResourceContainer(NewGameForm)
GET_GAME_REQUEST = endpoints.ResourceContainer(
        urlsafe_game_key=messages.StringField(1),)
CANCEL_GAME_REQUEST = endpoints.ResourceContainer(
        urlsafe_game_key=messages.StringField(1),)
MAKE_MOVE_REQUEST = endpoints.ResourceContainer(
    MakeMoveForm,
    urlsafe_game_key=messages.StringField(1),)
USER_REQUEST = endpoints.ResourceContainer(user_name=messages.StringField(1),
                                           email=messages.StringField(2))
HIGH_SCORES_REQUEST = endpoints.ResourceContainer(number_of_results=messages.IntegerField(1))


@endpoints.api(name='hangman', version='v1')
class HangmanApi(remote.Service):
    """Game API"""
    

    def __init__(self):
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
        """ Creates new game
            Creates new user, if it doesnt already exist
        """
        word_key = Word.get_random_word()
        user = User.query(User.name == request.user_name).get()
        if not user:
            # create new user
            user = User(name=request.user_name, email=request.email)
            user_key = user.put()
        else:
            user_key = user.key
            # try to get a word that has not been played by the user,
            # if there are any unplayed words left
            user_games = Game.query(Game.user == user.key).fetch()
            word_count = Word.query().count()
            if len(user_games) < word_count:
                while word_key in [user_game.word for user_game in user_games]:
                    word_key = Word.get_random_word()

        game = Game.new_game(user_key, word_key, request.attempts)

        return game.to_form('Make your move, {0}!'.format(user.name))


    @endpoints.method(request_message=GET_GAME_REQUEST,
                      response_message=GameForm,
                      path='game/{urlsafe_game_key}',
                      name='get_game',
                      http_method='GET')
    def get_game(self, request):
        """Returns the specified game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game:
            if game.game_over:
                msg = "Game Over."
                if game.won:
                    msg += " You Won! You scored {0}.".format(game.score)
                else:
                    msg += " You Lost!"
            else:
                msg = "Make your move, {0}!".format(game.user.get().name) 

            return game.to_form(msg)
        else:
            raise endpoints.NotFoundException('Game not found!')


    @endpoints.method(request_message=MAKE_MOVE_REQUEST,
                      response_message=GameForm,
                      path='game/make_move/{urlsafe_game_key}',
                      name='make_move',
                      http_method='PUT')
    def make_move(self, request):
        """Makes a move in a game. Returns the game state."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            return game.to_form('Game already over!')
            
        game.attempted_letters = game.attempted_letters + request.guess
           
        if game.is_won():
            game.end_game(True)
            # update user totals for ranking
            user = game.user.get()
            user.total_played += 1
            user.total_score += game.score
            user.put()
            return game.to_form('You won! You scored {0}.'.format(game.score))
        
        if request.guess in game.word.get().name:
            msg = "You chose well!"
        else:
            msg = "You chose poorly!"

        attempts_remaining = game.get_attempts_remaining()
        if attempts_remaining < 1:
            game.end_game(False)
            return game.to_form(msg + ' You lost!')
        else:
            game.put()
            return game.to_form(msg)
            

    @endpoints.method(request_message=CANCEL_GAME_REQUEST,
                        response_message=StringMessage,
                        path='game/cancel/{urlsafe_game_key}',
                        name='cancel_game',
                        http_method='POST')
    def cancel_game(self, request):
        """Deletes the specified game."""
        game = get_by_urlsafe(request.urlsafe_game_key, Game)
        if game.game_over:
            return game.to_form('Game completed. Cannot delete.')
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
        logging.info(request.number_of_results)
        result_count = 10
        if request.number_of_results is not None:
            result_count = request.number_of_results
        return ScoreForms(items=[game.to_score_form() for game in Game.query().order(-Game.score).fetch(result_count)])


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
                      path='games/user/rankings',
                      name='get_user_rankings',
                      http_method='GET')
    def get_user_rankings(self, request):
        """Returns all user rankings."""
        users = User.query().order(-User.total_score, User.total_played)
        return RankForms(items=[user.to_rank_form() for user in users])


    @endpoints.method(request_message=GET_GAME_REQUEST,
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