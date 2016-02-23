"use strict" 
// TODO:
//   o If num_attempts missing, assume 1.

/**
 * Workhorse that animates busstream.html. Creates a 
 * SchoolBus interaction instance that communicates to
 * and from the JavaScript-SchoolBus bridge.
 * 
 *  Subscribes to data streams from a data pump service
 *  on the SchoolBus.
 * 
 * Creates a grade visualization instance. Finally, communicates
 * all incoming grades tuples to that visualization instance.
 */


var PAUSE_BUTTON_PULSE_PERIOD = 1000;

// Make in instance of the grade visualiztion class:
var vizzer = gradeCharter.getInstance();

var gradeReceiver = function(gradeDataBusObj) {
	/**
	 * Called whenever a new grade tuple arrives from
	 * the SchoolBus. Checks the msg's syntax and semantics.
	 * Finally, calls on the grade visualization instance
	 * to update the chart(s).
	 */

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

// Get a SchoolBus interactor instance.
// Because instance creation takes a while
// due to connection setup with the JS bus
// bridge, a promise is used to wait for
// completion of the setup. Then the 
// kickoff() function is called to set up
// the interactor instance:
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
	/**
	 * Set the SchoolBus in-message handler
	 * to gradeReceiver, which will update
	 * the chart when grades arrive.
	 */
	bus.setMsgCallback(gradeReceiver);
	//bus.subscribeToTopic('gradesCompilers'); //******
	//*****
	//bus.subscribedTo(function(subscriptions) { console.log (subscriptions)});
	//*****
	
}

var getAvailableSources = function() {
	/**
	 * Requests a list of data source IDs and 
	 * data source descriptions from the data pump
	 * service. Return is an object of the form:
	 *    [{"sourceId" : "compilers", "info" : "Compiler course of Spring 2014/5"},
	 *     {"sourceId" : "databases", "info" : "Data base course pre-minis"}
	 *     ]
	 */
	bus.publish({"cmd" : "listSources",
			     "topic" : "datapumpControl",
			     "synchronous" : function(returnVal) {
			     	                buildSubscribeButtons(returnVal);
                      			    }
			    })
}

var buildSubscribeButtons = function(sourceIdsAndInfoArr) {
	
	subscribeBtnDiv  = document.getElementById("subscribeGrp");
	subscribeButtons = document.getElementsByClassName("subscriptionBtn");
	subscribeButtons.remove();
	
	for (var i=0; i<sourceIdsAndInfoArr.length; i++) {
		// Get obj of form: {"sourceId" : "myId", "info" : "My description."}:
		var srcIdAndInfo = sourceIdsAndInfoArr[i];
		
		// Ensure that this source info object has a sourceId
		// field:
		var sourceId = srcIdAndInfo.sourceId;
		if (typeof sourceId === 'undefined') {
			continue;
		}
		
		// New subscribe button:
		var subscribeButton =  document.createElement("BUTTON"); // Create a <button> element
		var btnLabel = document.createTextNode(sourceId);
		subscribeButton.appendChild(btnLabel);
		subscribeBtnDiv.append(subscribeButton);
		subscribeButton.addEventListener("click", function() {
			subscribe(sourceId);
		})
	}
}

var subscribe = function(button) {
	bus.subscribeToTopic(button.id);
}

var listSources = function(button) {
	bus.publish({"cmd" : "listSources"},
				"datapumpControl",
				function(returnVal) {
				   var returnObj = JSON.parse(returnVal)
				   console.log(returnObj);
				});
}	

// --------------------------------- Adding Event Listeners --------------------------

// Event listener for the Play button; ensures
// that pause button does not blink (any more), and
// sends a 'play' request to the data pump:

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
	/**
	 * Manages the pause button. If it is clicked
	 * while the grade visualization is paused, tells
	 * the data pump to continue the grade stream, and
	 * stops the pause button from blinking. 
	 * 
	 * Else starts the pause button blinking, and tells
	 * the data pump to pause.
	 */
	
	if (newState === 'playing') {
		bus.publish('{"cmd" : "play"}', "datapumpControl");
		button.status = 'playing';
		try {
			clearInterval(pauseButtonDimTimer);
			document.getElementById("pauseButton").style.opacity = 1.0;
		} catch (err) {
			return;
		}
	} else {
		// New state is to be paused:
		bus.publish('{"cmd" : "pause"}', "datapumpControl");
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

document.getElementById("fbackButton").addEventListener("click", function() {
	bus.publish('{"cmd" : "restart"}', "datapumpControl");
	});

// Stop button handler:
document.getElementById("stopButton").addEventListener("click", function() {
	if (confirm("This action will stop the stream. Do it?")) {
		bus.publish('{"cmd" : "stop"}', "datapumpControl");
	}
	});

// List-Sources button:
document.getElementById("listSources").addEventListener(buildSubscribeButtons);

// --------------------------- Utility Functions -----------------------

Element.prototype.remove = function() {
	/**
	 * Remove a given element from the DOM by calling
	 * removeChild() on the parent. Use like:
	 *     myElement.remove()
	 */
    this.parentElement.removeChild(this);
}

NodeList.prototype.remove = HTMLCollection.prototype.remove = function() {
	/**
	 * Given a NodeList or an HTMLCollection, remove all its members.
	 * Use like: myList.remove()
	 */

    for(var i = this.length - 1; i >= 0; i--) {
        if(this[i] && this[i].parentElement) {
            this[i].parentElement.removeChild(this[i]);
        }
    }
}

	
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


