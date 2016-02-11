"use strict" 
// TODO:
//   o If num_attempts missing, assume 1.


var PAUSE_BUTTON_PULSE_PERIOD = 1000;

var vizzer = gradeCharter.getInstance();

var gradeReceiver = function(gradeDataBusObj) {

	// gradeDataBusObj's 'content' field must be 
	// legal JSON, either a JSON array of JSON objs, 
	// or a single JSON obj:
	var gradeDataJSONStr = gradeDataBusObj.content;
	// Bus message really had a 'content' field?
	if (typeof gradeDataJSONStr === 'undefined') {
		console.log(`Error: received bus message without content field: '${gradeDataBusObj}'.`);
		return;
	}
	// Is content legal JSON?
	try {
		var jsGradeData = JSON.parse(gradeDataJSONStr);
	} catch(err) {
		console.log(`Error: bad JSON received (${err.message}): '${gradeDataJSONStr}'.`);
		return;
	}
	// Ensure we have an array of objs:
	if (Object.prototype.toString.call( jsGradeData ) !== '[object Array]') {
		jsGradeData = [jsGradeData];
	}
	
	// Sanity check: does the array contain either 
	// legal JSON strings, or JS objects? Turn all
	// JSON strings into objects.

	for (var i=0; i<jsGradeData.length; i++) {
		var gradeInfoObj = jsGradeData[i];
		if (typeof gradeInfoObj !== "object") {
			console.log(`Error: viz data must be an array of grade objects, not: ${gradeInfoObj}.`);
			return;
		}
		// Got a proper object, get its 'attempts' field:
		try {
			parseInt(gradeInfoObj['attempts']);
		} catch(err) {
			console.log(`Error: viz grade objects have an integer 'attempts' field: ${gradeInfoObj}.`);
			return;
		}

		if (typeof gradeInfoObj['probId'] !== "string") {
			console.log(`Error: viz data 'probId' field must a string not: ${gradeInfoObj['probId']}.`);
			return;
		}
	} // end for
	
	vizzer.updateViz(jsGradeData);
}

var bus;
var promise = busInteractor.getInstance();
promise.then(function(instance) {
	bus = instance;
	kickoff();
    },
	function(err_msg) {
		alert(err_msg);
	}
);

var kickoff = function() {
	bus.setMsgCallback(gradeReceiver);
	bus.subscribeToTopic('gradesCompilers');
	//*****
	//bus.subscribedTo(function(subscriptions) { console.log (subscriptions)});
	//*****
	
}

document.getElementById("playButton").addEventListener("click", function() {
	var pauseButton = document.getElementById('pauseButton');
	setPauseState('playing', pauseButton);
});

// Initialize the Pause button to indicated that we are 
// currently playing:
document.getElementById("pauseButton").status = 'playing';
document.getElementById("pauseButton").addEventListener("click", function() {
	var button = this;
	
	if (button.status === 'paused') {
		setPauseState('playing', button);
	} else {
		setPauseState('paused', button);
	}
});

var pauseButtonDimTimer = null;

var setPauseState = function(newState, button) {
	if (newState === 'playing') {
		bus.publish('{"cmd" : "resume"}', "dataserverControl");
		button.status = 'playing';
		try {
			clearInterval(pauseButtonDimTimer);
			document.getElementById("pauseButton").style.opacity = 1.0;
		} catch (err) {
			return;
		}
	} else {
		// New state is to be paused:
		bus.publish('{"cmd" : "pause"}', "dataserverControl");
		button.status = 'paused';
		// Every PAUSE_BUTTON_PULSE_PERIOD milliseconds: Dim or undim
		// the pause button:
		var pause_button_dimmed = false;
		pauseButtonDimTimer = setInterval(function() {
			if (pause_button_dimmed) {
				document.getElementById("pauseButton").style.opacity = 1.0;
				pause_button_dimmed = false;
			} else {
				document.getElementById("pauseButton").style.opacity = 0.5;
				pause_button_dimmed = true;
			}
			
		}, PAUSE_BUTTON_PULSE_PERIOD)
	}
}

document.getElementById("stopButton").addEventListener("click", function() {
	if (confirm("This action will stop the stream. Do it?")) {
		bus.publish('{"cmd" : "stop"}', "dataserverControl");
	}
});

/*var resumeData = function() {
	bus.publish('{"cmd" : "changeSpeed"}', "dataserverControl");
}
*/
//**********
var subscribe = function() {
	
	var promise = busInteractor.getInstance();
	promise.then(function(instance) {
		bus = instance;
		bus.subscribeToTopic('gradesCompilers');
	    },
		function(err_msg) {
			alert(err_msg);
		}
	)};

	
//**********
									  


var testData = [ 
				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "6a6c70f0f9672ca4a3e16bdb5407af51cd18e4e5",
				    "grade" : 10,
				    "attempts" : 3,
				    "firstSubmit" : "2013-06-11 15:12:13",
				    "lastSubmit" : "2013-07-07 00:10:51",
				    "probId" : "i4x://Medicine/HRP258/problem/5542da143b054d0ba3efdb243b5eb343"
				   },
				   {"course" : "Medicine/HRP258/Statistics_in_Medicine",
				    "learner" : "cb2bb63c14e6f5fc8d21b5f43c8fe412c7c64c39",
				    "grade" : 7,
				    "attempts" : 1,
				    "firstSubmit" : "2013-06-11 15:21:11",
				    "lastSubmit" : "2013-07-1506:13:51",
				    "probId" : "i4x://Medicine/HRP258/problem/8c13502687f642e1b514d4b522fc96d3",
				   }
	            ];


