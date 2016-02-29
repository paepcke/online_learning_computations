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


	/* ------------------------------------ Helper Classes ------------------*/

/*
 * Two-way mapping.
 */

function TwoWayMap(map) {

	var my = {};
	my.map = null;
	my.reverseMap = null;
	
	my.init = function(map) {
		my.map = map;
		my.reverseMap = {};
		for(var key in my.map){
			var value = my.map[key];
			my.reverseMap[value] = key;   
		}
	}

	my.get = function(key) { 
		return my.map[key]; 
	};

	
	my.revGet = function(key){ 
		return my.reverseMap[key]; 
	};
	
	
	my.put = function(key,val){
		my.map[key] = val;
		my.reverseMap[val] = key;
	};
	
	my.delete = function(key){
		var val = my.map[val];
		delete my.map[key];
		delete my.reverseMap[val];
	}
	
	my.revDelete = function(val){
		var key = my.reverseMap[val];
		delete my.reverseMap[val];
		delete my.map[key];
	}
	
	var that = {}
	that.init = my.init;
	that.get  = my.get;
	that.revGet = my.revGet;
	that.put = my.put;
	that.delete = my.delete;
	that.revDelete = my.revDelete;
	
	my.init(map);
	
	return that;
}
     
	/* ------------------------------------ Main Class ------------------*/

