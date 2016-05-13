# Hangman
A Hangman game utilizing Google Cloud Endpoints, Google App Engine, Google Datastore, 
and Python for the back end API, with an AngularJS application for the front end user interface.


##Prerequisites
The API endpoints are written in Python 2.7 and require the 
[App Engine SDK for Python](https://cloud.google.com/appengine/downloads) 
to be installed in order to run locally or to deploy to the Google cloud.


## Installation
To get the files, clone this repository on the command line.
```Shell
git clone https://github.com/iainbx/hangman.git
```


##Files And Folders
 - api.py: Contains the API endpoints.
 - app.yaml: App configuration.
 - cron.yaml: Cron job configuration.
 - main.py: Handler for cron job.
 - models.py: Entity and message definitions.
 - utils.py: Helper function for retrieving ndb.Models by urlsafe Key string.
 - words.json: List of words used by the game.
 - app: Folder containing a sample AngularJS web site that utilizes the endpoints.


##Set-Up Instructions
1.  Update the value of `application` in `app.yaml` to an app ID that you have registered
 in the Google App Engine admin console and would like to use to host your instance of this sample.
1.  Run the application in the Local Development Server with the following `python` command on the 
command line.
    ```Shell
    dev_appserver.py DIR
    ```
    where DIR is the path to the application folder containing the `app.yaml` file.

1.  Browse to the home page of the web site (by default [localhost:8080/](http://localhost:8080/)) and play the game.
1.  Try the endpoints by visiting the Google APIs Explorer, [localhost:8080/_ah/api/explorer](http://localhost:8080/_ah/api/explorer).

##Game Description
Start a new hangman game by calling the `new_game` endpoint with a user name. A new user will be created by the
endpoint if needed. The endpoint will return a `guesssed_word` value, which is the same length as the word
to be guessed, but filled with underscores.  A clue for the word to be guessed is also returned. 
Guess a letter in the word 
by calling the `make_move` endpoint with the game's urlsafe key, returned from `new_game`. If you guessed
correctly the `guessed_word` property will be updated to show the guessed letters in their correct positions.
If you guessed incorrectly, the `attempts_remaining` property will be decremented. Keep guessing until you
guess the word or run out of attempts remaining. If you guess the word, your score will be increased, 
and you can retrieve another word to be guessed by calling the `next_level` endpoint with the game key. You
can then call `make_move` again to guess letters. The game is over when you run out of attempts remaining.

##Endpoints
- **new_game**
  - Path: 'game'
  - Method: POST
  - Parameters: user_name, email (optional), attempts (optional, default=6)
  - Returns: GameForm with initial game state.
  - Description: Creates a new Game. Creates the first level of the game, containing the first
  word to be quessed. If a user does not exist with the specified user_name,
  a new user is created. The attempts parameter is the number of failed attempts to guess
  a word that are allowed before the game will end.
     
- **make_move**
  - Path: 'game/{urlsafe_game_key}'
  - Method: PUT
  - Parameters: urlsafe_game_key, guess
  - Returns: GameForm with new game state.
  - Description: Accepts a character 'guess' and returns the updated state of the game.
  If this causes a game to end, the user score will be updated.
  If the word is guessed, the level_complete flag is set to true, and a call will need to
  be made to the next_level endpoint, to retrieve the next word to guess.

- **next_level**
  - Path: 'game/next_level/{urlsafe_game_key}'
  - Method: GET
  - Parameters: urlsafe_game_key
  - Returns: GameForm with current game state.
  - Description: Call this endpoint to retrieve the next word to guess in a game,
  after a word has been guessed. The make_move endpoint can then be called again to
  guess the new word.

- **get_game**
  - Path: 'game/{urlsafe_game_key}'
  - Method: GET
  - Parameters: urlsafe_game_key
  - Returns: GameForm with current game state.
  - Description: Returns the current state of a game.

- **cancel_game**
  - Path: 'game/cancel/{urlsafe_game_key}'
  - Method: POST
  - Parameters: urlsafe_game_key
  - Returns: StringMessage.
  - Description: Deletes the specified game and associated levels, if it is active.

- **get_game_history**
  - Path: 'game/history/{urlsafe_game_key}'
  - Method: GET
  - Parameters: urlsafe_game_key
  - Returns: GameForm with current game state.
  - Description: Returns the history of the specified game, including guesses.

- **get_user_games**
  - Path: 'games/user/{user_name}'
  - Method: GET
  - Parameters: user_name
  - Returns: GameForms. 
  - Description: Returns all active games for a specified user (unordered).
  Will raise a NotFoundException if the User does not exist.
  
- **get_user_games_completed**
  - Path: 'games/completed/user/{user_name}'
  - Method: GET
  - Parameters: user_name
  - Returns: GameForms. 
  - Description: Returns all completed games for a specified user (unordered).
  Will raise a NotFoundException if the User does not exist.
  
- **get_user_rankings**
  - Path: 'user/rankings'
  - Method: GET
  - Parameters: None
  - Returns: RankForms. 
  - Description: Returns all user rankings, ordered by rank. Users are ranked based on
  their average score.
  
- **get_high_scores**
  - Path: 'scores/high_scores'
  - Method: GET
  - Parameters: number_of_results (optional, default=10)
  - Returns: ScoreForms.
  - Description: Returns the specied number of high scores, ordered by score descending.
  If number_of_results parameter is omitted, returns top ten scores.
  

##Models
- **User**
  - Stores unique user_name, (optional) email address, total score, and average score.
  
- **Game**
  - Stores unique game states. Associated with User model via KeyProperty.
  
- **Level**
  - Stores unique game levels. Associated with Game model via KeyProperty.
  Associated with Word model via KeyProperty.
  
- **Word**
  - Stores the list of words and clues used by the game.
    
##Forms
- **GameForm**
  - Representation of a Game's state (urlsafe_key, attempts_remaining,
  game_over flag, message, user_name, guessed_word, attempted_letters, clue, date, score, level_complete flag).
- **GameHistoryForm**
  - Representation of a completed Game's history (urlsafe_key, user_name,
  date, score, list of moves made in the game).
- **GameForms**
  - Multiple GameForm container.
- **NewGameForm**
  - Used to create a new game (user_name, email, attempts allowed)
- **MakeMoveForm**
  - Inbound make move form (guess).
- **ScoreForm**
  - Representation of a completed game's Score (user_name, date, score).
- **ScoreForms**
  - Multiple ScoreForm container.
- **RankForm**
  - Representation of a user's rank (user_name, total_score, total_played, average_score).
- **RankForms**
  - Multiple RankForm container.
- **StringMessage**
  - General purpose String container.