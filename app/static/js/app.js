// AngularJS App
var hangmanApp = angular.module('hangmanApp', ['ngRoute'])

// routing
hangmanApp.config(['$routeProvider',
    function ($routeProvider) {
        $routeProvider.
            when('/game/:websafeGameKey', {
                templateUrl: '/partials/play_game.html',
                controller: 'GameController'
            }).
            when('/highscores', {
                templateUrl: '/partials/high_scores.html',
                controller: 'HighScoresController'
            }).
            when('/mygames', {
                templateUrl: '/partials/user_games.html',
                controller: 'UserGamesController'
            }).
            when('/', {
                templateUrl: '/partials/new_game.html',
                controller: 'NewGameController'
            }).
            otherwise({
                redirectTo: '/'
            });
    }]);

hangmanApp.factory('User',function(){
  return {name:''};
});

// Navigation bar controller
hangmanApp.controller('NavController', function ($scope, $location, User) {
    $scope.user_name = User.name;
    $scope.$watch(function () { return User.name; }, function (value) {
        $scope.user_name = value;
    });

    $scope.isActive = function (viewLocation) { 
        return viewLocation === $location.path();
    };
    
    $scope.show_high_scores = function() {
        $location.path("/highscores");
    };
    
    $scope.show_user_games = function() {
        $location.path("/mygames");
    };
});
    
// High Scores controller
hangmanApp.controller('HighScoresController', function ($scope, $location, User) {
    gapi.client.hangman.get_high_scores().execute(function (resp) {
        if (!resp.code) {
            $scope.scores = resp.items;
            $scope.$apply();
        }
    });
});

// User Games controller
hangmanApp.controller('UserGamesController', function ($scope, $location, User) {
    gapi.client.hangman.get_user_games({
            'user_name': User.name
        }).execute(function (resp) {
        if (!resp.code) {
            $scope.games = resp.items;
            $scope.$apply();
        }
    });
});

// new game controller
hangmanApp.controller('NewGameController', function ($scope, $location, User) {
    $scope.user_name = User.name;
    
    $scope.play = function (user_name, email) {
        User.name = user_name;
        gapi.client.hangman.new_game({
            'user_name': user_name,
            'email': email
        }).execute(function (resp) {
            if (!resp.code) {
                $scope.user_name = resp.user_name;
                $location.path("/game/" + resp.urlsafe_key);
                $scope.$apply();
            }
        });
    };
    
});

// play game controller
hangmanApp.controller('GameController', function ($scope, $routeParams, $location, User) {
    $scope.game_key = $routeParams.websafeGameKey;
    canvas.init();
    
    // get game data
    gapi.client.hangman.get_game({
        'urlsafe_game_key': $scope.game_key
    }).execute(function (resp) {
        if (!resp.code) {
            $scope.game = resp;
            User.name = $scope.game.user_name;
            $scope.$apply();
            canvas.draw($scope.game.attempts_remaining);
            buttons($scope.game.attempted_letters);
        }
    });

    // user selected a letter
    $scope.make_move = function($event) {
        if ($scope.game.game_over) {
            return;
        }
        var el = $event.currentTarget;
        var guess = (el.innerHTML);
        el.setAttribute("class", "active");
        el.onclick = null;
        gapi.client.hangman.make_move({
            'urlsafe_game_key': $scope.game_key,
            'guess': guess
        }).execute(function (resp) {
            if (!resp.code) {
                $scope.game = resp;
                $scope.$apply();
                canvas.draw($scope.game.attempts_remaining);
            }
        });
    };
    
    // play again
    $scope.play_again = function (user_name) {
        gapi.client.hangman.new_game({
            'user_name': user_name
        }).execute(function (resp) {
            if (!resp.code) {
                $location.path("/game/" + resp.urlsafe_key);
                $scope.$apply();
            }
        });
    };

    // cancel game
    $scope.cancel_game = function () {
        gapi.client.hangman.cancel_game({
            'urlsafe_game_key': $scope.game_key
        }).execute(function (resp) {
            if (!resp.code) {
                $location.path("/");
                $scope.$apply();
            }
        });
    };

});

function buttons(attempted_letters) {
    var buttons = document.querySelectorAll("ul#alphabet li");
    for (var i = 0; i < buttons.length; i++) {
        if (attempted_letters.indexOf(buttons[i].innerHTML) >= 0) {
            buttons[i].setAttribute("class", "active");
            buttons[i].onclick = null;
        }
    }
}

// canvas drawing functions
var canvas = (function() {
    var context;
  
    var drawLine = function($pathFromx, $pathFromy, $pathTox, $pathToy) {
        context.beginPath();
        context.moveTo($pathFromx, $pathFromy);
        context.lineTo($pathTox, $pathToy);
        context.stroke();
    }
    
    var drawFloor = function() {
        drawLine(0, 150, 150, 150);
    }

    function drawSupport1() {
        drawLine(10, 0, 10, 600);
    }
    function drawSupport2() {
        drawLine(0, 5, 70, 5);
    }
    function drawRope() {
        drawLine(60, 5, 60, 15);
    }
    function drawHead() {
        context.beginPath();
        context.arc(60, 25, 10, 0, Math.PI * 2, true);
        context.stroke();
    }
    function drawTorso() {
        drawLine(60, 36, 60, 70);
    }
    function drawRightArm() {
        drawLine(60, 46, 100, 50);
    }
    function drawLeftArm() {
        drawLine(60, 46, 20, 50);
    }
    function drawRightLeg() {
        drawLine(60, 70, 100, 100);
    }
    function drawLeftLeg() {
        drawLine(60, 70, 20, 100);
    }

    var drawArray = [drawRightLeg, drawLeftLeg, drawRightArm, drawLeftArm, drawTorso,  drawHead, drawRope, drawSupport2, drawSupport1, drawFloor]; 

    return {
        init: function() {
            var canvasElement = document.getElementById("canvas");
            context = canvasElement.getContext('2d');
            context.clearRect(0, 0, 400, 400);
            context.strokeStyle = "#fff";
            context.lineWidth = 2;
        },
        draw: function(attempts_remaining) {
            for (var i = 9; i >= attempts_remaining; i--) {
                drawArray[i]();
            }
        }
    }
 
})();