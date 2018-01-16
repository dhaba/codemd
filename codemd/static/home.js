var players = [];

function callbackClosure(i, callback) {
  return function() {
    return callback(i);
  }
}

function playNextVideo(currentPlayer) {
  var currentIndex = 0;
  for (i = 0; i < players.length; i++) {
    if (players[i] == currentPlayer) {
      currentIndex = i;
      break;
    }
  }
  var nextIndex = currentIndex == players.length - 1 ? 0 : currentIndex + 1;

  $("#videoCarousel").carousel(nextIndex);
  players[nextIndex].playVideo();
}

function onPlayerReady(data) {
  console.log("player ready, playing video");
  data.target.playVideo();
}

function onPlayerStateChange(data) {
  console.log("my state changed to: " + data.data);
  if (data.data == 0) {
    playNextVideo(data.target);
  }
}

function config_slideshow() {
  // Create YT Object for each iFrame
  var vids = $(".demo-vid");
  for (i = 0; i < vids.length; i++) {
    var eventsObj = {
      events: { 'onStateChange': onPlayerStateChange }
    }
    if (i == 0) { // Play first vid as soon as it loads
      eventsObj.events.onReady = onPlayerReady;
    }
    players.push(new YT.Player(vids[i].id, eventsObj));
  }

  // for (i = 0; i < players.length; i++) {
  //   players[i].on('ended', callbackClosure(i, function(i){
  //     console.log("player index " + i + " has ended.");
  //     var nextIndex = i + 1;
  //     if (nextIndex >= players.length) {
  //       nextIndex = 0;
  //     }
  //     console.log('next video index: ' + nextIndex);
  //     $("#videoCarousel").carousel(nextIndex);
  //     players[nextIndex].play();
  //   }));
  // }
}
