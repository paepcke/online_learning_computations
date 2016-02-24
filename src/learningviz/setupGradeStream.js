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

function GradeVizUiController() {

	/* ------------------------------------ Constants ------------------*/

	/**
	 * Enforce singleton: official way to get the
	 * singleton instance of this class is to call
  	 * 
	 *   GradeVizUiController.getInstance();
	*/
	
	if (typeof my !== 'undefined') {
		throw "Please obtain the GradeVizUiController instance via GradeVizUiController.getInstance()";
	}
	
	// Make a private object in which we'll 
	// stick instance vars and private methods:
	var my = {};

	my.instance = null;
	
	
	my.PAUSE_BUTTON_PULSE_PERIOD = 1000;

	my.currStreamId;

	// Make in instance of the grade visualiztion class:
	my.vizzer = gradeCharter.getInstance();

	my.getInstance = function() {
		if (my.instance !== null) {
			return my.instance;
		} else {
			my.instance = GradeVizUiController();
			my.instance.initialize();
			return my.instance;
		}
	}
	
	my.initialize = function() {
		
	}
	
	my.gradeReceiver = function(gradeDataBusObj) {
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

		my.vizzer.updateViz(jsGradeData);
	}

	/*
	 * Get a SchoolBus interactor instance.
	 * Because instance creation takes a while
	 * due to connection setup with the JS bus
	 * bridge, a promise is used to wait for
	 * completion of the setup. Then the 
	 * kickoff() function is called to set up
	 * the interactor instance:
	 */
	my.bus = null;
	var promise = busInteractor.getInstance();
	promise.then(function(instance) {
		my.bus = instance;
		my.kickoff();
	},
	function(err_msg) {
		alert(err_msg);
	}
	);

	my.kickoff = function() {
		/**
		 * Set the SchoolBus in-message handler
		 * to gradeReceiver, which will update
		 * the chart when grades arrive.
		 */
		my.bus.setMsgCallback(my.gradeReceiver);
		//bus.subscribeToTopic('gradesCompilers'); //******
		//*****
		//bus.subscribedTo(function(subscriptions) { console.log (subscriptions)});
		//*****

	}

	my.getAvailableSources = function() {
		/**
		 * Requests a list of data source IDs and 
		 * data source descriptions from the data pump
		 * service. Return is an object of the form:
		 *    [{"sourceId" : "compilers", "info" : "Compiler course of Spring 2014/5"},
		 *     {"sourceId" : "databases", "info" : "Data base course pre-minis"}
		 *     ]
		 */
		my.bus.publish({"cmd" : "listSources"},
				       "datapumpControl",
				       {"syncCallback" : function(returnVal) {
				    	   					my.buildSubscribeButtons(returnVal);
				       					 }
				       }
		);
	}

	my.buildSubscribeButtons = function(sourceIdsAndInfoArr) {

		var subscribeBtnDiv  = document.getElementById("subscribeGrp");
		var subscribeButtons = document.getElementsByClassName("subscriptionBtn");
		my.subscribeButtons.remove();

		// Does data pump have nothing to offer?
		if (sourceIdsAndInfoArr.length === 0) {
			alert("Data pump has no data to offer.");
			return;
		}

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
			subscribeButton.id = sourceId;
			subscribeButton.setAttribute("class", "subscriptionBtn");
			subscribeBtnDiv.appendChild(subscribeButton);
			subscribeBtnDiv.appendChild(document.createElement('br'))
			subscribeButton.addEventListener("click", function(event) {
				var sourceId = this.id;
				var dataPumpCmd = {"cmd" : "initStream", "sourceId" : sourceId}
				bus.publish(dataPumpCmd, 
						"datapumpControl", 
						{"syncCallback" : function(streamId) {
							my.currStreamId = streamId;
						}})
			})
		}
	}

	my.subscribe = function(sourceId) {
		my.bus.subscribeToTopic(sourceId);
	}

//	--------------------------------- Adding Event Listeners --------------------------

	my.setPauseState = function(newState, button) {
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
			my.bus.publish('{"cmd" : "play"}', "datapumpControl");
			button.status = 'playing';
			try {
				clearInterval(my.pauseButtonDimTimer);
				document.getElementById("pauseButton").style.opacity = 1.0;
			} catch (err) {
				return;
			}
		} else {
			// New state is to be paused:
			my.bus.publish('{"cmd" : "pause"}', "datapumpControl");
			button.status = 'paused';
			// Every PAUSE_BUTTON_PULSE_PERIOD milliseconds: Dim or undim
			// the pause button:
			var pause_button_dimmed = false;
			my.pauseButtonDimTimer = setInterval(function() {
				if (pause_button_dimmed) {
					document.getElementById("pauseButton").style.opacity = 1.0;
					pause_button_dimmed = false;
				} else {
					document.getElementById("pauseButton").style.opacity = 0.5;
					pause_button_dimmed = true;
				}

			}, my.PAUSE_BUTTON_PULSE_PERIOD)
		}
	}


	my.attachAllEventListeners = function() {
		/**
		 * Event listener for the Play button; ensures
		 * that pause button does not blink (any more), and
		 * sends a 'play' request to the data pump:
		 */

		document.getElementById("playButton").addEventListener("click", function() {
			var pauseButton = document.getElementById('pauseButton');
			my.setPauseState('playing', pauseButton);
			my.bus.publish({"cmd" : "play", "streamId" : currStreamId},
						   "datapumpControl");
		});

		/**
		 * Initialize the Pause button to indicated that we are 
		 * currently playing:
		 */
		document.getElementById("pauseButton").status = 'playing';
		document.getElementById("pauseButton").addEventListener("click", function() {
			var button = this;

			if (button.status === 'paused') {
				setPauseState('playing', button);
			} else {
				setPauseState('paused', button);
			}
		});

		my.pauseButtonDimTimer = null;


		document.getElementById("fbackButton").addEventListener("click", function() {
			my.bus.publish('{"cmd" : "restart"}', "datapumpControl");
		});

		// Stop button handler:
		document.getElementById("stopButton").addEventListener("click", function() {
			if (confirm("This action will stop the stream. Do it?")) {
				my.bus.publish('{"cmd" : "stop"}', "datapumpControl");
			}
		});

		// List-Sources button:
		document.getElementById("listSources").addEventListener("click", getAvailableSources);
	} // end addEventListeners

//	--------------------------- Utility Functions -----------------------

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
	
//  -------------------------- Class-Level Initialization ----------------------------------
	
	// Make the object we would actually return
	// if this wasn't a singleton:
	that = {}
	// Add a reference to the public ones of the above methods:
	that.getInstance = my.getInstance;
	
	my.instance = that;
	return null;

} // end GradeVizUiController

GradeVizUiController().getInstance();

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


