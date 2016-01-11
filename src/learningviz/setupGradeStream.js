// TODO:
//   o If num_attempts missing, assume 1.


var vizzer = gradeCharter.getInstance();

var gradeReceiver = function(gradeData) {
	//console.log(gradeData);
	
	// Sanity check: are we handed an array?
	if (Object.prototype.toString.call( gradeData ) !== '[object Array]') {
		gradeData = [gradeData]
	}
	
	// Sanity check: does the array contain either 
	// legal JSON strings, or JS objects? Turn all
	// JSON strings into objects. Along the way,
	// build a new array of just the content objects:

	var cleanGradeDataArr = [];
	for (var i=0; i<gradeData.length; i++) {
		var gradeInfoObj = gradeData[i];
		if (typeof gradeInfoObj !== "object") {
			console.log(`Error: viz data must be an array of grade objects, not: ${gradeInfoObj}.`);
			return;
		}
		// Got a proper object, get its 'content' field:
		var gradeInfoStr = gradeInfoObj['content'];
		if (typeof gradeInfoStr !== 'string') {
			console.log(`Error: viz data content field must be parseable JSON string not: ${gradeInfoStr}.`);
			return;
		}
		// Must be a *proper* JSON:
		try{
			cleanGradeDataArr.push(JSON.parse(gradeInfoStr));
			continue;
		} catch(err) {
			console.log(`Error: bad JSON in grade object content field: '${gradeInfoStr}'.`);
			return;
		}
	} // end for
	
	vizzer.updateViz(cleanGradeDataArr);
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
									  


var testData = 
			nextData = [
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