function GradeVizUiController() {

	/* ------------------------------------ Constants and Class Variables ------------------*/

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

	my.currStreamId = null;
	my.currSourceId = null;

	/* Getting from an opaque streamID to the 
	   corresponding human-readable topic.
	   Maintained in subscriptionReceipt()
	   and stop button event handler:
	 */ 
	my.streamId2SourceId = TwoWayMap({});
	
	my.datapumpControlTopic = "datapumpControl";
	my.datapumpCmds = ['initStream',
	                   'play',
	                   'pause',
	                   'resume',
	                   'stop',
	                   'restart',
	                   'changeSpeed',
	                   'listSources'
	                   ]

	/* ------------------------------------ Methods ------------------*/
	
	/*---------------------------------
	 * getInstance
	 *---------------*/
	
	my.getInstance = function() {
		if (my.instance !== null) {
			return my.instance;
		} else {
			GradeVizUiController();
			return my.instance;
		}
	}
	
	/*---------------------------------
	 * gradeReceiver
	 *---------------*/
	
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

	/*---------------------------------
	 * makeDatapumpRequest 
	 *---------------*/
	
	/*
	 * Given a datapump command, and possibly additional
	 * command-specific options, return a properly formatted
	 * object that, once turned into JSON by the publish()
	 * method, will satisfy the datapump when it finds it
	 * in the content field of the bus message.
	 * 
	 * 
	 * :param cmd: the datapump command for which to construct a request.
	 * 		See my.datapumpCmds for legal values.
	 * :type cmd: string
	 * :param cmdArgs: an object containing additional arguments.
	 * :type cmdArgs: object
	 * :return command message for datapump or null if an error occurred.
	 * 	   an error occurs only if an unsupported cmd is provided, or the
	 *     cmdArgs argument is not present, or does not contain a required
	 *     argument. No uncertain network activity is involved.
	 * :rtype {object | null}
	 */
	
	my.makeDatapumpRequest = function(cmd, cmdArgs) {
		
		if (my.datapumpCmds.indexOf(cmd) === -1) {
			throw `Bad command for data pump: ${cmd}.`;
		}
		
		var retObj = {'cmd' : cmd};
		if (cmd === 'listSources') {
			// No arg required:
			return retObj;
		}
		
		// Any additional required options?
		if (cmd === 'initStream') {
			try {
				// Caller must specify the source ID:
				var sourceId = cmdArgs.sourceId;
			} catch(err) {
				my.errMsg('Datapump command initStream requires a sourceId in the cmdArgs of the makeDatapumpRequest() call.');
				return null;
			}
			retObj.sourceId = cmdArgs.sourceId;
			return retObj;
		}
		
		// All other commands take a stream id, which the caller
		// doesn't need to include:
		retObj.streamId = my.currStreamId;
		
		// changeSpeed needs the new speed:
		if (cmd == 'changeSpeed') {
			try {
				retObj.arg = cmdArgs.newSpeed;
			} catch(err) {
				my.errMsg("Datapump command changeSpeed needs a newSpeed field in the cmdArgs of the makeDatapumpRequest() call.");
				return null;
			}
		}
		
		return retObj;
	}
	
	/*---------------------------------
	 * kickoff 
	 *---------------*/
	
	
	my.kickoff = function() {
		// Make in instance of the grade visualiztion class:
		my.vizzer = gradeCharter.getInstance();

		/**
		 * Set the SchoolBus in-message handler
		 * to gradeReceiver, which will update
		 * the chart when grades arrive.
		 */
		my.bus.setMsgCallback(my.gradeReceiver);
		my.attachAllEventListeners();
		
		// Tooltip that appears when brushing over a
		// subscription buttons:
		my.subscribeBtnTooltip = d3.select("body").append("div")
			.attr("class", "brushTooltip")
			.attr("id", "subscribeButtonBrushTooltip")
			.attr("display", "inline")
			.style("visibility", "hidden");
		
		
		my.getAvailableSources();
		// Check whether a prior reload() left post-mortem
		// instructions for a stream to apply to. Happens
		// when user hits a new subscribe button while another
		// susbcribe is going on:
		
		if(typeof(Storage) !== "undefined") {
			// Browser has support for local and session storage:
			var initialSourceId = sessionStorage.initialSourceId;
			if (typeof initialSourceId !== 'undefined') {
				// Ensure that we don't init stream each time
				// user reloads before killing the browser tab:
				sessionStorage.removeItem('initialSourceId');
				// Subscribe to the stream:
				my.bus.publish(my.makeDatapumpRequest("initStream", {"sourceId" : initialSourceId}),
							   my.datapumpControlTopic,
							   {"syncCallback" : my.subscriptionReceipt}
				);
			}
		}
	}

	/*---------------------------------
	 * getAvailableSources 
	 *---------------*/
		
	my.getAvailableSources = function() {
		/**
		 * Requests a list of data source IDs and 
		 * data source descriptions from the data pump
		 * service. Return is an object of the form:
		 *    [{"sourceId" : "compilers", "info" : "Compiler course of Spring 2014/5"},
		 *     {"sourceId" : "databases", "info" : "Data base course pre-minis"}
		 *     ]
		 * The 'listSources' request to the data pump is 
		 * a synchronous publish. The result will be delivered
		 * to buildSubscribeButtons().
		 */
		var currSavedFunc = my.getErrCallback();
		my.setErrCallback(function(errMsg) {
			alert('Could not reach data pump; is it running?');
		})
		my.bus.publish(my.makeDatapumpRequest("listSources"),
				       my.datapumpControlTopic,
				       {"syncCallback" : function(returnVal) {
				    	   					// Reset original err callback func:
				    	   					my.setErrCallback(currSavedFunc);
				    	   					my.buildSubscribeButtons(returnVal);
				       					 }
				       }
		);
	}
	
	/*---------------------------------
	 *  buildSubscribeButtons
	 *---------------*/


	my.buildSubscribeButtons = function(sourceIdsAndInfoArr) {

		var subscribeBtnDiv  = document.getElementById("subscribeGrp");
		var subscribeButtons = document.getElementsByClassName("subscriptionBtn");
		if (typeof subscribeButtons !== 'undefined') {
			subscribeButtons.remove();
		}

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
			// Grab the source information text if available:
			var sourceInfo = srcIdAndInfo.info;
			if (typeof sourceInfo === 'undefined') {
				sourceInfo = "";
			}

			// New subscribe button:
			var subscribeButton =  document.createElement("BUTTON"); // Create a <button> element
			var btnLabel = document.createTextNode(sourceId);
			subscribeButton.appendChild(btnLabel);
			subscribeButton.id = sourceId;
			subscribeButton.description = sourceInfo;
			subscribeButton.setAttribute("class", "subscriptionBtn");
						
			subscribeBtnDiv.appendChild(subscribeButton);
			subscribeBtnDiv.appendChild(document.createElement('br'))

			// Add a brush-tooltip that appears while brushing
	        // over the button:
	        subscribeButton.addEventListener("mouseenter", function(event) {
	        							  my.brushIntoSubscribeBtn(event);
	                                     });
	        subscribeButton.addEventListener("mouseout", function(event) {
	        				              my.brushOutSubscriptionBtn(event);
	                                   });
			
			subscribeButton.addEventListener("click", function(event) {
				var sourceId = this.id;
				if (sourceId === my.currSourceId) {
					// nothing to do:
					return;
				}
				// Turn all subscribe buttons into their inactive state:
				my.deactivateSubscribeButtons();

				// Are we currently streaming another topic?
				if (my.currStreamId !== null && typeof my.currStreamId !== 'undefined') {
				   var abort = window.confirm(`Currently subscribed to '${my.currSourceId}'; abort that chart and underlying subscription?`)
				   if (abort) {
					   // Currently subscribed to a stream:
					   my.unsubscribe(my.currSourceId);
					   // We'll reload the page to enusure that all
					   // data structures are set up correctly. But
					   // before reloading the page, remember that 
					   // after reload the new stream should be subscribed
					   // to:
					   if (typeof Storage !== 'undefined') {
						   sessionStorage.initialSourceId = sourceId;
					   }
					   // Wipe out all state and start over. The kickoff()
					   // method will immediately subscribe to the new source:
					   location.reload();
				   } else {
					   return;
				   }
				} else {
					// No stream currently subscribed to, subscribe now:
					my.bus.publish(my.makeDatapumpRequest("initStream", {"sourceId" : sourceId}),
							my.datapumpControlTopic,
							{"syncCallback" : my.subscriptionReceipt}
					);
				}
			})
		}
	}
	
	/*---------------------------------
	 * brushIntoSubscribeBtn
	 *---------------*/
	
	/**
	 * Event handler when mouse brushes over a subscribe button.
	 * If the event button has a non-empty 'description' property,
	 * its value is assumed to be text. That text will be shown
	 * in a popup.
	 */

	my.brushIntoSubscribeBtn = function(event) {
		var subscribeButton = event.target;
		var sourceInfo = subscribeButton.description;
		if (sourceInfo.length === 0) {
			// No info to show.
			return;
		}
		
		var mouseX = event.pageX;
		var mouseY = event.pageY;
		var tooltipHeight = my.subscribeBtnTooltip.style.minHeight;
		my.subscribeBtnTooltip.text(sourceInfo);
		my.subscribeBtnTooltip
			.style("left", (mouseX - 34) + "px")
			//.style("top", (mouseY - 12) + "px")
			.style("top", (mouseY - 60) + "px")
			.style('visibility', 'visible');
		
		my.subscribeBtnTooltip.style('visibility', 'visible');
		
	}
	
	
	/*---------------------------------
	 * brushOutSubscriptionBtn
	 *---------------*/
	
	/**
	 * Event handler when mouse leaves a subscription button.
	 * the subscription tooltip will be made to disappear...poof!
	 */
	
	my.brushOutSubscriptionBtn = function(event) {
		my.subscribeBtnTooltip.style('visibility', 'hidden');
	}	
	
	/*---------------------------------
	 * deactivateSubscribeButtons 
	 *---------------*/

	/**
	 * If topic is provided, find the corresponding
	 * subscribe button and deactivate it. If sourceId
	 * is omitted, deactivate all subscribe buttons.
	 * 
	 * :param sourceId: if provided, the topic whose button is to be deactivated.
	 * :type sourceId: string
	 */
	
	my.deactivateSubscribeButtons = function(sourceId) {
		
		if (typeof sourceId === 'undefined') {
			var btns = document.getElementsByClassName('active');
			if (btns === null) {
				return;
			}
			for (var i=0; i<btns.length; i++) {
				btns[i].removeClass('active');
			}
		} else {
			// Only deactivate one button:
			// Get the stream's corresponding subscribe
			// button, and ensure it's turned inactive:
			var subscribeBtn = document.getElementById(sourceId);
			if (subscribeBtn !== null) {
				subscribeBtn.removeClass('active');   
		   }
		}
	}
	
	/*---------------------------------
	 * activateSubscribeButton
	 *---------------*/
	
	/**
	 * Given a sourceId, find the subscribe button for
	 * that sourceId and turn it into its 'active' state
	 * 
	 * :param sourceId: the ID of the source for which the button
	 *       subscribes.
	 * :type sourceId: string
	 */
	
	my.activateSubscribeButton = function(sourceId) {
		var btn = document.getElementById(sourceId);
		if (btn !== null) {
			btn.addClass('active');
		} 
	}
	
	/*---------------------------------
	 * subscriptionReceipt 
	 *---------------*/
	
	/**
	 * Called when datapump responds to an initStream command.
	 * The content of the response is a streamId, which is the
	 * topic to which the datapump will publish data once it
	 * has received a 'play' command from us. Until then, the
	 * stream is paused. We subscribe here to the streamId
	 * as the topic. For convenience, the server also echoes
	 * the name of the source stream. We use the streamId2SourceId
	 * to retain a map from the opaque streamId to the more readable
	 * corresponding source id.
	 * 
	 * :param streamIdSpec: response of the form 
	 *      {"streamId" : <someId>,
	 *       "sourceId  : <name of the stream>}
	 * :type streamIdSpec: object 
	 */
	
	my.subscriptionReceipt = function(streamIdSpec){
		
		// Data pump returns: {"streamId" : <someId>,
    	//                    "sourceId" : <sourceId>};
		// that is the topic we need to subscribe to:
		   try {
			   my.currStreamId = streamIdSpec.streamId;
			   my.currSourceId = streamIdSpec.sourceId;
		   } catch (err) {
			   my.bus.getErrCallback(`Datapump did not return a proper stream ID specification: ${streamIdSpec}`);
			   return;
		   }
		   my.bus.subscribeToTopic(my.currStreamId);
		   my.setPauseState('paused');
		   my.streamId2SourceId.put(my.currStreamId, my.currSourceId); 
		   my.activateSubscribeButton(my.currSourceId);
	}
	
	/*---------------------------------
	 * unsubscribe
	 *---------------*/
	
	/**
	 * Given a topic name, unsubscribes from it.
	 * If topic is omitted, unsubscribes from my.currStreamId.
	 * The stream from which we unsubscribe is also 
	 * stopped, i.e. the data pump will be allowd to 
	 * close the stream out.
	 * 
	 * :param topic: name of topic from which to unsubscribe. If
	 * 				omitted, will unsubscribe from my.currStreamId.
	 * :type topic { undefined | string }
	 */
	
	my.unsubscribe = function(topic) {
		if (typeof topic === 'undefined') {
			topic = my.currStreamId;
		}
		// Tell the data pump that we are done
		// with this stream:
		
		my.bus.publish(my.makeDatapumpRequest("stop", {"streamId" : my.currStreamId}),
					   my.datapumpControlTopic);
		my.bus.unsubscribeFromTopic(topic);
		my.deactivateSubscribeButtons(topic);
		my.currStreamId = null;
		my.currSourceId = null;
	}
	
	/*---------------------------------
	 * setErrCallback  
	 *---------------*/
	
	my.setErrCallback = function(errCallback) {
		/**
		 * Allows caller to control where messages error
		 * messages are delivered. Default is to show
		 * an alert.
		 * 
		 * :param errCallback: function that takes a string and 
		 *         signals an error to the end user.
		 * :type errCallback: function(str_
		 */
		
		my.bus.setErrCallback(errCallback);
	}
	
	/*---------------------------------
	 * getErrCallback
	 *---------------*/

	my.getErrCallback = function() {
		/**
		 * Returns the function that currently serves to
		 * report errors to the end user.
		 * 
		 * :return function that currently signals errors to end user.
		 * :rtype function(str)
		 */
		
		return my.bus.getErrCallback();
	}


//	--------------------------------- Adding Event Listeners --------------------------

	/*---------------------------------
	 * setPauseState
	 *---------------*/

	my.setPauseState = function(newState, button) {
		/**
		 * Manages the pause button. If it is clicked
		 * while the grade visualization is paused, 
		 * stops the pause button from blinking. 
		 * 
		 * Else starts the pause button blinking.
		 */

		var button = document.getElementById('pauseButton');
		if (newState === 'playing') {
			button.status = 'playing';
			try {
				clearInterval(my.pauseButtonDimTimer);
				document.getElementById("pauseButton").style.opacity = 1.0;
			} catch (err) {
				return;
			}
		} else {
			// New state is to be paused:
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


	/*---------------------------------
	 * attachAllEventListeners
	 *---------------*/
	
	my.attachAllEventListeners = function() {
		/**
		 * Event listener for the Play button; ensures
		 * that pause button does not blink (any more), and
		 * sends a 'play' request to the data pump:
		 */

		document.getElementById("playButton").addEventListener("click", function() {
			if (my.currStreamId === null) {
				my.errMsg('Not currently subscribed to any data stream.');
				return;
			}
			var pauseButton = document.getElementById('pauseButton');
			if (pauseButton.status === 'paused') {
				my.setPauseState('playing');
			}
			my.bus.publish(my.makeDatapumpRequest("play"), my.datapumpControlTopic);
		});

		/**
		 * Initialize the Pause button to indicated that we are 
		 * currently playing:
		 */
		my.pauseButtonDimTimer = null;
		document.getElementById("pauseButton").status = 'playing';
		document.getElementById("pauseButton").addEventListener("click", function() {
			var button = this;

			if (button.status === 'paused') {
				my.setPauseState('playing');
				my.bus.publish(my.makeDatapumpRequest('play'), my.datapumpControlTopic);
			} else {
				my.setPauseState('paused');
				my.bus.publish(my.makeDatapumpRequest("pause"), my.datapumpControlTopic);
			}
		});

		document.getElementById("fbackButton").addEventListener("click", function() {
			//*********
			alert("Rewind not implemented.");
			//*********
			if (my.currStreamId === null) {
				my.errMsg('Not currently subscribed to any data stream.');
				return;
			}
			my.bus.publish(my.makeDatapumpRequest("restart"), my.datapumpControlTopic);
		});

		// Stop button handler:
		document.getElementById("stopButton").addEventListener("click", function() {
			if (my.currStreamId === null) {
				my.errMsg('Not currently subscribed to any data stream.');
				return;
			}
			if (confirm("This action will stop the stream. Do it?")) {
				my.bus.publish(my.makeDatapumpRequest('stop'), my.datapumpControlTopic);
				my.deactivateSubscribeButtons(my.currSourceId);
				my.unsubscribe();
				// Remove the streamId-->sourceId from the map relating the two:
				my.streamId2SourceId.delete(my.currStreamId);
				
				// Totally brutal: Just reload the page to start fresh:
				location.reload();
			}
		});

		// List-Sources button:
		document.getElementById("listSources").addEventListener("click", my.getAvailableSources);
	} // end addEventListeners

//	--------------------------- Utility Functions -----------------------

	/*---------------------------------
	 * addClass 
	 *---------------*/

	/**
	 * Provide dynamic addition of a class to 
	 * a DOM element.
	 * 
	 * :param newClass: name of new class to add
	 * :type newClass: string
	 */
	
	Element.prototype.addClass = function(newClass) {
		// In case newClass is already one of the element's
		// classes, remove that class first:
		var classNameWithoutNewClass = this.className.replace(newClass, "");
		
		// Need leading space in front of class name b/c
		// there might be other classes on the element
		this.className = classNameWithoutNewClass + ' ' + newClass;
	}
	
	/*---------------------------------
	 * removeClass 
	 *---------------*/
	
	/**
	 * Provide dynamic removal of a class for all
	 * elements.
	 * 
	 * :param oldClass: name of class to remove
	 * :type oldClass: string
	 */
	
	Element.prototype.removeClass = function(oldClass) {
		this.className = this.className.replace(oldClass, '');
	}
	
	/*---------------------------------
	 * remove - an element from the DOM 
	 *---------------*/
	
	Element.prototype.remove = function() {
		/**
		 * Remove a given element from the DOM by calling
		 * removeChild() on the parent. Use like:
		 *     myElement.remove()
		 */
		this.parentElement.removeChild(this);
	}

	/*---------------------------------
	 * remove - all elements from a collection or NodeList
	 *---------------*/
	
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
	
	
	/*---------------------------------
	 * makeLegend
	 *---------------*/
	
	my.makeLegend = function() {
		var colors = colorbrewer.Reds[3];
		var achievementScale = d3.scale.ordinal()
		    					.range(colors)
		    					.domain(['firstTry', 'eventually', 'perGlobal']);
	}
	
//  -------------------------- Class-Level Initialization ----------------------------------

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
	function(errMsg) {
		alert(errMsg);
	}
	);
	
	// Make the object we would actually return
	// if this wasn't a singleton:
	that = {}
	
	/* PUBLIC METHODS */
	// Add a reference to the public ones of the above methods:
	
	that.getInstance    = my.getInstance;
	that.getErrCallback = my.getErrCallback;
	that.setErrCallback = my.setErrCallback; 
	
	my.instance = that;
	return that;

} // end GradeVizUiController

GradeVizUiController();

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


